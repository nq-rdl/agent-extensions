# Contract: `provision-worktree.sh`

CLI contract for the deterministic worktree-provisioning script bundled at
`skills/speckit-lifecycle/scripts/provision-worktree.sh`. This contract is the behavioral
spec the `.tests/provision-worktree.bats` suite verifies.

## Invocation

```
provision-worktree.sh <slug> [--base <branch>]
```

- `<slug>` (required) — kebab-case feature description; becomes the branch/dir suffix.
- `--base <branch>` (optional) — parent branch to cut from. Default: the discovered trunk.

## Preconditions

- CWD is inside a git repo following SpecKit conventions.
- `git` available.

## Behavior

1. **Trunk discovery** (only when `--base` absent): `git symbolic-ref --short
   refs/remotes/origin/HEAD` → strip `origin/`; fallback to first existing of
   `main`/`master`/`trunk`; final fallback current branch iff not `^\d{3}-`.
2. **NNN derivation**: scan `git branch -a` (strip `remotes/*/`), `specs/*`,
   `.claude/worktrees/*`; extract leading `\d{3}`; `NNN = printf '%03d' (max + 1)`; none → `001`.
3. **Conflict guard**: abort non-zero **before any mutation** if `NNN` already exists as a
   branch, a `specs/NNN-*` dir, or a `.claude/worktrees/NNN` slot.
4. **Provision**: `git worktree add -b <NNN>-<slug> .claude/worktrees/NNN <base>`.
5. **SpecKit probe**: if `.specify/scripts/bash/create-new-feature.sh` exists, invoke it with
   `--allow-existing-branch` (CWD = the new slot) so it adopts the branch and scaffolds
   `specs/NNN-slug/spec.md`; else bare-git fallback creates `specs/NNN-slug/` + template `spec.md`.

## Output contract (stdout)

Machine-readable line(s) the skill parses to report the result — at minimum `NNN`, the branch
name, the worktree path, and the base branch (JSON or `KEY=value`). The skill uses these to
print `claude --worktree .claude/worktrees/NNN`.

## Exit codes

| Code | Meaning |
|---|---|
| 0 | Branch + worktree (+ spec scaffold) created |
| non-0 | Conflict guard tripped, missing `<slug>`, or git failure — **no partial state left behind** |

## Postconditions (success)

- Branch `NNN-slug` exists, cut from `<base>`.
- `.claude/worktrees/NNN` checked out on that branch.
- `specs/NNN-slug/` exists with a `spec.md` (template or SpecKit-scaffolded).

## Verified acceptance (bats)

- NNN = max across all three sources + 1, zero-padded (US3 #1).
- Pre-existing NNN (branch **or** dir **or** slot) → abort, no mutation (US3 #2).
- No `--base` → cut from trunk; `--base X` → cut from `X` (US3 #3).
- `create-new-feature.sh` present → invoked with `--allow-existing-branch`; absent → bare-git
  fallback (US3 #4).
