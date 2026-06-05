---
name: jules
license: CC-BY-4.0
description: >-
  Use when dispatching tasks to Jules, creating or monitoring Jules AI coding
  sessions. Also covers approving Jules plans, sending follow-up messages,
  listing activities, and enumerating connected GitHub sources.
compatibility: >-
  Requires Go 1.25+, gh CLI
metadata:
  repo: https://github.com/nq-rdl/agent-skills
---

# Jules — Async AI Coding Sessions

## Overview

Jules is Google's AI coding assistant. This skill wraps the Jules REST API in a
self-contained Go binary: **no Node.js, no Python runtime required at execution time**.

The design is **fire-and-forget**: dispatch a task by creating a session, Jules works
asynchronously, you check on it later. Never block waiting — poll with `session get`
or `activity list`.

```
jules session create --prompt "Fix the auth bug" --branch main
#   → {"id":"ses_abc","state":"QUEUED",...}

# Jules works autonomously: QUEUED → PLANNING → IN_PROGRESS → COMPLETED (+ PR created)

# Check on it later:
jules session get ses_abc
#   → {"id":"ses_abc","state":"COMPLETED", "outputs": [...]}
```

## Defaults — Read This First

- **Do not use `--require-plan-approval`** unless the user explicitly asks to review
  Jules's plan before execution. The default behavior (`AUTO_CREATE_PR`) is fully
  autonomous: Jules plans, implements, and opens a PR with zero human intervention.
  This is the intended fire-and-forget workflow.
- `--source` is auto-detected from `git remote` — rarely needs to be specified.
- `--branch` should match the PR's head branch when addressing PR comments,
  or the default branch for new work.

## Self-Contained Environment

This skill manages its **own pixi environment** with the Go 1.25 toolchain.

### First-time setup

```bash
cd ~/.claude/skills/jules && pixi install
pixi run build
```

This compiles `scripts/bin/jules`. The binary is self-contained — no runtime deps.

### Verify installation

```bash
scripts/bin/jules --help
scripts/bin/jules version
```

## Authentication

Set `JULES_API_KEY` in your environment, or pass `--api-key` to any command:

```bash
export JULES_API_KEY=your_key_here
jules session list

# Or per-command:
jules --api-key your_key session list
```

## Session Lifecycle

```
Default (AUTO_CREATE_PR, no plan approval):
QUEUED → PLANNING → IN_PROGRESS → COMPLETED (+ PR auto-created)
                                 └─► FAILED

With --require-plan-approval:
QUEUED → PLANNING → AWAITING_PLAN_APPROVAL → IN_PROGRESS → COMPLETED | FAILED

Additional states (may appear during execution):
  AWAITING_USER_FEEDBACK — Jules needs more input (send a message to resume)
  PAUSED                 — Session suspended temporarily

Terminal states: COMPLETED, FAILED (no further transitions possible)
```

## Quick Reference

| Task | Command |
|------|---------|
| Create session | `jules session create --prompt "..."` |
| List sessions | `jules session list` |
| Get session | `jules session get <id>` |
| Delete session | `jules session delete <id>` |
| Send message | `jules session message <id> "text"` |
| Approve plan | `jules session approve <id>` (requires `--require-plan-approval`) |
| Cleanup old sessions | `jules session cleanup --older-than 7d` |
| List activities | `jules activity list --session <id>` |
| Get activity | `jules activity get --session <sid> <aid>` |
| List sources | `jules source list` |
| Get source | `jules source get <id>` |

Add `--human` to any command for tabular output instead of JSON.

## Commands

### session create

```
jules session create [flags]

Flags:
  --prompt string                 Coding task description (required)
  --source string                 Jules source ID (auto-detected from git remote)
  --branch string                 Starting git branch
  --require-plan-approval         Pause for plan approval before executing.
                                  Omit this flag unless the user explicitly asks
                                  to review the plan. Default is fully autonomous.
  --automation-mode string        Automation mode (default: AUTO_CREATE_PR)
  --api-key string                Jules API key
  --human                         Human-readable output
```

When `--source` is omitted, the binary reads `git remote get-url origin` and finds
the matching Jules source automatically.

### session list

```
jules session list [--human] [--api-key ...]
```

### session get

```
jules session get <session-id> [--human] [--api-key ...]
```

### session delete

```
jules session delete <session-id> [--api-key ...]
```

### session message

Send a follow-up message to a running session:

```
jules session message <session-id> "Your message" [--api-key ...]
jules session message <session-id> --message "Your message" [--api-key ...]
```

### session approve

Approve Jules's plan (use when `requirePlanApproval=true` and state is
`AWAITING_PLAN_APPROVAL`):

```
jules session approve <session-id> [--api-key ...]
```

### session cleanup

Bulk-delete old terminal sessions, optionally archiving their metadata first:

```
jules session cleanup [flags]

Flags:
  --older-than string    Delete sessions older than this duration (default: 7d)
  --state string         Comma-separated states to target (default: COMPLETED,FAILED)
  --archive string       JSONL file to append session data to before deleting
  --dry-run              Preview what would be deleted without making changes
  --api-key string       Jules API key
  --human                Human-readable output
```

Examples:

```bash
# Preview what would be cleaned up (no changes made)
jules session cleanup --dry-run --human

# Delete completed/failed sessions older than 30 days
jules session cleanup --older-than 30d --human

# Archive to JSONL first, then delete
jules session cleanup --older-than 7d --archive ~/.jules/archive.jsonl

# Only clean up failed sessions
jules session cleanup --state FAILED --older-than 14d
```

The archive file uses JSONL format (one JSON object per line), suitable for
processing with `jq` or importing into other tools.

### activity list

```
jules activity list --session <session-id> [--human] [--api-key ...]
```

Activities are produced by Jules as it works: analysing the repo, writing a plan,
generating commits, etc.

### activity get

```
jules activity get --session <session-id> <activity-id> [--human] [--api-key ...]
```

### source list

List GitHub repositories connected to Jules:

```
jules source list [--human] [--api-key ...]
```

### source get

```
jules source get <source-id> [--human] [--api-key ...]
```

## Exit Codes

| Code | Meaning |
|------|---------|
| 0 | Success |
| 1 | Usage error (bad flags, missing args) |
| 2 | API error (non-2xx response) |
| 3 | Network / other error |

## Running Scripts

All commands use the compiled binary. From the skill directory:

```bash
cd ~/.claude/skills/jules

# Build first
pixi run build

# Then use the binary
scripts/bin/jules session create --prompt "Add unit tests for auth module"
scripts/bin/jules session list --human
scripts/bin/jules activity list --session ses_abc --human
```

Or add `scripts/bin` to your PATH.

## Typical Agent Workflow

```bash
# 1. Dispatch task by creating a session (fire and forget — no --require-plan-approval)
SESSION=$(jules session create --prompt "Refactor the config module" --branch main | jq -r .id)
echo "Created: $SESSION"

# 2. Session runs autonomously. Poll until COMPLETED or FAILED (no more than once per 30s):
until jules session get "$SESSION" | jq -e '.state | test("COMPLETED|FAILED")' > /dev/null; do sleep 30; done
jules session get "$SESSION" | jq .state   # → COMPLETED (PR auto-created)

# 3. When COMPLETED, check outputs
jules session get "$SESSION" | jq .outputs
jules activity list --session "$SESSION" | jq '.[] | select(.commitEvent != null)'
```

> **Plan approval flow** (rarely needed): If the user explicitly requests plan review,
> add `--require-plan-approval` to `session create`. When the session reaches
> `AWAITING_PLAN_APPROVAL`, review and approve with `jules session approve <id>`.

## Building from Source

```bash
cd ~/.claude/skills/jules
pixi install          # installs Go 1.25 toolchain
pixi run build        # compiles scripts/bin/jules
pixi run test         # runs all tests
pixi run lint         # runs go vet
```

For details on the API, see `references/api-reference.rst`.
