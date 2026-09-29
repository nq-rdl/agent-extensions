Hook Output Contract
====================

Source: https://code.claude.com/docs/en/hooks (JSON output, decision control)
and https://code.claude.com/docs/en/hooks-guide#read-input-and-return-output

A hook reads event JSON on **stdin** and tells Claude Code what to do next
through **stdout** and its **exit code**. HTTP hooks use the response body in
place of stdout. This file is the canonical map of *what to print*.

--------------

Exit codes (command hooks)
--------------------------

===== ====================================================================
Code  Behavior
===== ====================================================================
0     No objection. stdout is parsed as JSON for structured control. For
      ``UserPromptSubmit``, ``UserPromptExpansion``, ``SessionStart``, and
      ``PostModelSwitch``, plain (non-JSON) stdout is added to Claude's
      context; for other events it goes to the debug log only.
2     Blocking error on events that can block. It blocks even if the JSON
      says ``allow``. Valid JSON on stdout is still read, and the blocking
      message is the JSON ``reason`` if present, otherwise stderr. Where the
      message goes is per event (``PreToolUse``: Claude; ``UserPromptSubmit``:
      the user only). ``PermissionRequest`` ignores exit 2. See the table in
      ``references/lifecycle.rst``.
other Without valid JSON: non-blocking error. Transcript shows ``<hook> hook
      error`` plus the first stderr line; the action proceeds, even on
      exit 1. With valid decision JSON, the JSON alone decides.
      ``WorktreeCreate`` and ``WorktreeRemove`` fail on any non-zero exit.
===== ====================================================================

.. note::

   **Pick one channel.** Use exit ``2`` + stderr to block with a message, *or*
   exit ``0`` + JSON for structured control. Mixing them is legal but harder
   to reason about: exit 2 always blocks, and a JSON ``reason`` replaces
   stderr as the message.

A minimal blocking command hook:

.. code:: bash

   #!/bin/bash
   INPUT=$(cat)
   COMMAND=$(echo "$INPUT" | jq -r '.tool_input.command')
   if echo "$COMMAND" | grep -q "drop table"; then
     echo "Blocked: dropping tables is not allowed" >&2   # becomes Claude's feedback
     exit 2                                                # block
   fi
   exit 0                                                  # no decision; normal flow applies

--------------

Universal JSON fields (any event, exit 0)
-----------------------------------------

.. code:: json

   {
     "continue": true,
     "stopReason": "shown to the user when continue is false; stays in the conversation",
     "suppressOutput": false,
     "systemMessage": "warning shown to the user",
     "terminalSequence": "allow-listed terminal escape (titles / notifications only)"
   }

- ``continue: false`` halts further processing entirely.
- ``suppressOutput`` is accepted but has no effect: a successful hook's stdout
  is never shown in the transcript.
- ``systemMessage`` surfaces a warning to the user.
- ``terminalSequence`` is restricted to an allowlist (see
  ``references/prompt-injection.rst``).

Context is added through ``hookSpecificOutput.additionalContext`` (and
``hookEventName`` is **required** whenever you use ``hookSpecificOutput``):

.. code:: json

   {
     "hookSpecificOutput": {
       "hookEventName": "PostToolUse",
       "additionalContext": "Build succeeded in 12s."
     }
   }

--------------

Decision control per event
---------------------------

Different events use different decision shapes. Use the right one:

PreToolUse — ``permissionDecision``
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

This is the **current canonical** form (the older top-level
``{"decision":"approve"|"block"}`` is superseded for ``PreToolUse``):

.. code:: json

   {
     "hookSpecificOutput": {
       "hookEventName": "PreToolUse",
       "permissionDecision": "deny",
       "permissionDecisionReason": "Use rg instead of grep for better performance"
     }
   }

``permissionDecision`` values:

- ``"allow"`` — skip the interactive prompt. **Deny / ask rules still apply** —
  managed deny lists always win.
- ``"deny"`` — cancel the tool call; the reason is sent to Claude.
- ``"ask"`` — show the normal permission prompt to the user.
- ``"defer"`` — only in non-interactive ``-p`` mode; exits with the tool call
  preserved so an Agent SDK wrapper can resume it.

Optional: ``updatedInput`` (rewrite the tool's arguments — last writer wins
across parallel hooks) and ``additionalContext``.

PostToolUse / PostToolUseFailure / PostToolBatch / Stop / SubagentStop / PreCompact / ConfigChange / TaskCreated — top-level ``decision``
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

.. code:: json

   { "decision": "block", "reason": "explanation fed back to Claude" }

- ``Stop`` / ``SubagentStop``: ``"block"`` *continues* the conversation instead
  of stopping; ``reason`` becomes Claude's next instruction.
- ``PostToolUse``: ``"block"`` surfaces ``reason`` to Claude (the tool already
  ran — it cannot be undone).
- ``PreCompact`` / ``ConfigChange`` / ``TaskCreated``: ``"block"`` prevents
  the operation.
- ``PostToolBatch``: ``"block"`` stops the loop before the next model call.

TeammateIdle / TaskCompleted — exit code or ``continue: false``
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

These events do not use top-level ``decision``. Exit ``2`` blocks with stderr
feedback; ``{"continue": false, "stopReason": "..."}`` stops the teammate.
``TaskCompleted`` ignores ``continue: false`` when the ``TaskUpdate`` tool
triggered it.

PermissionRequest — ``hookSpecificOutput.decision.behavior``
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

.. code:: json

   {
     "hookSpecificOutput": {
       "hookEventName": "PermissionRequest",
       "decision": {
         "behavior": "allow",
         "updatedInput": {},
         "updatedPermissions": [
           { "type": "setMode", "mode": "acceptEdits", "destination": "session" }
         ]
       }
     }
   }

``behavior`` is ``"allow"`` or ``"deny"``. ``updatedPermissions`` can switch the
session permission mode. Keep the matcher narrow — an empty / ``.*`` matcher
auto-approves *every* prompt.

PermissionDenied — ``retry``
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

.. code:: json

   { "hookSpecificOutput": { "hookEventName": "PermissionDenied", "retry": true } }

UserPromptSubmit / UserPromptExpansion
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Use ``hookSpecificOutput.additionalContext`` to inject context, or
``{"decision": "block", "reason": "..."}`` to reject the prompt. On exit 0,
plain stdout is also added as context.

SessionStart
~~~~~~~~~~~~

Plain stdout is added to context. Structured extras (``initialUserMessage`` is
also accepted):

.. code:: json

   {
     "hookSpecificOutput": {
       "hookEventName": "SessionStart",
       "additionalContext": "string",
       "sessionTitle": "string",
       "watchPaths": ["/abs/path/to/watch"],
       "reloadSkills": true
     }
   }

--------------

HTTP hook responses
-------------------

HTTP hooks reply through the response, not exit codes:

- ``2xx`` empty body → success, no output.
- ``2xx`` plain text → non-blocking error; the text is **not** added to
  context.
- ``2xx`` JSON → parsed with the schema above.
- non-2xx / connection failure / timeout → non-blocking error; execution
  continues.

**To block, return 2xx with the decision JSON** (status alone cannot block).

--------------

Prompt / agent hooks output
---------------------------

``type: "prompt"`` and ``type: "agent"`` hooks do **not** use this exit-code /
``permissionDecision`` contract. They return ``{"ok": true|false, "reason":
"..."}`` from a model. See ``references/prompt-and-agent-hooks.rst``.
