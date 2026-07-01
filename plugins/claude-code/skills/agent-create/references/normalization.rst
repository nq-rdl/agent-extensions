Upstream Normalization
======================

How to convert an upstream ``<name>.agent.md`` (almost always from
``github/awesome-copilot``, MIT) into a repo ``agents/<name>/agent.md`` that satisfies
``references/frontmatter-contract.rst``. This codifies the conversion recorded in the
provenance comment of the existing adapted agents (e.g.
``agents/go-mcp-expert/agent.md``).

The guiding principle: **change the wiring, keep the substance.** Normalize the
frontmatter and any tool/invocation prose to Claude Code conventions, but retain the
upstream methodology, checklists, and voice verbatim — that content is the value.

--------------

Frontmatter conversion
----------------------

Upstream ``.agent.md`` frontmatter is VS Code / Copilot shaped. Rewrite it to the
repo contract:

- **``name``** — set to the kebab-case agent name, equal to the directory
  ``agents/<name>/``.
- **``description``** — rewrite (or lift) into a **triggering** folded scalar in the
  "Delegate to this agent when…" voice. This is the routing signal; make it specific.
- **``tools``** — **strip VS Code-specific tool namespaces** (e.g. ``editFiles``,
  ``codebase``, ``search``, ``runCommands``, MCP-namespaced tool ids) and map to
  Claude Code's tool names: ``Read``, ``Write``, ``Edit``, ``Grep``, ``Glob``,
  ``Bash``, ``WebFetch``, etc. Keep the list **minimal** — only what the agent needs.
- **``license``** — set to the **upstream's** license: ``MIT`` for
  ``github/awesome-copilot``.
- **``model``** → ``inherit``; **``skills``** → ``[]`` (unless it bundles skills);
  **``color``** → a repo-palette color.
- **``metadata.upstream``** → the source file URL; **``metadata.repo``** → the repo.
- Drop upstream-only keys that have no repo meaning.

--------------

Provenance comment
------------------

Immediately after the closing ``---``, add the HTML comment (this is the exact form
used across the adapted agents):

.. code:: html

   <!--
   Derived from github/awesome-copilot (MIT) — see `metadata.upstream` above for the
   original. Conversion: stripped VS Code-specific tool namespace; normalized
   `$ARGUMENTS` / tool invocation prose; retained methodology and checklists verbatim.
   -->

If the upstream is **not** awesome-copilot, adjust the source name and license in the
first line accordingly, and describe the actual conversion you performed.

--------------

Body conversion
---------------

- **Normalize invocation prose.** Rewrite VS Code-isms — ``$ARGUMENTS`` placeholders,
  "use the *Run Command* tool", ``#tool`` mentions, Copilot chat-mode phrasing — into
  plain, tool-agnostic instructions that read naturally for a Claude Code subagent.
- **Retain methodology and checklists verbatim.** The numbered approaches, expertise
  lists, review checklists, and response-style sections are the substance — keep them.
- **Keep a single top-level ``# Title``** heading, then the role and sections.
- Do **not** invent new capabilities or tighten/loosen the agent's remit; a faithful
  adaptation is the goal.

--------------

Fetch fallback
--------------

Fetch the upstream with ``WebFetch``. If the fetch fails (network, auth, moved file),
fall back to content the contributor pastes in. If neither the URL nor pasted content
is available, **stop** — there is nothing to normalize.
