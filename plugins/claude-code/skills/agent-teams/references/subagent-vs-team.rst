Subagent vs Agent Team: When to Use Which
=========================================

The Core Difference
-------------------

**Subagents** (the ``Agent`` tool) are workers within a single session.
They do focused work and report results back to the parent. They cannot
talk to each other. Think of them as running an errand — you send
someone out, they come back with an answer.

**Agent teams** are fully independent Claude Code sessions. Each
teammate has its own context window, can message any other teammate
directly, and coordinates through a shared task list. Think of them as a
meeting room — everyone can see and talk to everyone else.

Decision Flowchart
------------------

::

   Does the work require agents to discuss findings with each other?
   ├── YES → Agent Team
   │         (teammates can message each other, challenge findings, converge)
   └── NO
       ├── Is it a quick, focused task where only the result matters?
       │   └── YES → Subagent
       │             (lower token cost, simpler, results return to caller)
       └── NO
           ├── Do workers need to coordinate on who does what?
           │   └── YES → Agent Team
           │             (shared task list, self-claiming, dependency tracking)
           └── NO
               └── Subagent (default choice — simpler, cheaper)

Side-by-Side Comparison
-----------------------

+-------------------+------------------------------------+--------------------------------------------+
| Aspect            | Subagent (Agent tool)              | Agent Team                                 |
+===================+====================================+============================================+
| **How to invoke** | ``Agent`` tool in any session      | Natural language: “Create a team…”         |
+-------------------+------------------------------------+--------------------------------------------+
| **Enable          | No — always available              | Yes — needs                                |
| required?**       |                                    | ``CLAUDE_CODE_EXPERIMENTAL_AGENT_TEAMS=1`` |
+-------------------+------------------------------------+--------------------------------------------+
| **Context**       | Own context window; results return | Own context window; fully independent      |
|                   | to caller                          |                                            |
+-------------------+------------------------------------+--------------------------------------------+
| **Communication** | Report results back to parent only | Teammates message each other directly      |
+-------------------+------------------------------------+--------------------------------------------+
| **Coordination**  | Parent manages all work            | Shared task list with self-coordination    |
+-------------------+------------------------------------+--------------------------------------------+
| **Isolation**     | Optional worktree via              | Each teammate works in the same repo       |
|                   | ``isolation: "worktree"``          |                                            |
+-------------------+------------------------------------+--------------------------------------------+
| **Model           | Per-agent via ``model`` parameter  | Per-teammate via natural language or lead  |
| selection**       |                                    | decision                                   |
+-------------------+------------------------------------+--------------------------------------------+
| **Lifecycle**     | Ephemeral — dies when task         | Persistent — runs until shut down or team  |
|                   | completes                          | cleaned up                                 |
+-------------------+------------------------------------+--------------------------------------------+
| **Token cost**    | Lower — results summarized back    | Higher — each teammate is a separate       |
|                   |                                    | Claude instance                            |
+-------------------+------------------------------------+--------------------------------------------+
| **State storage** | None                               | ``~/.claude/teams/`` and                   |
|                   |                                    | ``~/.claude/tasks/``                       |
+-------------------+------------------------------------+--------------------------------------------+
| **Nesting**       | Subagents can spawn subagents      | Teammates cannot spawn their own teams     |
+-------------------+------------------------------------+--------------------------------------------+
| **User            | None — runs in background          | Direct: Shift+Down to message, or click    |
| interaction**     |                                    | pane                                       |
+-------------------+------------------------------------+--------------------------------------------+
| **Best for**      | Focused tasks where only the       | Complex work requiring discussion and      |
|                   | result matters                     | collaboration                              |
+-------------------+------------------------------------+--------------------------------------------+

When Subagents Win
------------------

**Quick research or verification:**

::

   Use the Agent tool to check if the auth module has any SQL injection vulnerabilities.

One agent, focused task, result comes back. No coordination needed.

**Parallel independent queries:**

::

   Launch 3 subagents to:
   1. Search for all uses of the deprecated API
   2. Check test coverage for the payments module
   3. Read the migration docs and summarize changes

Three independent queries, no need to talk to each other. Subagents are
cheaper and simpler here.

**Code generation with isolation:**

::

   Use the Agent tool with worktree isolation to implement the new parser
   without affecting the main branch.

Single focused task, isolated environment, result matters not the
process.

When Agent Teams Win
--------------------

**Competing hypotheses (debugging):**

::

   Users report the app exits after one message. Spawn 5 teammates to
   investigate different hypotheses. Have them talk to each other to try
   to disprove each other's theories.

The debate structure prevents anchoring bias. Sequential investigation
would stop at the first plausible explanation.

**Cross-layer feature development:**

::

   Create a team: one teammate on the API endpoints, one on the React
   components, one on the database migrations, one on tests.

Each owns different files, but they need to agree on interfaces and data
shapes. Messaging between teammates handles this.

**Parallel code review with synthesis:**

::

   Create a team of 3 reviewers: security, performance, test coverage.
   Have them each review PR #142 and report findings.

Independent review lenses, but the lead synthesizes findings across all
three for a complete picture.

**Research with cross-pollination:**

::

   Create a team to evaluate 3 database options. Each teammate deeply
   researches one option, then they discuss trade-offs together.

Each teammate becomes an expert, then the group discussion surfaces
trade-offs that individual research would miss.

Common Mistakes
---------------

Using teams for sequential work
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

**Wrong**: “Create a team — one to write the schema, one to write the
API, one to write tests.” (If the API depends on the schema and tests
depend on the API, only one agent works at a time.)

**Right**: Use subagents sequentially, or give a single session the full
task.

Using subagents when coordination matters
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

**Wrong**: “Launch 3 subagents to each implement a part of the feature.”
(They can’t coordinate on shared interfaces, leading to integration
bugs.)

**Right**: Create a team so teammates can discuss interfaces and
agreements.

Teams for simple tasks
~~~~~~~~~~~~~~~~~~~~~~

**Wrong**: “Create a team to fix this typo.” (Coordination overhead
exceeds the benefit.)

**Right**: Just fix it yourself. Or use a single subagent if you want
delegation.

Too many teammates
~~~~~~~~~~~~~~~~~~

**Wrong**: “Spawn 10 teammates for this feature.” (Token costs scale
linearly, coordination overhead grows quadratically.)

**Right**: Start with 3-5. Scale up only if the work genuinely benefits.
