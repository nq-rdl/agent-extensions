#!/usr/bin/env bash
# Read-only prerequisite report. No credential printing, refresh, or config writes.
set -u
model=${1:-}
failed=0
check() {
    local tool=$1
    if command -v "$tool" >/dev/null 2>&1; then
        printf '%s: installed\n' "$tool"
    else
        printf '%s: MISSING\n' "$tool"; failed=1; return 1
    fi
}
if check pi; then pi --version || failed=1; fi
if check wt; then wt --version || failed=1; fi
printf 'wt shell integration: inspect `type wt` in your interactive shell (not detectable from this child shell)\n'
if check gh; then
    if gh auth status >/dev/null 2>&1; then printf 'gh auth: ready\n'
    else printf 'gh auth: NOT READY; run gh auth login yourself\n'; failed=1; fi
fi
check jq || true
if [ -n "$model" ] && command -v pi >/dev/null 2>&1; then
    printf 'chosen model/thinking: %s\n' "$model"
    # Catalog listing is not inference. The orchestrator must verify an exact row;
    # fuzzy matching and exit 0 alone do not prove the requested model exists.
    printf 'model catalog (verify exact provider/id and supported thinking):\n'
    pi --offline --list-models "${model%:*}" || failed=1
    if pi auth check --model "${model%:*}" --no-refresh >/dev/null 2>&1; then
        printf 'pi auth: ready (no refresh)\n'
    else printf 'pi auth: NOT READY; use /login in pi yourself, then recheck\n'; failed=1; fi
else
    printf 'model/provider: choose provider/id:thinking and rerun preflight\n'; failed=1
fi
repo=$(gh repo view --json nameWithOwner --jq .nameWithOwner 2>/dev/null) || repo='unknown-repo'
state=${PI_DISPATCH_STATE_DIR:-${XDG_STATE_HOME:-$HOME/.local/state}/pi-dispatch/${repo//\//--}}
printf 'state directory: %s (not created; approve before preparing)\n' "$state"
parent=$state
while [ ! -e "$parent" ] && [ "$parent" != / ] && [ "$parent" != . ]; do parent=$(dirname "$parent"); done
if [ -d "$parent" ] && [ -w "$parent" ]; then printf 'state parent: writable\n'
else printf 'state parent: NOT WRITABLE\n'; failed=1; fi
exit "$failed"
