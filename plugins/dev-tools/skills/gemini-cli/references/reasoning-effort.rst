Gemini Reasoning Effort & Thinking Configuration
================================================

Gemini exposes its "think harder" knob only through ``settings.json`` — there
is **no CLI flag** for reasoning effort. That makes it a power-user feature
most callers miss. This reference covers how to set it cleanly without
clobbering unrelated configuration.

The knob lives under ``modelConfigs`` in either:

- ``.gemini/settings.json`` — project scope (checked into the repo, applies
  to anyone running ``gemini`` in that working directory)
- ``~/.gemini/settings.json`` — user scope (your machine, every project)

Project settings win when both are present.

--------------

Quick Recipes
-------------

Bump a Gemini 3 model to HIGH reasoning (project scope)
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

The most common case. Drop this into ``.gemini/settings.json``:

.. code:: json

   {
     "modelConfigs": {
       "customAliases": {
         "gemini-3-pro-preview": {
           "model": "gemini-3-pro-preview",
           "generationConfig": {
             "thinkingConfig": { "thinkingLevel": "HIGH" }
           }
         }
       }
     }
   }

Now every ``gemini --model gemini-3-pro-preview ...`` invocation thinks at
HIGH. No flag needed at the call site.

Crank Gemini 2.5 thinking budget to the max
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Gemini 2.5 uses an integer token budget, not a level. ``-1`` means
"think as long as you need":

.. code:: json

   {
     "modelConfigs": {
       "customAliases": {
         "gemini-2.5-pro": {
           "model": "gemini-2.5-pro",
           "generationConfig": {
             "thinkingConfig": { "thinkingBudget": -1 }
           }
         }
       }
     }
   }

Agent-scoped override (only one agent thinks harder)
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

When you want a single sub-agent (e.g. ``codebaseInvestigator``) to use HIGH
without changing the base model behavior, use ``overrides`` with
``overrideScope``:

.. code:: json

   {
     "modelConfigs": {
       "overrides": [
         {
           "match": { "overrideScope": "codebaseInvestigator" },
           "config": {
             "generationConfig": {
               "thinkingConfig": { "thinkingLevel": "HIGH" }
             }
           }
         }
       ]
     }
   }

Turn thinking off for fast/cheap calls
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Useful for batch jobs where latency matters more than nuance:

.. code:: json

   {
     "modelConfigs": {
       "customAliases": {
         "gemini-2.5-flash-lite": {
           "model": "gemini-2.5-flash-lite",
           "generationConfig": {
             "thinkingConfig": { "thinkingBudget": 0 }
           }
         }
       }
     }
   }

--------------

Which Parameter to Use (Model Family Routing)
---------------------------------------------

The parameter name depends on the model generation. There is no overlap —
sending the wrong field is silently ignored.

+----------------------------+----------------------------+-------------------------+
| Model family               | Models                     | Parameter               |
+============================+============================+=========================+
| Gemini 2.5                 | ``gemini-2.5-pro``,        | ``thinkingBudget``      |
|                            | ``gemini-2.5-flash``,      | (integer, tokens)       |
|                            | ``gemini-2.5-flash-lite``  |                         |
+----------------------------+----------------------------+-------------------------+
| Gemini 3                   | ``gemini-3-pro-preview``,  | ``thinkingLevel``       |
|                            | ``gemini-3-flash-preview`` | (enum: HIGH / LOW)      |
+----------------------------+----------------------------+-------------------------+

Both live under ``generationConfig.thinkingConfig`` in the per-model config.

``thinkingBudget`` (Gemini 2.5)
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Integer token budget for the model's hidden reasoning trace.

+---------+----------------------------------------------------------+
| Value   | Meaning                                                  |
+=========+==========================================================+
| ``-1``  | Dynamic — model decides, can spend as many tokens as it  |
|         | needs. Best for hard problems.                           |
+---------+----------------------------------------------------------+
| ``0``   | Off — disable the thinking step entirely. Fastest,       |
|         | cheapest, lowest quality for hard tasks.                 |
+---------+----------------------------------------------------------+
| Other   | Hard cap in tokens. ``8192`` is the default for          |
|         | ``gemini-2.5-pro``. Pick higher for harder reasoning;    |
|         | lower to bound cost.                                     |
+---------+----------------------------------------------------------+

``thinkingLevel`` (Gemini 3)
~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Enum analog of OpenAI / Anthropic ``reasoning_effort``. The current build
ships only two values — **there is no ``MEDIUM``**.

+------------+-------------------------------------------------------+
| Value      | Meaning                                               |
+============+=======================================================+
| ``HIGH``   | Spend more compute on reasoning. Use for complex      |
|            | tasks where quality dominates latency.                |
+------------+-------------------------------------------------------+
| ``LOW``    | Spend less. Default for most flash-class invocations. |
+------------+-------------------------------------------------------+

--------------

Scope Choices: ``customAliases`` vs ``overrides``
-------------------------------------------------

Two different ways to apply a thinking config. Pick based on **whose**
behavior you want to change.

``customAliases`` — redefine the model entry
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Replaces the built-in alias. Every caller that resolves to that alias gets
the new config. Model-wide.

.. code:: json

   "modelConfigs": {
     "customAliases": {
       "gemini-3-pro-preview": { "model": "...", "generationConfig": { ... } }
     }
   }

Use when: you want one consistent reasoning policy for a model across all
agents and call sites in this project.

``overrides`` — match by scope
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

A list of ``{ match, config }`` entries. The CLI walks the list and applies
the first match. The most common selector is ``match.overrideScope``, which
matches the agent name (e.g. ``codebaseInvestigator``, ``planner``).

.. code:: json

   "modelConfigs": {
     "overrides": [
       { "match": { "overrideScope": "codebaseInvestigator" },
         "config": { "generationConfig": { "thinkingConfig": { "thinkingLevel": "HIGH" } } } }
     ]
   }

Use when: you want surgical control — crank thinking for the deep-research
agent, leave fast utility agents alone.

Overrides win over ``customAliases`` for matched scopes.

--------------

Mapping from OpenAI / Anthropic ``reasoning_effort``
----------------------------------------------------

If you're porting a config from another provider, here's the cheat sheet:

+----------------------+-----------------------------+-----------------------------+
| ``reasoning_effort`` | Gemini 3 (``thinkingLevel``)| Gemini 2.5                  |
|                      |                             | (``thinkingBudget``)        |
+======================+=============================+=============================+
| ``low``              | ``LOW``                     | ``2048`` (or ``0`` for off) |
+----------------------+-----------------------------+-----------------------------+
| ``medium``           | ``LOW`` (no MEDIUM yet) —   | ``8192`` (the default)      |
|                      | or pick ``HIGH`` if quality |                             |
|                      | matters                     |                             |
+----------------------+-----------------------------+-----------------------------+
| ``high``             | ``HIGH``                    | ``-1`` (dynamic) or         |
|                      |                             | ``24576``                   |
+----------------------+-----------------------------+-----------------------------+

The medium row is the awkward one — Gemini 3 doesn't have an exact match, so
choose by intent (latency-sensitive → LOW, quality-sensitive → HIGH).

--------------

Merging Into Existing ``settings.json``
---------------------------------------

``settings.json`` typically already contains keys like ``general``, ``ide``,
``security``, ``ui``, and ``mcpServers``. **Deep-merge** the
``modelConfigs`` block in — don't overwrite the whole file.

Manual edit pattern
~~~~~~~~~~~~~~~~~~~

1. Read the existing file (``cat .gemini/settings.json`` — or treat as
   ``{}`` if it doesn't exist; ``mkdir -p .gemini`` first if needed).
2. Add or merge the ``modelConfigs`` key alongside the existing top-level
   keys.
3. Inside ``modelConfigs``, merge ``customAliases`` / ``overrides``
   sub-keys without dropping existing entries.
4. Write back atomically.

``jq``-based merge (shell)
~~~~~~~~~~~~~~~~~~~~~~~~~~

For automation, ``jq`` can deep-merge a snippet without touching unrelated
keys:

.. code:: bash

   mkdir -p .gemini
   touch .gemini/settings.json

   # Idempotent: if the file is empty, start from {}; otherwise reuse.
   EXISTING=$(jq '.' .gemini/settings.json 2>/dev/null || echo '{}')

   # The patch — only the modelConfigs subtree we want to add.
   PATCH='{
     "modelConfigs": {
       "customAliases": {
         "gemini-3-pro-preview": {
           "model": "gemini-3-pro-preview",
           "generationConfig": {
             "thinkingConfig": { "thinkingLevel": "HIGH" }
           }
         }
       }
     }
   }'

   # Deep-merge with `*` (jq recursive merge) and write atomically.
   jq -s '.[0] * .[1]' <(echo "$EXISTING") <(echo "$PATCH") \
     > .gemini/settings.json.tmp && \
     mv .gemini/settings.json.tmp .gemini/settings.json

Two cautions:

- ``jq``'s ``*`` operator merges *objects* recursively but **replaces**
  arrays. If you're touching the ``overrides`` array, read it, append your
  entry, write the whole list back — don't expect ``*`` to concatenate.
- After the merge, validate: ``jq '.modelConfigs' .gemini/settings.json``.

Verifying the config took effect
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

After editing, sanity-check by running a prompt and watching response time.
Gemini doesn't echo the resolved thinking config back, so:

- A HIGH-reasoning prompt should noticeably take longer than the same
  prompt with the default.
- For ``thinkingBudget: 0`` (off), responses to reasoning-heavy prompts
  should degrade in quality compared to the default ``8192``.

If you suspect the config isn't being picked up, run
``gemini --output-format stream-json -p "..." --yolo`` and inspect the
``model`` field in the ``init`` event — it should match the alias whose
config you edited.

--------------

Where to Look Upstream
----------------------

In a local Gemini CLI install (paths relative to ``@google/gemini-cli`` in
``node_modules`` or the global npm prefix):

- ``bundle/docs/cli/generation-settings.md`` — full ``modelConfigs``
  overview
- ``bundle/docs/reference/configuration.md`` — reference for
  ``aliases``, ``customAliases``, and ``overrides``
- ``bundle/chunk-*.js`` (search for ``DEFAULT_MODEL_CONFIGS``) — the
  built-in alias table, including the ``ThinkingLevel.HIGH`` example for
  ``chat-base-3``
