#!/usr/bin/env bash
# pi-review.sh - read-only code review of local git changes through pi, using
# the OpenAI Codex native review rubric (assets/review-rubric.md). Bash 3.2 + jq.
#
#   pi-review.sh run    [--base REF] [--scope auto|working-tree|branch] [--model M] [--json]
#   pi-review.sh prompt [--base REF] [--scope ...]   print the review request, no pi call
#   pi-review.sh render FILE TARGET MODEL            render a saved final message
#
# --wait/--background are accepted and ignored: the host decides how to run us.
# Any other argument (focus text) is rejected: this is a native review only.
# Model: --model, else "model" in the approved pi-dispatch config (/pi:setup).
# pi runs with --tools read,grep,find,ls, --no-session and --no-approve; the
# diff is embedded in the request because those tools cannot run git.
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

# collect writes the review request body to $1 and sets TARGET; returns 3 when
# there is nothing to review.
TARGET=""
collect() {
    local out=$1 diff mb f
    diff=$(mktemp)
    if [ "$SCOPE" = auto ]; then
        if [ -n "$BASE" ]; then
            SCOPE=branch
        elif [ -n "$(git status --porcelain --untracked-files=all)" ]; then
            SCOPE=working-tree
        else
            SCOPE=branch
        fi
    fi
    if [ "$SCOPE" = working-tree ]; then
        TARGET="working tree (staged, unstaged and untracked changes)"
        git diff --cached >"$diff"
        git diff >>"$diff"
        git ls-files --others --exclude-standard | while IFS= read -r f; do
            git diff --no-index -- /dev/null "$f" || true
        done >>"$diff"
        if [ ! -s "$diff" ]; then rm -f "$diff"; return 3; fi
        {
            printf 'Status:\n'
            git status --short --untracked-files=all
        } >"$out"
    else
        [ -n "$BASE" ] || BASE=$(default_base)
        git rev-parse -q --verify "$BASE^{commit}" >/dev/null || die "unknown base ref: $BASE"
        mb=$(git merge-base "$BASE" HEAD) || die "no merge base between $BASE and HEAD"
        TARGET="branch diff against $BASE"
        git diff "$mb" HEAD >"$diff"
        if [ ! -s "$diff" ]; then rm -f "$diff"; return 3; fi
        {
            printf 'Merge base: %s\n\nCommits:\n' "$mb"
            git log --oneline "$mb..HEAD"
            printf '\nFiles:\n'
            git diff --stat "$mb" HEAD
        } >"$out"
    fi
    {
        printf '\n<diff>\n'
        if [ "$(wc -c <"$diff")" -gt "$MAX_DIFF_BYTES" ]; then
            head -c "$MAX_DIFF_BYTES" "$diff"
            printf '\n[diff truncated after %s bytes; read the remaining changed files with the read tool]\n' "$MAX_DIFF_BYTES"
        else
            cat "$diff"
        fi
        printf '</diff>\n'
    } >>"$out"
    rm -f "$diff"
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
render() {
    local file=$1 target=$2 model=$3 json
    json=$(mktemp)
    # Accept bare JSON, or JSON wrapped in a fence or short prose.
    if ! jq -e . "$file" >"$json" 2>/dev/null; then
        sed -n '/^[[:space:]]*{/,$p' "$file" | sed '/^[[:space:]]*```[[:space:]]*$/,$d' >"$json"
    fi
    # Slurp so empty input (no JSON found) fails instead of passing vacuously.
    if ! jq -s -e 'length == 1 and (.[0].findings | type) == "array"
            and (.[0].overall_correctness | type) == "string"' "$json" >/dev/null 2>&1; then
        printf '# Pi Review\n\nTarget: %s\nModel: %s\n\npi returned output that is not the expected review JSON.\n\nRaw final message:\n\n```text\n' "$target" "$model"
        cat "$file"
        printf '\n```\n'
        rm -f "$json"
        return 1
    fi
    jq -r --arg target "$target" --arg model "$model" '
        def pri: if (.priority | type) == "number" then .priority else 9 end;
        def title: (.title // "untitled") as $t
                   | if ($t | test("^\\[P[0-3]\\]")) or ((.priority | type) != "number")
                     then $t else "[P\(.priority)] \($t)" end;
        def where: (.code_location.absolute_file_path // "?")
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
        (.overall_explanation // empty), "",
        if (.findings | length) == 0 then "No findings."
        else "Full review comments:", "",
             (.findings | sort_by(pri)[]
              | "- \(title) — \(where)",
                (.body // "" | split("\n") | map("  " + .) | join("\n")),
                "")
        end' "$json"
    rm -f "$json"
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
    rc=0
    collect "$tmp/body" || rc=$?
    if [ "$rc" -eq 3 ]; then
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
        >"$tmp/final.txt" || rc=$?
    if [ "$rc" -ne 0 ]; then
        printf '# Pi Review\n\nTarget: %s\nModel: %s\n\npi exited with status %s.\n' "$TARGET" "$MODEL" "$rc"
        [ -s "$tmp/final.txt" ] && { printf '\nOutput:\n\n```text\n'; cat "$tmp/final.txt"; printf '\n```\n'; }
        exit 1
    fi
    if [ "$RAW_JSON" -eq 1 ]; then cat "$tmp/final.txt"; exit 0; fi
    render "$tmp/final.txt" "$TARGET" "$MODEL" || exit 1
    ;;
*)
    die "usage: pi-review.sh run|prompt [--base REF] [--scope auto|working-tree|branch] [--model M] [--json] | render FILE TARGET MODEL"
    ;;
esac
