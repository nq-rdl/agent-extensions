Send-back note
==============

The analyst's paste-ready note for **Send back**, shared by ``/data-request:explain``
and ``/data-request:release``. Add one finding block per change:

.. code-block:: text

   outcome: send-back
   deliverable PR: <PR URL> at head <SHA>
   run commit: <operator run SHA, or missing>
   review: <slug> revision <n>, SQL fingerprint <hash>
   already resolved by the analyst: <requester answers, governance checks and decisions, with who and when, or "none">
   finding: <F1: observed issue>
   affected files: <maintained source, generated SQL to regenerate, runbook and UAT checklist>
   expected result: <the concrete value, column, rule or count the engineer must produce>
   waiting on: <"nothing", or the requester question with who asked it and when>
   classification: <logic or defect | presentation>
   route: </data-request:fix | /data-request:amend>
   evidence: <review item/revision, SQL lines, run QA or output schema; no row-level data>
   open gates: <governance restrictions and missing evidence>
   return to review: <refresh analyse, operator-run/UAT evidence and triage hand-off>

Completeness check
------------------

The note must let the engineer act without a reply that asks for more detail. Before you
present it, finish the analyst's share. Get answers the analyst can give now: the expected
result, the requester's words and the governance check. Then check each finding:

* ``expected result:`` is concrete. "Fix it" or "make it right" is not a result.
* ``affected files:`` names paths, not a description.
* ``evidence:`` names where the engineer looks: an item id, SQL lines or a QA output.
* A meaning that only the requester can decide goes in ``waiting on:``, with the requester
  question. Offer to draft that question for the analyst. The engineer starts that finding
  only after the analyst posts the answer on the PR.

Fill each gap from the walkthrough, or ask the analyst now. Never leave a gap for the
engineer to ask about later.
