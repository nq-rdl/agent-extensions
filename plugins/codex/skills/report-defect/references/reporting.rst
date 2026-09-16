Shared defect reporting procedure
=================================

Follow every gate below in order. The entrypoint supplies the installed
PLUGIN_ROOT and the user-selected defect ID. Shell-quote arguments literally.

Read the marker
---------------

.. code-block:: bash

   node "${PLUGIN_ROOT}/scripts/codex-defects.mjs" show --latest

If the user supplied a defect ID, pass that exact ID as one quoted argument to ``show`` instead of ``--latest``. To see what else is pending:

.. code-block:: bash

   node "${PLUGIN_ROOT}/scripts/codex-defects.mjs" list

Output is always JSON; ``--json`` is accepted but is a no-op. If the CLI exits non-zero with ``Defect marker not found.``, tell the user there is nothing to report and stop.

Decide on the verdict
---------------------

Branch on ``classification.verdict`` from the ``show`` payload:

- ``not-a-defect`` — a usage or environment problem, not a plugin bug. Show the user ``classification.cause`` and ``classification.remedy`` in plain language and STOP. Do not file anything. Only mark it handled with ``mark-reported`` if the user asks.
- ``candidate-defect`` — proceed to drafting. ``classification.cause`` is either ``unclassified`` or ``readiness-check-disagreement``; in the latter case the readiness check disagrees with the observed auth failure, and that disagreement is itself the headline of the report.
- ``needs-cross-check`` — the CLI resolves auth markers against a live readiness probe before emitting, so this must never appear. If it somehow does, treat it as ``candidate-defect`` and say so in the draft.

Privacy gate
------------

If the marker's ``homeScrubbed`` field is ``false``, the home directory could not be resolved, so ``message``, ``stderrTail``, and ``argv`` may still carry the user's username. Show the user the raw evidence verbatim and require an explicit confirmation before including any of it in a draft. Never file in this state without that confirmation.

Draft the issue
---------------

Never include tokens, credentials, private prompts, or full transcripts. Check
existing issues before proposing a new report.

Assemble a body from the marker after the privacy gate: ``id``, ``recordedAt``, ``surface``, ``argv`` (already redacted and home-scrubbed), ``exitCode``, ``message``, ``stderrTail``, ``environment`` (``node``, ``codex``, ``plugin``, ``platform``, ``release``, ``repo`` basename, ``isGitRepo``), and ``classification``.

Show the complete draft to the user and get approval before filing. Never file without showing the draft first.

File it
-------

On approval, save the exact approved body to a file, then run:

.. code-block:: bash

   gh issue create --repo nq-rdl/agent-extensions --title "<title>" --body-file "<draft-file>"

Only after successful publication, record the outcome so the hook stops nudging:

.. code-block:: bash

   node "${PLUGIN_ROOT}/scripts/codex-defects.mjs" mark-reported "<defect-id>" --url "<issue-url>"

If the user declines to file, ``mark-reported`` without ``--url`` still silences the nudge — offer that as the explicit opt-out.

Where the report lives
----------------------

The ``show`` payload's ``defectsDir`` is where an optional ``<id>.md`` write-up may be written alongside the marker.
