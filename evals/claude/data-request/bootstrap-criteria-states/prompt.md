---
description: Bootstrap records a state for every criterion and never records researcher-applies without applied_by on the sidecar
tags:
- bootstrap
- criteria
runs: 3
max_turns: 8
timeout_seconds: 300
allowed_tools:
- Read
- Glob
- Grep
- Skill
---

I am the Data Engineer (login eengineer) scoping the SQL for fictional ENQ9430, approval
THHSAQUIRE-9430, revision 1 of its scope. The analyst has finished the intake. This session has no
shell and cannot write files, so describe the states you would record instead of writing them.

answers.intake.json is schema 2. Its criteria are all confirmed by the analyst and none is withdrawn:

- N1, entry event: "Elective AAA repair admission"
- I1, inclusion: "Aged 65 and over"
- E1, exclusion: "Previous AAA repair" (no `applied_by`)
- E2, exclusion: "Died before the index admission" (`applied_by: rdl`)
- D1, data element: "Length of stay in days"
- D2, data element: "Admission datetime"
- D3, data element: "Discharge datetime"

What the ticket and the planned SQL say:

- The cohort is built from elective AAA repair admissions, and the SQL filters age 65 and over at
  admission.
- The requester says the researcher will remove the patients with a previous AAA repair themselves
  from the delivered extract (E1).
- The requester wants patients who died before the admission marked, not removed. The SQL delivers
  the flag as a 0/1 column named `died_before_admission` in the `cohort` output (E2).
- The SQL delivers the admission and discharge datetimes. The researcher computes the length of stay
  from them, and the SQL does not deliver it (D1).

Tell me the state each criterion would get.

End your reply with one fenced `yaml` block with exactly these top-level keys:

- `N1`, `I1`, `E2`, `D1`, `D2`, `D3`: the state recorded for that criterion
- `E1`: the state recorded for E1 in this revision
- `E2_flag`: the output and column that carry the E2 flag, as `<output>.<column>`
- `D1_reason_inputs`: the ids of the criteria that the D1 reason names as delivered inputs, comma-separated with no spaces
- `analyst_question`: `yes` when you raise an `Analyst question:` for the analyst, otherwise `no`
