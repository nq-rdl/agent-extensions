#!/usr/bin/env bash
# Offline pi-review / pi-rescue contracts. The test copies skills/pi-review and
# skills/pi-rescue next to this file as review/ and rescue/. No real pi calls.
set -euo pipefail
export FIXTURE=$PWD HOME="$PWD/home" XDG_CONFIG_HOME="$PWD/config" XDG_STATE_HOME="$PWD/state"
export PATH="$PWD/bin:$PATH"
unset PI_OUT PI_EXIT PI_REVIEW_MAX_DIFF_BYTES PI_RESCUE_STATE_DIR
mkdir -p "$HOME"
R="$PWD/review/scripts/pi-review.sh"
Q="$PWD/rescue/scripts/pi-rescue.sh"
MODEL=openai-codex/gpt-6.1-sol:high

fail() { echo "FAIL: $*" >&2; exit 1; }
config() { mkdir -p "$XDG_CONFIG_HOME/pi-dispatch"; jq -n --arg m "$MODEL" '{model:$m}' > "$XDG_CONFIG_HOME/pi-dispatch/config.json"; }
# expect CODE CMD...: run CMD, require exit CODE. stdout/stderr go to
# $FIXTURE/out and $FIXTURE/err, outside the repo so they never count as changes.
expect() {
    local want=$1 rc=0; shift
    "$@" >"$FIXTURE/out" 2>"$FIXTURE/err" || rc=$?
    [ "$rc" -eq "$want" ] || fail "exit $rc, want $want: $* :: $(cat "$FIXTURE/out" "$FIXTURE/err")"
}
# File arguments below are names inside $FIXTURE (default: out).
has() { grep -qF -- "$1" "$FIXTURE/${2:-out}" || fail "missing [$1] in ${2:-out}: $(cat "$FIXTURE/${2:-out}")"; }
lacks() { if grep -qF -- "$1" "$FIXTURE/${2:-out}"; then fail "unexpected [$1] in ${2:-out}"; fi; }
OUT() { jq -e "$@" "$FIXTURE/out" >/dev/null; }
arg() { jq -e --arg a "$1" 'index($a) != null' "$FIXTURE/pi.args" >/dev/null || fail "pi args lack $1: $(cat "$FIXTURE/pi.args")"; }
noarg() { if jq -e --arg a "$1" 'index($a) != null' "$FIXTURE/pi.args" >/dev/null; then fail "pi args include $1"; fi; }
after() { jq -e --arg f "$1" --arg v "$2" '(index($f)) as $i | $i != null and .[$i + 1] == $v' "$FIXTURE/pi.args" >/dev/null \
    || fail "pi args lack $1 $2: $(cat "$FIXTURE/pi.args")"; }

repo() {
    rm -rf repo; mkdir repo; cd repo
    git init -q -b main; git config user.name T; git config user.email t@example.com
    printf 'one\n' > a.txt; git add a.txt; git commit -qm base
    git branch -q base
    cd ..
}

case "$1" in
render)
    expect 0 bash "$R" render review.json "branch diff against main" "$MODEL"
    has "# Pi Review"; has "Target: branch diff against main"; has "Model: $MODEL"
    has "Verdict: patch is incorrect (confidence 0.8)"; has "Two defects."
    has "- [P1] Handle empty input — /repo/b.sh:3"; has "- [P2] Keep the guard — /repo/a.sh:5-7"
    has "  Second line."
    # P1 sorts before P2.
    [ "$(grep -n 'P1' "$FIXTURE/out" | cut -d: -f1)" -lt "$(grep -n 'P2' "$FIXTURE/out" | cut -d: -f1)" ] || fail "priority order"
    { printf 'Here is the review:\n```json\n'; cat review.json; printf '```\n'; } > fenced.txt
    expect 0 bash "$R" render fenced.txt t m; has "Full review comments:"
    jq '.findings = []' review.json > clean.json
    expect 0 bash "$R" render clean.json t m; has "No findings."
    printf 'not json\n' > bad.txt
    expect 1 bash "$R" render bad.txt t m; has "not the expected review JSON"; has "not json"
    : > empty.txt
    expect 1 bash "$R" render empty.txt t m; has "not the expected review JSON"
    ;;
review-args)
    repo; cd repo
    expect 2 bash "$R" run focus on errors; has "takes no focus text" err
    expect 2 bash "$R" run --scope staged; has "--scope must be" err
    printf 'two\n' > a.txt
    expect 2 bash "$R" run; has "no model" err
    [ ! -f "$FIXTURE/pi.args" ] || fail "pi ran without a model"
    ;;
review-branch)
    repo; config; cd repo
    git checkout -q -b feature; printf 'two\n' > a.txt; git commit -qam change
    PI_OUT=../review.json expect 0 bash "$R" run --wait --base base
    has "Target: branch diff against base"; has "- [P1] Handle empty input"
    cd ..
    arg -p; after --mode text; arg --no-session; arg --no-approve; after --tools read,grep,find,ls
    after --model "$MODEL"; noarg --session-id
    [ "$(cat "$FIXTURE/pi.cwd")" = "$(cd repo && pwd -P)" ] || fail "pi cwd"
    head -1 "$FIXTURE/pi.system" | grep -qx '# Review guidelines:' || fail "rubric comment not stripped"
    lacks "SPDX" pi.system; has '"overall_correctness"' pi.system
    has "Target: branch diff against base" pi.request; has "+two" pi.request; has "change" pi.request
    # Raw JSON passthrough and an explicit model override.
    cd repo; PI_OUT=../review.json expect 0 bash "$R" run --base base --json --model openai/gpt-x; cd ..
    OUT '.overall_correctness' || fail "--json output"; after --model openai/gpt-x
    # Default base resolves to main when origin is absent.
    cd repo; PI_OUT=../review.json expect 0 bash "$R" run; has "Target: branch diff against main"; cd ..
    ;;
review-worktree)
    repo; config; cd repo
    expect 0 bash "$R" run; has "Nothing to review"
    [ ! -f "$FIXTURE/pi.args" ] || fail "pi ran with nothing to review"
    printf 'two\n' > a.txt; printf 'new file\n' > untracked.txt
    PI_OUT=../review.json expect 0 bash "$R" run
    has "Target: working tree"; cd ..
    has "+two" pi.request; has "+new file" pi.request; has "?? untracked.txt" pi.request
    # Truncation keeps a bounded request and says so.
    cd repo; PI_REVIEW_MAX_DIFF_BYTES=10 PI_OUT=../review.json expect 0 bash "$R" run; cd ..
    has "diff truncated after 10 bytes" pi.request
    # pi failure and unexpected output both exit 1 and show the raw output.
    cd repo
    printf 'boom\n' > ../boom.txt
    PI_OUT=../boom.txt PI_EXIT=3 expect 1 bash "$R" run; has "pi exited with status 3"; has "boom"
    PI_OUT=../boom.txt expect 1 bash "$R" run; has "not the expected review JSON"
    ;;
rescue)
    # Runs under Bash 3.2 too: only rev-parse is needed, via a shim there.
    if ! command -v git >/dev/null 2>&1; then export PATH="$PWD/gitshim:$PATH"; mkdir -p repo; else repo; fi
    cd repo
    expect 0 bash "$Q" candidate; OUT '.available == false' || fail "candidate before any run"
    expect 2 bash "$Q" task investigate; has "no model" err
    config
    expect 2 bash "$Q" task; has "task text is required" err
    expect 2 bash "$Q" task --wait look; has "host routing flag" err
    expect 2 bash "$Q" task --thinking ultra look; has "--thinking must be" err
    expect 1 bash "$Q" task --resume-last look; has "No previous pi rescue session" err
    printf 'PILOT_OK\n' > ../ok.txt
    PI_OUT=../ok.txt expect 0 bash "$Q" task -- Reply exactly PILOT_OK.
    [ "$(cat "$FIXTURE/out")" = PILOT_OK ] || fail "stdout not verbatim"
    cd ..
    arg -p; after --mode text; arg --no-approve; after --tools read,grep,find,ls; after --model "$MODEL"
    jq -e '.[-2] == "--" and .[-1] == "Reply exactly PILOT_OK."' "$FIXTURE/pi.args" >/dev/null || fail "task text"
    first=$(jq -r '.[(index("--session-id")) + 1]' "$FIXTURE/pi.args")
    case "$first" in rescue-*) ;; *) fail "session id $first" ;; esac
    cd repo
    expect 0 bash "$Q" candidate; OUT --arg s "$first" '.available and .session == $s' || fail "candidate after run"
    # Resume reuses the session; --write drops the read-only tool list.
    PI_OUT=../ok.txt expect 0 bash "$Q" task --resume-last --write --thinking low -- apply the fix; cd ..
    after --session-id "$first"; noarg --tools; after --thinking low
    # A fresh run starts and records a new session.
    cd repo; sleep 1; PI_OUT=../ok.txt expect 0 bash "$Q" task again; cd ..
    second=$(jq -r '.[(index("--session-id")) + 1]' "$FIXTURE/pi.args")
    [ "$second" != "$first" ] || fail "fresh run reused the session"
    cd repo; expect 0 bash "$Q" candidate; OUT --arg s "$second" '.session == $s' || fail "last session"
    PI_EXIT=4 expect 4 bash "$Q" task fails
    ;;
*) fail "unknown case $1" ;;
esac
echo "ok $1"
