#!/bin/bash
# pre-push helper: run `claude plugin eval` for every plugin whose suite
# (evals/claude/<plugin>/) or plugin tree (plugins/<plugin>/) changed in the
# commits being pushed, using the local `claude` CLI and its login. Local-only;
# there is no CI twin, because a run costs money and its scores vary.
#
# OPT-IN: does nothing unless CLAUDE_EVAL_ENABLE=1, so installing the hooks never
# starts paid model calls by itself. When enabled it is informational: results are
# printed but never block the push unless CLAUDE_EVAL_STRICT=1. Note the job runs
# in parallel with the hard pre-push gates, so a push they reject still spends.
#
# Both change detection and staging use the pushed commit (from git's pre-push
# stdin, else HEAD), never the working tree, so uncommitted edits cannot change
# the score. Override the eval flags with CLAUDE_EVAL_ARGS and the per-plugin
# spend cap with EVAL_MAX_COST_USD.

set -uo pipefail

REPO_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
EVAL_ARGS="${CLAUDE_EVAL_ARGS:---model claude-sonnet-5 --judge-model claude-haiku-4-5 --threshold 0.8}"
ZERO_SHA="0000000000000000000000000000000000000000"

skip() {
  echo "claude-plugin-eval: $1; skipping."
  exit 0
}

[ "${CLAUDE_EVAL_ENABLE:-0}" = "1" ] ||
  skip "opt-in job (paid model calls); set CLAUDE_EVAL_ENABLE=1 to run it"

# git feeds pre-push "<local ref> <local sha> <remote ref> <remote sha>" lines.
revs=()
remote_revs=()
saw_ref=0
if [ ! -t 0 ]; then
  while read -r _ local_sha _ remote_sha; do
    saw_ref=1
    if [ -n "${local_sha:-}" ] && [ "$local_sha" != "$ZERO_SHA" ]; then
      revs+=("$local_sha")
      remote_revs+=("${remote_sha:-$ZERO_SHA}")
    fi
  done
fi
if [ "${#revs[@]}" -eq 0 ]; then
  [ "$saw_ref" -eq 0 ] || skip "push contains only ref deletions"
  head_sha="$(git -C "$REPO_ROOT" rev-parse --verify HEAD 2>/dev/null)" || skip "no HEAD commit"
  revs=("$head_sha")
  remote_revs=("$ZERO_SHA")
fi

command -v "${CLAUDE_BIN:-claude}" >/dev/null 2>&1 || skip "claude CLI not found"

failed=()
ran=0
seen_evals=" "
for index in "${!revs[@]}"; do
  rev="${revs[$index]}"
  # Peel annotated tags too: each commit should incur at most one eval per plugin.
  rev="$(git -C "$REPO_ROOT" rev-parse --verify "$rev^{commit}")" || {
    failed+=("invalid revision")
    continue
  }
  remote_sha="${remote_revs[$index]}"
  if [ "$remote_sha" = "$ZERO_SHA" ]; then
    base="$(git -C "$REPO_ROOT" merge-base "$rev" origin/main 2>/dev/null)"
  else
    base="$(git -C "$REPO_ROOT" rev-parse --verify "$remote_sha^{commit}" 2>/dev/null)"
  fi
  if [ -z "$base" ]; then
    echo "claude-plugin-eval: cannot resolve comparison base for $rev; skipping it."
    failed+=("missing comparison base")
    continue
  fi
  if ! changed="$(git -C "$REPO_ROOT" diff --name-only "$base" "$rev")"; then
    failed+=("failed change detection")
    continue
  fi
  # Suites come from the pushed revision too, not from the working tree.
  suites="$(git -C "$REPO_ROOT" ls-tree -d --name-only "$rev" evals/claude/ 2>/dev/null)"
  for suite in $suites; do
    plugin="$(basename "$suite")"
    grep -qE "^(evals/claude|plugins)/$plugin/" <<<"$changed" || continue
    # Different remote bases can select different plugins at the same tip.
    # Deduplicate only after selection, preserving the union of those updates.
    case "$seen_evals" in *" $rev/$plugin "*) continue ;; esac
    seen_evals="$seen_evals$rev/$plugin "
    ran=$((ran + 1))
    echo "claude-plugin-eval: evaluating $plugin (cap \$${EVAL_MAX_COST_USD:-5}, may overshoot by in-flight runs)"
    output_dir="${EVAL_OUTPUT_DIR:-$REPO_ROOT/.eval-results/$plugin}/$rev"
    # The runner must match the revision whose plugin and suite it stages.
    # Reject mismatches rather than execute different flags or staging logic.
    if git -C "$REPO_ROOT" diff --quiet "$rev" -- scripts/eval-claude-plugin.sh; then
      # shellcheck disable=SC2086
      EVAL_OUTPUT_DIR="$output_dir" EVAL_REV="$rev" "$REPO_ROOT/scripts/eval-claude-plugin.sh" "$plugin" $EVAL_ARGS </dev/null
      rc=$?
    else
      echo "claude-plugin-eval: runner differs from $rev; evaluation skipped (use a matching checkout)."
      rc=2
    fi
    echo "claude-plugin-eval: $plugin exit=$rc, report: $output_dir/report.html"
    [ "$rc" -eq 0 ] || failed+=("$plugin(exit $rc)")
  done
done

[ "$ran" -gt 0 ] || [ "${#failed[@]}" -gt 0 ] || skip "no plugin with a suite changed in the pushed commits"

if [ "${#failed[@]}" -gt 0 ]; then
  echo "claude-plugin-eval: below threshold or incomplete: ${failed[*]}"
  [ "${CLAUDE_EVAL_STRICT:-0}" = "1" ] && exit 1
fi
exit 0
