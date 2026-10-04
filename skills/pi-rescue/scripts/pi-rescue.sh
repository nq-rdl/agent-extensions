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
# becomes the last one. Model: --model, else "model" in the approved
# pi-dispatch config (/pi:setup). pi's final message is printed unchanged.
#
# Exit codes: pi's own status for a task run; 1 no session to resume;
# 2 usage, configuration or repository error.
set -euo pipefail

CONFIG="${XDG_CONFIG_HOME:-$HOME/.config}/pi-dispatch/config.json"
READ_ONLY_TOOLS="read,grep,find,ls"

die() { printf 'pi-rescue: %s\n' "$1" >&2; exit "${2:-2}"; }

# One state directory per checkout: pi stores sessions per working directory.
state_file() {
    local root key
    root=$(git rev-parse --show-toplevel 2>/dev/null) || die "not inside a git repository"
    key=$(printf '%s' "$root" | tr -c 'A-Za-z0-9._-' '-' | sed 's/^-*//')
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
        (umask 077; mkdir -p "$STATE_DIR")
        printf '%s\n' "$SESSION" >"$STATE.tmp"
        mv "$STATE.tmp" "$STATE"
    fi
    set -- -p --mode text --session-id "$SESSION" --model "$MODEL" --no-approve
    [ "$WRITE" -eq 1 ] || set -- "$@" --tools "$READ_ONLY_TOOLS"
    [ -z "$THINKING" ] || set -- "$@" --thinking "$THINKING"
    cd "$ROOT"
    exec pi "$@" -- "$TEXT"
    ;;
*)
    die "usage: pi-rescue.sh candidate | task [--write] [--resume-last] [--model M] [--thinking LEVEL] [--] TEXT"
    ;;
esac
