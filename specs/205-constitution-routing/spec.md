# Feature Specification: CLAUDE.md and constitution routing guidance

**Feature Branch**: `205-constitution-routing`
**Created**: 2026-07-02
**Status**: Templates delivered
**Input**: Epic #207 child #205 — the routing-guidance layer that makes #203/#204's tooling choices stick. Synthesizes #203, #204, #206.

## Problem

Dual-ownership drift: Superpowers' brainstorming/writing-plans skills auto-trigger on
"building something" cues and can produce parallel spec artifacts alongside SpecKit's
own `/speckit.specify → clarify → plan → tasks` sequence; and execution can silently
diverge from `constitution.md` because nothing enforces reading it. Every approach
surveyed (cc-spex, superpowers-bridge, plain constitution clause) treats this the same:
SpecKit planning stays authoritative, and a single bridging principle routes the handoff
at the task-list boundary.

## What this issue delivers

Copy-paste **templates** a team drops into its own target speckit repo:
1. A **constitution clause** establishing SpecKit-planning-authoritative /
   Superpowers-execution-only ownership, handoff at the `/speckit.tasks` boundary.
2. A **CLAUDE.md routing block** encoding SpecKit vocabulary (what the constitution is,
   where specs live, what definition-of-done requires) so Claude reads the routing every
   session, including after `/clear`.
3. The two **anti-patterns**: running both `/speckit.implement` and the Superpowers
   workflow on the same task; skipping `/speckit.tasks`.

## Requirements

- FR-1: Constitution clause template (ownership, handoff boundary).
- FR-2: CLAUDE.md routing block template (vocabulary, definition-of-done).
- FR-3: Anti-patterns documented (dual-executor, skipping `/speckit.tasks`).
- FR-4: Wired into `speckit-lifecycle` guidance and/or a `docs/` playbook; referenced by #204.
- FR-5: changie fragment.

## Success Criteria

- SC-1: `docs/playbooks/speckit-constitution-routing.md` exists with both templates + anti-patterns, ready to copy into a target repo.
- SC-2: Consistent with the epic constitution (`da38e3d`) and #204's playbook.

## Non-goals

New tooling; enforcing the routing mechanically (that is #204's `superb` layer).
