# Playbook: enforcing Superpowers discipline in a SpecKit repo (#204)

Part of epic #207. Recommends a **SpecKit-native** extension (the `specify extension`
layer, scoped per target repo — distinct from this repo's Claude Code plugin set in
#203) to enforce the worktree → TDD → subagent → review → finish discipline, and how to
wire it into a fresh speckit repo.

## Options compared

| Option | Layer / install | Enforces | Maintained? | Fit |
|---|---|---|---|---|
| **`superpowers-bridge`** (`RbBtSn0w/spec-kit-extensions`, catalog id `superb`) | SpecKit-native (`specify extension add superb`) | plan-gate validation, RED-GREEN-REFACTOR before `/speckit.implement`, post-implement verify gate requiring **fresh test evidence** | dedicated extension | **Strong** — evidence-first gates map 1:1 to Superpowers execution |
| **`cc-spex` bundled extensions** | SpecKit-native hooks (`after_specify`/`after_tasks`/`after_implement`) | quality gates, worktrees, teams, deep-review | broader plugin suite | **Deferred** — #203 recommends *not* adopting `cc-spex` yet |
| **Constitution clause** (hand-rolled) | `constitution.md` text (#205) | routing/ownership by convention; not mechanically enforced | n/a (you own it) | **Baseline** — zero-dependency, every repo gets it |

## Friction points addressed

- **`constitution.md` drift during execution** — the constitution clause (#205) fixes
  ownership (SpecKit plans, Superpowers executes) but is *convention*; `superpowers-bridge`
  makes it *mechanical* by gating `/speckit.implement` on RED-GREEN-REFACTOR + verify
  evidence, so execution cannot silently diverge.
- **Session continuity across pauses** — the CLAUDE.md routing block (#205) re-establishes
  vocabulary every session (including after `/clear`); the SpecKit-native gates fire
  regardless of session state, so a resumed session still hits the same evidence checks.

## Recommendation

**Layered:**
1. **Baseline (every repo, zero dependency):** the #205 constitution clause + CLAUDE.md
   routing block. This is the floor and needs no install.
2. **Opt-in enforcement (recommended for teams wanting hard gates):**
   `superpowers-bridge` (`superb`). It is the focused, SpecKit-native option whose
   evidence-first gates directly enforce the discipline at the command boundary.
3. **Do not adopt `cc-spex` for this purpose now** — per #203 (CONDITIONAL / not yet).

`speckit-lifecycle` (#124) should reference this playbook when it sets a repo up, and
point at #205 for the constitution/CLAUDE.md templates.

## Target-repo setup (not this repo)

Run inside the team's **speckit** repo:

```bash
# 1. Baseline routing (always) — apply the #205 templates
#    - add the SpecKit-authoritative / Superpowers-execution clause to constitution.md
#    - add the CLAUDE.md routing block (vocabulary + definition-of-done)

# 2. Opt-in enforcement gates
specify extension catalog add https://github.com/RbBtSn0w/spec-kit-extensions
specify extension add superb        # superpowers-bridge

# 3. Verify the gates fire
#    - /speckit.plan   -> plan-gate validation runs
#    - /speckit.implement -> blocked until RED-GREEN-REFACTOR + fresh verify evidence
```

Anti-patterns to avoid (see #205): running both `/speckit.implement` and the Superpowers
workflow on the same task; skipping `/speckit.tasks`.

## References

- `RbBtSn0w/spec-kit-extensions` → `superpowers-bridge` (`superb`)
- #203 — cc-spex evaluation (conditional, not adopted)
- #205 — constitution / CLAUDE.md routing templates
- #124 — `speckit-lifecycle` (references this playbook at repo setup)
