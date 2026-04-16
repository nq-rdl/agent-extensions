---
name: cc-agent-teams
license: MIT
description: >-
  Claude Code agent teams — coordinate multiple independent Claude Code sessions
  working in parallel with shared task lists and inter-agent messaging. Use when
  the user asks to create a team, spawn teammates, coordinate parallel work, or
  describes work that benefits from parallel agents. Also triggers on TeamCreate,
  SendMessage, teammate mode, team lead, agent coordination, parallel sessions,
  or 'can we parallelize this with agents?'. Helps with planning parallel
  execution strategies and structuring team-based work.
argument-hint: "Describe the work to parallelize (e.g., 'review PR #42 for security and performance')"
compatibility: >-
  Requires Claude Code v2.1.32+. Split-pane mode requires tmux or iTerm2.
user-invocable: true
metadata:
  repo: https://github.com/nq-rdl/agent-skills
---

## User Input

```text
$ARGUMENTS
```

When the user invokes `/agent-teams`, design an agent team for their request.
If `$ARGUMENTS` is empty, ask the user what work they want to parallelize.

Follow the **Team Design Workflow** below to produce a ready-to-execute team
plan, then offer to create the team.

---

## Team Design Workflow

When designing a team, follow these steps:

1. **Understand the work** — what is the user trying to accomplish?
2. **Identify parallel lanes** — which parts can run independently?
3. **Choose team vs subagents** — see [references/subagent-vs-team.rst](references/subagent-vs-team.rst) for the decision flowchart. Only recommend a team when teammates genuinely need to communicate with each other or coordinate via shared tasks.
4. **Size the team** — aim for 2-5 teammates. More than 6 is rarely justified.
5. **Define roles and ownership** — each teammate needs a clear name, responsibility, and file ownership boundaries to prevent overwrites.
6. **Set dependency order** — which teammates must share interfaces before others can proceed?
7. **Choose display mode** — `in-process` (default, one terminal) or `tmux` (split panes, requires tmux/iTerm2).
8. **Consider quality gates** — recommend `TeammateIdle`, `TaskCreated`, or `TaskCompleted` hooks where appropriate.

### Output Format

Present the team design as:

```
## Team: <team-name>

**Goal**: <one-sentence description>

### Teammates

| # | Name | Role | Owns | Model |
|---|------|------|------|-------|
| 1 | ... | ... | ... | ... |

### Dependency Order
<which teammate feeds into which>

### Prompt
<the natural-language prompt the user should give Claude to create this team>

### Configuration
<any settings needed — env vars, display mode, permissions>
```

See [references/examples.rst](references/examples.rst) for complete team
configurations across common workflows.

---

# Agent Teams — Parallel Claude Code Coordination

## Overview

Agent teams coordinate multiple independent Claude Code instances working in
parallel. One session acts as the **team lead**, coordinating work, assigning
tasks, and synthesizing results. **Teammates** work independently, each in its
own context window, and communicate directly with each other.

This is fundamentally different from subagents. Read
[references/subagent-vs-team.rst](references/subagent-vs-team.rst) for the full
comparison — it matters because choosing the wrong one wastes tokens or limits
capability.

## Prerequisites

Agent teams are **experimental and disabled by default**. Before using them:

1. Enable the feature flag
2. Verify the configuration is correct

### Enable agent teams

Add to your project or user `settings.json`:

```json
{
  "env": {
    "CLAUDE_CODE_EXPERIMENTAL_AGENT_TEAMS": "1"
  }
}
```

**Settings file locations** (checked in this order):
- Project: `<project>/.claude/settings.json`
- Project local: `<project>/.claude/settings.local.json`
- User: `~/.claude/settings.json`
- User local: `~/.claude/settings.local.json`

### Verify or toggle configuration

Run the bundled config script:

```bash
# Check current status
bash scripts/check-config.sh

# Enable agent teams (writes to user settings)
bash scripts/check-config.sh --enable

# Disable agent teams
bash scripts/check-config.sh --disable
```

## When to Use Teams (Not Subagents)

Teams add real value when:

- **Teammates need to talk to each other** — subagents can only report back
  to the parent; teammates can message each other, challenge findings, and
  converge on answers together
- **Work benefits from parallel exploration** — multiple independent agents
  investigating different angles of a problem simultaneously
- **Tasks are large and independent** — each teammate owns a distinct piece
  of work (different files, modules, or domains)
- **You want competing hypotheses** — agents actively try to disprove each
  other's theories, like a scientific debate

Teams are **NOT** the right choice when:

- Tasks are sequential (A must finish before B starts)
- Multiple agents would edit the same files (causes overwrites)
- You just need a quick focused worker that reports back (use subagent)
- The coordination overhead exceeds the benefit of parallelism

## How to Create a Team

Tell Claude what you want in natural language. Be specific about roles:

```text
Create an agent team to review PR #142. Spawn three reviewers:
- One focused on security implications
- One checking performance impact
- One validating test coverage
Have them each review and report findings.
```

Claude handles TeamCreate, task list setup, and teammate spawning.

### Team sizing guidance

| Team size | Best for |
|-----------|----------|
| 2-3 | Focused tasks: review, investigate, prototype |
| 4-5 | Complex features: frontend + backend + tests + docs |
| 6+ | Rarely justified — coordination overhead dominates |

Aim for **5-6 tasks per teammate** to keep everyone productive. If you have
15 independent tasks, 3 teammates is a good starting point.

### Display modes

| Mode | Setting | When to use |
|------|---------|-------------|
| `in-process` | Default | All teammates in one terminal. Shift+Down to cycle. |
| `tmux` | Requires tmux or iTerm2 | Each teammate gets its own pane. |
| `auto` | Default behavior | Uses split panes if already in tmux, in-process otherwise. |

Set in `~/.claude.json`:

```json
{
  "teammateMode": "in-process"
}
```

Or per-session: `claude --teammate-mode in-process`

### Specify teammates and models

Claude decides the number of teammates based on your task, or you can specify:

```text
Create a team with 4 teammates to refactor these modules in parallel.
Use Sonnet for each teammate.
```

### Require plan approval for teammates

For risky changes, require teammates to plan before implementing:

```text
Spawn an architect teammate to refactor the authentication module.
Require plan approval before they make any changes.
```

The lead reviews and approves/rejects plans autonomously. Influence judgment with
criteria: "only approve plans that include test coverage."

### Use subagent definitions for teammates

Reference any subagent type (project, user, plugin, or CLI-defined) when
spawning a teammate. The teammate inherits that subagent's system prompt, tools,
and model:

```text
Spawn a teammate using the security-reviewer agent type to audit the auth module.
```

## Interacting with Teams

### Message teammates directly

- **In-process mode**: Shift+Down to cycle through teammates, then type.
  Press Enter to view a teammate's session, Escape to interrupt.
  Press Ctrl+T to toggle the task list.
- **Split-pane mode**: Click into a teammate's pane

### Task coordination

The shared task list coordinates work. Tasks have three states:
`pending` -> `in progress` -> `completed`. Tasks can have dependencies —
a pending task with unresolved dependencies cannot be claimed.

The lead can assign tasks explicitly, or teammates can self-claim the next
unassigned, unblocked task after finishing their current one. Task claiming uses
file locking to prevent race conditions.

### Quality gates with hooks

Three hooks enforce quality:

- **`TeammateIdle`**: runs when a teammate is about to go idle. Exit code 2
  sends feedback and keeps the teammate working.
- **`TaskCreated`**: runs when a task is being created. Exit code 2 prevents
  creation and sends feedback.
- **`TaskCompleted`**: runs when a task is being marked complete. Exit code 2
  prevents completion and sends feedback.

### Shut down and clean up

```text
Ask the researcher teammate to shut down
```

When done with the whole team:

```text
Clean up the team
```

Always use the lead to clean up — teammates should not run cleanup.

## Architecture

| Component | Role |
|-----------|------|
| **Team lead** | Main session that creates the team, spawns teammates, coordinates |
| **Teammates** | Separate Claude Code instances working on assigned tasks |
| **Task list** | Shared work items at `~/.claude/tasks/{team-name}/` |
| **Mailbox** | Inter-agent messaging system |

Team config lives at `~/.claude/teams/{team-name}/config.json` (auto-generated,
do not edit by hand — runtime state is overwritten on each update).

### Context rules

- Teammates load project context (CLAUDE.md, MCP servers, skills) automatically
- Teammates do **NOT** inherit the lead's conversation history
- The lead's spawn prompt is the only initial context
- Include task-specific details in spawn prompts (file paths, constraints)

### Permissions

Teammates start with the lead's permission settings. Pre-approve common
operations to reduce interruptions:

```json
{
  "permissions": {
    "allow": [
      "Read", "Glob", "Grep",
      "Bash(git *)",
      "Bash(npm test *)",
      "Bash(go test *)"
    ]
  }
}
```

### Token usage

Agent teams use significantly more tokens than a single session. Each teammate
has its own context window, and usage scales linearly with active teammates.
For research, review, and new feature work, the extra tokens are usually
worthwhile. For routine tasks, a single session is more cost-effective.

## Common Issues

| Issue | Fix |
|-------|-----|
| Teammates not appearing | Press Shift+Down to cycle; check task was complex enough |
| Too many permission prompts | Pre-approve common operations in permission settings |
| Teammates stopping on errors | Message them directly with additional instructions |
| Lead implements instead of delegating | Say "Wait for teammates to complete before proceeding" |
| Task status lagging | Check manually; tell lead to nudge the teammate |
| Orphaned tmux sessions | `tmux ls` then `tmux kill-session -t <name>` |

## Limitations (Experimental)

- No session resumption for in-process teammates (`/resume` won't restore them)
- One team per session (clean up before starting a new one)
- No nested teams (teammates cannot spawn their own teams)
- Lead is fixed for the lifetime of the team
- Split panes require tmux or iTerm2 (not VS Code terminal, Windows Terminal, Ghostty)
- Requires Claude Code v2.1.32+

## References

- [references/subagent-vs-team.rst](references/subagent-vs-team.rst) — detailed
  comparison with decision flowchart
- [references/examples.rst](references/examples.rst) — complete team
  configurations for common workflows

## Skill Commands

| Command | Description |
|---------|-------------|
| `bash scripts/check-config.sh` | Check if agent teams are enabled |
| `bash scripts/check-config.sh --enable` | Enable agent teams in user settings |
| `bash scripts/check-config.sh --disable` | Disable agent teams in user settings |
