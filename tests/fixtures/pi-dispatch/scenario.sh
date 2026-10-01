#!/usr/bin/env bash
set -euo pipefail
export FIXTURE=$PWD PATH="$PWD/bin:$PATH" HOME="$PWD/home" XDG_STATE_HOME="$PWD/state" PI_DISPATCH_CAP=2
mkdir -p "$HOME"
unset PI_DISPATCH_STATE_DIR
S="$PWD/dispatch/scripts/pi-dispatch.sh"
P="$PWD/setup/scripts/pi-preflight.sh"
run() { bash "$S" "$@"; }
unit() {
    jq -n --arg b "$1" --argjson n "$2" '{branch:$b,number:$n,brief:"Fix quotes \"x\" and backslash \\; $(touch BAD)\nnew line",classification:"dispatchable",paths:["shared/lib.sh"],wave:1}' > unit.json
}
prepare() {
    unit "$1" "$2"
    WT=$(run worktree "$1")
    run render unit.json "$WT" > prompt
}
wait_exit() {
    local i=0
    while [ ! -f "$1" ] && [ "$i" -lt 100 ]; do sleep 0.1; i=$((i+1)); done
    test -f "$1"
}
case "$1" in
parse)
    run resolve '476 477-480 476' | jq -e 'map(.number)==[476,477,478,479,480] and all(.[];.classification=="untriaged" and (.brief|contains("Comment scope")))'
    run resolve '>=477' | jq -e 'map(.number)==[477,480]'
    run resolve 'label:help wanted' | jq -e 'length==3'
    grep -F -- '--label help wanted' gh.calls
    run resolve 'Tighten lychee exclusions!' | jq -e 'length==1 and .[0].number==null and .[0].branch=="pi/tighten-lychee-exclusions"'
    run resolve --text '476 examples' | jq -e '.[0].branch=="pi/476-examples"'
    run resolve '9-2' > rejected 2>&1 && exit 1
    run resolve '0' > rejected 2>&1 && exit 1
    run resolve '1-1001' > rejected 2>&1 && exit 1
    FILTER_FULL=1 run resolve 'label:bug' > rejected 2>&1 && exit 1
    run resolve --text '!!!' > rejected 2>&1 && exit 1
    ;;
waves)
    printf '%s\n' '[{"branch":"a","classification":"dispatchable","paths":["shared"]},{"branch":"b","classification":"dispatchable","paths":["other"]},{"branch":"c","classification":"dispatchable","paths":["third"]},{"branch":"d","classification":"dispatchable","paths":["shared/lib.sh"]},{"branch":"e","classification":"human-only","paths":[]},{"branch":"f","classification":"umbrella","paths":[]},{"branch":"g","classification":"blocked","paths":[]},{"branch":"h","classification":"dispatchable","paths":[]}]' > plan.json
    run waves plan.json | jq -e 'map(.wave)==[1,1,2,2,null,null,null,3]'
    PI_DISPATCH_CAP=0 run waves plan.json > rejected 2>&1 && exit 1
    ;;
render)
    prepare issue-476 476
    jq -e '.==["switch","--create","issue-476","--base","origin/main","--no-cd","--no-hooks"]' wt.args
    grep -F "Work ONLY in $WT" prompt
    grep -F 'Include Closes #476' prompt
    grep -F 'Never merge' prompt
    grep -F '$(touch BAD)' prompt
    test ! -e BAD
    prepare pi/tighten-lychee null
    grep -F 'Free-text task: no Closes line' prompt
    ! grep -F 'Include Closes #' prompt
    jq '.classification="blocked"' unit.json > blocked.json
    run render blocked.json "$WT" > rejected 2>&1 && exit 1
    ;;
launch)
    prepare pi/tighten-lychee null
    run launch unit.json "$WT" prompt provider/model:high > rejected 2>&1 && exit 1
    meta=$(run launch unit.json "$WT" prompt provider/model:high --confirmed)
    wait_exit "${meta%.json}.exit"
    jq -e '.[0:9]==["-p","--mode","json","--session-id","pi-tighten-lychee","--model","provider/model:high","--no-approve","--"]' pi.args
    test "$(< pi.cwd)" = "$WT"
    test "$(< "${meta%.json}.exit")" = 0
    ! grep -F -- '--approve' pi.args
    # User/harness starts use the same metadata, and session resumes unchanged.
    run launch unit.json "$WT" prompt provider/model:high --confirmed > second
    wait_exit "${meta%.json}.exit"
    test -n "$(find "${meta%/*}" -name '*.jsonl.*' -print)"
    ;;
cap)
    export PI_DELAY=2 PI_DISPATCH_CAP=1
    prepare issue-476 476
    meta=$(run launch unit.json "$WT" prompt provider/model:high --confirmed)
    run status | jq -e '.workers[0].phase=="running" and .memory.pressure!=null'
    run launch unit.json "$WT" prompt provider/model:high --confirmed > rejected 2>&1 && exit 1
    grep -F 'Concurrency cap 1 reached' rejected
    # A different branch is also refused, not just the duplicate.
    prepare issue-477 477
    run launch unit.json "$WT" prompt provider/model:high --confirmed > rejected 2>&1 && exit 1
    wait_exit "${meta%.json}.exit"
    run launch unit.json "$WT" prompt provider/model:high --confirmed > second
    wait_exit "$(< second)" # metadata is created immediately
    wait_exit "${meta%/*}/issue-477.exit"
    # The default cap admits exactly two simultaneous workers, not three.
    export PI_DISPATCH_CAP=2
    prepare issue-478 478
    a=$(run launch unit.json "$WT" prompt provider/model:high --confirmed)
    prepare issue-479 479
    b=$(run launch unit.json "$WT" prompt provider/model:high --confirmed)
    prepare issue-480 480
    run launch unit.json "$WT" prompt provider/model:high --confirmed > rejected 2>&1 && exit 1
    grep -F 'Concurrency cap 2 reached' rejected
    wait_exit "${a%.json}.exit"; wait_exit "${b%.json}.exit"
    ;;
status)
    prepare issue-476 476
    export PI_EXIT=7
    meta=$(run launch unit.json "$WT" prompt provider/model:high --confirmed)
    wait_exit "${meta%.json}.exit"
    # Tolerate a partial final log line; model error is not a successful exit.
    printf '{"partial":' >> "${meta%.json}.jsonl"
    run status | jq -e '.workers[0] | .phase=="exited" and .exitCode==7 and .lastTools[0].toolName=="bash" and .pr.url=="https://github.com/owner/repo/pull/1" and .ci=="pending" and .errors[0].stopReason=="error"'
    CI_BUCKET=fail CHECK_EXIT=1 run status | jq -e '.workers[0].ci=="fail"'
    CI_BUCKET=pass CHECK_EXIT=0 run status | jq -e '.workers[0].ci=="pass"'
    GH_FAIL=1 run status | jq -e '.workers[0].ci=="unknown"'
    NO_PR=1 run status | jq -e '.workers[0].pr==null and .workers[0].ci=="unknown"'
    rm "${meta%.json}.exit"
    run status | jq -e '.workers[0].phase|contains("unknown")'
    run launch unit.json "$WT" prompt model --confirmed > rejected 2>&1 && exit 1
    grep -F 'Unresolved worker' rejected
    ;;
lock)
    prepare issue-476 476
    mkdir -p "$XDG_STATE_HOME/pi-dispatch/owner--repo/.launch-lock"
    run launch unit.json "$WT" prompt provider/model:high --confirmed > rejected 2>&1 && exit 1
    grep -F 'Launch lock held' rejected
    test ! -e pi.args
    # Bad branch cannot become a state path or execute shell text.
    jq '.branch="pi/../../bad"' unit.json > bad.json
    run worktree 'pi/../../bad' > rejected 2>&1 && exit 1
    run launch bad.json "$WT" prompt model --confirmed > rejected 2>&1 && exit 1
    # Refuse untriaged/blocked units and stale worktree branch bindings.
    jq '.classification="blocked"' unit.json > blocked.json
    run launch blocked.json "$WT" prompt model --confirmed > rejected 2>&1 && exit 1
    grep -F 'Need triaged' rejected
    printf 'wrong-branch\n' > branch
    run launch unit.json "$WT" prompt model --confirmed > rejected 2>&1 && exit 1
    grep -F 'Worktree branch mismatch' rejected
    ;;
setup)
    bash "$P" provider/model:high > report
    for phrase in 'pi: installed' 'wt: installed' 'jq: installed' 'gh auth: ready' 'pi auth: ready' 'chosen model/thinking: provider/model:high' 'state parent: writable' 'shell integration:'; do grep -F "$phrase" report; done
    test ! -d "$XDG_STATE_HOME"
    jq -e '.==["auth","check","--model","provider/model","--no-refresh"]' pi.args
    AUTH_FAIL=1 bash "$P" provider/model:high > report && exit 1
    grep -F 'NOT READY' report
    test ! -e "$HOME/.config"
    ;;
*) exit 99 ;;
esac
exit 0
