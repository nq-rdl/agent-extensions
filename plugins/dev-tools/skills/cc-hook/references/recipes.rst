Hook Recipes
============

Copy-paste Claude Code hook patterns with full implementations. Each uses the
current I/O contract — see ``references/output.rst`` for the schema and
``references/lifecycle.rst`` for which events can block.

Source patterns adapted from
https://code.claude.com/docs/en/hooks-guide#what-you-can-automate

--------------

1. Block destructive shell commands
-----------------------------------

Deny ``rm -rf /``, force push, and ``dd`` to a device. Uses
``permissionDecision: "deny"`` so it blocks even under ``bypassPermissions``.

Script — ``block-destructive.sh``
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

.. code:: bash

   #!/usr/bin/env bash
   set -euo pipefail
   input=$(cat)
   cmd=$(echo "$input" | jq -r '.tool_input.command // empty')

   if echo "$cmd" | grep -qE 'rm[[:space:]]+-rf[[:space:]]+(/|~)|git[[:space:]]+push[[:space:]].*--force|dd[[:space:]]+if=.*of=/dev'; then
     jq -nc '{
       hookSpecificOutput: {
         hookEventName: "PreToolUse",
         permissionDecision: "deny",
         permissionDecisionReason: "Destructive command blocked by safety hook"
       }
     }'
   fi

Config
~~~~~~

.. code:: json

   {
     "hooks": {
       "PreToolUse": [
         {
           "matcher": "Bash",
           "hooks": [
             { "type": "command", "command": "\"$CLAUDE_PROJECT_DIR\"/.claude/hooks/block-destructive.sh", "timeout": 10 }
           ]
         }
       ]
     }
   }

The same effect with a pure exit-code hook (no JSON): ``echo`` the reason to
stderr and ``exit 2``.

--------------

2. Protect sensitive files
--------------------------

Block edits/writes to ``.env``, credentials, private keys, and lock files. The
official pattern uses exit 2 + stderr — simplest and version-proof.

Script — ``protect-files.sh``
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

.. code:: bash

   #!/usr/bin/env bash
   set -euo pipefail
   input=$(cat)
   file_path=$(echo "$input" | jq -r '.tool_input.file_path // empty')

   for pattern in ".env" "credentials" ".pem" ".key" "pixi.lock" ".git/"; do
     if [[ "$file_path" == *"$pattern"* ]]; then
       echo "Blocked: $file_path matches protected pattern '$pattern'" >&2
       exit 2
     fi
   done
   exit 0

Config — register for both ``Edit`` and ``Write`` (the matcher accepts ``|``):

.. code:: json

   {
     "hooks": {
       "PreToolUse": [
         {
           "matcher": "Edit|Write",
           "hooks": [
             { "type": "command", "command": "\"$CLAUDE_PROJECT_DIR\"/.claude/hooks/protect-files.sh", "timeout": 10 }
           ]
         }
       ]
     }
   }

--------------

3. Auto-format edited files
---------------------------

Run a formatter after every ``Edit``/``Write``. ``PostToolUse`` runs after the
tool, so the file is already on disk.

.. code:: json

   {
     "hooks": {
       "PostToolUse": [
         {
           "matcher": "Edit|Write",
           "hooks": [
             { "type": "command", "command": "path=$(jq -r '.tool_input.file_path // empty'); [ -n \"$path\" ] && npx prettier --write -- \"$path\"" }
           ]
         }
       ]
     }
   }

--------------

4. Completion check — deterministic (Stop, command)
---------------------------------------------------

Continue the turn until tests/lint pass. Uses top-level ``decision: "block"``
(``Stop`` semantics) and respects the ``stop_hook_active`` block cap.

Script — ``stop-gate.sh``
~~~~~~~~~~~~~~~~~~~~~~~~~~

.. code:: bash

   #!/usr/bin/env bash
   set -euo pipefail
   input=$(cat)

   # Avoid infinite loops — Claude Code caps Stop blocks at 8 in a row.
   if [ "$(echo "$input" | jq -r '.stop_hook_active')" = "true" ]; then
     exit 0
   fi

   if ! npm test >/tmp/stop-gate.log 2>&1; then
     jq -nc '{decision: "block", reason: "Tests are failing — fix them before stopping. See /tmp/stop-gate.log"}'
     exit 0
   fi
   exit 0

Config
~~~~~~

.. code:: json

   {
     "hooks": {
       "Stop": [
         { "hooks": [ { "type": "command", "command": "\"$CLAUDE_PROJECT_DIR\"/.claude/hooks/stop-gate.sh", "timeout": 120 } ] }
       ]
     }
   }

--------------

5. Completion check — judgment (Stop, prompt)
---------------------------------------------

When "are we done?" needs judgment, use a ``prompt`` hook. The model returns
``{"ok": false, "reason": "..."}`` to keep Claude working. See
``references/prompt-and-agent-hooks.rst``.

.. code:: json

   {
     "hooks": {
       "Stop": [
         {
           "hooks": [
             {
               "type": "prompt",
               "prompt": "Check if all tasks the user requested are complete. If not, respond with {\"ok\": false, \"reason\": \"what remains\"}."
             }
           ]
         }
       ]
     }
   }

--------------

6. Inject project context safely (SessionStart)
------------------------------------------------

Re-inject context at session start / after compaction. Phrase it as **facts**,
not instructions, so it is not mistaken for prompt injection
(``references/prompt-injection.rst``).

Script — ``session-context.sh``
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

.. code:: bash

   #!/usr/bin/env bash
   # Declarative facts only — no imperatives. Branch names and commit subjects
   # are untrusted; sanitize them before injecting (see prompt-injection.rst).
   branch=$(git branch --show-current 2>/dev/null || echo "unknown")
   branch=$(printf '%s' "$branch" | tr -cd 'A-Za-z0-9._/-'); [ -n "$branch" ] || branch="unknown"
   last=$(git log -1 --pretty=%s 2>/dev/null | tr -cd '[:print:]' | cut -c1-72)
   echo "Current branch: $branch. Last commit subject: ${last:-none}. This project uses pixi and lefthook."

Config — fire on fresh start and after compaction:

.. code:: json

   {
     "hooks": {
       "SessionStart": [
         {
           "matcher": "startup|compact",
           "hooks": [
             { "type": "command", "command": "\"$CLAUDE_PROJECT_DIR\"/.claude/hooks/session-context.sh", "timeout": 5 }
           ]
         }
       ]
     }
   }

--------------

7. Auto-approve a known permission prompt (PermissionRequest)
-------------------------------------------------------------

Skip the dialog for a tool you always allow — here ``ExitPlanMode``. Keep the
matcher narrow; an empty matcher auto-approves everything.

.. code:: json

   {
     "hooks": {
       "PermissionRequest": [
         {
           "matcher": "ExitPlanMode",
           "hooks": [
             {
               "type": "command",
               "command": "echo '{\"hookSpecificOutput\": {\"hookEventName\": \"PermissionRequest\", \"decision\": {\"behavior\": \"allow\"}}}'"
             }
           ]
         }
       ]
     }
   }

``PermissionRequest`` hooks do **not** fire in non-interactive ``-p`` mode — use
``PreToolUse`` with ``permissionDecision: "allow"`` there.

--------------

8. Desktop notification when Claude needs input (Notification)
--------------------------------------------------------------

.. code:: json

   {
     "hooks": {
       "Notification": [
         {
           "matcher": "",
           "hooks": [
             { "type": "command", "command": "notify-send 'Claude Code' 'Claude Code needs your attention'" }
           ]
         }
       ]
     }
   }

macOS: ``osascript -e 'display notification ...'``. Windows: a PowerShell
``MessageBox``. Narrow the matcher to ``permission_prompt`` or ``idle_prompt``
to fire only on those.

--------------

9. Log every Bash command (PostToolUse)
---------------------------------------

.. code:: json

   {
     "hooks": {
       "PostToolUse": [
         {
           "matcher": "Bash",
           "hooks": [
             { "type": "command", "command": "jq -r '.tool_input.command' >> ~/.claude/command-log.txt" }
           ]
         }
       ]
     }
   }

--------------

10. Audit configuration changes (ConfigChange)
----------------------------------------------

.. code:: json

   {
     "hooks": {
       "ConfigChange": [
         {
           "matcher": "",
           "hooks": [
             { "type": "command", "command": "jq -c '{timestamp: now | todate, source: .config_source, keys: .changed_keys}' >> ~/claude-config-audit.log" }
           ]
         }
       ]
     }
   }

Exit 2 or ``{"decision": "block"}`` to reject an unauthorized change.

--------------

11. Reload environment on directory change (CwdChanged + direnv)
----------------------------------------------------------------

.. code:: json

   {
     "hooks": {
       "SessionStart": [
         { "hooks": [ { "type": "command", "command": "direnv export bash > \"$CLAUDE_ENV_FILE\"" } ] }
       ],
       "CwdChanged": [
         { "hooks": [ { "type": "command", "command": "direnv export bash > \"$CLAUDE_ENV_FILE\"" } ] }
       ]
     }
   }

``CLAUDE_ENV_FILE`` is run as a preamble before each Bash command. Run
``direnv allow`` once per directory.
