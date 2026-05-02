Orchestration Examples
======================

Worked examples showing how the orchestrator drives TDD cycles. All
examples use ``claude:subagent`` as the default backend. For other
backends, use the ``dispatch`` skill to determine routing.

--------------

Example 1: All-Claude (Default)
-------------------------------

The simplest configuration — every phase uses Claude Code subagents.

Orchestrator actions
~~~~~~~~~~~~~~~~~~~~

::

   User: "Implement a calculator with add, subtract, multiply, divide. Raise ValueError for division by zero."

   1. Agent tool → subagent_type: tdd-red-team
      prompt: |
        FEATURE: Implement a calculator with add, subtract, multiply, divide. Raise ValueError for division by zero.
        TEST FILE: /abs/path/tests/test_calculator.py
        IMPL FILE: /abs/path/src/calculator.py
        LANGUAGE: python
        FRAMEWORK: pytest
        Write failing tests for this feature.

      → Subagent writes tests → returns DONE|red

   2. Run: pytest tests/test_calculator.py
      → Confirms tests FAIL

   3. Agent tool → subagent_type: tdd-green-team
      prompt: |
        FEATURE: ...
        TEST FILE: ...
        Write the simplest implementation that makes the tests pass.

      → Subagent writes implementation → returns DONE|green

   4. Run: pytest tests/test_calculator.py
      → Confirms tests PASS

   5. Agent tool → subagent_type: tdd-refactor
      prompt: |
        FEATURE: ...
        Refactor the implementation for clarity and quality.

      → Subagent refactors → returns DONE|refactor

   6. Run: pytest tests/test_calculator.py
      → Confirms tests still PASS

   7. Agent tool → subagent_type: tdd-reviewer
      prompt: |
        FEATURE: ...
        TEST RESULTS: 4 passed
        CYCLES: 1/3
        Review this TDD cycle.

      → Reviewer returns APPROVED|review

   8. Run: tdd-archive.sh calculator
      Orchestrator reports: "TDD cycle complete. Feature approved."

--------------

Example 2: Parallel Red-Phase Fan-Out (agent-team)
--------------------------------------------------

Use ``claude:agent-team`` for the red phase to dispatch multiple
features simultaneously.

When to use
~~~~~~~~~~~

- You need tests for multiple independent features at the same time
- Each feature gets an isolated context window (no cross-contamination)

.. _orchestrator-actions-1:

Orchestrator actions
~~~~~~~~~~~~~~~~~~~~

::

   # Start team once for the session
   TeamCreate(name="tdd-session")

   # Dispatch 3 red phases in parallel
   SendMessage(to="tdd-calculator-red", message=<calculator red phase input>)
   SendMessage(to="tdd-url-shortener-red", message=<url-shortener red phase input>)
   SendMessage(to="tdd-rate-limiter-red", message=<rate-limiter red phase input>)

   # As each completes, extract status token from response and continue
   # with claude:subagent for green/refactor/review (sequential per feature)

--------------

Example 3: Mixed Backend via dispatch skill
-------------------------------------------

If you have ``jules``, ``gemini-cli``, or ``pi-rpc`` installed, load the
``dispatch`` skill to determine how to route phases to external
backends. The dispatch skill handles session lifecycle — you just pass
the uniform phase input format and receive the status token.

--------------

Error Handling
--------------

Backend returns ERROR
~~~~~~~~~~~~~~~~~~~~~

::

   Backend returns: ERROR|red|Could not determine test framework

   Action:
     - Report the error
     - Ask user if they want to retry or adjust the input

Unrecognized output token
~~~~~~~~~~~~~~~~~~~~~~~~~

::

   Backend returns unrecognized output (no valid status token)

   Action:
     - Re-invoke the backend with a reminder:
       PREVIOUS ATTEMPT: You did not return a valid status token. End your response with one of:
         DONE|<phase>, APPROVED|review, REQUEST_CHANGES|review|<reason>, ERROR|<phase>|<reason>
     - Retry once; if still unrecognized, pause and show raw output to user

Tests don’t fail after red phase
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

::

   pytest → all tests PASS (should have failed)

   Action:
     - Re-invoke red-team with:
       PREVIOUS ATTEMPT: Tests passed trivially — they must FAIL against an empty stub.
       Do not implement the logic in the test file.
     - Retry once; if tests still pass, pause and ask user to review

Tests don’t pass after green phase
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

::

   pytest → 2 of 5 tests FAIL

   Action:
     - Re-invoke green-team with the failure output:
       CURRENT TEST FAILURES:
       <paste pytest output>
       <original prompt>

Reviewer requests changes
~~~~~~~~~~~~~~~~~~~~~~~~~

::

   Reviewer returns: REQUEST_CHANGES|review|Missing test for empty input case

   Action:
     - Increment cycle counter, reset to red phase
     - Include reviewer feedback in the next red-team prompt:
       REVIEWER FEEDBACK: Missing test for empty input case
       CYCLES: 2/3
       <original prompt>

Cycle cap reached
~~~~~~~~~~~~~~~~~

::

   Cycle 3 completes without APPROVED

   Action:
     - Pause and ask: "3 cycles completed without approval. Continue (4+), switch backend, or abort?"
     - If continue: reset cycle cap in config and resume
     - If abort: run tdd-cancel.sh <slug>
