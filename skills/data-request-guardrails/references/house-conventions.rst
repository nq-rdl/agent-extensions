House conventions
=================

Read this at bootstrap and before drafting. Ask the engineer for any item below that the
scope, the child repository or a recorded decision does not already settle. Ask once, up
front, and record the answer in the scope. Do not wait for a late correction.

Who owns which decision
-----------------------

* The analyst owns cohort decisions. These include which wards, locations and facility
  sets define the cohort, the population, the window and every requester-defined
  measure. Never record one as an engineer decision.
* The engineer owns technical decisions. These include source choice, joins, column
  naming, read isolation and the form of UAT. Proceed on an evidenced choice and flag it
  for the analyst, as ``decision-authority.rst`` describes.
* Ask who owns a point before you write it as an open question. A requester question is
  an analyst question, even when it is deferred to bootstrap.
* A technical value that only the engineer can supply is engineer input. Ask for it. Do
  not record it as an analyst clarification.
* When you cite a rule, quote the file and the line. Keep your own recommendation
  separate from the rule, and label it as a recommendation. A runbook note is not a rule.

Read isolation
--------------

Read isolation is an engineer and DBA decision. Do not state a default as policy. Ask
the engineer which level the run uses, then record the answer in the scope and as an
assumption at the affected logic. The mechanics are in ``performance.rst``.

Naming and locations
--------------------

* Delivered column names follow the engineer's house style, not the source names. Ask
  for the style when the repository does not state it, and apply it in the final rename.
* Request SQL lives at ``sql/v<N>/<name>_request.sql``. The suffix matters because the
  runner discovers files by it.
* Probes live in the scaffold's probe location, not in the extract runner. A probe
  never runs through the extract runner.
* A UAT check is a script that returns a verdict. It is not a prose list of counts.

Tests and pushes
----------------

* Child tests that import the child's source live in ``tests_framework/``. The
  ``tests/`` folder holds the offline suite, which must run with the standard library.
* Run both suites before every push: the unit suite in ``tests/`` and the framework
  suite in ``tests_framework/``. Never push with a test red or leave a known red test
  for hand-off.
* Prefer structural asserts, such as a parsed SQL tree, over exact SQL strings. A
  re-pin can change quoting and temp-table names without any change in logic.
* Give each new module constant a name that no existing variable uses.
