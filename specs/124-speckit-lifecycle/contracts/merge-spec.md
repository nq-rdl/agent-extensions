# Contract: `merge-spec.sh`

CLI contract for the deterministic spec-merge/cleanup script bundled at
`skills/speckit-lifecycle/scripts/merge-spec.sh`. Verified by `.tests/merge-spec.bats`.

## Invocation

```
merge-spec.sh <NNN>
```

- `<NNN>` (required) — the 3-digit id of the completed spec to merge.

## Preconditions

- The spec branch `NNN-slug` exists and its work is committed.
- CWD is inside the git repo.

## Behavior (ordered)

1. **Resolve** the spec branch (`NNN-*`) and slot (`.claude/worktrees/NNN`).
2. **Uncommitted-changes guard**: if the slot's working tree is dirty
   (`git -C <slot> status --porcelain` non-empty), **refuse loudly, abort non-zero** — never
   stash or discard.
3. **Merge-target resolution**: via git topology (`git merge-base`) — trunk, or the integration
   branch the spec was cut from. Never assumed to be trunk.
4. **Merge**: `git checkout <target>` then `git merge --no-ff <NNN>-slug -m "<conventional msg>"`.
5. **Cleanup — strict order**:
   1. `git worktree remove .claude/worktrees/NNN` (**before** branch deletion; idempotent if
      already absent),
   2. `git branch -d <NNN>-slug`,
   3. `git push origin --delete <NNN>-slug` (best-effort; skip if no remote branch).
6. **Retain** `specs/NNN-slug/` as the permanent record; `NNN` is never reused.

## Exit codes

| Code | Meaning |
|---|---|
| 0 | Merge complete; slot removed then branch deleted; spec dir retained |
| non-0 | Uncommitted changes in slot, missing branch/NNN, or merge conflict — loud message, no data loss |

## Idempotency

Re-running after a partial failure completes cleanly: absent slot / already-deleted branch are
treated as satisfied, not errors.

## Verified acceptance (bats)

- Merge target inferred from topology — trunk vs integration branch (US3 #5, edge case).
- `--no-ff` merge performed (US3 #5).
- Worktree slot removed **before** branch deletion (FR-007, SC-006).
- Worktree removal idempotent (FR-007).
- Dirty slot → loud refusal, no mutation (FR-007, SC-006).
- `specs/NNN-slug/` retained; `NNN` never reused (FR-008).
