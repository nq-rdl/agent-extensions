---
license: CC-BY-4.0
description: >-
  Create, save, and reuse Claude Code dynamic workflows — JavaScript
  orchestration scripts that Claude writes and a runtime executes to fan out to
  many subagents at scale. Use when the user wants to build a workflow, automate
  a repeatable multi-agent process, codify an orchestration, or save a run for
  later. Also triggers on `ultracode`, `/workflows`, `.claude/workflows/`,
  `/deep-research`, "orchestrate subagents", "codebase audit", "large
  migration", "cross-checked research", or "make this a reusable command". The
  skill first decides whether a workflow is even the right tool (vs a subagent,
  skill, or agent team), then drives the author-and-save loop and the
  `.claude/workflows/` distribution rules.
argument-hint: "Describe the task to turn into a workflow (e.g. 'audit every API route for missing auth checks')"
compatibility: >-
  Requires Claude Code v2.1.154+ for dynamic workflows. Monorepo path-walking
  requires v2.1.178+. Before v2.1.160 the trigger keyword was `workflow` instead
  of `ultracode` (natural-language requests work in both).
user-invocable: true
metadata:
  repo: https://github.com/nq-rdl/agent-extensions
---

## User Input

```text
$ARGUMENTS
```

When the user invokes `/claude-code:create-workflow`, help them produce a saved,
reusable workflow for the task in `$ARGUMENTS`. If empty, ask what repeatable
multi-agent task they want to codify.

**Always run the decision gate first** — most tasks should *not* be a workflow.
Only proceed to authoring when the gate says a workflow is the right tool.

---

## Step 1 — Decision gate (do this before anything else)

A workflow is the heaviest of four primitives. The real difference is **who holds
the plan**. Steer the user to the lightest tool that fits.

| Use… | When | Plan held by |
|------|------|--------------|
| **Skill** | Reusable *instructions* one agent follows | Claude, following the prompt |
| **Subagent** | Offload one focused side-task; only the summary matters | Claude, turn by turn |
| **Agent team** | A few workers that must **talk to each other** / challenge findings | Lead + teammates, turn by turn |
| **Workflow** | **Repeatable, codified** fan-out to **dozens–hundreds** of agents | The **JavaScript script** |

Pick a **workflow** only when *all* of these hold:

- The orchestration is worth **codifying and rerunning** (a per-branch review, a
  recurring audit), not a one-off.
- The task needs **more agents than one conversation can coordinate** — bug
  sweeps across a repo, 500-file migrations, research cross-checked across many
  sources, drafting a plan from several independent angles.
- You want intermediate results to stay in **script variables**, keeping Claude's
  context holding only the final answer.

If the user just needs collaboration between a handful of agents, that's an
**agent team** (`/claude-code:agent-teams`). If they want reusable instructions,
that's a **skill** (`/claude-code:...` via the skill catalog). If it's a single
delegated lookup, that's a **subagent**. Say so and stop.

> Subagents are the worker primitive a workflow orchestrates; an agent team can
> reuse subagent *definitions* as teammate roles. Workflows don't "call skills" —
> the agents they spawn load skills by context, the same as any session.

## Step 2 — Frame the task for the runtime

Workflows have a fixed shape you must design *for*, not against:

- **The script coordinates; agents do the work.** The script itself has **no
  filesystem or shell access** — only its spawned agents read, write, and run
  commands. Frame the task as "fan out N agents, each does X, collect/compare
  results," not "the script edits files."
- **Codify a quality pattern, not just parallelism.** The payoff over plain
  subagents is repeatable structure: have agents **adversarially review** each
  other's findings, or draft a plan from several angles and weigh them, before
  reporting.
- **Stage gating needs separate workflows.** There is **no mid-run user input** —
  only agent permission prompts can pause a run. For sign-off between stages, run
  each stage as its own workflow.
- **Respect the caps:** up to **16 concurrent agents** (fewer on low-CPU
  machines) and **1,000 agents total per run**. Design the fan-out to fit.

## Step 3 — Have Claude write it

You don't hand-author the JavaScript — **Claude writes the script** from the task
description. Trigger it one of two ways:

- **Single task:** include the keyword **`ultracode`** in the prompt (or just say
  "use a workflow"). Example: `ultracode: audit every API endpoint under
  src/routes/ for missing auth checks`.
- **Whole session:** `/effort ultracode` — Claude plans a workflow for every
  substantive task until the session ends or you drop back with `/effort high`.

Claude shows the planned phases and asks to approve before running (the prompt's
frequency depends on permission mode; `Ctrl+G` opens the script, `Tab` edits the
prompt first). Iterate on the task description until a run does what you want.

> The run writes its script to a file under `~/.claude/projects/` and Claude gets
> the path — ask for it to read, diff, or edit the orchestration directly.

## Step 4 — Save for reuse

Once a run is good, save its script as a command: run `/workflows`, select the
run, press **`s`**, and `Tab` to pick the location:

| Location | Scope |
|----------|-------|
| `.claude/workflows/` | **Project — committed to the repo, shared with everyone who clones it** |
| `~/.claude/workflows/` | Personal — every project, only you |

Saved workflows run as `/<name>` and appear in `/` autocomplete alongside
built-ins like `/deep-research`. If a project and personal workflow share a name,
the **project** one wins.

**Monorepo (v2.1.178+):** saving to the project location writes to the closest
existing `.claude/workflows/` between your cwd and the repo root (or the repo root
if none exists). Workflows load from *every* `.claude/workflows/` along that path;
on a name clash the one nearest your cwd runs.

## Step 5 — Parameterize with `args`

A saved workflow reads invocation input from a global named **`args`**:

```text
> Run /triage-issues on issues 1024, 1025, and 1030
```

Claude passes the input as **structured data**, so the script calls array/object
methods on `args` directly — no parsing. If omitted, `args` is `undefined`.

---

## Distribution reality (important)

**Workflows cannot be bundled into a plugin or installed from a marketplace.**
The recognized plugin components are skills, agents, hooks, MCP servers, LSP
servers, monitors, and themes — `workflows/` is not one of them, and plugins are
copied into a cache that workflow discovery never scans. The **only** sharing
mechanisms are the two `.claude/workflows/` locations above. To share a workflow
with a team, **commit it to `.claude/workflows/` in the repo**. To make the
*authoring* reusable instead, package a skill like this one.

## Cost & model

A run spawns many agents, so it can cost meaningfully more than doing the task in
conversation; runs count toward plan usage and rate limits. Before a large run:

- **Gauge on a slice first** — one directory, not the whole repo — and watch
  per-agent token usage in `/workflows`; stop anytime without losing completed work.
- Every agent uses the **session model** unless the script routes a stage
  elsewhere. Check `/model` before a big run, and ask Claude to route low-stakes
  stages to a smaller model.

## Permissions

Your session permission mode controls **only the launch prompt**. The subagents a
workflow spawns always run in **`acceptEdits`** and inherit your tool allowlist
regardless of session mode — file edits are auto-approved. Shell commands, web
fetches, and MCP tools **not** in your allowlist still prompt mid-run, so
**pre-allowlist what the agents need** before a long run to avoid interruptions.
In `claude -p` / Agent SDK there's no prompt; runs start immediately.

## Turn workflows off

`disableWorkflows: true` in `~/.claude/settings.json` (or managed settings for an
org), the `CLAUDE_CODE_DISABLE_WORKFLOWS=1` env var, or the Dynamic workflows
toggle in `/config`. When disabled, bundled workflow commands vanish and
`ultracode` no longer triggers.

## Resumption

A paused run resumes **within the same session** (completed agents return cached
results). **Exiting Claude Code loses progress** — the next session starts the
workflow fresh.

---

## Verify against canonical source

Dynamic workflows are new and evolving (keyword, monorepo paths, and limits have
all changed across versions). When being wrong would mislead, verify against the
canonical docs: <https://code.claude.com/docs/en/workflows>. Related primitives:
[subagents](https://code.claude.com/docs/en/sub-agents),
[agent teams](https://code.claude.com/docs/en/agent-teams),
[plugins reference](https://code.claude.com/docs/en/plugins-reference).
