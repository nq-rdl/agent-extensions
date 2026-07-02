# Playbook: enforcing Superpowers discipline in a SpecKit repo (#204)

Part of epic #207. Recommends a **SpecKit-native** extension (the `specify extension`
layer, scoped per target repo — distinct from this repo's Claude Code plugin set in
#203) to enforce the worktree → TDD → subagent → review → finish discipline, and how to
wire it into a fresh speckit repo.

## Options compared

| Option | Layer / install | Enforces | Maintained? | Fit |
|---|---|---|---|---|
| **`superpowers-bridge`** (`RbBtSn0w/spec-kit-extensions`, catalog id `superb`, v1.8.0, Spec Kit `>=0.12.0`) | SpecKit-native (`specify extension add superb`) | mandatory gates across the whole chain: plan-gate (`after_plan`), TDD/RED-GREEN-REFACTOR controller (`before_implement`), verify with **fresh test evidence** (`after_implement`/`after_converge`), plus `review`/`critique` and `finish` gates | dedicated extension (10 commands / 6 hooks) | **Strong** — evidence-first gates map 1:1 to the full worktree→TDD→subagent→review→finish discipline |
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

Run inside the team's **speckit** repo. **Prerequisite:** `superb` requires **Spec Kit
`>=0.12.0`** — check with `specify --version` first and upgrade if older.

```bash
# 1. Baseline routing (always) — apply the #205 templates
#    - add the SpecKit-authoritative / Superpowers-execution clause to constitution.md
#    - add the CLAUDE.md routing block (vocabulary + definition-of-done)

# 2. Opt-in enforcement gates — register the catalog, then install `superb`.
#    --install-allowed is REQUIRED or `extension add` is blocked by policy.
specify extension catalog add https://raw.githubusercontent.com/RbBtSn0w/spec-kit-extensions/main/catalog.json \
  --name rbbtsn0w-spec-kit-extensions \
  --priority 1 \
  --install-allowed \
  --description "RbBtSn0w Spec Kit Extensions"
specify extension add superb        # superpowers-bridge (id: superb)

#    Alternative (no catalog): pin a specific release directly —
# specify extension add superpowers-bridge \
#   --from https://github.com/RbBtSn0w/spec-kit-extensions/releases/download/superpowers-bridge-v1.8.0/superpowers-bridge.zip

# 3. Verify the gates fire (all mandatory hooks)
#    - /speckit.plan      -> plan-gate (after_plan): plan completeness + SDD directives
#    - /speckit.implement -> controller (before_implement): bridges TDD (RED-GREEN-REFACTOR)
#    - completion         -> verify (after_implement/after_converge): no task done without
#                            fresh test evidence
```

Anti-patterns to avoid (see #205): running both `/speckit.implement` and the Superpowers
workflow on the same task; skipping `/speckit.tasks`.

## References

- `RbBtSn0w/spec-kit-extensions` → `superpowers-bridge` (`superb`)
- #203 — cc-spex evaluation (conditional, not adopted)
- #205 — constitution / CLAUDE.md routing templates
- #124 — `speckit-lifecycle` (references this playbook at repo setup)
