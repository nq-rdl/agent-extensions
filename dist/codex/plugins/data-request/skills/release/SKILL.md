---
name: release
license: CC-BY-4.0
description: Draft the researcher-facing Extraction Summary and Extraction Assumptions
  / Important limitations for a release from the release tag's own pipeline, outputs
  and validation, checked against the confirmed scope and .sqlreview reviews. A stale
  review or conflicting source holds its claim; the analyst accepts, rewords or rejects
  each claim, and the record keeps wording and provenance. It never publishes. Use
  when an analyst prepares a release body.
compatibility: .sqlreview schema 2 (schema 1 remains readable) (docs/specs/2026-09-15-sql-review-plugin-design.md);
  bash 3.2+, jq >= 1.6, git (reads the release tag). Scaffold paths (specs/amendments.md,
  .copier-answers.yml, runbook, UAT checklist) follow data-analysis-scaffold 0.5.0;
  verify the repository's own layout at use time.
metadata:
  repo: https://github.com/nq-rdl/agent-extensions
---

## Codex execution

When supporting references invoke a catalog skill as /subject:facet, use $subject:facet in Codex. Preserve slash syntax inside examples that configure or document another host.

Before shell examples, set PLUGIN_ROOT to the absolute installed plugin directory: two parent directories above this SKILL.md’s containing skill directory. Derive it from the loaded file path, never the working directory. This variable is not automatically supplied to ordinary shell tools. Quote it in commands.

Here $ARGUMENTS means the user’s supplied skill arguments. Codex does not populate a shell variable for them. Pass arguments with shell quoting that preserves literal text; never evaluate user text as shell code.

# Data Request — release (Data Analyst)

This step is Analyst → Researcher communication. `$data-request:analyse` stays the engineer's
detailed review, and `$data-request:explain` walks the analyst through it. This skill drafts a
short release body from the release's own artifacts. It never changes a scope, review or SQL
file, and it never publishes a release, pushes a tag or posts the body.

Order: the Data Engineer completes `analyse`, the authorised operator run, UAT and the triage
hand-off; the Data Analyst runs `explain`, accepts for release preparation, sends back or
amends presentation, then drafts here and publishes. Never direct the engineer to release.
If the analyst chooses **Send back** here, use the paste-ready send-back note in
`${PLUGIN_ROOT}/skills/explain/references/send-back-note.rst`, with its completeness check: logic changes or defects to `fix`, presentation
changes to `amend` before or after release. Add two lines after `outcome:`: `release ref: <tag
or candidate ref>`, and `release claims: <claim and question ids, with the conflicting sources
for each>`. The engineer then has the claim, its sources and the expected result in one comment. Keep unresolved claims `pending` and the current
candidate record `draft`; do not overwrite a previously approved release record, post the
note or clear a gate. The note belongs on the deliverable PR, never the child issue or
service-desk. See *Communication channel* in `${PLUGIN_ROOT}/skills/triage/references/handoff.rst`. Refreshed review and operator-run/UAT evidence precede another hand-off.

For RDL cohort SQL, invoke `$data-request:guardrails` when a claim rests on
a storage fact or conversion. Worked example:
[references/worked-example.rst](references/worked-example.rst).

Arguments: `$ARGUMENTS` — the release tag or candidate ref (for example `v1.0.0`). If none is
given, work it out before you ask. Read the release tags (`git tag --list 'v*'`), published
releases and their notes, `.sqlreview/releases/*/release.json`, the ledger and merged release
PRs. Guardrails `references/release.rst`, **Release state from evidence**, lists these signals.
When exactly one tag has no `approved` release record, use it and say so in one line. For
example: "Candidate v1.1.0: v1.0.0 has an approved record, v1.1.0 has none." Ask only when no
tag or more than one tag qualifies, and list the candidates in the question.

```bash
S="${PLUGIN_ROOT}/skills/setup/scripts"
bash "$S/sqlreview.sh" status --json   # exit 3 → stop: not initialised, run $data-request:setup first
```

## 0. Amend gate

Do this before any other step. A part that `$data-request:amend` handed off blocks the release
until a strict comment on the deliverable PR closes it. `release.sh evidence` enforces this from
amend's part-state record, `.sqlreview/amendments/<request>.json` (amend step 5). Each part has
the status `done`, `handed off` or `withdrawn`.

First bring the record up to date. Find the deliverable PR in the ledger, or use the PR URL the
analyst gives. Read its comments, read-only, for each `amendment hand-off:` comment and its `part:`
entries. Only a later comment whose first line has one of two forms closes a handed-off part:

- **Completed:** `done: P<n> <commit>`, from the engineer. Set the part to `done` with that commit.
  The script checks that the commit is in the release ref (`git merge-base --is-ancestor <commit> <ref>`).
  If the check fails or cannot run, the part stays open.
- **Withdrawn:** `withdrawn: P<n> <reason>`, from the analyst. Set the part to `withdrawn` with that
  reason. A `withdrawn:` line with no reason leaves the part open.

Any other comment that names the part leaves it open, for example "P3 is still in progress".
For each handed-off part, say in one line which comment you read and what it decided. A hand-off
comment with no record is a blocker: write the record with the part `handed off`. The script also
holds when the ledger shows an `amend` stage and the record file is missing. If you cannot
read the PR, say so and stop. Never assume that no part is open.

Then run `bash "$S/release.sh" evidence "<ref>"`. Exit 11 means release held: stop before step 1.
Give its stderr in one or two lines, for example "Release held: P3 is handed off and open. Next:
the engineer comments `done: P3 <commit>` on the PR, or you withdraw it there." Offer to draft
`withdrawn: P3 <reason>` with the analyst's own reason. Do not draft it without a reason. Post
nothing. Never edit the record to pass the gate without a strict comment.

## 1. Gather the release evidence

Read every source at the tag with `git show <tag>:<path>`, never the working tree or another
branch:

- the request, confirmed scope (`scope.json`), analyst intake, answers configuration
  (`answers.yaml` or `.copier-answers.yml`), open questions and `specs/amendments.md`;
- the pipeline or builder that produced the extract, and the SQL it generates;
- the output manifest or schema: each delivered file, its columns and its row grain;
- validation and UAT evidence: runbook, UAT checklist and validation outputs.

For counts in that evidence, apply guardrails `references/release.rst`, **Probe disclosure control**, before quoting them.

Then list the reviews and whether each describes the release:

```bash
bash "$S/release.sh" evidence "<tag>"   # exit 0 every review applies · 10 at least one does not · 11 amend hold · 2 unknown ref
```

For each slug, load `bash "$S/sqlreview.sh" questions "$SLUG" review`: `questions.json`
is the authoritative current handoff question status; `release.sh evidence` includes its
structured rows and open-only compatibility list. Closed legacy strings in scope/review
are not unresolved questions. Label these as current handoff evidence against the tag, not
question status at the historical tag. Reconcile obsolete intake copies with their owner;
do not silently update `answers.yaml` or convert engineer choices into analyst answers.

A claim that needs a missing manifest, schema or validation result is a question, not a fact.
Say which source is missing.

## 2. Check that each review applies

Do this before you use any review item. `evidence` reports `applies` for each review:

- `current`: the SQL at the tag is the reviewed SQL.
- `header-only`: only the leading comment header differs. The items apply.
- `changed`: the SQL at the tag differs. The review is stale for this release.
- `missing-at-ref`: the reviewed SQL is not in the release.
- `unreviewed`: a scope only, with no review.

It also reports `reviewed_commit_in_ref`: `false` means the review was made on a commit outside
the release. Then compare the review with the pipeline yourself. A review of draft SQL, or of SQL
the pipeline no longer generates, does not describe the release, even when a file matches.

A review that does not apply blocks every claim based on it. Re-derive the claim from the
release's own files and cite them, or raise it as a question. Never infer confirmation from an
old review. Offer `$data-request:analyse --update` to the engineer when the release SQL needs a
current review.

## 3. Compare the release with scope and review

Before you draft any wording, compare each source with the others and with any existing release
wording:

- **inclusion rule**: the codes, text matches and Boolean structure (and, or) that admit a record;
- **unit of observation**: the grain of each delivered file, against source-citing scope/intake
  and review `grain`, keeping the main grain separate from requested finer outputs. Apply
  guardrails `references/grain.rst`: a bare answers-file default is not a confirmed scope;
- **delivered outputs**: each file and field, against the requested elements. A requested element
  that is absent is a finding;
- **derivations**: period, site, age basis and other derived fields.

Bare-default drift alone is not a blocking discrepancy: reuse the existing `L-grain-answers`
finding once and offer correction to the engineer, without changing answers or SQL here.
An unknown grain or real conflict with an evidenced agreed grain still holds its claim.
Each meaning-changing difference is a blocking discrepancy. Record it as a question (`Q1`, `Q2`, ...) with the
conflicting evidence from each source and a proposed correction, and hold the draft until the
analyst resolves it. Never soften a discrepancy into boilerplate, and never leave it out. A prose
or typo pass comes after.

## 4. Select and translate

Go through each confirmed review item (`A1`, `L1`, ...), scope item, amendment and validation
finding. A research criterion (`N1`, `I1`, `E1`, `D1`, ...) belongs in the table of step 6, not
here. Keep an item for the researcher when it affects cohort membership, field meaning,
completeness, comparability or interpretation. Merge related items. Keep implementation detail
(locking hints, row order, query structure) in the internal review, unless its consequence
matters to the researcher. Then state the consequence, not the mechanism. Use plain language and
short sentences, without SQL terms.

Show the analyst the items you kept internal, with a one-line reason each, so no omission is
silent.

Draft two sections:

- **Extraction Summary**: population, site, period, unit of observation, delivered files and
  fields, and major derivations.
- **Extraction Assumptions / Important limitations**: what the researcher must know to interpret
  the data.

Label each claim as a **confirmed fact** (the release's files support it) or a **question**
(analyst or engineer resolution needed), and give its **proposed wording**. Give each claim an id
(`C1`, `C2`, ...) and keep its sources: review items by slug, id and revision, and release files
by path and tag.

## 5. The analyst decides each claim

Put the questions first, then each claim, via the host user-question tool, in batches of at most four. For a
claim, show the proposed wording and its sources, with the options **Accept (Recommended)** /
**Reword** / **Reject**. A reworded claim is shown again. For a question, show the conflicting
evidence and the proposed correction, and record the analyst's resolution. An unresolved question
holds the release: the record stays `draft`.

Never fill `decided_by` or `decided_at` from anything but an answered question. `decided_by` is
the analyst's handle (GitHub login where known, else `git config user.name`, else ask; never
`user.email` — `release.sh check` refuses an `@`). `recorded_by` and `resolved_by` follow the same rule. `decided_at` is now (UTC ISO). If
the analyst stops, write a `draft` record with the undecided claims `pending`, and say so.

## 6. Criteria in this release

The body carries `## Criteria in this release` before **Extraction Assumptions / Important
limitations**: every research criterion, in the order entry event, inclusions, exclusions, data
elements, with the columns ID, Researcher's request, This release and Change since <previous tag>.
`release.sh criteria` builds it as the record's `criteria` object (`previous_tag`, `scope`,
`rows`, `status`, `held_reasons`) from `answers.intake.json` and the one scope that carries
criteria states, both read at the tag.

**Fingerprints first.** The agent runs the answers validator; `release.sh` runs no Python and
never runs the validator. Write `git show <tag>:answers.yaml` to a temporary directory, with the
tag's `answers.intake.json` beside it when the tag has one, and run the validator from the
rendered child:

```bash
T="$(mktemp -d)"
git show "<tag>:answers.yaml" > "$T/answers.yaml"
git show "<tag>:answers.intake.json" > "$T/answers.intake.json" 2>/dev/null   # beside answers.yaml
pixi run python scripts/validate_answers.py "$T/answers.yaml" --fingerprints > "$T/fp.json"
# or: data-analysis-scaffold validate-answers "$T/answers.yaml" --fingerprints > "$T/fp.json"
bash "$S/release.sh" criteria "<tag>" --fingerprints "$T/fp.json"   # exit 0 complete · 10 held · 2 error
```

Read the validator's exit status. Only a validation failure means `--answers-invalid` (pass it
instead of `--fingerprints`): the child script's exit 3, or the generator CLI's exit 1 after it prints its
`✗ <path>: N problem(s)` report. Any other failure is not a verdict on the answers: the child's
exit 2 (operational, including an older child that rejects `--fingerprints`), `pixi run`'s exit 1
when it cannot prepare the environment, or a generator exit 1 without that report. Stop and report
it; do not hold the table as `answers-invalid`. With neither flag the table is held
(`fingerprints-unchecked`). Remove the temporary directory afterwards.

**Previous tag.** `previous_tag` is the greatest earlier stable `X.Y.Z` release whose record is in
the tag's tree: never a prerelease, a later tag or the working tree. The change column compares
with that record's table. With none, the header reads `Change` and every cell is `—`.

**The analyst decides each row, on the note only.** Show every row through the host user-question tool, in
batches of at most four: the researcher's request quoted as recorded, the state, and the
`proposed_note`, with **Accept (Recommended)** / **Reword** / **Reject**. Accept sets `final_note`
to the proposed note. Reword takes the analyst's note, which is shown again. Reject leaves
`final_note` null. The researcher's wording is never editable. Do not reword `text`, even to
tidy it; a changed wording shows as a change in the next release. Fill `decided_by` and
`decided_at` as in step 5. Row decisions carry over while the proposed note is unchanged, so re-running
`release.sh criteria` after the record is written keeps them; a changed note is `pending` again.

A rejection means the stated state is wrong. It sends the state back to the engineer: fix the
scope, then re-run `release.sh criteria`. Record it in order: write the record with the row
`rejected`, then re-run `release.sh criteria` with the same fingerprints file (exit 10; the
decisions carry over), embed the object it prints, which names `note-rejected:<id>`, and write
the record again. A rejected row fails `release.sh check` unless the embedded table is held
with `note-rejected:<id>`, on a draft record too. The table never drops the row.

**Held.** `release.sh criteria` ends with exit 10 and `status` is `held` for any of these `held_reasons`:
`no-owning-scope`, `review-stale`, `scope-stale`, `state-missing:<id>`, `fingerprint-mismatch:<field>`, `owning-scope-ambiguous`,
`note-rejected:<id>`, `answers-invalid` and `fingerprints-unchecked`. A free-text mismatch goes
back to `$data-request:intake`; the others go to the engineer, except `fingerprints-unchecked`,
which the analyst fixes by re-running the step above. `no-owning-scope` means the tag's sidecar itemises live criteria but no scope carries their states (a scope
published before the analyst itemised): the engineer must run `$data-request:bootstrap` to record criteria states,
and a new tag follows. It comes with `state-missing:<id>` for each live criterion, whose row shows the
researcher's request with no state; such a table is never "not itemised". `scope-stale` means the SQL body at
the tag differs from the body the owning scope recorded, so its states may be false. A header-only change
does not hold. The engineer rescopes with `$data-request:bootstrap`, publishes, and a new tag follows. `answers-invalid` means the tag's
`answers.yaml` failed validation and the tag cannot change, so it needs an engineer or intake fix
and a new tag. The body then shows
one line, `Criteria table held: <reasons>`, with no partial table. A held table, or any row whose
decision is `pending`, fails `release.sh check` only when the record is `approved`: keep the
record `draft`, and never present a held table as final.

**No repeats.** Never repeat a criterion in the limitations. A claim whose source is a scope
source whose `item` is a criterion id is left out of the limitations when the record has a
`criteria` object. A pending one is hidden from the draft body yet still blocks approval, so
resolve those claims too; the record still needs a kept non-criterion claim under
**Extraction Assumptions / Important limitations**. A row filter RDL added on its own (test
patients, cancelled admissions) is not a criterion: it stays a limitation.

**Not itemised.** With no sidecar, a schema 1 sidecar, or a schema 2 sidecar with no live criterion and no scope carrying criteria states, `release.sh criteria` prints
`null`. Write `"criteria": null` (or omit it). The body then carries one line, `Criteria are not
itemised for this request.`, and the rest of the body is unchanged. Run inside the repository,
`release.sh check` rejects an approved record without a criteria table when the sidecar at its
commit has a live criterion.

## 7. Record and render

Write the whole record to `.sqlreview/releases/<tag>/release.json` (the guard validates it):

```json
{"schemaVersion": 1, "kind": "release", "tag": "<tag>", "commit": "<commit from evidence>",
 "status": "approved", "recorded_at": "<UTC ISO>", "recorded_by": "<analyst>",
 "evidence": [{"slug": "<slug>", "revision": 3, "applies": "current"}],
 "claims": [{"id": "C1", "section": "summary", "proposed": "…", "final": "…",
             "decision": "accepted", "decided_by": "<analyst>", "decided_at": "<UTC ISO>",
             "sources": [{"kind": "review", "slug": "<slug>", "item": "A1", "revision": 3},
                         {"kind": "file", "path": "src/pipelines/x.py", "ref": "<tag>"}]}],
 "questions": [{"id": "Q1", "text": "…", "sources": [], "resolution": "…",
                "resolved_by": "<analyst>", "resolved_at": "<UTC ISO>"}],
 "criteria": {"previous_tag": "0.1.0", "scope": {"slug": "<slug>", "revision": 5},
              "rows": [{"id": "E2", "kind": "exclusion", "text": "<verbatim>", "state": "flagged",
                        "proposed_note": "…", "final_note": "…", "decision": "accepted",
                        "change": "changed", "previous_state": "not-applied",
                        "decided_by": "<analyst>", "decided_at": "<UTC ISO>"}],
              "status": "complete", "held_reasons": []}}
```

`evidence` copies `slug`, `revision` and `applies` from `release.sh evidence`. `section` is
`summary` or `assumptions`. `decision` is `pending`, `accepted` (`final` equals `proposed`),
`reworded` (new `final`) or `rejected` (`final` is null). `status` is `approved` only when every
claim is decided and every question is resolved, and the `criteria` table (the object `release.sh
criteria` printed, with your row decisions) is `complete` (empty `held_reasons`) with no `pending` row. Copy
`text`, `state` and `change` as printed.

```bash
bash "$S/release.sh" check ".sqlreview/releases/<tag>/release.json"    # exit 4 → one violation per line
bash "$S/release.sh" render ".sqlreview/releases/<tag>/release.json" > ".sqlreview/releases/<tag>/release.md"
```

Show the rendered body. It is paste-ready for the release: each claim carries its sources in an
HTML comment, which GitHub does not display. The confirmed technical review is not changed; a
disagreement with a review item goes to the engineer through `$data-request:analyse --update`.
No claim, question or record may contain row-level data: no identifiers, record values or small
cell counts. The analyst publishes the release.
