.. SPDX-License-Identifier: Apache-2.0
.. Derived from openai/codex-plugin-cc v1.0.6 (db52e28), Apache-2.0. Modified for rdl-agent-extensions.
.. Copied from skills/gpt-5-6-prompting/SKILL.md and adapted for pi:rescue.

GPT Prompting for pi:rescue
===========================

Source: OpenAI, `Prompting guidance for GPT-5.6 Sol
<https://developers.openai.com/api/docs/guides/prompt-guidance-gpt-5p6>`_,
verified 2026-09-29 for the Codex plugin's ``gpt-5-6-prompting`` skill. Apply
it only when the pi model's provider is ``openai`` or ``openai-codex``. If the
guide and this file disagree, follow the guide for wording and ``pi:rescue``
for helper flags. Other providers have no guidance here yet: forward their
task text unchanged.

Prompt pi like an operator: state the task once, give the output contract, set
follow-through defaults, and stop.

Core rules
----------

- **State instructions once.** GPT-5.6 follows one clear instruction; repeating
  it degrades quality. Prune redundant examples and restated rules.
- **One autonomy policy.** GPT-5.6 is proactive. Repeated "ask first" lines
  cause over-asking. Use one block that says when to proceed and when to stop
  for high-risk missing context. In print mode pi cannot ask the user, so a
  stop means returning the blocker in its answer.
- **No generic length prose.** "Be brief" or "be thorough" over-corrects. pi
  exposes no verbosity setting; put task-specific length in the output contract.
- One clear task per run; split unrelated asks.
- Say what done looks like.
- Add grounding and verification rules only where guesses would hurt.
- Prefer a better contract over a higher ``--thinking`` level.
- Use XML tags consistently.

Default recipe
--------------

- ``<task>``: the concrete job and the relevant repository or failure context.
- ``<structured_output_contract>`` or ``<compact_output_contract>``: exact
  shape, order and length.
- ``<autonomy_policy>``: one block for proceed-by-default and stop conditions.
- ``<verification_loop>`` or ``<completeness_contract>``: for debugging,
  implementation or risky fixes.
- ``<grounding_rules>`` or ``<citation_rules>``: for review, research or
  anything that could drift into unsupported claims.

When to add blocks:

- Coding or debugging: ``completeness_contract``, ``verification_loop`` and
  ``missing_context_gating``.
- Review: ``grounding_rules``, ``structured_output_contract`` and
  ``dig_deeper_nudge``. For local git changes, prefer ``/pi:review``.
- Research or recommendation: ``research_mode`` and ``citation_rules``.
- Write-capable tasks (``--write``): ``action_safety``, so pi stays narrow and
  avoids unrelated refactors.

For a continued session (``--resume-last``), send only the delta instruction
unless the direction changed materially.

Checklist
---------

1. Define the exact task and scope in ``<task>``.
2. Choose the smallest output contract that keeps the answer usable.
3. Write one ``<autonomy_policy>``.
4. Add verification, grounding and safety blocks only where needed.
5. Remove redundant instructions before sending.

Reusable blocks: `prompt-blocks.rst <prompt-blocks.rst>`_. Templates:
`prompt-recipes.rst <prompt-recipes.rst>`_. Failure modes:
`prompt-antipatterns.rst <prompt-antipatterns.rst>`_.
