.. SPDX-License-Identifier: Apache-2.0
.. Derived from openai/codex-plugin-cc v1.0.6 (db52e28), Apache-2.0. Modified for rdl-agent-extensions.

Codex Prompt Anti-Patterns
==========================

Avoid these when prompting Codex or GPT-5.6.

Vague task framing
------------------

Bad::

    Take a look at this and let me know what you think.

Better:

.. code-block:: xml

    <task>
    Review this change for material correctness and regression risks.
    </task>

Missing output contract
-----------------------

Bad::

    Investigate and report back.

Better:

.. code-block:: xml

    <structured_output_contract>
    Return:
    1. root cause
    2. evidence
    3. smallest safe next step
    </structured_output_contract>

No autonomy policy
------------------

Bad::

    Debug this failure.

Better:

.. code-block:: xml

    <autonomy_policy>
    Keep going until you have enough evidence to identify the root cause confidently.
    Stop only for a missing detail that changes correctness, safety, or an irreversible action.
    </autonomy_policy>

Asking for more reasoning instead of a better contract
------------------------------------------------------

Bad::

    Think harder and be very smart.

Better:

.. code-block:: xml

    <verification_loop>
    Before finalizing, verify that the answer matches the observed evidence and task requirements.
    </verification_loop>

Mixing unrelated jobs into one run
----------------------------------

Bad::

    Review this diff, fix the bug you find, update the docs, and suggest a roadmap.

Better:

- Run review first.
- Run a separate fix prompt if needed.
- Use a third run for docs or roadmap work.

Unsupported certainty
---------------------

Bad::

    Tell me exactly why production failed.

Better:

.. code-block:: xml

    <grounding_rules>
    Ground every claim in the provided context or tool outputs.
    If a point is an inference, label it clearly.
    </grounding_rules>

5.6-specific: repeating the same instruction
--------------------------------------------

5.6 follows a single clear instruction. Restating the same rule two or three
times (in the system prompt, the task block, and again at the end) degrades
quality and burns tokens. State it once.

Bad::

    Be thorough. ... Remember to be thorough. ... Above all, be thorough.

Better: say it once, and put any non-negotiable in exactly one place.

5.6-specific: scattered "ask first" lines
-----------------------------------------

Multiple "check with me before X" instructions make a proactive 5.6 model
over-ask and stall. Consolidate into one ``<autonomy_policy>`` block that states
both the proceed-by-default behavior and the narrow set of stop conditions.

5.6-specific: steering length with prose
----------------------------------------

Do not push length or terseness through repeated prose instructions. Set
``text.verbosity`` (and reasoning effort) at the API/CLI level; keep the prompt
body focused on the task and its output contract.
