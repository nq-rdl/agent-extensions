Claude Code Hooks — Core Reference
==================================

Sources (Claude Code official docs):

- Guide: https://code.claude.com/docs/en/hooks-guide
- Reference: https://code.claude.com/docs/en/hooks

Hooks are user-defined commands that execute at specific points in Claude
Code's lifecycle. They provide *deterministic* control — an action always
happens, rather than relying on the model to choose to run it. For decisions
that need judgment, see ``references/prompt-and-agent-hooks.rst``.

--------------

Config Location
---------------

Where you add a hook determines its scope
(https://code.claude.com/docs/en/hooks-guide#configure-hook-location):

+-----------------------------------+------------------------------------+------------------------------+
| Location                          | Scope                              | Shareable                    |
+===================================+====================================+==============================+
| ``~/.claude/settings.json``       | All your projects                  | No — local to your machine   |
+-----------------------------------+------------------------------------+------------------------------+
| ``.claude/settings.json``         | Single project                     | Yes — commit to the repo     |
+-----------------------------------+------------------------------------+------------------------------+
| ``.claude/settings.local.json``   | Single project                     | No — gitignored              |
+-----------------------------------+------------------------------------+------------------------------+
| Managed policy settings           | Organization-wide                  | Yes — admin-controlled       |
+-----------------------------------+------------------------------------+------------------------------+
| Plugin ``hooks/hooks.json``       | When the plugin is enabled         | Yes — bundled with plugin    |
+-----------------------------------+------------------------------------+------------------------------+
| Skill / agent frontmatter         | While that component is active     | Yes — in the component file  |
+-----------------------------------+------------------------------------+------------------------------+

- Run ``/hooks`` to browse configured hooks grouped by event. The menu is
  **read-only**: edit the settings JSON directly or ask Claude to change it.
- Set ``"disableAllHooks": true`` to turn hooks off. Hooks in managed settings
  still run unless ``disableAllHooks`` is also set there.
- Editing a settings file while Claude Code runs is normally picked up
  automatically by the file watcher.

--------------

Configuration Schema
--------------------

.. code:: json

   {
     "hooks": {
       "<EventName>": [
         {
           "matcher": "ToolNameOrPattern",
           "hooks": [
             {
               "type": "command",
               "command": "\"$CLAUDE_PROJECT_DIR\"/.claude/hooks/check.sh",
               "if": "Bash(git *)",
               "timeout": 10
             }
           ]
         }
       ]
     }
   }

Each event name maps to an array of *hook groups*. Each group has an optional
``matcher`` and a ``hooks`` array of hook definitions. If a settings file
already has a ``hooks`` key, add new event names as siblings rather than
replacing the object.

Hook definition fields
~~~~~~~~~~~~~~~~~~~~~~~

- **type** (required): ``command``, ``http``, ``mcp_tool``, ``prompt``, or
  ``agent`` — see *Hook Types* below.
- **command** (command hooks): shell command to run. Receives event JSON on
  stdin. Use ``"$CLAUDE_PROJECT_DIR"`` for repo-relative script paths.
- **args** (command hooks, optional): switches to *exec form* — the program is
  spawned directly with these args, **without a shell**, avoiding quoting and
  profile-sourcing problems. Without ``args`` it runs in *shell form*
  (``sh -c`` / Git Bash).
- **if** (tool events, v2.1.85+): permission-rule pattern filtering by tool
  name *and* arguments together, e.g. ``"Bash(git *)"``, ``"Edit(*.ts)"``. The
  hook process only spawns when a subcommand matches (or the command can't be
  parsed). Works only on ``PreToolUse``, ``PostToolUse``, ``PostToolUseFailure``,
  ``PermissionRequest``, ``PermissionDenied``.
- **timeout** (optional): seconds before the hook is killed. Defaults:
  ``command``/``http``/``mcp_tool`` = 10 min (lowered to 30 s under
  ``UserPromptSubmit``), ``prompt`` = 30 s, ``agent`` = 60 s.
- **url**, **headers**, **allowedEnvVars** (http hooks): see *Hook Types*.
- **prompt**, **model** (prompt/agent hooks): see
  ``references/prompt-and-agent-hooks.rst``.

--------------

Hook Types
----------

+-------------+----------------------------------------+-------------------------------+
| Type        | What it does                           | When to use                   |
+=============+========================================+===============================+
| ``command`` | Runs a shell command; reads stdin      | Most hooks — checks, scripts, |
|             | JSON, replies via stdout + exit code   | formatting, logging           |
+-------------+----------------------------------------+-------------------------------+
| ``http``    | POSTs event JSON to a URL; reply is     | Web servers, shared audit /   |
|             | the HTTP response body                 | logging services              |
+-------------+----------------------------------------+-------------------------------+
| ``mcp_tool``| Calls a tool on a connected MCP server | Reuse MCP tooling as a hook   |
+-------------+----------------------------------------+-------------------------------+
| ``prompt``  | Single-turn LLM evaluation             | Yes/no judgment from event    |
|             | (``{"ok": bool, "reason": ...}``)      | data alone                    |
+-------------+----------------------------------------+-------------------------------+
| ``agent``   | Multi-turn subagent with tool access   | Verify against real codebase  |
| *(exp.)*    | (same ``ok``/``reason`` format)        | state (run tests, read files) |
+-------------+----------------------------------------+-------------------------------+

``prompt`` and ``agent`` hooks are documented in
``references/prompt-and-agent-hooks.rst``. ``command`` and ``http`` share the
same JSON output contract (``references/output.rst``).

HTTP hook fields
~~~~~~~~~~~~~~~~

.. code:: json

   {
     "type": "http",
     "url": "http://localhost:8080/hooks/tool-use",
     "headers": { "Authorization": "Bearer $MY_TOKEN" },
     "allowedEnvVars": ["MY_TOKEN"]
   }

- The endpoint receives the same JSON a command hook gets on stdin and returns
  results in the response body using the same output format.
- Header values interpolate ``$VAR`` / ``${VAR}`` **only** for variables listed
  in ``allowedEnvVars``; all other ``$VAR`` references resolve to empty.
- HTTP status codes alone cannot block. To block, return a 2xx response whose
  JSON body carries the decision fields (e.g. ``permissionDecision: "deny"``).

--------------

Events
------

When an event fires, all matching hooks run **in parallel** and identical
commands are deduplicated. After they finish, Claude Code merges their outputs.
For ``PreToolUse`` permission decisions the **most restrictive wins**
(``deny`` > ``ask`` > ``allow``); ``additionalContext`` from every hook is kept.

Full firing order and blocking semantics are in ``references/lifecycle.rst``.
Quick event table
(https://code.claude.com/docs/en/hooks-guide#how-hooks-work):

============================ =====================================================
Event                        When it fires
============================ =====================================================
``SessionStart``             A session begins or resumes
``Setup``                    ``--init-only`` / ``--init`` / ``--maintenance``
``UserPromptSubmit``         You submit a prompt, before Claude processes it
``UserPromptExpansion``      A typed command expands into a prompt (can block)
``PreToolUse``               Before a tool call executes (can block)
``PermissionRequest``        A permission dialog is about to appear
``PermissionDenied``         A tool call was denied by the auto-mode classifier
``PostToolUse``              After a tool call succeeds
``PostToolUseFailure``       After a tool call fails
``PostToolBatch``            After a batch of parallel tool calls resolves
``Notification``             Claude Code sends a notification
``MessageDisplay``           While assistant message text is displayed
``SubagentStart``            A subagent is spawned
``SubagentStop``             A subagent finishes
``TaskCreated``              A task is being created via ``TaskCreate``
``TaskCompleted``            A task is being marked complete
``Stop``                     Claude finishes responding
``StopFailure``              The turn ends due to an API error (output ignored)
``TeammateIdle``             An agent-team teammate is about to go idle
``InstructionsLoaded``       A CLAUDE.md / ``.claude/rules/*.md`` file is loaded
``ConfigChange``             A configuration file changes during a session
``CwdChanged``               The working directory changes (e.g. ``cd``)
``FileChanged``              A watched file changes on disk
``WorktreeCreate``           A worktree is being created
``WorktreeRemove``           A worktree is being removed
``PreCompact``               Before context compaction
``PostCompact``              After context compaction completes
``Elicitation``              An MCP server requests user input
``ElicitationResult``        After the user responds to an MCP elicitation
``SessionEnd``               A session terminates
============================ =====================================================

--------------

Matchers
--------

Without a ``matcher`` a hook fires on every occurrence of its event. The
``matcher`` field is interpreted per event
(https://code.claude.com/docs/en/hooks-guide#filter-hooks-with-matchers):

- **Tool events** (``PreToolUse``, ``PostToolUse``, ``PostToolUseFailure``,
  ``PermissionRequest``, ``PermissionDenied``) — tool name: ``Bash``,
  ``Edit|Write``, ``mcp__github__.*``.
- **SessionStart** — ``startup``, ``resume``, ``clear``, ``compact``.
- **Setup** — ``init``, ``maintenance``.
- **SessionEnd** — ``clear``, ``resume``, ``logout``, ``prompt_input_exit``,
  ``bypass_permissions_disabled``, ``other``.
- **Notification** — ``permission_prompt``, ``idle_prompt``, ``auth_success``,
  ``elicitation_dialog``, ``elicitation_complete``, ``elicitation_response``.
- **SubagentStart / SubagentStop** — agent type (``Explore``, ``Plan``,
  ``general-purpose``, custom names).
- **PreCompact / PostCompact** — ``manual``, ``auto``.
- **ConfigChange** — ``user_settings``, ``project_settings``, ``local_settings``,
  ``policy_settings``, ``skills``.
- **StopFailure** — ``rate_limit``, ``authentication_failed``, ``server_error``, …
- **InstructionsLoaded** — ``session_start``, ``nested_traversal``,
  ``path_glob_match``, ``include``, ``compact``.
- **Elicitation / ElicitationResult** — MCP server name.
- **FileChanged** — literal filenames split on ``|`` (``.envrc|.env``), **not**
  a regex.
- **UserPromptExpansion** — command / skill name.
- **No matcher support** (always fires): ``UserPromptSubmit``, ``PostToolBatch``,
  ``Stop``, ``TeammateIdle``, ``TaskCreated``, ``TaskCompleted``,
  ``WorktreeCreate``, ``WorktreeRemove``, ``CwdChanged``, ``MessageDisplay``.

Tool-name matchers accept plain names and regex alternation (``Edit|Write``).
MCP tools are named ``mcp__<server>__<tool>`` — match a whole server with
``mcp__github__.*`` or cross-server with ``mcp__.*__write.*``.

.. note::

   Claude can also change files by running shell commands through ``Bash``. If a
   hook must see *every* file change (audit / compliance), add a ``Stop`` hook
   that scans the working tree once per turn, or also match ``Bash`` and list
   modified files with ``git status --porcelain``.

--------------

Combining results from multiple hooks
--------------------------------------

When several hooks match one event, every command runs to completion before
results merge. One hook returning ``deny`` does **not** stop sibling hooks from
running — don't rely on a ``deny`` to suppress side effects in another hook. For
``PreToolUse`` the most restrictive permission decision wins.

--------------

Environment Variables
---------------------

Available to hooks (https://code.claude.com/docs/en/hooks):

- ``CLAUDE_PROJECT_DIR`` — project root (use for script paths).
- ``CLAUDE_PLUGIN_ROOT`` / ``CLAUDE_PLUGIN_DATA`` — plugin install / data dirs.
- ``CLAUDE_EFFORT`` — effort level for the current turn.
- ``CLAUDE_CODE_REMOTE`` — ``"true"`` in web environments.
- ``CLAUDE_ENV_FILE`` — path to persist env vars; Claude Code runs it as a
  preamble before each Bash command. Available to ``SessionStart``, ``Setup``,
  ``CwdChanged``, ``FileChanged`` hooks. Pairs well with ``direnv``.

On macOS/Linux (since v2.1.139) hooks run **without a controlling terminal** —
they cannot open ``/dev/tty`` or emit escape sequences directly. Use the
``terminalSequence`` output field instead (see ``references/output.rst`` and
``references/prompt-injection.rst``).

--------------

Worked example (multiple types)
--------------------------------

.. code:: json

   {
     "hooks": {
       "PreToolUse": [
         {
           "matcher": "Bash",
           "hooks": [
             {
               "type": "command",
               "if": "Bash(rm *)",
               "command": "\"$CLAUDE_PROJECT_DIR\"/.claude/hooks/block-rm.sh",
               "timeout": 10
             }
           ]
         },
         {
           "matcher": "mcp__.*__write.*",
           "hooks": [
             {
               "type": "http",
               "url": "http://localhost:8080/validate-mcp-write",
               "headers": { "Authorization": "Bearer $SECURITY_TOKEN" },
               "allowedEnvVars": ["SECURITY_TOKEN"]
             }
           ]
         }
       ],
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

Curated configs in this repo
----------------------------

Ready-to-adapt configs live in ``examples/``. Copy or merge into
``.claude/settings.local.json``:

.. code:: bash

   cp examples/<config>.json .claude/settings.local.json

   # Merge into existing settings
   jq -s '.[0] * .[1]' .claude/settings.local.json examples/<config>.json > /tmp/merged.json \
     && mv /tmp/merged.json .claude/settings.local.json
