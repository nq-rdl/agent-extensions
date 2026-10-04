#!/usr/bin/env bash
# pi-rescue.sh - forward one investigation or fix request to pi in print mode,
# keeping one resumable rescue session per repository checkout. Bash 3.2 + jq.
#
#   pi-rescue.sh candidate
#       {"available":true,"session":ID} when this checkout has a rescue session
#   pi-rescue.sh task [--write] [--resume-last] [--model M] [--thinking LEVEL] [--] TEXT...
#
# Read-only by default (--tools read,grep,find,ls); --write enables pi's
# default tools (read, bash, edit, write). Neither is a sandbox. --resume-last
# reuses the checkout's last rescue session; otherwise a new session starts and
# becomes the last one only if pi exits 0, so a failed start keeps the previous
# pointer. Model: --model, else "model" in the approved pi-dispatch config
# (/pi:setup). pi's final message is printed unchanged.
#
# Exit codes: pi's own status for a task run; 1 no session to resume (none
# saved, or the saved one no longer exists); 2 usage, configuration or
# repository error. pi's stdout and stderr are relayed after it exits.
set -euo pipefail

CONFIG="${XDG_CONFIG_HOME:-$HOME/.config}/pi-dispatch/config.json"
READ_ONLY_TOOLS="read,grep,find,ls"

die() { printf 'pi-rescue: %s\n' "$1" >&2; exit "${2:-2}"; }

# digest TEXT: a hex digest of TEXT, using whichever SHA-256 tool exists.
digest() {
    if command -v sha256sum >/dev/null 2>&1; then printf '%s' "$1" | sha256sum | cut -c1-16
    elif command -v shasum >/dev/null 2>&1; then printf '%s' "$1" | shasum -a 256 | cut -c1-16
    else printf '%s' "$1" | cksum | tr ' ' '-'
    fi
}

# One state directory per checkout: pi stores sessions per working directory.
# The key is a readable, shortened path plus a digest of the full path, so
# paths such as /a/b and /a-b never share a pointer.
state_file() {
    local root key
    root=$(git rev-parse --show-toplevel 2>/dev/null) || die "not inside a git repository"
    key=$(printf '%s' "$root" | tr -c 'A-Za-z0-9._-' '-' | sed 's/^-*//' | cut -c1-80)
    key="$key-$(digest "$root")"
    STATE_DIR="${PI_RESCUE_STATE_DIR:-${XDG_STATE_HOME:-$HOME/.local/state}/pi-rescue/$key}"
    STATE="$STATE_DIR/last-session"
    ROOT=$root
}

cmd=${1:-}
[ "$#" -gt 0 ] && shift
case "$cmd" in
candidate)
    command -v jq >/dev/null 2>&1 || die "jq is required"
    state_file
    if [ -s "$STATE" ]; then
        jq -n --arg session "$(cat "$STATE")" '{available: true, session: $session}'
    else
        jq -n '{available: false}'
    fi
    ;;
task)
    WRITE=0 RESUME=0 MODEL="" THINKING=""
    while [ "$#" -gt 0 ]; do
        case "$1" in
        --write) WRITE=1; shift ;;
        --resume-last) RESUME=1; shift ;;
        --model|-m) [ "$#" -ge 2 ] || die "--model needs a value"; MODEL=$2; shift 2 ;;
        --model=*) MODEL=${1#--model=}; shift ;;
        --thinking) [ "$#" -ge 2 ] || die "--thinking needs a level"; THINKING=$2; shift 2 ;;
        --thinking=*) THINKING=${1#--thinking=}; shift ;;
        --wait|--background|--resume|--fresh)
            die "$1 is a host routing flag; strip it before calling task" ;;
        --) shift; break ;;
        *) break ;;
        esac
    done
    TEXT="$*"
    [ -n "$TEXT" ] || die "task text is required"
    case "$THINKING" in ""|off|minimal|low|medium|high|xhigh|max) ;;
        *) die "--thinking must be off, minimal, low, medium, high, xhigh or max" ;; esac
    if [ -z "$MODEL" ] && [ -f "$CONFIG" ]; then
        MODEL=$(jq -r '.model // empty' "$CONFIG" 2>/dev/null || true)
    fi
    [ -n "$MODEL" ] || die "no model: pass --model provider/id[:thinking] or approve a default with /pi:setup"
    command -v pi >/dev/null 2>&1 || die "pi is not on PATH; run /pi:setup"
    state_file
    if [ "$RESUME" -eq 1 ]; then
        [ -s "$STATE" ] || die "No previous pi rescue session was found for this repository." 1
        SESSION=$(cat "$STATE")
    else
        # pi session IDs must not contain "/".
        SESSION="rescue-$(date -u +%Y%m%dT%H%M%SZ)-$$"
    fi
    # Fresh runs create the session by exact ID. Resumes use --session, which
    # fails when the session no longer exists instead of silently starting an
    # empty one (as --session-id would).
    if [ "$RESUME" -eq 1 ]; then
        set -- -p --mode text --session "$SESSION"
    else
        set -- -p --mode text --session-id "$SESSION"
    fi
    set -- "$@" --model "$MODEL" --no-approve
    [ "$WRITE" -eq 1 ] || set -- "$@" --tools "$READ_ONLY_TOOLS"
    [ -z "$THINKING" ] || set -- "$@" --thinking "$THINKING"
    # pi treats any message starting with "@" as a file attachment, even after
    # "--"; a leading space keeps the request literal text.
    case "$TEXT" in @*) TEXT=" $TEXT" ;; esac
    cd "$ROOT"
    tmp=$(mktemp -d)
    trap 'rm -rf "$tmp"' EXIT
    rc=0
    # pi -p reads a non-TTY stdin to EOF; an open host pipe would hang it.
    pi "$@" -- "$TEXT" </dev/null >"$tmp/out" 2>"$tmp/err" || rc=$?
    if [ "$RESUME" -eq 1 ] && { grep -q "No session found matching" "$tmp/err" \
            || grep -q "Session found in different project" "$tmp/out"; }; then
        # The saved session is gone (or now belongs to another project, where
        # pi would only ask to fork it): drop the stale pointer and say so.
        rm -f "$STATE"
        die "the saved pi rescue session $SESSION no longer exists for this checkout; start a new session" 1
    fi
    cat "$tmp/out"
    cat "$tmp/err" >&2
    if [ "$RESUME" -eq 0 ]; then
        if [ "$rc" -eq 0 ]; then
            # A per-run temporary file keeps concurrent updates from colliding.
            (umask 077; mkdir -p "$STATE_DIR")
            printf '%s\n' "$SESSION" >"$STATE.$$.tmp"
            mv "$STATE.$$.tmp" "$STATE"
        else
            printf 'pi-rescue: pi exited %s; kept the previous resumable session (this run used %s)\n' \
                "$rc" "$SESSION" >&2
        fi
    fi
    exit "$rc"
    ;;
*)
    die "usage: pi-rescue.sh candidate | task [--write] [--resume-last] [--model M] [--thinking LEVEL] [--] TEXT"
    ;;
esac
