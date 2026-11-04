Send-back note
==============

The analyst's paste-ready note for **Send back**, shared by ``/data-request:explain``
and ``/data-request:release``. Add one finding block per change:

.. code-block:: text

   outcome: send-back
   run commit: <operator run SHA, or missing>
   finding: <F1: observed issue and affected files>
   expected result: <analyst's requested outcome; mark undecided meaning explicitly>
   classification: <logic or defect | presentation>
   route: </data-request:fix | /data-request:amend>
   evidence: <review item/revision, SQL lines, run QA or output schema; no row-level data>
   open gates: <unanswered decisions, governance restrictions and missing evidence>
   return to review: <refresh analyse, operator-run/UAT evidence and triage hand-off>
