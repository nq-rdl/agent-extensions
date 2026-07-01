Agent Frontmatter Contract
==========================

The exact YAML frontmatter schema for ``agents/<name>/agent.md`` in this catalog,
grounded in the real repo files (e.g. ``agents/go-mcp-expert/agent.md``,
``agents/agent-governance-reviewer/agent.md``). CI enforces the required keys — see
``references/pipeline.rst`` for which gate checks what.

--------------

The shape
---------

.. code:: yaml

   ---
   name: my-agent
   description: >-
     Delegate to this agent when <trigger>; it <what it does and how>.
   license: MIT
   tools:
     - Read
     - Write
     - Edit
     - Grep
     - Glob
     - Bash
   model: inherit
   skills: []
   color: teal
   metadata:
     upstream: https://github.com/github/awesome-copilot/blob/main/agents/my-agent.agent.md
     repo: https://github.com/nq-rdl/agent-extensions
   ---

--------------

Field-by-field
--------------

============== =================================================================
Field         Rule
============== =================================================================
``name``       kebab-case; **must equal the directory name** ``agents/<name>/``.
               CI-required (``validate-plugins.sh`` agent-frontmatter check).
``description`` Folded scalar (``>-``); **triggering**, in the "Delegate to this
               agent when…" voice — this is what routes work to the subagent.
               CI-required. State the trigger and what the agent does.
``license``    ``MIT`` for ``github/awesome-copilot`` adaptations (their license);
               otherwise ``CC-BY-4.0`` or the source's actual license. For a
               from-scratch agent with no upstream, ``CC-BY-4.0``.
``tools``      Explicit, **minimal** list. Common set: ``Read``, ``Write``,
               ``Edit``, ``Grep``, ``Glob``, ``Bash``. Omit anything the agent
               does not use (a review-only agent typically drops ``Write``/
               ``Edit``/``Bash`` — see ``agent-governance-reviewer``).
``model``      ``inherit`` — the subagent runs on the session's model.
``skills``     ``[]`` unless the agent bundles skills of its own.
``color``      From the palette already used in the repo (e.g. ``teal``, ``red``).
               Pick one that is not overloaded within the target bundle.
``metadata.upstream`` The source URL — include **iff** the agent is adapted from
               an upstream. Omit entirely for from-scratch agents.
``metadata.repo`` Always ``https://github.com/nq-rdl/agent-extensions``.
============== =================================================================

--------------

Body
----

After the frontmatter:

1. For an **adapted** agent, a provenance HTML comment immediately after the
   frontmatter (see ``references/normalization.rst`` for the exact wording).
2. The **system prompt** — a top-level ``# Title`` heading, then the agent's role,
   expertise, approach, and checklists. For an adapted agent this is the upstream
   body, normalized but with its methodology and checklists retained verbatim.

Keep ``name`` in the frontmatter, the directory ``agents/<name>/``, and the changie
fragment's mention of the agent all spelling the same kebab-case string — the Stop
hook and the CI cross-checks key off it.
