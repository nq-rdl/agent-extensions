# tdd-team-workflow subagent architecture review

A focused review of how `skills/tdd-team-workflow/` manages phase subagents, and whether the three awesome-copilot TDD agents (`tdd-red`, `tdd-green`, `tdd-refactor`) can be adopted as complementary phase-agent implementations.

- **Author**: review written 2026-04-21 as a companion to `docs/awesome-copilot-review.md`
- **Source files**: `skills/tdd-team-workflow/SKILL.md`, `skills/tdd-team-workflow/references/*.rst`, `skills/tdd-team-workflow/scripts/*.sh`
- **Upstream agents reviewed**: `github/awesome-copilot/agents/tdd-{red,green,refactor}.agent.md`

---

## 1. How tdd-team-workflow manages subagents

tdd-team-workflow is not a phase agent — it is a **strict orchestrator** that delegates every phase to a backend via the `dispatch` skill. The orchestrator never writes test or implementation code itself; line 33 of its SKILL.md is blunt: _"If you catch yourself writing test or implementation code — STOP. Delegate to a phase agent instead."_

### 1.1 Three-layer execution model

```
┌─────────────────────────────────────────────────────────────┐
│ Layer 1 — Orchestrator (tdd-team-workflow skill)            │
│ Loops RED → GREEN → REFACTOR → REVIEW with test gates       │
│ between phases. Owns state tracking (.tdd/active/*.yaml).   │
└───────────────────────────┬─────────────────────────────────┘
                            │ dispatch(phase, input)
                            ▼
┌─────────────────────────────────────────────────────────────┐
│ Layer 2 — Dispatch skill (skills/dispatch)                  │
│ Routes to a configured backend (default claude:subagent).   │
│ Known backends: claude:subagent, claude:agent-team,         │
│ plus any installed dispatch backend.                        │
└───────────────────────────┬─────────────────────────────────┘
                            │ backend.invoke(prompt)
                            ▼
┌─────────────────────────────────────────────────────────────┐
│ Layer 3 — Phase subagent                                    │
│ Executes one phase. Named tdd-<slug>-<phase> when spawned   │
│ via agent-team, or an inline general-purpose Agent prompt   │
│ when claude:subagent is used.                               │
└─────────────────────────────────────────────────────────────┘
```

The phase-agent names (`tdd-red-team`, `tdd-green-team`, `tdd-refactor`, `tdd-reviewer`) referenced at line 48 of the SKILL.md **do not currently exist as their own skills in the catalog.** They are protocol identifiers, not installable assets. When the default `claude:subagent` backend is used, the orchestrator spawns a fresh general-purpose subagent for each phase and supplies an inline prompt. The "phase agent" is therefore a prompt template injected at dispatch time, not a reusable SKILL.md.

### 1.2 The phase-agent contract (the "protocol")

Any implementation that wants to serve as a phase agent — whether inline prompt, SKILL.md, teammate, or external dispatch backend — must honour two wire formats.

**Input format (5 mandatory fields, plus optional context):**

```
FEATURE: <feature description>
TEST FILE: <absolute path to test file>
IMPL FILE: <absolute path to implementation file>
LANGUAGE: <python|go|typescript|javascript|rust|java>
FRAMEWORK: <pytest|go-test|jest|vitest|cargo-test>
```

Optional fields the orchestrator appends when carrying context across cycles:
`CYCLES: <N>/<max>`, `FEEDBACK: <reviewer feedback>`, `TEST RESULTS: <output>`, `PREVIOUS ATTEMPT: <error>`.

**Output format (exactly one status token on the last line):**

| Token | When | Who emits |
|---|---|---|
| `DONE\|<phase>` | Phase body completed | red / green / refactor |
| `APPROVED\|review` | Cycle approved, exit loop | review |
| `REQUEST_CHANGES\|review\|<reason>` | New cycle needed, carry reason forward | review |
| `ERROR\|<phase>\|<reason>` | Phase failed | any |

The orchestrator extracts the token from the last line of the subagent's response and uses it to decide the next phase, retry, or exit.

### 1.3 State, retries, and cycle caps

Between phases the orchestrator runs the test command (`pytest -x`, `go test ./...`, etc.) and updates `.tdd/active/<slug>.yaml`. Red phases that pass on first run trigger a trivial-test retry (line 116). Unrecognised tokens trigger a single retry then pause (line 130). Cycles exceeding `max_cycles` (default 3) pause with a continue/switch/abort prompt.

This is the piece that matters for complementarity: the orchestrator is only as good as the phase agents it dispatches to. A phase agent that doesn't emit a valid status token breaks the loop. A phase agent that blocks on user confirmation breaks autonomous cycling.

---

## 2. Fit assessment of awesome-copilot's tdd-red/green/refactor

### 2.1 What the three awesome-copilot agents actually do

| File | Input assumption | Output contract | User-interaction stance |
|---|---|---|---|
| `tdd-red.agent.md` | GitHub issue number extracted from branch name | None (prose completion) | "NEVER start making changes without user confirmation" |
| `tdd-green.agent.md` | GitHub issue acceptance criteria | None | "Confirm your plan with the user. NEVER start making changes without user confirmation" |
| `tdd-refactor.agent.md` | GitHub issue status + architectural decisions | None | Same user-confirmation gate |

All three declare a Copilot-specific `tools:` list (`github/*`, `search/fileSearch`, `edit/editFiles`, `execute/runTests`, `execute/runInTerminal`, `read/problems`, `read/terminalSelection`) and wrap a substantial GitHub-integration layer around the TDD phase work (fetch issue, post progress comments, link related issues, update acceptance criteria).

### 2.2 Three-way contract mismatch

| Contract dimension | tdd-team-workflow expects | awesome-copilot provides | Fit |
|---|---|---|---|
| Requirements source | 5-field `FEATURE:` string | GitHub issue fetched from branch | ❌ mismatch |
| Autonomy | Autonomous phase execution | Blocks on user confirmation before writing | ❌ blocks the loop |
| Output protocol | `DONE\|<phase>` token on last line | Prose completion, no token | ❌ unparseable |
| Tool vocabulary | Host-agnostic (Read, Write, Edit, Bash) | Copilot namespaces (`edit/editFiles`, etc.) | ⚠️ rewritable |
| Content overlap with `skills/tdd/` | FIRST rules, AAA pattern, minimal-code principle | Same principles, restated | ⚠️ duplicative |

Two of the mismatches are fatal: **autonomy** and **output protocol**. A phase agent that stops to ask the user for confirmation cannot serve a loop that runs red → green → refactor → review in sequence. A phase agent that doesn't emit `DONE|red` cannot signal loop progression. Fixing both would require gutting the existing prose and rewriting from the protocol outward, which is authoring from scratch with these agents as loose inspiration — not adoption.

### 2.3 What's actually salvageable

Stripping out the contract-incompatible parts leaves:

- From `tdd-red`: the AAA pattern narrative (already in `skills/tdd/SKILL.md` line 52–60).
- From `tdd-green`: the "fake it till you make it → triangulation" progression strategies (novel to our corpus but thin — 3 bullets).
- From `tdd-refactor`: the OWASP-oriented security checklist (8 items — genuinely novel).

The security checklist in `tdd-refactor` is the single substantive piece we don't have elsewhere. It could be absorbed into `skills/go-secure/` (stack-narrow) or into a new `skills/tdd-refactor-security-checklist/` skill (~40 lines of checklist material). That's a fork decision, not a phase-agent adoption.

---

## 3. Three options and a recommendation

### Option A — Skip all three (current decision in `docs/awesome-copilot-review.md`)

Leave tdd-team-workflow as-is. Users who want phase-by-phase TDD use `skills/tdd/SKILL.md` for principles and `skills/tdd-team-workflow/SKILL.md` for automation.

- **Cost**: zero.
- **Value lost**: the `tdd-refactor` security checklist doesn't land.

### Option B — Fork the refactor security checklist only

Extract the ~8-item OWASP-flavoured checklist from `tdd-refactor.agent.md` into a small skill or into `skills/go-secure/`. Skip `tdd-red` and `tdd-green` entirely (nothing novel).

- **Cost**: one upstream PR (~40 lines), or a diff against an existing skill.
- **Value gained**: security-checklist content addressable from refactor phases.
- **Risk**: checklist-style skills rot faster than principle-style skills; OWASP Top 10 changes roughly every 3 years.

### Option C — Author new `tdd-red-team`, `tdd-green-team`, `tdd-refactor` skills from scratch

Build three proper phase-agent skills that implement the tdd-team-workflow protocol: accept the 5-field input, emit the `DONE|<phase>` token, remain autonomous. Use the awesome-copilot agents as loose reference for phase-specific prose but rewrite the envelope.

- **Cost**: three net-new skills in `nq-rdl/agent-skills`, ~150 lines each. Tests against the orchestrator loop.
- **Value gained**: named, installable, introspectable phase agents that any dispatch backend can route to by name — as the SKILL.md's line 48 already anticipates.
- **Risk**: over-engineering if the default `claude:subagent` inline-prompt approach already works well enough.

### Recommendation

**Option A (skip) remains the right decision for the awesome-copilot review specifically** — the three source agents fundamentally don't fit the protocol.

**Option C is a separate future project** worth tracking as a standalone item in the `agent-skills` backlog. It's not an awesome-copilot adoption; it's authoring work informed by the contract gap this review surfaced. Flag it as a follow-up rather than absorbing it into the complementary-agents review.

**Option B is a sidequest** — if the maintainer values the OWASP checklist content enough, extract it into `skills/go-secure/` as a new section. This can ship without waiting on Option C.

---

## 4. Traceability back to the main review

`docs/awesome-copilot-review.md` rows B22 / B23 / B24 (tdd-red/green/refactor) retain their `skip` decision. The rationale column is updated to point at this document: `"Contract mismatch with tdd-team-workflow protocol — see docs/tdd-workflow-review.md § 2.2. Refactor security checklist may be salvageable (Option B)."`

The main review's next-steps checklist gains one item under Tier-B maintainer decisions: _"Option B — extract OWASP refactor checklist from tdd-refactor.agent.md into skills/go-secure or a new skill (optional)."_
