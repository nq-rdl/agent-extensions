Archive a merged spec as ADRs
=============================

Read this when a feature spec has merged and its decisions should outlive the
spec directory. A spec-driven workflow such as GitHub Spec Kit often deletes the
directory or stops reading it after merge. The consent gate in SKILL.md applies
to every write here.

Prefer a dedicated command
--------------------------

If the project ships a command that archives specs into ADRs, offer it first.
An example is a speckit extension's finalize command; look for it in
``.specify/`` or the agent's command list. Keep the offer and consent here, and
let the command do the mechanics. Otherwise continue below.

Which decisions qualify
-----------------------

A spec is not an ADR. Most of it (user stories, tasks, test plans) stays with
the spec. Archive only the decisions that pass the skill's decision-moment test.
In Spec Kit these usually appear as:

- ``research.md`` entries in its ``Decision:`` / ``Rationale:`` /
  ``Alternatives considered:`` format. Each significant entry is a candidate
  record;
- ``plan.md`` Technical Context choices (language, storage, platform) that were
  argued rather than defaulted;
- ``plan.md`` Complexity Tracking rows, which justify a deviation from the
  project constitution;
- clarification answers in ``spec.md`` that closed off a design option.

One spec can yield zero, one or several records. List the candidates and let
the user pick before drafting.

Field mapping
-------------

======================== =====================================================
MADR field               Source in the spec directory
======================== =====================================================
Title                    The decision, not the feature name
Context and Problem      ``spec.md`` summary and the problem the feature
Statement                solves; link the spec and its PR
Decision Drivers         The requirements (FR-/NFR-) and success criteria
                         (SC-) that separated the options, and clarification
                         answers; cite their IDs
Considered Options       ``research.md`` *Decision* plus every *Alternatives
                         considered* entry
Decision Outcome         ``research.md`` *Decision* and *Rationale*, rewritten
                         so the ``because`` clause names a driver
Consequences             Rationale trade-offs, Complexity Tracking, known
                         risks in ``plan.md``
Confirmation             Contract tests, acceptance scenarios or success
                         criteria that verify the decision
Pros and Cons            Per-alternative reasons from ``research.md``; nothing
                         else
More Information         Spec and PR permalinks, merge commit, related ADRs
======================== =====================================================

A field the spec does not support gets ``Not recorded in the spec``. Never fill
it with plausible text. The status is ``accepted`` because the work merged. The
date is today. The original decision date goes in More Information as
"Decided in <spec path> (merged <date>); archived on <today>."

Permalinks
----------

The spec directory may be deleted after merge. Link it at the merge commit, not
at a branch:

.. code-block:: text

   https://github.com/<owner>/<repo>/tree/<merge-sha>/specs/<NNN-slug>

Find the merge commit with ``git log --diff-filter=A --format=%H -1 -- specs/<NNN-slug>``
on the main branch, or from the PR. If the repository has no forge URL, record
the commit SHA and path as plain text.

After archiving
---------------

Number, index and verify exactly as for any new record. Don't delete or edit the
spec directory; its lifecycle belongs to the spec workflow, not to this skill.
