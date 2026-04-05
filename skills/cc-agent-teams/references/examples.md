# Agent Team Examples

Complete examples showing how to set up and use agent teams for common
workflows. Each includes the setup prompt, expected team structure, and
tips for getting the best results.

---

## 1. Parallel Code Review

**When**: PR is large or touches multiple domains. A single reviewer tends to
gravitate toward one type of issue at a time.

**Prompt**:
```text
Create an agent team to review PR #142. Spawn three reviewers:
- One focused on security implications (auth, input validation, injection)
- One checking performance impact (queries, allocations, complexity)
- One validating test coverage (edge cases, error paths, assertions)
Have them each review independently and report findings.
```

**Expected team structure**:
- Lead: coordinates, synthesizes final review
- security-reviewer: reads diff with security lens
- performance-reviewer: profiles critical paths
- test-reviewer: checks coverage gaps

**Tips**:
- Each reviewer applies a different filter to the same diff
- The lead synthesizes findings into a single coherent review
- Add hook on `TaskCompleted` to require severity ratings

---

## 2. Debugging with Competing Hypotheses

**When**: Root cause is unclear and you want to avoid anchoring bias.

**Prompt**:
```text
Users report the WebSocket connection drops after exactly one message.
Spawn 5 agent teammates to investigate different hypotheses:
1. Server-side connection lifecycle (close after response?)
2. Client reconnection logic (creating new connection per message?)
3. Proxy/load balancer timeouts (nginx, cloudflare)
4. Authentication token expiry during connection
5. Message framing or protocol mismatch

Have them talk to each other to try to disprove each other's theories,
like a scientific debate. Update a findings doc with whatever consensus
emerges.
```

**Expected team structure**:
- Lead: moderates debate, maintains findings doc
- 5 investigators: each deeply explores one hypothesis
- Investigators message each other to challenge findings

**Tips**:
- The debate structure is the key mechanism — it prevents the first
  plausible theory from becoming the accepted answer
- More teammates (5) is justified here because each hypothesis is
  genuinely independent
- "Talk to each other" is critical — without it, this is just 5 subagents

---

## 3. Cross-Layer Feature Development

**When**: Feature spans multiple layers (API, frontend, database, tests) and
teammates need to agree on interfaces.

**Prompt**:
```text
We're adding a user notification system. Create a team:
- database-teammate: design the schema and write migrations
- api-teammate: implement the REST endpoints and WebSocket events
- frontend-teammate: build the notification bell component and dropdown
- test-teammate: write integration tests for the full flow

Database teammate should share the schema with API teammate.
API teammate should share endpoint contracts with frontend teammate.
Test teammate should wait for interfaces to stabilize before writing tests.
Require plan approval for the database teammate before they run migrations.
```

**Expected team structure**:
- Lead: coordinates interface agreements, reviews plans
- database: owns `migrations/`, `models/`
- api: owns `routes/notifications/`, `services/`
- frontend: owns `components/Notifications/`
- test: owns `tests/integration/notifications/`

**Tips**:
- Explicit file ownership prevents overwrites
- "Require plan approval" for risky changes (database migrations)
- Dependency order: database -> API -> frontend, with tests last
- Each teammate messages the next when their interface is ready

---

## 4. Research and Evaluate Options

**When**: You need to deeply evaluate multiple alternatives and compare
trade-offs.

**Prompt**:
```text
We need to choose a message queue for our event system. Create a team
of 3 researchers:
- One to deeply evaluate RabbitMQ (setup, ops burden, Go client ecosystem)
- One to evaluate NATS (JetStream, clustering, performance characteristics)
- One to evaluate Redis Streams (we already run Redis, so lower ops cost)

Each should build a small proof-of-concept and benchmark it. Then have
them discuss trade-offs together before the lead writes a recommendation
doc.
```

**Expected team structure**:
- Lead: writes final recommendation with trade-off matrix
- rabbitmq-researcher: builds PoC, benchmarks, documents findings
- nats-researcher: builds PoC, benchmarks, documents findings
- redis-researcher: builds PoC, benchmarks, documents findings
- Group discussion phase after individual research

**Tips**:
- Each researcher becomes a genuine expert in their option
- The discussion phase surfaces trade-offs that individual research misses
- The lead's synthesis is informed by actual evidence, not vibes

---

## 5. Documentation Audit

**When**: Docs are spread across many files and you want thorough coverage.

**Prompt**:
```text
Create a team to audit our documentation. Spawn 3 teammates:
- One to check all README files for accuracy (do code examples still work?)
- One to verify API docs match the actual implementation
- One to find undocumented features by scanning the codebase

Have them share findings and flag contradictions between docs and code.
```

**Expected team structure**:
- Lead: prioritizes fixes, creates issues
- readme-checker: runs code examples, flags broken ones
- api-docs-checker: compares OpenAPI spec vs actual routes
- feature-scanner: greps for undocumented public APIs

---

## 6. Refactoring with Safety Net

**When**: Large refactor where you want parallel implementation with
continuous testing.

**Prompt**:
```text
We're migrating from Express to Hono. Create a team:
- migrator-1: convert routes in src/routes/auth/
- migrator-2: convert routes in src/routes/api/
- migrator-3: convert middleware and plugins
- test-runner: continuously run the test suite and report failures to
  the migrators

Test runner should message the relevant migrator whenever a test breaks.
Migrators should not edit each other's files.
```

**Expected team structure**:
- Lead: tracks overall progress, handles conflicts
- migrator-1: owns `src/routes/auth/`
- migrator-2: owns `src/routes/api/`
- migrator-3: owns `src/middleware/`, `src/plugins/`
- test-runner: runs tests, messages migrators on failures

**Tips**:
- Explicit file ownership is critical — overlapping edits cause overwrites
- Test runner acts as continuous feedback loop
- Good candidate for `TeammateIdle` hooks to prevent migrators stopping too early

---

## Settings Configuration

### Minimal setup (enable teams only)

```json
{
  "env": {
    "CLAUDE_CODE_EXPERIMENTAL_AGENT_TEAMS": "1"
  }
}
```

### Full setup (teams + display mode + permissions)

```json
{
  "env": {
    "CLAUDE_CODE_EXPERIMENTAL_AGENT_TEAMS": "1"
  }
}
```

In `~/.claude.json` (global config):

```json
{
  "teammateMode": "in-process"
}
```

Pre-approving common operations in permissions reduces interruptions when
teammates request permission:

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
