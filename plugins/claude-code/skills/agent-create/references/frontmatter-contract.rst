Skill and delegation contract
=============================

Author ``skills/<name>/SKILL.md`` with YAML frontmatter containing ``name``
(matching the canonical directory), a task-specific ``description``, and the
correct ``license``. Preserve ``metadata.upstream`` for imported content and
``metadata.repo`` for this catalog. API examples need a compatibility pin and
an instruction to verify the matching canonical source.

Keep the direct workflow in SKILL.md. Link ``references/subagent.rst`` and say
that the main agent reads it when delegation helps or the user requests a
subagent. Do not force every skill invocation to load the worker outline.

The outline contains:

* The worker's objective and scope, including read-only boundaries.
* Inputs: task, source paths, relevant context, and authorized changes.
* Needed capabilities and companion instructions, resolved from the installed
  environment. No automatic skill preload is available.
* The task-specific execution procedure and expected result with evidence.
* The parent's verification responsibilities and behavior if workers are unavailable.

Use the host's supported subagent mechanism; do not assume a custom agent type
exists. Model and permission selection belong to the host and user's settings.
A prose capability list does not enforce tool restrictions or create a sandbox.

Do not create a canonical or packaged ``agents/`` tree or registry ``agents:``
entry. The existing asctl structure validator accepts ``scripts/``,
``references/`` (rST only), and ``assets/`` inside skills.
