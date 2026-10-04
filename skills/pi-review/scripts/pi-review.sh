#!/usr/bin/env bash
# pi-review.sh - read-only code review of local git changes through pi, using
# the OpenAI Codex native review rubric (assets/review-rubric.md). Bash 3.2 + jq.
#
#   pi-review.sh run    [--base REF] [--scope auto|working-tree|branch] [--model M] [--json]
#   pi-review.sh prompt [--base REF] [--scope ...]   print the review request (never
#                                                     truncated), no pi call
#   pi-review.sh render FILE TARGET MODEL            render a saved final message
#
# --wait/--background are accepted and ignored: the host decides how to run us.
# Any other argument (focus text) is rejected: this is a native review only.
# Model: --model, else "model" in the approved pi-dispatch config (/pi:setup).
# pi runs with --tools read,grep,find,ls, --no-session and --no-approve; the
# diff is embedded in the request because those tools cannot run git. stdin is
# /dev/null: pi -p reads a non-TTY stdin to EOF, so an open pipe would hang it.
#
# Exit codes: 0 review rendered (or nothing to review), 1 pi failed or returned
# an unexpected shape, 2 usage, configuration or repository error.
set -euo pipefail

SELF_DIR=$(cd "$(dirname "$0")" && pwd)
RUBRIC="$SELF_DIR/../assets/review-rubric.md"
CONFIG="${XDG_CONFIG_HOME:-$HOME/.config}/pi-dispatch/config.json"
MAX_DIFF_BYTES="${PI_REVIEW_MAX_DIFF_BYTES:-150000}"
READ_ONLY_TOOLS="read,grep,find,ls"

die() { printf 'pi-review: %s\n' "$1" >&2; exit "${2:-2}"; }

BASE="" SCOPE=auto MODEL="" RAW_JSON=0
parse_opts() {
    while [ "$#" -gt 0 ]; do
        case "$1" in
        --base) [ "$#" -ge 2 ] || die "--base needs a ref"; BASE=$2; shift 2 ;;
        --base=*) BASE=${1#--base=}; shift ;;
        --scope) [ "$#" -ge 2 ] || die "--scope needs a value"; SCOPE=$2; shift 2 ;;
        --scope=*) SCOPE=${1#--scope=}; shift ;;
        --model|-m) [ "$#" -ge 2 ] || die "--model needs a value"; MODEL=$2; shift 2 ;;
        --model=*) MODEL=${1#--model=}; shift ;;
        --json) RAW_JSON=1; shift ;;
        --wait|--background) shift ;;
        *) die "pi:review is a native review and takes no focus text (got: $1)" ;;
        esac
    done
    case "$SCOPE" in auto|working-tree|branch) ;; *) die "--scope must be auto, working-tree or branch" ;; esac
}

resolve_model() {
    if [ -z "$MODEL" ] && [ -f "$CONFIG" ]; then
        MODEL=$(jq -r '.model // empty' "$CONFIG" 2>/dev/null || true)
    fi
    [ -n "$MODEL" ] || die "no model: pass --model provider/id[:thinking] or approve a default with /pi:setup"
}

default_base() {
    local ref
    ref=$(git symbolic-ref -q --short refs/remotes/origin/HEAD 2>/dev/null || true)
    if [ -n "$ref" ]; then printf '%s\n' "$ref"; return; fi
    for ref in origin/main origin/master main master; do
        if git rev-parse -q --verify "$ref^{commit}" >/dev/null 2>&1; then
            printf '%s\n' "$ref"; return
        fi
    done
    die "cannot find a base branch; pass --base REF"
}

# collect OUT DIFF: write the review request body to OUT and the complete diff
# to DIFF (kept for the pi run, so a truncated request can point at it). Sets
# TARGET, and EMPTY=1 when there is nothing to review. Call it plainly, never
# in an if/||/&& context: that would disable set -e for every git call here.
TARGET="" EMPTY=0
collect() {
    local out=$1 diff=$2 mb f size status
    if [ "$SCOPE" = auto ]; then
        status=$(git status --porcelain --untracked-files=all) || die "git status failed"
        if [ -n "$BASE" ]; then
            SCOPE=branch
        elif [ -n "$status" ]; then
            SCOPE=working-tree
        else
            SCOPE=branch
        fi
    fi
    if [ "$SCOPE" = working-tree ]; then
        TARGET="working tree (staged, unstaged and untracked changes)"
        git diff --cached >"$diff" || die "git diff --cached failed"
        git diff >>"$diff" || die "git diff failed"
        # NUL-delimited: default output quotes unusual names, which git diff
        # would then fail to open. --no-index exits 1 for "differences".
        git ls-files -z --others --exclude-standard | while IFS= read -r -d '' f; do
            rc=0
            git diff --no-index -- /dev/null "$f" || rc=$?
            [ "$rc" -le 1 ] || exit "$rc"
        done >>"$diff" || die "git diff of untracked files failed"
        if [ ! -s "$diff" ]; then EMPTY=1; return 0; fi
        {
            printf 'Status:\n'
            git status --short --untracked-files=all
        } >"$out" || die "git status failed"
    else
        [ -n "$BASE" ] || BASE=$(default_base)
        git rev-parse -q --verify "$BASE^{commit}" >/dev/null || die "unknown base ref: $BASE"
        mb=$(git merge-base "$BASE" HEAD) || die "no merge base between $BASE and HEAD"
        TARGET="branch diff against $BASE"
        git diff "$mb" HEAD >"$diff" || die "git diff $mb HEAD failed"
        if [ ! -s "$diff" ]; then EMPTY=1; return 0; fi
        {
            printf 'Merge base: %s\n\nCommits:\n' "$mb"
            git log --oneline "$mb..HEAD"
            printf '\nFiles:\n'
            git diff --stat "$mb" HEAD
        } >"$out" || die "git log/diff --stat failed"
    fi
    size=$(wc -c <"$diff" | tr -d ' ')
    {
        printf '\n<diff>\n'
        # prompt mode prints the whole diff: its temporary files vanish on exit.
        if [ "$cmd" != prompt ] && [ "$size" -gt "$MAX_DIFF_BYTES" ]; then
            head -c "$MAX_DIFF_BYTES" "$diff"
            printf '\n[diff truncated after %s of %s bytes. The complete diff is %s:\n' "$MAX_DIFF_BYTES" "$size" "$diff"
            printf 'read the rest of it with the read tool (offset/limit) before concluding.]\n'
        else
            cat "$diff"
        fi
        printf '</diff>\n'
    } >>"$out"
}

# request writes the full user request to $1 (TARGET must already be set).
request() {
    local body=$1 out=$2
    {
        printf 'Review the code changes below and report prioritized findings following the review guidelines.\n\n'
        printf 'Target: %s\nRepository root: %s\n\n' "$TARGET" "$(pwd -P)"
        printf 'This review runs with read-only tools (%s) and cannot run git, so the diff is included below. ' "$READ_ONLY_TOOLS"
        printf 'Read surrounding code with the tools when the diff is not enough. '
        printf 'Use absolute file paths under the repository root in code_location.\n\n'
        cat "$body"
    } >"$out"
}

# render FILE TARGET MODEL: print the final message as a Codex-style review.
# Every step checks its own status (callers use render in an || context, where
# set -e is off); on any failure print the raw message and return 1.
render() {
    local file=$1 target=$2 model=$3 json out
    json=$(mktemp)
    out=$(mktemp)
    # Accept bare JSON, or JSON wrapped in a fence or short prose.
    if ! jq -e . "$file" >"$json" 2>/dev/null; then
        sed -n '/^[[:space:]]*{/,$p' "$file" | sed '/^[[:space:]]*```[[:space:]]*$/,$d' >"$json"
    fi
    # Slurp so empty input (no JSON found) fails instead of passing vacuously.
    if jq -s -e 'length == 1 and (.[0].findings | type) == "array"
            and all(.[0].findings[]; type == "object")
            and (.[0].overall_correctness | type) == "string"' "$json" >/dev/null 2>&1 \
        && jq -r --arg target "$target" --arg model "$model" '
        def pri: if (.priority | type) == "number" then .priority else 9 end;
        def title: (.title // "untitled" | tostring) as $t
                   | if ($t | test("^\\[P[0-3]\\]")) or ((.priority | type) != "number")
                     then $t else "[P\(.priority)] \($t)" end;
        def where: (.code_location.absolute_file_path // "?" | tostring)
                   + (if .code_location.line_range.start then
                        ":\(.code_location.line_range.start)"
                        + (if (.code_location.line_range.end // .code_location.line_range.start)
                              != .code_location.line_range.start
                           then "-\(.code_location.line_range.end)" else "" end)
                      else "" end);
        "# Pi Review", "",
        "Target: \($target)",
        "Model: \($model)",
        "Verdict: \(.overall_correctness)"
          + (if .overall_confidence_score then " (confidence \(.overall_confidence_score))" else "" end),
        "",
        (.overall_explanation // empty | tostring), "",
        if (.findings | length) == 0 then "No findings."
        else "Full review comments:", "",
             (.findings | sort_by(pri)[]
              | "- \(title) — \(where)",
                (.body // "" | tostring | split("\n") | map("  " + .) | join("\n")),
                "")
        end' "$json" >"$out" 2>/dev/null; then
        cat "$out"
        rm -f "$json" "$out"
        return 0
    fi
    printf '# Pi Review\n\nTarget: %s\nModel: %s\n\npi returned output that is not the expected review JSON.\n\nRaw final message:\n\n```text\n' "$target" "$model"
    cat "$file"
    printf '\n```\n'
    rm -f "$json" "$out"
    return 1
}

cmd=${1:-}
[ "$#" -gt 0 ] && shift
case "$cmd" in
render)
    [ "$#" -eq 3 ] || die "usage: render FILE TARGET MODEL"
    render "$1" "$2" "$3"
    ;;
prompt|run)
    parse_opts "$@"
    command -v jq >/dev/null 2>&1 || die "jq is required"
    root=$(git rev-parse --show-toplevel 2>/dev/null) || die "not inside a git repository"
    cd "$root"
    tmp=$(mktemp -d)
    trap 'rm -rf "$tmp"' EXIT
    collect "$tmp/body" "$tmp/full.diff"
    if [ "$EMPTY" -eq 1 ]; then
        printf 'Nothing to review: no changes in the %s.\n' "$([ "$SCOPE" = branch ] && echo "branch diff" || echo "working tree")"
        exit 0
    fi
    request "$tmp/body" "$tmp/request.md"
    if [ "$cmd" = prompt ]; then cat "$tmp/request.md"; exit 0; fi
    resolve_model
    command -v pi >/dev/null 2>&1 || die "pi is not on PATH; run /pi:setup"
    # Drop the leading attribution comment; send the rubric text itself.
    awk 'NR == 1 && /^<!--/ { skip = 1 } skip { if (/^-->$/) skip = 0; next } { print }' \
        "$RUBRIC" >"$tmp/rubric.md"
    rc=0
    pi -p --mode text --no-session --no-approve --tools "$READ_ONLY_TOOLS" \
        --model "$MODEL" --append-system-prompt "$tmp/rubric.md" \
        @"$tmp/request.md" "Review the change described in the attached request." \
        </dev/null >"$tmp/final.txt" 2>"$tmp/stderr.txt" || rc=$?
    # Failure reports carry pi's stderr (invalid model, expired login, ...):
    # the skill returns this stdout verbatim, so the cause must be in it.
    stderr_block() {
        if [ -s "$tmp/stderr.txt" ]; then
            printf '\nstderr:\n\n```text\n'; cat "$tmp/stderr.txt"; printf '\n```\n'
        fi
    }
    if [ "$rc" -ne 0 ]; then
        printf '# Pi Review\n\nTarget: %s\nModel: %s\n\npi exited with status %s.\n' "$TARGET" "$MODEL" "$rc"
        if [ -s "$tmp/final.txt" ]; then
            printf '\nOutput:\n\n```text\n'; cat "$tmp/final.txt"; printf '\n```\n'
        fi
        stderr_block
        exit 1
    fi
    if [ "$RAW_JSON" -eq 1 ]; then cat "$tmp/final.txt"; cat "$tmp/stderr.txt" >&2; exit 0; fi
    if ! render "$tmp/final.txt" "$TARGET" "$MODEL"; then
        stderr_block
        exit 1
    fi
    cat "$tmp/stderr.txt" >&2
    ;;
*)
    die "usage: pi-review.sh run|prompt [--base REF] [--scope auto|working-tree|branch] [--model M] [--json] | render FILE TARGET MODEL"
    ;;
esac
