# Quickstart: Architecture Decision Records Skill

Two parts: (A) the **build/validate loop** that ships the skill (the "red→green"
evidence standing in for TDD on a doc skill), and (B) the **behavioral acceptance
walkthrough** that exercises each user story against its success criteria.

## A. Build & validate loop (repo CI-parity)

Run from the worktree root. Steps 1–4 author; 5–7 package; 8 validates exactly what CI
does. Before the edits, `asctl repo-check` and the consistency checks pass on `main`;
after step 5 but before the skill is complete they should surface the new skill (the
"red" state), and after step 8 everything is green.

```bash
# 1. Author canonical skill
#    skills/architecture-decision-records/SKILL.md  (+ references/*.md)
# 2. Cross-link the agent
#    edit agents/adr-generator/agent.md → add a pointer to the skill
# 3. Register in the planning bundle
#    registry/bundles/planning.yaml → skills: [architecture-decision-records]
# 4. Changelog fragment (mandatory — Constitution V, FR-016)
changie new --interactive=false --kind Added \
  --body "New \`architecture-decision-records\` skill captures in-session decisions as Structured MADR v4 under \`docs/adr/\` — cross-links the \`adr-generator\` agent (#202)"

# 5. Sync plugin trees from canonical sources (skill + re-synced agent)
bash scripts/sync-plugins.sh planning
# 6. Regenerate manifests + docs (do NOT hand-edit generated files)
python3 scripts/generate_manifests.py .
python3 scripts/generate_bundles_doc.py .

# 7–8. Validate exactly what CI validates
go -C tools/asctl build -o /tmp/asctl ./cmd/asctl/ && /tmp/asctl repo-check
python3 scripts/check_bundle_refs.py .
python3 scripts/check_grouping.py .
python3 scripts/generate_manifests.py . --check
python3 scripts/generate_bundles_doc.py . --check
python3 scripts/check_consistency.py .
bash scripts/validate-plugins.sh
python3 -m unittest discover -s tests -p 'test_*.py'
```

**Definition of Done (Constitution V)**: all of step 8 green, the changie fragment
exists, and `lefthook` (pre-commit + pre-push) passes.

## B. Behavioral acceptance walkthrough

Install the skill locally and drive each scenario. Each row maps to a spec Acceptance
Scenario + Success Criterion.

```bash
claude --plugin-dir ./plugins/planning   # single-session, reads the working tree
```

| # | Do this | Expect | Traces |
|---|---|---|---|
| 1 | In a session with no `docs/adr/`, say "let's record why we picked the queue over the cron poller" | Skill OFFERS to capture; **no file written** yet; offers to initialize `docs/adr/` | US1 AC1/AC4, FR-002/FR-007, SC-002 |
| 2 | Consent to capture | Writes `docs/adr/0001-*.md` as **Structured MADR v4**: Drivers first, one Pros/Cons block per option, outcome that names a driver, a `Links` section; appends a row to `docs/adr/README.md` | US1 AC2/AC3, FR-003/FR-005/FR-006, SC-001/SC-003 |
| 3 | Trigger a second capture; consent | New file numbered `0002`; index updated | FR-006, SC-003 |
| 4 | Delete `0002-*.md`, trigger a third capture | Next number is `0003` (max+1, **never reused**) | R4, SC-003 |
| 5 | Trigger a decision, then **decline** | No file created or modified | US1 AC5, FR-002, SC-002 |
| 6 | Ask "why did we choose the queue over the cron poller?" | Answer quotes the recorded Drivers + Outcome from `0001` via the index | US2 AC1, FR-009, SC-004 |
| 7 | Ask "why did we choose GraphQL?" (unrecorded) | "Not recorded" + offer to capture; **no fabricated rationale** | US2 AC2, FR-009, SC-004 |
| 8 | Point the archival path at a merged `specs/NNN-slug/` with context/options/outcome; consent | ADR whose Context/Drivers/Options/Outcome carry the spec's fields; a field the spec is silent on is marked "Not recorded", not invented | US3 AC1–AC3, FR-010, SC-005 |
| 9 | Create a superseding decision for `0001`; consent | New ADR links `0001`; `0001` marked `superseded by`; `0001` file otherwise preserved | edge case, FR-003 |
| 10 | With a pre-existing `docs/adr/adr-0005-foo.md`, capture a new ADR | New ADR is `0006` (scans both `NNNN-*` and `adr-NNNN-*`); the legacy file is **byte-unchanged** | R3/R4, FR-008, SC-007 |
| 11 | `claude plugin install planning@rdl` (or inspect `/`) | `architecture-decision-records` appears as an installable member of the `planning` plugin | FR-015, SC-006 |

## Pass criteria

All of Part A step 8 is green **and** every row in Part B behaves as its "Expect"
column — with SC-002 (zero unconsented writes) and SC-007 (pre-existing files
byte-unchanged) holding across the whole walkthrough.
