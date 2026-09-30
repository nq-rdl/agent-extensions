#!/usr/bin/env bash
# Small JSON/file plumbing, sourced by sqlreview.sh (Bash 3.2 + jq).
# Published scope/review bytes are never changed by these commands.
_q_context() { # slug: load validated store or a read-only legacy projection into Q_DOC
  local slug="$1" d="$SR_REVIEWS/$1" f scope=/dev/null review=/dev/null path="" declared=false
  sr_safe_slug "$slug"
  sr_no_symlinks "$d/questions.json" || exit 2
  for f in scope review; do
    sr_no_symlinks "$d/$f.json" || exit 2
    [ ! -e "$d/$f.json" ] || [ -f "$d/$f.json" ] || sr_die 2 "question source is not a regular file"
    [ -f "$d/$f.json" ] || continue
    cmd_check "$d/$f.json" >/dev/null || sr_die 4 "invalid question source: $f.json"
    local bound
    bound="$(jq -r .sql_path "$d/$f.json")"
    [ -z "$path" ] || [ "$path" = "$bound" ] || sr_die 4 "question sources have conflicting sql_path"
    path="$bound"
    [ "$(jq -r .slug "$d/$f.json")" = "$slug" ] || sr_die 4 "question source slug mismatch"
    jq -e 'has("question_store")' "$d/$f.json" >/dev/null && declared=true
    if [ "$f" = scope ]; then scope="$d/$f.json"; else review="$d/$f.json"; fi
  done
  [ -n "$path" ] || sr_die 4 "questions require an existing scope or review"
  sr_safe_sql "$path"
  if [ -e "$d/questions.json" ]; then
    [ -f "$d/questions.json" ] || sr_die 2 "question store is not a regular file"
    cmd_check "$d/questions.json" >/dev/null || sr_die 4 "invalid questions.json"
    jq -e --arg slug "$slug" --arg path "$path" '.slug == $slug and .sql_path == $path' "$d/questions.json" >/dev/null || sr_die 4 "question store binding mismatch"
    # Old embedded arrays are historical. Refuse new untracked strings rather than hide them.
    if [ "${2:-}" != publish ]; then
      jq -e -L "$SR_SCRIPT_DIR" --slurpfile scope "$scope" --slurpfile review "$review" '
        include "sqlreview-questions"; legacy_covered($scope[0]; $review[0])' "$d/questions.json" >/dev/null || sr_die 4 "untracked legacy questions; reconcile in questions.json, not scope/review"
    fi
    Q_DOC="$(jq . "$d/questions.json")" || sr_die 4 "cannot read questions"
  else
    [ "$declared" = false ] || [ "${2:-}" = publish ] || sr_die 4 "declared questions.json is missing"
    Q_DOC="$(jq -n -L "$SR_SCRIPT_DIR" --slurpfile scope "$scope" --slurpfile review "$review" --arg slug "$slug" --arg path "$path" '
      include "sqlreview-questions"; legacy_questions($scope[0]; $review[0]; $slug; $path)')" || sr_die 4 "cannot project legacy questions"
  fi
  Q_SCOPE="$scope" Q_REVIEW="$review"
}

cmd_questions() (
  [ $# -ge 1 ] && [ $# -le 2 ] || usage
  sr_need_jq; sr_require_root
  local kind="${2:-review}" Q_DOC
  case "$kind" in scope|review) ;; *) usage ;; esac
  _q_context "$1"
  printf '%s\n' "$Q_DOC" | jq -L "$SR_SCRIPT_DIR" --arg kind "$kind" 'include "sqlreview-questions"; visible_questions($kind)'
)

# Serialize both writers before reading history. mkdir is portable to macOS Bash 3.2;
# fail busy rather than steal a lock or guess whether another publisher is still alive.
_q_lock() { # slug; caller owns local Q_LOCK and tmp, and runs in a subshell
  sr_safe_slug "$1"
  local lock="$SR_REVIEWS/$1/.questions.lock"
  sr_no_symlinks "$lock" || exit 2
  mkdir "$lock" 2>/dev/null || sr_die 2 "question store busy or lock unavailable; retry after reloading questions"
  Q_LOCK="$lock"
  trap 'rm -f "$tmp"; rmdir "$Q_LOCK"' EXIT
  trap 'exit 2' HUP INT TERM
}

cmd_migrate_questions() (
  [ $# -eq 1 ] || usage
  sr_need_jq; sr_require_root
  local Q_DOC Q_LOCK="" tmp="" dest="$SR_REVIEWS/$1/questions.json"
  _q_lock "$1"
  _q_context "$1"
  [ ! -f "$dest" ] || { printf 'already migrated\t%s\n' "$1"; exit 0; }
  tmp="$(mktemp "$SR_REVIEWS/$1/.questions.XXXXXX")" || sr_die 2 "mktemp failed"
  printf '%s\n' "$Q_DOC" > "$tmp" || sr_die 2 "cannot stage questions"
  cmd_check "$tmp" >/dev/null || sr_die 4 "invalid migration"
  # Never overwrite a store that appeared during migration.
  ln "$tmp" "$dest" || sr_die 2 "cannot install question store (retry after checking existing store)"
  printf 'migrated questions\t%s\n' "$1"
)

cmd_publish_questions() (
  [ $# -eq 2 ] || usage
  sr_need_jq; sr_require_root
  local slug="$1" draft="$2" Q_DOC Q_LOCK="" tmp="" dest="$SR_REVIEWS/$1/questions.json"
  _q_lock "$slug"
  _q_context "$slug" publish
  # Keep original components: normalizing link/../ first hides the symlink.
  case "$draft" in /*) ;; *) draft="$(pwd -P)/$draft" ;; esac
  sr_no_symlinks "$draft" || exit 2
  [ -f "$draft" ] || sr_die 2 "no such question draft"
  tmp="$(mktemp "$SR_REVIEWS/$slug/.questions.XXXXXX")" || sr_die 2 "mktemp failed"
  cp "$draft" "$tmp" || sr_die 2 "cannot stage question draft"
  cmd_check "$tmp" || exit 4
  jq -e -L "$SR_SCRIPT_DIR" --slurpfile scope "$Q_SCOPE" --slurpfile review "$Q_REVIEW" '
    include "sqlreview-questions"; legacy_covered($scope[0]; $review[0])' "$tmp" >/dev/null || sr_die 4 "question draft omits untracked legacy questions"
  jq -e --argjson old "$Q_DOC" '
    . as $new | .slug == $old.slug and .sql_path == $old.sql_path
    and all($old.questions[]; . as $prior | [$new.questions[] | select(.id == $prior.id)] as $matches |
      ($matches | length) == 1 and ($matches[0] | . as $q |
        .text == $prior.text and .applies == $prior.applies
        and (if $prior.status == "closed" then . == $prior else true end)))
    and all(.questions[]; . as $q | if any($old.questions[]; .id == $q.id) then true else .status == "open" end)
  ' "$tmp" >/dev/null || sr_die 4 "question identity/history changed, removed, or new question already closed"
  if [ -f "$dest" ] && jq -e --slurpfile old "$dest" '. == $old[0]' "$tmp" >/dev/null; then
    printf 'already published questions\t%s\n' "$slug"; exit 0
  fi
  mv "$tmp" "$dest" || sr_die 2 "cannot publish questions"
  printf 'published questions\t%s\n' "$slug"
)
