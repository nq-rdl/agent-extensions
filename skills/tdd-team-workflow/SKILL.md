---
name: tdd-team-workflow
license: CC-BY-4.0
description: >-
  TDD orchestration workflow — drives a red→green→refactor→review cycle by
  delegating each phase to a subagent or any installed dispatch backend. Use
  when implementing a feature with test-driven development and you want
  automated phase sequencing, test verification, cycle tracking, and
  multi-backend dispatch.
metadata:
  repo: https://github.com/nq-rdl/agent-skills
---

# TDD Team Workflow

## Quick Start

```
/tdd-team-workflow "Implement calculator with add, subtract, multiply, divide. Raise ValueError for division by zero." \
  --test tests/test_calculator.py --impl src/calculator.py --lang python --framework pytest
```

## You Are The Orchestrator

You NEVER write tests or implementation code directly. You delegate each phase to a subagent or dispatch backend. Your job:

1. Accept a feature description and resolve file paths to absolute (`$PWD`-relative)
2. Read `.tdd/config.yaml` for backend preferences (defaults if absent)
3. If state tracking enabled: `bash scripts/tdd-init.sh` then `bash scripts/tdd-new.sh <slug> ...`
4. Run the orchestration loop below — run tests between each phase
5. If the reviewer requests changes, start a new cycle (up to `max_cycles`)

**If you catch yourself writing test or implementation code — STOP. Delegate to a phase agent instead.**

---

## Dispatch

Each phase is delegated to a backend. The default is `claude:subagent` (Agent tool). Other backends are
dispatched via the `dispatch` skill — load it and follow its routing guidance to choose the right backend.

| Backend | Mechanism | Phases | Prerequisites |
|---------|-----------|--------|---------------|
| `claude:subagent` | Agent tool → phase agent | all | None |
| `claude:agent-team` | TeamCreate + SendMessage | all | `CLAUDE_CODE_EXPERIMENTAL_AGENT_TEAMS=1` |
| Any installed dispatch backend | Via the `dispatch` skill | all | Backend-specific |

**Phase agents**: `tdd-red-team`, `tdd-green-team`, `tdd-refactor`, `tdd-reviewer`.

Per-phase backends are configured in `.tdd/config.yaml`. Default: all phases use `claude:subagent`.

---

## Orchestration Loop

Follow this sequence exactly. Do NOT skip steps or combine phases.

```
cycle = 1
1. RED      → dispatch(red)      → run tests → expect FAIL
2. GREEN    → dispatch(green)    → run tests → expect PASS
3. REFACTOR → dispatch(refactor) → run tests → expect PASS
4. REVIEW   → dispatch(review)
   ├─ APPROVED|review             → Done
   └─ REQUEST_CHANGES|review|reason → cycle++, go to step 1 (carry feedback)
```

### Phase Input Format

All dispatch mechanisms accept the same 5-field input:

```
FEATURE: <feature description>
TEST FILE: <absolute path to test file>
IMPL FILE: <absolute path to implementation file>
LANGUAGE: <python|go|typescript|javascript|rust|java>
FRAMEWORK: <pytest|go-test|jest|vitest|cargo-test>
```

Optional context (append when available): `CYCLES: <N>/<max>`, `FEEDBACK: <reviewer feedback>`, `TEST RESULTS: <output>`, `PREVIOUS ATTEMPT: <error>`.

### Status Token Grammar

All backends emit exactly one token on their last output line:

| Token | Meaning |
|-------|---------|
| `DONE\|<phase>` | Phase completed |
| `APPROVED\|review` | Cycle approved |
| `REQUEST_CHANGES\|review\|<reason>` | New cycle needed |
| `ERROR\|<phase>\|<reason>` | Phase failed |

**Token extraction**: `claude:subagent` → last line of Agent response. `claude:agent-team` → last message from teammate. Other backends → last line of dispatch output.

### claude:agent-team Dispatch

To use agent-teams instead of subagents, set backend to `claude:agent-team` in `.tdd/config.yaml`. Requires `CLAUDE_CODE_EXPERIMENTAL_AGENT_TEAMS=1` in environment.

**Dispatch pattern**: `TeamCreate(name="tdd-<slug>")` once per feature cycle, then `SendMessage(to="tdd-<slug>-<phase>", message=<uniform input>)` to spawn a teammate per phase. Parse the status token from the teammate's response message.

**Naming**: Teammates use `tdd-<slug>-<phase>` format (e.g., `tdd-calculator-red`).

**When to use**: Parallel red phases for multiple features. Each teammate gets an independent context window, avoiding cross-contamination.

---

## Test Verification

After each code phase, run the test command (e.g., `pytest -x`, `go test ./...`):

- **After red**: tests MUST FAIL. If they pass → trivial tests (see below).
- **After green/refactor**: tests MUST PASS. If they fail → re-invoke the phase with failure output.

### Trivial-Test Detection

If tests PASS after red, re-invoke the red-team agent with:
```
PREVIOUS ATTEMPT: Tests passed when they should have failed. Write tests that assert real feature behaviour and fail against an empty/stub implementation.
```
Retry once. If tests still pass, pause and show the issue to the user.

### Cycle Cap

Default `max_cycles: 3` (from `.tdd/config.yaml`). At the cap without approval, pause and ask: "N cycles completed without approval. Continue, switch backend, or abort?" State is preserved.

---

## Error Handling

**Unrecognized token**: Log raw output, retry the phase once. If retry also fails, pause and show raw output to the user.

**Test runner error** (missing deps, import errors — not test failures): Show raw error, ask user to fix the environment. Do NOT retry automatically.

**Phase agent/script failure** (`ERROR|<phase>|<reason>`): Retry once. If retry fails, pause and suggest fallback to `claude:subagent`.

---

## State Tracking

Enabled by default. When disabled in `.tdd/config.yaml`, track progress in conversation only.

**Init**: `bash scripts/tdd-init.sh` — creates `.tdd/{active,archive,.gitignore}`
**New cycle**: `bash scripts/tdd-new.sh <slug> "<feature>" <test_file> <impl_file> <language> <framework>`
**Archive**: `bash scripts/tdd-archive.sh <slug>` (on APPROVED)

Between phases: update `.tdd/active/<slug>.yaml` — set `phase`, append to `phases[]`, update `test_summary` and `updated`. On REQUEST_CHANGES: increment `cycle`, set `phase: red`.

See `references/state-files.rst` for the full YAML schema.

**Session resume** — on activation, BEFORE `tdd-init.sh`: generate slug, check `.tdd/active/<slug>.yaml`. If exists: read `phase`, `cycle`, `phases[]`; determine next phase; prompt "Found cycle '<slug>' at '<phase>', cycle N/max. Resume from <next>? (y/n)". Yes → skip init/new, continue from next phase. No → `bash scripts/tdd-archive.sh <slug>`, start fresh.

---

## Parallel Cycles

Multiple TDD cycles can run concurrently using slug-based isolation. Each cycle gets its own `.tdd/active/<slug>.yaml` — no shared state.

**Starting concurrent cycles**: Run the skill once per feature with different slugs.

**Red-phase fan-out**: Use `claude:agent-team` for the red phase to dispatch multiple features simultaneously. Switch to `claude:subagent` for green/refactor/review.

**Orchestration**: Progress each cycle independently. Use `/tdd-team-workflow.list` to see all active cycles.

---

## Skill Commands

| Command | Script | Purpose |
|---------|--------|---------|
| `/tdd-team-workflow` | — (orchestration) | Start a TDD cycle |
| `/tdd-team-workflow.status` | `scripts/tdd-status.sh` | Show phase and progress |
| `/tdd-team-workflow.list` | `scripts/tdd-list.sh` | List all cycles |
| `/tdd-team-workflow.cancel` | `scripts/tdd-cancel.sh` | Cancel active cycle |
| `/tdd-team-workflow.config` | `scripts/tdd-config.sh` | Display config (read-only) |

When state tracking is disabled: status, list, cancel print "State tracking is disabled — enable it in `.tdd/config.yaml` to use this command" and exit. Config always works.

---

## PreToolUse Hook

A PreToolUse hook warns when the orchestrator uses Write/Edit on test/impl files — a reminder to delegate to phase agents. Available in `agent-extensions` as an opt-in hook.

## References

- `references/state-files.rst` — `.tdd/` YAML schema reference
- `references/orchestration-examples.rst` — worked examples (all using claude:subagent)
- `references/tdd-methodology.rst` — TDD theory and principles
