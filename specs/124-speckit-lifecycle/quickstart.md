# Quickstart: authoring & validating the `speckit-lifecycle` skill + `speckit` bundle

Repo-side workflow for building and verifying this feature end to end. All commands run from
the repo root of the `124-speckit-lifecycle` worktree.

## Prerequisites

- `git`, `bash`, `python3` + `pyyaml`
- `bats` 1.13+ (installed) — `bats --version`
- `asctl` built from `tools/asctl/`
- `changie` (for the required changelog fragment)

## 1. Author the skill

Create the canonical skill under `skills/speckit-lifecycle/`:

```text
skills/speckit-lifecycle/
├── SKILL.md                         # generic-trigger description + context detection + modes
├── scripts/provision-worktree.sh
├── scripts/merge-spec.sh
└── .tests/{provision-worktree.bats,merge-spec.bats,helpers.bash}
```

- `SKILL.md` frontmatter `description` = the issue's generic description verbatim (no
  repo-specific references).
- Follow **CONTRIBUTING.md → "Skill content conventions"** (non-inferable delta, version pins,
  verify-canonical guard).

## 2. Run the tests (TDD — write these first)

```bash
bats skills/speckit-lifecycle/.tests/          # all script behaviors, must pass
```

The six required areas: NNN derivation, conflict-guard abort, branch/worktree creation,
`--base` parentage, merge-target topology, post-merge cleanup (slot-before-branch +
idempotency + uncommitted refusal).

## 3. Verify skill structure

```bash
go -C tools/asctl build -o /tmp/asctl ./cmd/asctl/ && /tmp/asctl repo-check
```

Confirms `.tests/` (hidden) does not trip the allowed-subdir check; only
`assets/`/`references/`/`scripts/` are permitted non-hidden subdirs.

## 4. Register the `speckit` bundle

- Create `registry/bundles/speckit.yaml` (model on `registry/bundles/pixi.yaml`):
  `id: speckit`, `displayName: SpecKit`, `skills: [speckit-lifecycle]`, empty
  agents/hooks/prompts/mcp, `targets.claude` → `enabled: true`, `pluginName: speckit`,
  `marketplaceName: rdl`.
- Add `speckit` to `registry/marketplace.yaml` `order` (the `rdl` meta-plugin deps regenerate
  from enabled bundles).

## 5. Regenerate plugin tree, manifests, docs

```bash
bash scripts/sync-plugins.sh speckit                 # copy canonical skill → plugins/speckit/
python3 scripts/generate_manifests.py .              # plugin.json + marketplace.json
python3 scripts/generate_bundles_doc.py .            # docs/bundles.md
```

## 6. Full Quality Gates (CI parity)

```bash
python3 scripts/check_bundle_refs.py .
python3 scripts/check_grouping.py .
python3 scripts/check_consistency.py .
python3 scripts/generate_manifests.py . --check
python3 scripts/generate_bundles_doc.py . --check
bash scripts/validate-plugins.sh
/tmp/asctl repo-check
python3 -m unittest discover -s tests -p 'test_*.py'
bats skills/speckit-lifecycle/.tests/
```

All must pass (SC-003). Then add the changelog fragment:

```bash
changie new
```

## 7. Smoke-test install

```bash
claude --plugin-dir ./plugins/speckit     # single-session, reads plugin tree directly
```

Confirm `speckit-lifecycle` is offered and its `description` triggers on the generic phrases.

## Acceptance mapping

| Success criterion | Verified by |
|---|---|
| SC-001 mode selection / halt-and-ask | scenario test on trunk / spec branch / ad-hoc branch |
| SC-002 six bats areas pass | step 2 |
| SC-003 all validators green | step 6 |
| SC-004 traceability + generic description | spec cross-ref + `SKILL.md` review |
| SC-005 single-session spec + worktree | step 1 in root mode via the skill |
| SC-006 slot-before-branch + loud refusal | `merge-spec.bats` (step 2) |
