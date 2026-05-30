Prompt-based and Agent-based Hooks
==================================

Sources:

- https://code.claude.com/docs/en/hooks-guide#prompt-based-hooks
- https://code.claude.com/docs/en/hooks-guide#agent-based-hooks
- https://code.claude.com/docs/en/hooks (Prompt-based hooks, Agent-based hooks)

For decisions that need *judgment* rather than a deterministic rule, Claude Code
can run the hook through a model instead of a shell command. Two types:
``type: "prompt"`` (one LLM call) and ``type: "agent"`` (a tool-using subagent).

.. important::

   These are **not** static-text hooks. A frequent misconception is that
   ``type: "prompt"`` injects a fixed reminder string into context. It does
   not. It sends your prompt **plus the hook's input data** to a Claude model
   that returns a yes/no decision as JSON. If you only want to inject static
   text, use a ``command`` hook that ``echo``-s it (and read
   ``references/prompt-injection.rst`` first).

--------------

The ``ok`` / ``reason`` response format
----------------------------------------

Both prompt and agent hooks make the model return:

- ``{"ok": true}`` — the action proceeds.
- ``{"ok": false, "reason": "..."}`` — what happens depends on the event:

  - ``Stop`` / ``SubagentStop``: ``reason`` is fed back to Claude so it keeps
    working (use it as the next instruction).
  - ``PreToolUse``: the tool call is denied and ``reason`` is returned to Claude
    as the tool error, so it can adjust and continue.
  - ``PostToolUse`` / ``PostToolBatch`` / ``UserPromptSubmit`` /
    ``UserPromptExpansion``: the turn ends and ``reason`` appears in the chat as
    a warning line.

--------------

Prompt-based hooks (``type: "prompt"``)
---------------------------------------

A single-turn LLM evaluation. By default it uses **Haiku**; set ``model`` for
more capability. Use prompt hooks when the **hook input data alone** is enough
to decide. Default timeout: 30 s.

.. code:: json

   {
     "hooks": {
       "Stop": [
         {
           "hooks": [
             {
               "type": "prompt",
               "prompt": "Check if all tasks are complete. If not, respond with {\"ok\": false, \"reason\": \"what remains to be done\"}."
             }
           ]
         }
       ]
     }
   }

If the model returns ``"ok": false``, Claude keeps working and uses ``reason``
as its next instruction.

Optional fields:

- ``model`` — override the default model (e.g. a Sonnet identifier) for harder
  judgments.
- ``timeout`` — seconds (default 30).

--------------

Agent-based hooks (``type: "agent"``) — experimental
-----------------------------------------------------

.. warning::

   Agent hooks are **experimental**; behavior and configuration may change. For
   production workflows prefer command hooks.

When verification requires inspecting files or running commands, an agent hook
spawns a subagent that can read files, search code, and use tools before
returning the same ``ok`` / ``reason`` decision. Default timeout: 60 s, up to 50
tool-use turns. ``$ARGUMENTS`` interpolates provided arguments into the prompt.

.. code:: json

   {
     "hooks": {
       "Stop": [
         {
           "hooks": [
             {
               "type": "agent",
               "prompt": "Verify that all unit tests pass. Run the test suite and check the results. $ARGUMENTS",
               "timeout": 120
             }
           ]
         }
       ]
     }
   }

--------------

Choosing between them
---------------------

- Deterministic rule (path match, regex, command check) → ``command`` hook.
- Judgment from the event data alone → ``prompt`` hook.
- Judgment that needs to inspect the real codebase / run commands → ``agent``
  hook.
