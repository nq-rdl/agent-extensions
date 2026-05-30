Debugging Hooks
===============

Source: https://code.claude.com/docs/en/hooks-guide#limitations-and-troubleshooting
and https://code.claude.com/docs/en/hooks#debug-hooks

--------------

Universal checklist
-------------------

Work through these in order when a hook isn't behaving:

1. **Registered?** Run ``/hooks`` and confirm the hook appears under the correct
   event.
2. **Valid JSON config?** ``jq . <settings-file>``. Trailing commas and comments
   are not allowed.
3. **Right event?** ``PreToolUse`` fires *before* a tool, ``PostToolUse``
   *after*. Names are case-sensitive (``PreToolUse``, not ``pretooluse``).
4. **Matcher matches?** Tool names are exact and case-sensitive (``Bash``, not
   ``bash``). For tool events the matcher is a tool name / regex; for other
   events it is an enum (see ``references/claude-code.rst``).
5. **Script runs standalone?** ``echo '{}' | bash hook.sh``.
6. **Parses stdin?** Pipe realistic JSON:
   ``echo '{"tool_name":"Bash","tool_input":{"command":"ls"}}' | bash hook.sh``.
7. **Output is JSON-only?** stdout on exit 0 must be valid JSON (or empty/plain
   for context events). Mixed text + JSON breaks parsing — send debug to stderr.
8. **Right output shape?** ``PreToolUse`` uses ``permissionDecision``;
   ``PostToolUse``/``Stop`` use top-level ``decision``. See
   ``references/output.rst``.
9. **Timeout enough?** A killed hook lets the action proceed silently.

--------------

Testing a hook manually
-----------------------

.. code:: bash

   # Blocking PreToolUse hook (current shape)
   echo '{"tool_name":"Bash","tool_input":{"command":"rm -rf /"}}' | bash hook.sh
   # Expect:
   # {"hookSpecificOutput":{"hookEventName":"PreToolUse","permissionDecision":"deny","permissionDecisionReason":"..."}}

   # Safe command — expect empty output (no decision)
   echo '{"tool_name":"Bash","tool_input":{"command":"ls -la"}}' | bash hook.sh

   # Check the exit code too
   echo '{"tool_name":"Bash","tool_input":{"command":"ls"}}' | ./hook.sh; echo $?

--------------

Common failure modes
--------------------

+---------------------------------+--------------------------------+--------------------------------------+
| Symptom                         | Cause                          | Fix                                  |
+=================================+================================+======================================+
| Hook never fires               | Wrong settings level, wrong    | Check global vs project vs local;    |
|                                | event, or bad matcher          | confirm via ``/hooks``               |
+---------------------------------+--------------------------------+--------------------------------------+
| ``<hook> hook error`` in        | Script exited non-zero         | Test manually; use absolute paths or |
| transcript                     | unexpectedly / not found       | ``$CLAUDE_PROJECT_DIR``; add         |
|                                |                                | ``"args": []`` for exec form         |
+---------------------------------+--------------------------------+--------------------------------------+
| "command not found"            | Relative path / missing tool   | Absolute path; install ``jq`` or use |
|                                |                                | Python/Node for JSON parsing         |
+---------------------------------+--------------------------------+--------------------------------------+
| Permission denied              | Script not executable          | ``chmod +x hook.sh``                 |
+---------------------------------+--------------------------------+--------------------------------------+
| Block has no reason shown      | Missing ``reason`` /           | Add ``permissionDecisionReason`` or  |
|                                | ``permissionDecisionReason``   | ``reason`` to the decision JSON      |
+---------------------------------+--------------------------------+--------------------------------------+
| Hook killed silently           | Timeout too short              | Increase ``timeout``; keep it fast   |
+---------------------------------+--------------------------------+--------------------------------------+
| JSON parse error despite valid | Shell profile echoes a banner  | Guard profile output behind          |
| output                         | before the JSON                | ``[[ $- == *i* ]]``; debug to stderr |
+---------------------------------+--------------------------------+--------------------------------------+
| ``"allow"`` doesn't bypass a   | Deny rules always win          | Hooks can tighten, not loosen,       |
| prompt                         |                                | permissions                          |
+---------------------------------+--------------------------------+--------------------------------------+
| Injected context shown to user | Phrased as an imperative       | Use factual phrasing — see           |
| instead of used                | "system command"               | ``references/prompt-injection.rst``  |
+---------------------------------+--------------------------------+--------------------------------------+

--------------

The "JSON validation failed" trap
----------------------------------

Shell-form command hooks (no ``args``) spawn ``sh -c`` (or Git Bash on Windows).
If your profile prints unconditionally, that output is prepended to the hook's
stdout::

   Shell ready on arm64
   {"decision": "block", "reason": "Not allowed"}

Claude Code then fails to parse it. Fix by only printing in interactive shells:

.. code:: bash

   # ~/.zshrc or ~/.bashrc
   if [[ $- == *i* ]]; then
     echo "Shell ready"
   fi

Or switch the hook to **exec form** by adding ``"args": []``, which spawns the
program directly without a shell.

--------------

Stop hook hits the block cap
----------------------------

Claude keeps working then ends with a warning that the Stop hook blocked too
many times. Claude Code overrides a Stop hook after **8 consecutive blocks**.
Parse ``stop_hook_active`` and exit early when it is ``true`` (see
``references/lifecycle.rst``). Raise the cap with
``CLAUDE_CODE_STOP_HOOK_BLOCK_CAP``.

--------------

Reading the debug log
---------------------

- ``Ctrl+O`` toggles the transcript view — one line per hook: success is silent,
  blocking errors show stderr, non-blocking errors show ``<hook> hook error`` +
  the first stderr line.
- For full detail (which hooks matched, exit codes, stdout, stderr), start with
  ``claude --debug-file /tmp/claude.log`` and ``tail -f /tmp/claude.log``. If you
  started without it, run ``/debug`` mid-session.

--------------

Reference implementation
------------------------

Anthropic's Bash command validator example:
https://github.com/anthropics/claude-code/blob/main/examples/hooks/bash_command_validator_example.py
