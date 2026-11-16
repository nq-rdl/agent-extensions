---
license: CC-BY-4.0
description: >-
  Interview the Data Analyst on the research decisions of a data request — cohort and age
  limits, code-set edges, outcomes and windows, identifiers and presentation, governance and
  the grain — then itemise the research criteria, fill answers.yaml, write
  answers.intake.json (schema 2) and, on approval, render the data-analysis-scaffold over a request-template repo with copier. Needs no
  .sqlreview/. Re-running walks through what changed. Use before the engineer's
  /data-request:bootstrap, whenever an analyst fills or revises answers.yaml.
argument-hint: '[answers.yaml path] [--update]'
user-invocable: true
compatibility: >-
  answers.intake.json schemaVersion 1 or 2, validated by data-analysis-scaffold validate-answers or a
  generated child's scripts/validate_answers.py (sidecar checks from scaffold v0.5.1; schema 2 and
  validate-answers --fingerprints need a scaffold release that accepts schema 2). Render
  step verified with copier 9.18.2, scaffold v0.5.1 and request-template 47b702d; needs
  copier >= 9.15 and GitHub access to nq-rdl/data-analysis-scaffold. Python 3 with PyYAML.
allowed-tools: Bash, Read, Glob, Grep, Write, Edit, AskUserQuestion
metadata:
  repo: https://github.com/nq-rdl/agent-extensions
---

# Data Request — intake (Data Analyst)

The **Data Analyst** runs this pass while filling `answers.yaml`, before the Data Engineer
starts. The analyst has the requester's knowledge: what the research needs. The engineer has
the systems knowledge: which sources, keys and joins deliver it. This skill is the analyst's
interview; `/data-request:bootstrap` is the engineer's. It is not a separate stage: it is the
`answers.yaml` filling pass, guided.

Arguments: `$ARGUMENTS` — the answers file (default `answers.yaml` at the repository root).
The sidecar is always its sibling `answers.intake.json`.

Before this skill: Power Automate opens the enquiry issue in `rdl-service-desk/service-desk`,
and the analyst creates the request repository from `rdl-service-desk/request-template` with
GitHub's template button and opens it in the session. This skill does not create repositories.

Read `${CLAUDE_PLUGIN_ROOT}/skills/setup/references/analyst-intake.rst` first. It is the
schema contract shared with `validate-answers`; this skill does not restate it. It writes
`answers.yaml` and `answers.intake.json`; only the approved copier run writes anything else.
Never write `.sqlreview/`, `scope.json` or SQL, and do not require `/data-request:setup`: the
engineer runs it later.

## Validate before and after

```bash
pixi run python scripts/validate_answers.py answers.yaml    # generated child
data-analysis-scaffold validate-answers answers.yaml        # otherwise, when installed
python .github/scripts/validate_answers.py answers.yaml     # request-template seed: answers.yaml only
```

Run one before the interview (an existing sidecar can already be invalid) and again after
every write. The first two validate the sibling sidecar too, but only from a scaffold that
ships `scripts/analyst_intake.py`. Diagnostics name fields, never values.
If neither command is available, say that validation did not run; never report a pass.
The seed's `.github/scripts/validate_answers.py` checks required fields and choices only:
it never reads the sidecar, so its pass is not a sidecar pass.

## Gather the evidence

Read `answers.yaml`, the enquiry (service-desk issue, intake form, requester comments) and the
governance approval when the analyst supplies them. Draft each proposed decision from that
wording and cite where it came from in `rationale`. The analyst's answer is the confirmation;
a draft built from request text is only a proposal until they answer.

On a re-run, or when the enquiry says "as per request <prior>", read the prior request's SQL
and the current build outputs (delivered columns and grain) before you propose a cohort or a
grain. Cite the file in `rationale`. Issue wording alone is not evidence. A prior request's
decisions are proposals: the analyst confirms each one again in this pass. A written, dated
review by the analyst (an enquiry comment) is evidence too: name it in `decided`, and still
ask for confirmation here.

## Keep the interview state

A session can restart in the middle of the interview. Keep every answer in
`answers.intake.draft.json`, beside `answers.yaml`. These helper commands need no `.sqlreview/`:

```bash
S="${CLAUDE_PLUGIN_ROOT}/skills/setup/scripts"
bash "$S/sqlreview.sh" intake answers.intake.draft.json 1    # start of the pass: read a draft back
bash "$S/sqlreview.sh" now                                   # right after each answer: confirmed_at
bash "$S/sqlreview.sh" intake-draft answers.intake.draft.json < next.json    # after each batch
```

- At the start, read back a draft that exists. Its decisions and open questions are answered:
  do not ask them again. Ask only what it lacks. A re-run starts the draft from the current sidecar.
- After each answered batch, write the whole document (all earlier answers and this batch) to
  `next.json` with `schemaVersion: 1`, then stage it. A stage that fails leaves the old draft:
  fix the named rule and stage again.
- The draft is not the sidecar. Never commit it. Delete it after the final sidecar validates.

## The interview

Ask about research decisions only, in this order. Each topic maps to a schema `topic`:

1. **cohort** — the cohort in clinical terms; age limits with their anchor (age at index event
   differs from age today); sex; inclusions and exclusions. Facility: when the request is silent
   or names TUH, the engineer imports the TUH house default — do not ask. Record a facility
   decision only when the request names a different facility set.
2. **codes** — each code set, its edges and edition (which subcodes count, whether a category
   includes its children). For code discovery run `/data-request:lookup`, and cite its record
   (not its counts) in the decision's `rationale`. A lookup hit is not the analyst's choice.
3. **outcomes** — each outcome, its window and anchor, and who applies it (SQL or researcher).
4. **outputs** — required identifiers and presentation (column names, formats, de-identified
   or identified).
5. **governance** — the approval number and any known restriction. A restriction applies at
   once. An approval number alone does not prove each element was checked; that check is the
   analyst's at delivery review.
6. **grain** — always ask, in these words: "What does one row represent — one row per <unit>,
   in clinical terms? Are any requested outputs finer, such as per surgery or per ward stay?"
   Record the answer as the one `grain` decision with `unit` and any `finer_outputs`.
   `measurement_granularity: Patient` in `answers.yaml` is often an untouched Copier default,
   not an answer: never copy it into the sidecar, even when it matches.

Put proposals to the analyst with AskUserQuestion, at most four per call, one question per
decision. Show the proposed `text` **and** `rationale` — both are recorded. Options:
**Confirm (Recommended)** / **Reword** / **Leave open**. A reworded decision is asked again
in its new words. **Leave open** becomes an `open_questions` entry phrased for the requester,
with the proposed reading noted. Batch the open questions so the analyst can send them to the
requester in one message.

### Itemise the criteria

Itemise the four free-text answers in `answers.yaml` into `criteria`, one entry per item:
`cohort_entry_event` (kind `entry_event`), `inclusion_criteria` (`inclusion`),
`exclusion_criteria` (`exclusion`) and `requested_data_elements` (`data_element`). Ids are
`N`, `I`, `E` and `D` plus a number counted from 1 within the kind (`E1`, `E2`). Keep the
researcher's own wording in `text`: split into items, never paraphrase or merge. Itemising does not
edit the free text in `answers.yaml`; filling or correcting it is a separate edit, below. Put the numbered list to the analyst per kind, with
the same options as a decision; an item left open goes to `open_questions` and is not written to
`criteria`.

Ask `applied_by` only where the request is unclear about who applies an inclusion or exclusion
(`rdl` or `researcher`). When the enquiry says so, record it and do not ask. Add `decided` only
when the enquiry names who decided and when (`by`, `role`, `at`, `source`); never infer them.
Never set `applied_by` on an entry event or data element.

When no entry event is stated (for example "all patients with diagnosis X"), do not invent an
`N1`: ask which item fixes the index date, and record the answer as a `cohort` decision naming
that item's `id`, or as an open question when the analyst cannot answer.

Stay out of the engineer's lane. Do not ask about source tables, joins, keys, timezones,
validity rules or SQL. If the analyst volunteers one, keep it for the hand-off note; do not
record it as a decision. Prior SQL or delivery can support a proposal, but only the analyst's
answer confirms it.

## Recording a decision

- `confirmed_by` is the analyst's handle: GitHub login when known, else
  `git config user.name`, else ask. Never an email, and never the agent's identity.
- `confirmed_at` is the UTC time of the analyst's answer (`YYYY-MM-DDTHH:MM:SSZ`), from the `now` helper.
- `decided` only when the evidence names who made the decision (for example a requester's
  dated reply); omit it otherwise. Never infer a decider or date from prose.
- `approval_number` matches `answers.yaml` exactly.
- No identifiable patient data, and no lookup counts, in either file.

With no human to answer (a non-interactive run), confirm nothing: every proposal goes to
`open_questions`, itemised criteria included (write no `criteria` entry for one). A partial
intake is valid; an invented confirmation is not.

## Fill `answers.yaml` in the same pass

When an interview answer fills an empty or placeholder field, or contradicts one (for example
the grain answer against `measurement_granularity`), show the field and the proposed value
and write it only when the analyst agrees. Offer each correction once. If the analyst
corrects `approval_number`, the sidecar takes the corrected value.

Field ownership — write a field only where this table allows it:

| Field | Owner | This skill |
|---|---|---|
| `answers.intake.json` | Analyst | Writes all of it |
| `request_id` | Analyst | The enquiry number from the service-desk issue, as issued: `THHSRDLENQ-<n>`, no zero padding |
| `approval_number`, `governance_type` | Analyst | Asks under governance; writes after confirmation; keeps the sidecar's approval equal |
| `measurement_granularity` | Analyst | Sets it from the grain answer, never from a default |
| `short_title`, `project_title`, `project_description`, `delivery_outcomes`, `requestor_name`, `requestor_email` | Analyst | Fills from the enquiry, after confirmation |
| research text (`cohort_entry_event`, `inclusion_criteria`, `exclusion_criteria`, `requested_data_elements`, `ehr_sources`) | Analyst | Fills or corrects from answers, after confirmation. Itemising never edits it: a change to the text is a separate, confirmed edit, made before fingerprinting |
| `license`, `platform`, `include_*`, `use_*`, `framework_ref`, `engineering_reviewers` | Engineer / defaults | Never changes them; shows them before the render |

A `request-template` copy holds a short form without most of these fields: add them. The
rendered project's validator requires every field in the first five rows, and copier
renders a missing one as its placeholder text. `measurement_granularity` is blank in the
seed: map the grain answer to `Patient`, `Admission`, `Encounter` or `Observation`. If no
choice fits the clinical unit, ask which to use and keep the exact unit in the sidecar.

## Render the scaffold (after approval)

A `request-template` copy is a thin seed. Rendering the scaffold over it gives the project
its pipeline, validator and DVC layout, which a supplied cohort needs. Render once, after the
sidecar validates, and only when the analyst approves.

1. Skip this section when `.copier-answers.yml` already records `nq-rdl/data-analysis-scaffold`:
   the project is rendered. A later answers change goes to the engineer as `copier update`.
2. Follow `${CLAUDE_PLUGIN_ROOT}/skills/setup/references/scaffold-render.rst`. It is the one
   render procedure, shared with triage. It probes the tools, lists the tags again just before
   you ask (v0.5.1 or later, never a branch), and passes `framework_ref`, `seed_mode=no` and
   `project_slug` with `--data`, so no seed answer decides them. It uses `copier copy`, not
   `recopy` or `update`, because the seed names the retired `data-science-template`.
3. Show the analyst the command, the tag and the explicit values, and ask for approval. The
   approval covers committing `answers.yaml` and the sidecar on a branch first.
4. Check the result as that reference says: `answers.yaml` and `answers.intake.json` unchanged,
   `.copier-answers.yml` naming the scaffold, the tag and the passed values, and the seed's
   `.github/workflows/` files unchanged. If the rendered `scripts/` has no `analyst_intake.py`,
   report that the sidecar was not validated.
5. Commit the render only when the analyst asks. Re-locking pixi is its own commit. `pixi run
   setup` (DVC remote and credentials) is the analyst's or engineer's, on the VM; do not run it.

## A cohort supplied by the requester

When the requester supplies the cohort (a file of participants), record a `cohort` decision
that describes it by shape only: who supplies it, its columns, an approximate row count and
any instalments. Never ask for, open, read, copy or print the file: it holds identifiers.
After the render, give the analyst these steps to run on the VM: `pixi run setup` if the DVC
remote is not set, place the file under `data/00_raw/`, `dvc add` it, `dvc push`, and commit
only the `.dvc` pointer. The engineer declares the cohort with query-builder's supplied-cohort
support and joins to it; name the file and its `.dvc` pointer in the hand-off.

The runner loads the file into a `#<table>` temp table at run time, so the SQL never holds a value.
Keep every value out of the sidecar, `answers.yaml`, the hand-off, issues and chat: if the requester
pastes identifiers into the thread, do not repeat them. Never read anything under `data/00_raw/`; the
plugin guard denies `Read` there (not `.dvc` pointers) and denies `Grep` and `Glob` rooted there or above it, beside a scaffold child's own `Read(/data/**)` deny. See
`${CLAUDE_PLUGIN_ROOT}/skills/guardrails/references/supplied-cohorts.rst`.

## Write and validate

Write `answers.intake.json` as one complete document (`approval_number`, `decisions`,
`open_questions`; `open_questions` may be empty). Without confirmed criteria, write
`schemaVersion: 1`. With them, add `criteria` and `fingerprints` and write `schemaVersion: 2`,
but only after confirming the installed `validate-answers` accepts schema 2: an older release
reports `intake.schemaVersion`. If it does not and no schema 2 sidecar exists, write schema 1 without `criteria` and tell the
analyst the scaffold release is needed. If a schema 2 sidecar already exists, keep it as is,
write nothing and stop: report that the validator needs upgrading. Never downgrade a sidecar
or drop its confirmed criteria.

If `answers.yaml` does not parse (`yaml.safe_load`), show the analyst the line and column, propose a
repair and write it only after they confirm it. Repair before you fingerprint.

Fingerprints record the free text the itemisation was made from. After writing `answers.yaml`,
and before writing the new sidecar, run `validate-answers answers.yaml --fingerprints` on a copy of `answers.yaml` in a new temporary directory with no sidecar beside it,
which prints one JSON object, and store the JSON as `fingerprints`:

```bash
T="$(mktemp -d)"; cp answers.yaml "$T/answers.yaml"
data-analysis-scaffold validate-answers "$T/answers.yaml" --fingerprints
# in a generated child: pixi run python scripts/validate_answers.py "$T/answers.yaml" --fingerprints
```

The command validates a sibling sidecar too; the copy has none, so only the answers are validated.
In place, the old sidecar could fail it (a changed `approval_number` on a re-run, or `criteria`
without `fingerprints`) and print nothing. Remove the directory afterwards. Never compute a
fingerprint by hand. If the command is not available, apply the same rule: write schema 1 only
when no schema 2 sidecar exists, otherwise keep it as is, stop and report that the validator
needs upgrading.

After writing the sidecar, run `validate-answers answers.yaml` in place, which validates the new sidecar
with the answers. On failure, fix the named fields and run it again; do not hand over
an invalid sidecar. A warning that the free text changed since itemisation means a later edit
to the four answers: re-run this pass. When the sidecar validates, delete
`answers.intake.draft.json`.

## Re-run: walk what changed

When `answers.intake.json` exists (or `--update`):

1. Run the validation and read the sidecar. Read `git log -p -- answers.intake.json
   answers.yaml` when tracked, and the current enquiry, to find what moved since the last pass.
2. Keep an unchanged decision or criterion verbatim: its `confirmed_by`, `confirmed_at` and
   `decided` stay as recorded. Do not re-stamp it.
3. Walk only decisions that the new evidence touches (confirm / reword / remove) and new
   topics. A reworded decision gets the analyst's new confirmation. A knock-on edit to
   another decision (a finer output's wording that the new answer contradicts) is a
   proposal too: put it to the analyst. Until they answer, keep that decision verbatim and
   name the conflict in the hand-off; never re-stamp it with this run's time. Keep its `id` when the
   decision is the same one in new words; use a new `id` for a different decision.
4. Criteria: compare the four free-text answers with the live criteria (those without
   `withdrawn`). Never renumber, and never reuse an `id`: a new item takes the next number of its
   kind, counting withdrawn ones. For each wording change, ask the analyst to classify it; do
   not guess. A rewording (same meaning) keeps the `id`, with the new `text` and a fresh
   confirmation. A change of meaning withdraws the old criterion (a `reason`, a date and
   `replaced_by` naming the new `id`) and adds the new one. An item the researcher dropped is
   withdrawn without `replaced_by`. Keep withdrawn entries. Until the analyst answers, keep the
   criterion verbatim and name it in the hand-off. Then refresh `fingerprints` as above.
5. Move an open question into `decisions` only with the analyst's answer. Remove a question
   only when it is answered or the analyst withdraws it — say which.
6. If `.sqlreview/reviews/*/scope.json` holds `A-intake-<id>` items, the engineer has already
   imported the intake. Name each changed or removed `id` in the hand-off: bootstrap routes
   them as changed analyst decisions on its next run. Name each reworded, withdrawn or new
   criterion `id` too.

## Hand over

Show the analyst a short note for the engineer:

- the branch, the two file paths, the scaffold tag rendered (or why not), and the validation
  result (which validator ran, and whether it covered the sidecar);
- for a supplied cohort, the file's `.dvc` pointer path, or that it is still to come;
- the decisions by topic, the grain (`one row per <unit>`) and finer outputs;
- the criteria by kind (ids only), any withdrawn or reworded since the last pass, and whether
  `fingerprints` were recorded;
- the open questions that wait on the requester;
- any technical notes the analyst volunteered;
- next: the engineer runs `/data-request:setup` (if `.sqlreview/` is absent), then
  `/data-request:bootstrap <intended sql path>`, which imports these decisions with the
  analyst's confirmation and asks the engineer only about what the sidecar leaves open.

Commit or push only when the analyst asks.
