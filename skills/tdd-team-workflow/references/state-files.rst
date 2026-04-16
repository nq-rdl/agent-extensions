State Files Reference (``.tdd/`` Directory)
===========================================

The ``.tdd/`` directory tracks TDD cycle progress, phase history, and
test results. It lives at the **project root** (not in the skill
directory).

Directory Structure
-------------------

::

   <project-root>/
     .tdd/
       config.yaml                    # project-level TDD configuration
       active/
         <feature-slug>.yaml          # one file per active TDD cycle
       archive/
         <feature-slug>-c<N>.yaml     # completed/closed cycles
       .gitignore                     # ignores archive/

- **One file per feature** avoids merge conflicts with concurrent
  features
- **``archive/``** preserves history for debugging; gitignored to keep
  repo clean
- **``active/`` is git-tracked** intentionally — gives team members
  visibility into in-progress TDD cycles. Add ``.tdd/active/`` to your
  project’s ``.gitignore`` for local-only state.

Feature Slug Rules
------------------

The slug is derived from the feature description:

- Lowercase, hyphen-separated words
- Length between 2 and 40 characters
- Must match regex: ``^[a-z0-9]([a-z0-9-]*[a-z0-9])?$``
- First few meaningful words of the feature description
- No special characters — alphanumeric and hyphens only

Examples:

+--------------------------------------------+-----------------------------------+
| Feature description                        | Slug                              |
+============================================+===================================+
| ``fizzbuzz(n): Fizz for 3, Buzz for 5``    | ``fizzbuzz``                      |
+--------------------------------------------+-----------------------------------+
| ``Health check endpoint returning 200 OK`` | ``health-check-endpoint``         |
+--------------------------------------------+-----------------------------------+
| ``User authentication with JWT tokens``    | ``user-auth-jwt``                 |
+--------------------------------------------+-----------------------------------+
| ``CSV parser with pipe delimiter support`` | ``csv-parser-pipe-delimiter``     |
+--------------------------------------------+-----------------------------------+

--------------

Config Schema: ``.tdd/config.yaml``
-----------------------------------

.. code:: yaml

   state_tracking: true
   test_command: "pytest -x"
   max_cycles: 3
   backends:
     red: "claude:subagent"
     green: "claude:subagent"
     refactor: "claude:subagent"
     review: "claude:subagent"

Field Reference
~~~~~~~~~~~~~~~

+--------------------+---------------+-----------------------------------+
| Field              | Type          | Description                       |
+====================+===============+===================================+
| ``state_tracking`` | bool          | Whether to write state files to   |
|                    |               | ``.tdd/``. Defaults to ``true``.  |
+--------------------+---------------+-----------------------------------+
| ``test_command``   | string        | Command to run tests. Defaults to |
|                    |               | auto-detecting based on project   |
|                    |               | language.                         |
+--------------------+---------------+-----------------------------------+
| ``max_cycles``     | int           | Maximum number of TDD cycles      |
|                    |               | before giving up (range: 1-10).   |
|                    |               | Defaults to 3.                    |
+--------------------+---------------+-----------------------------------+
| ``backends``       | object        | Map of phase (``red``, ``green``, |
|                    |               | ``refactor``, ``review``) to      |
|                    |               | backend strings. Supported:       |
|                    |               | ``claude:subagent``,              |
|                    |               | ``claude:agent-team``, or any     |
|                    |               | backend name supported by the     |
|                    |               | ``dispatch`` skill.               |
+--------------------+---------------+-----------------------------------+

--------------

Feature Cycle Schema: ``.tdd/active/<slug>.yaml``
-------------------------------------------------

.. code:: yaml

   feature: "fizzbuzz(n): Fizz for 3, Buzz for 5, FizzBuzz for both, number otherwise"
   test_file: /home/user/project/tests/test_fizzbuzz.py
   impl_file: /home/user/project/src/fizzbuzz.py
   language: python
   framework: pytest

   cycle: 1
   phase: green          # current phase: red | green | refactor | review | done | cancelled

   phases:
     - phase: red
       backend: "claude:subagent"
       started: "2026-03-15T10:00:00Z"
       ended: "2026-03-15T10:01:23Z"
       status: DONE
       reason: null
       test_summary: "5 collected, 5 failed"

     - phase: green
       backend: "claude:subagent"
       started: "2026-03-15T10:02:00Z"
       ended: null
       status: null
       reason: null
       test_summary: null

   created: "2026-03-15T10:00:00Z"
   updated: "2026-03-15T10:02:00Z"

.. _field-reference-1:

Field Reference
~~~~~~~~~~~~~~~

+------------------+---------------+-----------------------------------+
| Field            | Type          | Description                       |
+==================+===============+===================================+
| ``feature``      | string        | Full feature description (quoted) |
+------------------+---------------+-----------------------------------+
| ``test_file``    | path          | Absolute path to the test file    |
+------------------+---------------+-----------------------------------+
| ``impl_file``    | path          | Absolute path to the              |
|                  |               | implementation file               |
+------------------+---------------+-----------------------------------+
| ``language``     | string        | ``python``, ``typescript``,       |
|                  |               | ``go``, ``rust``, ``javascript``  |
+------------------+---------------+-----------------------------------+
| ``framework``    | string        | ``pytest``, ``jest``, ``vitest``, |
|                  |               | ``go test``, ``cargo test``       |
+------------------+---------------+-----------------------------------+
| ``cycle``        | int           | Current cycle number (starts at   |
|                  |               | 1, increments on                  |
|                  |               | ``REQUEST_CHANGES``)              |
+------------------+---------------+-----------------------------------+
| ``phase``        | string        | Current phase: ``red``,           |
|                  |               | ``green``, ``refactor``,          |
|                  |               | ``review``, ``done``,             |
|                  |               | ``cancelled``                     |
+------------------+---------------+-----------------------------------+
| ``phases``       | list          | History of all phase executions   |
+------------------+---------------+-----------------------------------+
| ``created``      | ISO 8601      | When the cycle was created        |
+------------------+---------------+-----------------------------------+
| ``updated``      | ISO 8601      | When the cycle was last modified  |
+------------------+---------------+-----------------------------------+

Phase Entry Fields
~~~~~~~~~~~~~~~~~~

+------------------+---------------+-----------------------------------+
| Field            | Type          | Description                       |
+==================+===============+===================================+
| ``phase``        | string        | ``red``, ``green``, ``refactor``, |
|                  |               | ``review``, ``cancelled``         |
+------------------+---------------+-----------------------------------+
| ``backend``      | string        | Backend used:                     |
|                  |               | ``claude:subagent``,              |
|                  |               | ``claude:agent-team``, or         |
|                  |               | dispatch backend name             |
+------------------+---------------+-----------------------------------+
| ``started``      | ISO 8601      | When the phase agent was invoked  |
+------------------+---------------+-----------------------------------+
| ``ended``        | ISO 8601 or   | When the agent completed (null if |
|                  | null          | in progress)                      |
+------------------+---------------+-----------------------------------+
| ``status``       | string or     | ``DONE``, ``APPROVED``,           |
|                  | null          | ``REQUEST_CHANGES``, ``ERROR``,   |
|                  |               | or null                           |
+------------------+---------------+-----------------------------------+
| ``reason``       | string or     | Reason from ``REQUEST_CHANGES``   |
|                  | null          | or ``ERROR`` status               |
+------------------+---------------+-----------------------------------+
| ``test_summary`` | string or     | One-line test runner output       |
|                  | null          | (e.g., “5 passed”, “3 failed, 2   |
|                  |               | passed”)                          |
+------------------+---------------+-----------------------------------+

--------------

State Lifecycle
---------------

+------------------------+-----------------+-----------------------------+
| Event                  | Who             | Action                      |
+========================+=================+=============================+
| User starts TDD cycle  | Orchestrator    | Run ``tdd-init.sh`` (if     |
|                        |                 | needed) + ``tdd-new.sh`` to |
|                        |                 | create                      |
|                        |                 | ``.tdd/active/<slug>.yaml`` |
+------------------------+-----------------+-----------------------------+
| Before invoking agent  | Orchestrator    | Append new entry to         |
|                        |                 | ``phases`` list with        |
|                        |                 | ``started`` timestamp       |
+------------------------+-----------------+-----------------------------+
| Agent completes        | Orchestrator    | Read agent status token,    |
|                        |                 | update ``phases[-1]`` with  |
|                        |                 | ``ended``, ``status``,      |
|                        |                 | ``reason``                  |
+------------------------+-----------------+-----------------------------+
| Tests run between      | Orchestrator    | Update                      |
| phases                 |                 | ``phases[-1].test_summary`` |
|                        |                 | with result                 |
+------------------------+-----------------+-----------------------------+
| Phase advances         | Orchestrator    | Set ``phase`` to next       |
|                        |                 | phase, update ``updated``   |
|                        |                 | timestamp                   |
+------------------------+-----------------+-----------------------------+
| ``REQUEST_CHANGES``    | Orchestrator    | Increment ``cycle``, set    |
|                        |                 | ``phase: red``, update      |
|                        |                 | ``updated``                 |
+------------------------+-----------------+-----------------------------+
| ``APPROVED``           | Orchestrator    | Set ``phase: done``, run    |
|                        |                 | ``tdd-archive.sh``          |
+------------------------+-----------------+-----------------------------+

--------------

State Ownership
---------------

- **Orchestrator writes**: All state creation and updates are done by
  the orchestrator
- **Agents read**: Phase agents can optionally read
  ``.tdd/active/<slug>.yaml`` for context
- **Agents never write state**: This keeps agents stateless
