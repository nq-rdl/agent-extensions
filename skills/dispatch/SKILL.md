---
name: dispatch
license: MIT
description: >-
  Use this skill when the user says "dispatch", "offload", "fan out",
  "fan-out", or asks to route tasks to external coding backends. Also trigger
  when the user asks to send work to jules, gemini-cli, agent-teams, or any
  other installed dispatch target. Teaches the dispatch pattern: identify task,
  choose backend, invoke backend skill, track status.
metadata:
  repo: https://github.com/nq-rdl/agent-skills
---

# dispatch — Tool-Agnostic Task Dispatch

Route work from a primary agent to one or more backend agents or services. This skill teaches the dispatch *pattern* — the backend skills do the actual work.

---

## When to Dispatch

Dispatch when any of these apply:

- **Task too large** — exceeds current context or would dominate the session
- **Parallel work** — multiple independent subtasks that benefit from concurrent execution
- **Different tool is better suited** — web search, async coding, specialized model
- **Fire-and-forget** — work that doesn't need immediate results
- **User explicitly asks** — "dispatch this", "offload to jules", "fan out"

Do **not** dispatch when:
- The task is small enough to complete inline
- The task requires tight back-and-forth with the user
- No suitable backend is available

---

## The Dispatch Cycle

Every dispatch follows four steps:

### 1. Identify

Determine what needs to be dispatched. Sources:

- User instruction ("dispatch issue #42 to jules")
- GitHub issue body (`gh issue view <number> --json title,body`)
- Task description from a plan or backlog
- Conversation context

Extract a clear, self-contained task description. The backend agent won't have your conversation history — give it everything it needs.

### 2. Choose

Select a backend. In order of preference:

1. **User specified** — "use jules for this" → use jules
2. **Explicit signal** — GitHub issue has a `dispatch:*` label, project config maps task types to backends → follow the signal
3. **Infer from task** — match the task to a backend category (see below)
4. **Ask** — when ambiguous, ask: "Which backend should I use for this?"

### 3. Invoke

Activate the backend's skill and pass the task context:

- Use the backend skill's primary entry point (e.g., `/jules`, `/gemini-cli`, `/agent-teams`)
- Include: task description, relevant file paths, branch name, any constraints
- For coding tasks: specify the target branch and expected deliverable (PR, diff, file changes)

### 4. Track

Report what was dispatched and how to check on it:

- Task reference (issue number, description)
- Backend used
- Session ID, team name, or other tracking handle
- Status: dispatched / failed / pending user input

---

## Backend Categories

Backends fall into three categories. Use these to guide selection when the user doesn't specify.

| Category | When to use | Pattern | Examples |
|----------|-------------|---------|----------|
| **CLI tools** | Standalone coding tasks, research, web search | Create session → fire-and-forget → poll status | jules, gemini-cli |
| **Agent teams** | Parallel subtasks needing coordination | Create team → fan out teammates → collect results | agent-teams |
| **External services** | Tasks routed to a remote API or service | API call → await result → report | pi.swe, opencode |

---

## Choosing a Backend

When the user doesn't specify, use this decision tree:

1. **Standalone coding change** (single feature, bug fix, refactor on a branch) → CLI tool (jules for async, gemini-cli for fast iteration)
2. **Web search or research** → gemini-cli (has built-in web search)
3. **Multiple independent subtasks** → agent-teams (parallel execution)
4. **Task needs a specific model or service** → whichever backend provides it
5. **Unsure** → ask the user

If multiple backends could work, prefer the simpler option. One jules session beats a team of one.

---

## Dispatch Patterns

### CLI Tool Dispatch (jules, gemini-cli)

```
1. Activate the backend skill
2. Create a session with the task description
   - Include branch name, file paths, constraints
   - Set the working directory or repo context
3. Do not block — the backend works asynchronously
4. Record the session ID for later status checks
5. Report: "Dispatched to [backend] — session [ID]"
```

To check later: use the backend skill's status or list command.

### Agent Team Dispatch (agent-teams)

```
1. Create a team for the overall goal
2. For each independent subtask:
   - Spawn a teammate with the subtask description
   - Include relevant context (file paths, branch, constraints)
3. Monitor progress via the team's task list
4. Collect results when teammates complete
5. Report: summary table of teammates and their status
```

Best for: 3+ independent subtasks, parallel investigation, multi-area changes.

### External Service Dispatch (pi.swe, opencode)

```
1. Activate the backend skill
2. Send the task via the service's API
3. Handle connection or auth errors (report and suggest checking setup)
4. Record the session or job reference
5. Report: "Dispatched to [service] — reference [ID]"
```

---

## Batch Dispatch

When dispatching multiple tasks:

| Scenario | Strategy |
|----------|----------|
| Independent tasks, same backend | Dispatch in parallel |
| Independent tasks, different backends | Dispatch each to its backend in parallel |
| Dependent tasks | Dispatch sequentially, pass outputs forward |
| Many tasks, same type | Create one agent-team with a teammate per task |

After batch dispatch, report a summary:

```
| # | Task | Backend | Status | Reference |
|---|------|---------|--------|-----------|
| 1 | Fix login bug | jules | dispatched | session-abc |
| 2 | Update docs | jules | dispatched | session-def |
| 3 | Research API options | gemini-cli | dispatched | session-ghi |
```

---

## Status Tracking

Each backend has its own status mechanism. After dispatching, always record:

- **What**: task description or issue reference
- **Where**: backend name and session/team/job ID
- **When**: dispatch timestamp

On follow-up ("check on the dispatched tasks"), use the backend skill's status commands to retrieve current state and report back.

---

## Error Handling

| Error | Action |
|-------|--------|
| Backend unreachable | Report the error. Suggest checking the backend's setup or credentials. |
| Auth failure | Report the specific auth requirement (API key, CLI login, token). |
| Unknown backend | List available backends (installed skills that accept dispatch). Ask the user to choose. |
| Task too vague | Ask the user to clarify scope, deliverable, or constraints before dispatching. |
| Partial failure in batch | Report which tasks succeeded and which failed. Offer to retry failures. |
