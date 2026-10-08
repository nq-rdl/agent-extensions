---
name: intake
license: CC-BY-4.0
description: Interview the Data Analyst on the research decisions of a data request
  — cohort and age limits, code-set edges, outcomes and windows, identifiers and presentation,
  governance and the grain — and write answers.intake.json (schema 1) in the same
  pass that fills answers.yaml. Needs no .sqlreview/. Re-running walks through what
  changed. Use before the engineer's $data-request:bootstrap, whenever an analyst
  fills or revises answers.yaml.
compatibility: answers.intake.json schemaVersion 1, validated by data-analysis-scaffold
  validate-answers or a generated child's scripts/validate_answers.py. Python 3 optional
  (validation only).
metadata:
  repo: https://github.com/nq-rdl/agent-extensions
---

## Codex execution

Before shell examples, set PLUGIN_ROOT to the absolute installed plugin directory: two parent directories above this SKILL.md’s containing skill directory. Derive it from the loaded file path, never the working directory. This variable is not automatically supplied to ordinary shell tools. Quote it in commands.

Here $ARGUMENTS means the user’s supplied skill arguments. Codex does not populate a shell variable for them. Pass arguments with shell quoting that preserves literal text; never evaluate user text as shell code.

# Data Request — intake (Data Analyst)

The **Data Analyst** runs this pass while filling `answers.yaml`, before the Data Engineer
starts. The analyst has the requester's knowledge: what the research needs. The engineer has
the systems knowledge: which sources, keys and joins deliver it. This skill is the analyst's
interview; `$data-request:bootstrap` is the engineer's. It is not a separate stage: it is the
`answers.yaml` filling pass, guided.

Arguments: `$ARGUMENTS` — the answers file (default `answers.yaml` at the repository root).
The sidecar is always its sibling `answers.intake.json`.

Read `${PLUGIN_ROOT}/skills/setup/references/analyst-intake.rst` first. It is the
schema contract shared with `validate-answers`; this skill does not restate it. Writes are
limited to `answers.yaml` and `answers.intake.json`. Never write `.sqlreview/`, `scope.json`
or SQL, and do not require `$data-request:setup`: the engineer runs it later.

## Validate before and after

```bash
pixi run python scripts/validate_answers.py answers.yaml    # generated child
data-analysis-scaffold validate-answers answers.yaml        # otherwise, when installed
```

Run one before the interview (an existing sidecar can already be invalid) and again after
every write. Both validate the sibling sidecar too. Diagnostics name fields, never values.
If neither command is available, say that validation did not run; never report a pass.

## Gather the evidence

Read `answers.yaml`, the enquiry (service-desk issue, intake form, requester comments) and the
governance approval when the analyst supplies them. Draft each proposed decision from that
wording and cite where it came from in `rationale`. The analyst's answer is the confirmation;
a draft built from request text is only a proposal until they answer.

## The interview

Ask about research decisions only, in this order. Each topic maps to a schema `topic`:

1. **cohort** — the cohort in clinical terms; age limits with their anchor (age at index event
   differs from age today); sex; inclusions and exclusions. Facility: when the request is silent
   or names TUH, the engineer imports the TUH house default — do not ask. Record a facility
   decision only when the request names a different facility set.
2. **codes** — each code set, its edges and edition (which subcodes count, whether a category
   includes its children). For code discovery run `$data-request:lookup`, and cite its record
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

Put proposals to the analyst with the host user-question tool, at most four per call, one question per
decision. Show the proposed `text` **and** `rationale` — both are recorded. Options:
**Confirm (Recommended)** / **Reword** / **Leave open**. A reworded decision is asked again
in its new words. **Leave open** becomes an `open_questions` entry phrased for the requester,
with the proposed reading noted. Batch the open questions so the analyst can send them to the
requester in one message.

Stay out of the engineer's lane. Do not ask about source tables, joins, keys, timezones,
validity rules or SQL. If the analyst volunteers one, keep it for the hand-off note; do not
record it as a decision. Prior SQL or delivery can support a proposal, but only the analyst's
answer confirms it.

## Recording a decision

- `confirmed_by` is the analyst's handle: GitHub login when known, else
  `git config user.name`, else ask. Never an email, and never the agent's identity.
- `confirmed_at` is the UTC time of the analyst's answer (`YYYY-MM-DDTHH:MM:SSZ`).
- `decided` only when the evidence names who made the decision (for example a requester's
  dated reply); omit it otherwise. Never infer a decider or date from prose.
- `approval_number` matches `answers.yaml` exactly.
- No identifiable patient data, and no lookup counts, in either file.

With no human to answer (a non-interactive run), confirm nothing: every proposal goes to
`open_questions`. A partial intake is valid; an invented confirmation is not.

## Fill `answers.yaml` in the same pass

When an interview answer fills an empty or placeholder field, or contradicts one (for example
the grain answer against `measurement_granularity`), show the field and the proposed value
and write it only when the analyst agrees. Offer each correction once. If the analyst
corrects `approval_number`, the sidecar takes the corrected value.

## Write and validate

Write `answers.intake.json` as one complete document (`schemaVersion: 1`, `approval_number`,
`decisions`, `open_questions`; `open_questions` may be empty). Run the validation above. On
failure, fix the named fields and run it again; do not hand over an invalid sidecar.

## Re-run: walk what changed

When `answers.intake.json` exists (or `--update`):

1. Run the validation and read the sidecar. Read `git log -p -- answers.intake.json
   answers.yaml` when tracked, and the current enquiry, to find what moved since the last pass.
2. Keep an unchanged decision verbatim: its `confirmed_by`, `confirmed_at` and `decided`
   stay as recorded. Do not re-stamp it.
3. Walk only decisions that the new evidence touches (confirm / reword / remove) and new
   topics. A reworded decision gets the analyst's new confirmation. A knock-on edit to
   another decision (a finer output's wording that the new answer contradicts) is a
   proposal too: put it to the analyst. Until they answer, keep that decision verbatim and
   name the conflict in the hand-off; never re-stamp it with this run's time. Keep its `id` when the
   decision is the same one in new words; use a new `id` for a different decision.
4. Move an open question into `decisions` only with the analyst's answer. Remove a question
   only when it is answered or the analyst withdraws it — say which.
5. If `.sqlreview/reviews/*/scope.json` holds `A-intake-<id>` items, the engineer has already
   imported the intake. Name each changed or removed `id` in the hand-off: bootstrap routes
   them as changed analyst decisions on its next run.

## Hand over

Show the analyst a short note for the engineer:

- the branch and the two file paths, and the validation result;
- the decisions by topic, the grain (`one row per <unit>`) and finer outputs;
- the open questions that wait on the requester;
- any technical notes the analyst volunteered;
- next: the engineer runs `$data-request:setup` (if `.sqlreview/` is absent), then
  `$data-request:bootstrap <intended sql path>`, which imports these decisions with the
  analyst's confirmation and asks the engineer only about what the sidecar leaves open.

Commit or push only when the analyst asks.
