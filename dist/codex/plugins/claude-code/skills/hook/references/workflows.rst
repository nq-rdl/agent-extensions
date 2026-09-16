Hook Workflows
==============

Focused, ordered procedures for the three things people do with hooks:
**create**, **debug**, and **audit**. These are the stable entrypoints that a
downstream Claude Code plugin maps to namespaced commands (``/cc-hook:create``,
``/cc-hook:debug``, ``/cc-hook:audit``) — keep their headings stable so the
plugin lenses can point at them. Each workflow says *which reference to read at
each step* rather than repeating it.

--------------

.. _workflow-create:

Create a hook
-------------

Goal: go from "I want X to always happen" to a registered, smoke-tested hook.

1. **Clarify intent.** What should trigger it, and what should happen — *block*
   an action, *observe* (log/format/notify), or *inject context*? If the rule
   is a hard guarantee, it must be deterministic (a ``command`` hook), not prose.
2. **Pick the event.** Match the trigger to a lifecycle event and confirm it can
   do what you need (e.g. only some events can block). → ``lifecycle.rst``.
3. **Pick the hook type.** Deterministic check → ``command``; remote service →
   ``http``; MCP tool → ``mcp_tool``; judgment from event data → ``prompt``;
   judgment needing codebase inspection → ``agent``. → ``claude-code.rst``
   (decision tree) and ``prompt-and-agent-hooks.rst``.
4. **Choose the matcher (and ``if``).** Narrow the firing set: tool name /
   regex, or ``if: "Bash(git *)"`` for tool-name-plus-args. → ``claude-code.rst``.
5. **Decide the output mechanism.** Block with **exit 2 + stderr** *or* **exit 0
   + JSON** — never both. For ``PreToolUse`` use
   ``hookSpecificOutput.permissionDecision``; for ``PostToolUse``/``Stop`` use
   top-level ``decision``. → ``output.rst``. If the hook injects context, read
   ``prompt-injection.rst`` first and phrase it as **facts, not commands**.
6. **Write it.** Put logic in a script at
   ``"$CLAUDE_PROJECT_DIR"/.claude/hooks/<name>.sh`` rather than a long inline
   string; switch to exec form (``"args": []``) if shell quoting gets hairy.
   Start bash scripts with ``input=$(cat)``; send debug to ``>&2``.
7. **Smoke-test before wiring it in.** Pipe a realistic event and check stdout +
   exit code::

      echo '{"tool_name":"Bash","tool_input":{"command":"rm -rf /"}}' | bash hook.sh; echo $?

   Validate that stdout is well-formed JSON (``... | jq .``). → ``debugging.rst``.
8. **Choose the install location.** Personal (``~/.claude/settings.json``),
   shared project (``.claude/settings.json``), or local
   (``.claude/settings.local.json``). → ``claude-code.rst``.
9. **Register and confirm.** Add the config, then run ``/hooks`` to verify it
   appears under the right event with the right matcher.

--------------

.. _workflow-debug:

Debug a hook
------------

Goal: a hook that doesn't fire, fires wrong, or whose output is ignored.

1. **Registered?** ``/hooks`` — is it under the expected event?
2. **Config valid?** ``jq . <settings-file>`` (no trailing commas/comments).
3. **Right event + matcher?** Names and tool matchers are case-sensitive;
   ``PreToolUse`` is before, ``PostToolUse`` is after.
4. **Runs standalone?** ``echo '{}' | bash hook.sh`` and with realistic JSON.
5. **Output correct?** stdout must be JSON-only on exit 0; confirm the **shape
   matches the event** (``permissionDecision`` vs ``decision`` vs
   ``decision.behavior``). → ``output.rst``.
6. **Output looks like injection?** If injected context is shown to the user
   instead of used, it's phrased imperatively — make it factual.
   → ``prompt-injection.rst``.
7. **Timeout / exit code?** A killed hook lets the action proceed silently; exit
   ``2`` blocks, other non-zero is a non-blocking error.
8. **Stop hook looping?** Check the ``stop_hook_active`` block cap.
   → ``lifecycle.rst``.
9. **Read the log.** ``claude --debug-file /tmp/claude.log`` then
   ``tail -f``; or ``/debug`` mid-session. → ``debugging.rst``.

Full symptom→cause→fix table lives in ``debugging.rst``.

--------------

.. _workflow-audit:

Audit hooks
-----------

Goal: review every hook that can run, for correctness, safety, and portability.

1. **Enumerate sources.** Global, project shared, project local, managed policy,
   enabled plugins, and skill/agent frontmatter. Note the merge precedence.
   → ``claude-code.rst`` (config location).
2. **See the effective set.** ``/hooks`` shows what actually loads.
3. **Output contract.** Flag any ``PreToolUse`` still using the legacy
   ``{"decision":"approve"|"block"}`` — migrate to
   ``permissionDecision``. → ``output.rst``.
4. **Context-injecting hooks.** Factual (not imperative) phrasing? Untrusted
   values summarized rather than spliced into instructions? Output under ~10k
   chars? → ``prompt-injection.rst``.
5. **Permission safety.** Any ``PermissionRequest`` auto-approve with a broad /
   empty matcher? Any hook assuming ``"allow"`` bypasses deny rules (it does
   not)? Are deny guardrails enforced via ``PreToolUse`` so they hold even under
   ``bypassPermissions``? → ``lifecycle.rst``.
6. **Portability.** Are active hook configs living *inside* a skill directory?
   They shouldn't — skills stay platform-agnostic; deployable hooks belong in
   the extension/plugin layer.
7. **Hygiene.** Scripts executable, ``jq``/interpreters available, no shell
   profile printing banners onto stdout. → ``debugging.rst``.
