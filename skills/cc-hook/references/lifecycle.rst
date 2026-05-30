Hook Lifecycle
==============

Source: https://code.claude.com/docs/en/hooks (Hooks reference) and
https://code.claude.com/docs/en/hooks-guide#how-hooks-work

Understanding *when* each event fires — and whether it can block — is the single
most important thing for writing correct hooks. Events are grouped by where they
sit in Claude Code's lifecycle.

--------------

Firing order
------------

Session-level (once per session)
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

- ``Setup`` — started with ``--init-only``, or ``--init`` / ``--maintenance``
  in ``-p`` mode. For one-time CI / script preparation.
- ``SessionStart`` — a session begins or resumes (matcher: ``startup``,
  ``resume``, ``clear``, ``compact``).
- ``SessionEnd`` — a session terminates.

Turn-level (once per turn)
~~~~~~~~~~~~~~~~~~~~~~~~~~~

- ``UserPromptSubmit`` — you submit a prompt, *before* Claude processes it.
- ``UserPromptExpansion`` — a typed command expands into a prompt, before it
  reaches Claude. Can block the expansion.
- ``Stop`` — Claude finishes responding. Fires whenever Claude finishes, **not
  only at task completion**, and **not** on user interrupts.
- ``StopFailure`` — the turn ends due to an API error. Output and exit code are
  ignored.

Agentic loop (per tool call)
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

- ``PreToolUse`` — before a tool call executes. **Can block.**
- ``PermissionRequest`` — a permission dialog is about to appear. (Does **not**
  fire in non-interactive ``-p`` mode — use ``PreToolUse`` there.)
- ``PermissionDenied`` — a tool call was denied by the auto-mode classifier.
- ``PostToolUse`` — after a tool call succeeds.
- ``PostToolUseFailure`` — after a tool call fails.
- ``PostToolBatch`` — after a full batch of parallel tool calls resolves,
  before the next model call.
- ``SubagentStart`` / ``SubagentStop`` — a subagent is spawned / finishes.
- ``TaskCreated`` / ``TaskCompleted`` — a task is created / marked complete.

Async / reactive events
~~~~~~~~~~~~~~~~~~~~~~~~

- ``Notification`` — Claude Code sends a notification.
- ``MessageDisplay`` — while assistant message text is displayed.
- ``TeammateIdle`` — an agent-team teammate is about to go idle.
- ``InstructionsLoaded`` — a CLAUDE.md / ``.claude/rules/*.md`` file is loaded
  (at session start and lazily during a session).
- ``ConfigChange`` — a configuration file changes during a session.
- ``CwdChanged`` — the working directory changes (e.g. Claude runs ``cd``).
- ``FileChanged`` — a watched file changes on disk.
- ``WorktreeCreate`` / ``WorktreeRemove`` — a worktree is created / removed.
- ``PreCompact`` / ``PostCompact`` — before / after context compaction.
- ``Elicitation`` / ``ElicitationResult`` — an MCP server requests user input /
  the user responds.

--------------

Which events can block (exit code 2)
-------------------------------------

Exit code ``2`` blocks where supported; elsewhere stderr is shown but execution
continues (https://code.claude.com/docs/en/hooks#exit-code-2-behavior-per-event):

================================ ======== =================================================
Event                            Blocks?  Effect of a block
================================ ======== =================================================
``PreToolUse``                   Yes      Blocks the tool call
``PermissionRequest``            Yes      Denies permission
``UserPromptSubmit``             Yes      Blocks the prompt, erases it
``UserPromptExpansion``          Yes      Blocks the expansion
``Stop``                         Yes      Prevents stopping; conversation continues
``SubagentStop``                 Yes      Prevents the subagent from stopping
``TeammateIdle``                 Yes      Prevents the teammate from going idle
``TaskCreated``                  Yes      Rolls back task creation
``TaskCompleted``                Yes      Prevents completion
``ConfigChange``                 Yes      Blocks the config change
``PreCompact``                   Yes      Blocks compaction
``WorktreeCreate``               Yes      Fails worktree creation (any non-zero exit)
``Elicitation``                  Yes      Denies the elicitation
``ElicitationResult``            Yes      Blocks the response
``PostToolBatch``                Yes      Stops the agentic loop before the next model call
``PostToolUse``                  No       Shows stderr to Claude (tool already ran)
``PostToolUseFailure``           No       Shows stderr to Claude
``PermissionDenied``             No       Ignored — use JSON ``{"retry": true}`` instead
``SessionStart`` / ``Setup`` /   No       Shows stderr to the user only
``Notification`` / others
================================ ======== =================================================

.. important::

   ``PreToolUse`` hooks fire **before** any permission-mode check. A hook
   returning ``permissionDecision: "deny"`` blocks the tool even in
   ``bypassPermissions`` mode or under ``--dangerously-skip-permissions``. The
   reverse is not true: returning ``"allow"`` does **not** override deny rules
   from settings. Hooks can tighten, never loosen, permission rules.

--------------

Stop hooks: the block cap
-------------------------

``Stop`` (and ``SubagentStop``) hooks can keep Claude working by blocking. To
avoid infinite loops, Claude Code **overrides a Stop hook after it blocks 8
times in a row** without progress. A correct Stop hook checks the
``stop_hook_active`` input field and exits early when it is already ``true``:

.. code:: bash

   #!/bin/bash
   INPUT=$(cat)
   if [ "$(echo "$INPUT" | jq -r '.stop_hook_active')" = "true" ]; then
     exit 0   # allow Claude to stop
   fi
   # ... rest of your hook logic

Raise the cap with ``CLAUDE_CODE_STOP_HOOK_BLOCK_CAP``
(https://code.claude.com/docs/en/env-vars) if convergence legitimately needs
more iterations.

--------------

Limitations to keep in mind
---------------------------

- Command hooks talk only through stdout/stderr/exit codes; they cannot trigger
  ``/`` commands or tool calls. ``additionalContext`` is injected as a system
  reminder Claude reads as plain text (see ``references/prompt-injection.rst``).
- ``PostToolUse`` cannot undo an action — the tool already ran.
- When multiple ``PreToolUse`` hooks return ``updatedInput``, the last to finish
  wins, and order is non-deterministic. Avoid two hooks rewriting one tool's
  input.
