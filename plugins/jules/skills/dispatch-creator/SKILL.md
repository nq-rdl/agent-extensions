---
name: jules-dispatch-creator
license: CC-BY-4.0
description: >-
  Use when the user wants to set up, add, configure, or adapt Jules GitHub
  Actions dispatch workflows for a repository. Triggers when they say "adapt
  the Jules workflows", "set up Jules dispatch", "add Jules to my repo", "wire
  up Jules", "write Jules prompts for this project", "configure Jules for this
  repo", "integrate Jules", or "onboard Jules as a coding agent". Also applies
  when the user is adding Jules to an existing GitHub project and needs tailored
  workflow YAML files.
metadata:
  repo: https://github.com/nq-rdl/agent-skills
---

# Jules Dispatch Workflow Adapter

Your job is to write Jules GitHub Actions dispatch workflows tailored to the
current project. Jules is Google's async AI coding agent — each workflow fires
when a GitHub issue comment mentions a `@jules-*` handle. The only thing that
varies between projects is the `prompt:` block; the surrounding YAML is fixed
boilerplate provided as template files in this skill.

Work through the following phases.

---

## Phase 0 — Configure

Before reading the codebase, ask the user two quick questions:

1. **Which workflow(s)?** Available: `swe`, `security`, `docs`, `infra`,
   `ci-review`. If the user doesn't specify, generate all applicable ones.
2. **Secret name** — What GitHub Actions secret holds the Jules API key?
   (Each team member typically has their own token; name it accordingly, e.g.
   `JK_JULES_API`, `AB_JULES_API`.)

If the user doesn't specify which workflows, generate all of them. Store the
secret name — it replaces `[SECRET_NAME]` in every template.

---

## Phase 1 — Assess the project

Build an accurate picture of the project by reading in parallel:

- **`CLAUDE.md`** at the repo root — project conventions, commands, architecture.
  Note whether it is comprehensive; if so, the SWE prompt can defer to it rather
  than reproducing its contents.
- **Root `README.md`** — first-impression overview.
- **Structural doc files** — if any of these exist, read them; they provide
  stable context worth including in prompts:
  - `ARCHITECTURE.md` — system/infra topology, languages, deployment setup
  - `DESIGN.md` — layout decisions, component rationale
  - `CONTRIBUTING.md` — contribution patterns, LLM-specific conventions
- **`docs/`** — skim (don't exhaustively read) to understand the project domain
  and any explicit quality standards already in use for writing.
- **Source tree** — launch an Explore subagent to scan the codebase. Direct
  reads are sufficient for well-known top-level files (CLAUDE.md, README.md),
  but the source tree assessment should use the Explore agent because it follows
  nested directories and surfaces non-obvious files that glob patterns miss:
  infrastructure configs, Compose files, CI definitions, test fixtures, and
  supporting scripts. If you rely only on direct tool calls here you will miss
  files that matter for the prompts — for example, a Compose file that defines
  the local development cluster, or a CI workflow that constrains what Jules
  can validate.

### Conflicting sources

Treat docs and code differently:

- **Docs = stated intention.** Content describing planned or in-progress work is
  aspirational — Jules is expected to close those gaps. Never weaken or remove it.
- **Code = current reality.** If a doc describes something the code contradicts
  (a renamed module, a removed command, a missing directory), that is a factual
  error. Note it, but do *not* try to encode the fix into the Jules system prompt.
  Factual errors belong in a GitHub issue or `TODO.md` — encoding them in the
  system prompt creates stale context that misleads Jules over time.

### Report before proceeding

Summarise your findings:

1. A 2–4 sentence project description (domain, stack, key concepts).
2. Which structural doc files were found (`ARCHITECTURE.md`, `DESIGN.md`,
   `CONTRIBUTING.md`) — these will be referenced in the relevant prompts.
3. Any factual errors found — file and discrepancy — with a suggestion to file
   them as GitHub issues or TODO entries rather than embedding fixes in the prompt.
4. Ask: "Anything else Jules should know before I draft the prompts?"

Wait for the user's response before moving to Phase 2.

---

## Phase 2 — Draft the prompts

For each requested workflow, draft a `prompt:` block that gives Jules enough
context to work autonomously. The goal is to teach Jules *how to orient itself*,
not to pre-load it with a snapshot of the codebase. Snapshots go stale; process
doesn't.

### Quick reference by role

| Role | Key constraint | Key reference doc |
|------|---------------|-------------------|
| `swe` | Keep sparse — CLAUDE.md covers conventions | `CLAUDE.md`, `ARCHITECTURE.md` |
| `security` | Describe risk patterns, not specific files | `ARCHITECTURE.md`, `CLAUDE.md` |
| `docs` | Read code first, verify every claim | `ARCHITECTURE.md`, `DESIGN.md`, `CONTRIBUTING.md` |
| `infra` | No live infra access — repo-local validation only | `ARCHITECTURE.md`, `CONTRIBUTING.md` |
| `ci-review` | Triggered by CI failure, not a human mention; uses `workflow_run` trigger | CI workflow definitions, `CONTRIBUTING.md` |

See the per-role sections below for full guidance on each.

### Prompt structure (follow this order for every workflow)

```
[Role + project overview — one sentence]

[Orientation process or key conventions — stable, non-stale guidance]

[Role-specific reference material — see per-role guidance below]

[Issue context — injected by GitHub Actions, keep interpolations verbatim]
## GitHub Issue #${{ github.event.issue.number }}: ${{ steps.issue.outputs.title }}

Labels: ${{ steps.issue.outputs.labels }}

${{ steps.issue.outputs.body }}

[Triggering comment — keep verbatim, always last]
## Triggering comment

${{ github.event.comment.body }}

[Instructions — role-specific, ends with "open a PR when complete"]
```

### Instruction density

Match the density and specificity of the instructions block to what Jules
actually needs for that role:

- **SWE** — keep sparse. The task is free-form; CLAUDE.md covers conventions.
  Over-specifying the instructions poisons context when the issue asks for
  something slightly different. A brief "implement the request; open a PR" is
  enough.
- **Security / docs / infra** — use structured constraints. These roles have
  narrower operational boundaries and Jules benefits from explicit expectations:
  what it is allowed to do, what it must not do, what output format is expected,
  and a clear action to close with ("open a pull request").

---

### SWE prompt guidance

If a comprehensive `CLAUDE.md` exists: keep the prompt thin. Reference CLAUDE.md
explicitly — Jules will read it. Don't reproduce its contents in the prompt;
doing so creates a second source of truth that will diverge from the real one.

**Orientation notes must point to documents, not encode facts.** If you discover
during Phase 1 that the project has a non-obvious layout (e.g. Python source
under `backend/` rather than at the repo root), resist the temptation to encode
that fact directly in the prompt. Instead, point Jules to the stable document
that describes it — `docs/ARCHITECTURE.md`, or wherever the layout is
documented. A prompt that says "all Python source lives under `backend/`"
becomes incorrect the moment a PR moves things and the docs are updated. A
prompt that says "read `docs/ARCHITECTURE.md` for current project layout"
remains accurate indefinitely, and Jules benefits automatically from every
docs improvement the docs workflow makes. This principle applies to any
structural fact that could change: entry points, module names, directory
conventions. If the structural documentation doesn't yet exist or is stale,
file a GitHub issue — don't encode the correction in the system prompt.

```
You are a Software Engineer working on [project name] — [one-sentence description].

Read `CLAUDE.md` at the repo root for the authoritative project layout, commands,
testing strategy, and conventions before starting work. Read `docs/ARCHITECTURE.md`
for the current system topology and entry points.

[Add only what neither CLAUDE.md nor ARCHITECTURE.md covers — e.g. a
project-specific pattern that matters for this workflow but isn't documented
anywhere stable.]

## GitHub Issue ...
## Triggering comment
## Instructions
Implement the request described in the issue. Open a pull request when complete.
```

If no CLAUDE.md exists: include enough pattern-based context for Jules to
navigate (architecture style, key directories, test runner) — but prefer
conventions over exhaustive file lists, which go stale.

---

### Security prompt guidance

Describe risk *patterns* tied to this stack, not specific files. The issue tells
Jules where to focus; the system prompt should help Jules recognise *what kind of
threats* to look for, not prescribe which files to audit. Specific file paths
become incorrect as the codebase evolves.

Point Jules to `docs/ARCHITECTURE.md` (and `CLAUDE.md` if it exists) for
orientation — the same principle applies here as for SWE: encode the *process*
of reading stable documents, not the structural facts those documents contain.
A system prompt that says "read `docs/ARCHITECTURE.md` to understand current
structure" remains accurate after a refactor; one that names specific source
directories will lie to Jules from the moment those directories are moved.

Pattern-based guidance looks like:

- "This stack generates SQL from config files — SQL injection from config values
  is a risk class to assess."
- "User-controlled strings are used to construct filesystem paths — path traversal
  is a risk class."
- "Credentials are passed through environment variables — check for leakage into
  logs or error responses."

Keep the severity model and PR conventions stable. Let Jules discover which files
are affected from the issue and by reading the code.

**Instructions block for security** should specify:
- What to produce (findings as PR comments or a report file)
- Severity classification expected (e.g. critical / high / medium / low)
- Whether to fix or only report
- "Open a pull request with your findings when complete."

---

### Docs prompt guidance

The user maintains three structural doc files across their projects. If any are
present (discovered in Phase 1), reference them explicitly in the prompt — they
are stable anchors, not ephemeral `docs/` subpaths:

- **`ARCHITECTURE.md`** — system topology, infra, languages, setup
- **`DESIGN.md`** — component layout, design decisions
- **`CONTRIBUTING.md`** — contribution patterns; often contains LLM-specific
  conventions Jules should follow

Do NOT list ad-hoc files under `docs/`. Those paths change frequently; listing
them leads Jules to edit the wrong files or create duplicates.

Instead, describe the *process* Jules should follow:

1. **Read source code first** to understand the current state of whatever the
   issue asks about. Treat existing docs as potentially outdated until verified.
2. **Verify every claim against code** before writing — no aspirational statements,
   no guesses about behaviour.
3. **Writing standards** — tone, tense, heading style, commit prefix (`docs:`).

**Instructions block for docs** should specify:
- Files in scope (the structural files above if present, plus `README.md`;
  avoid open-ended lists)
- Commit prefix convention (`docs:`)
- "Open a pull request when complete."

---

### Infra prompt guidance

Infrastructure changes carry real operational risk. The infra prompt must give
Jules a hard boundary: it writes and validates IaC code in the repository, but it
has **no access to live infrastructure** — no CLI calls, no API calls, no
applying changes.

The prompt should include:

- **Architecture context** — stable overview of the infra topology (tools,
  platforms, directory layout). Reference `ARCHITECTURE.md` if present.
- **Per-tool conventions** — naming patterns, module structure, coding standards
  for each IaC tool in use (Ansible, Terraform, Helm, etc.). Reference
  `CONTRIBUTING.md` if it covers these.
- **Constraints** (make these explicit):
  - No live infra access — no `terraform apply`, no `ansible-playbook`, no
    `kubectl apply`
  - Validation is repo-local only: `terraform validate`, `ansible-lint`,
    `helm lint`, etc.
- **Implementation expectations**:
  - Follow existing patterns in the repo before introducing new abstractions
  - Validate all changes before committing
- **Instructions block for infra** should end with:
  "Open a pull request with the implementation when complete."

---

### CI Review prompt guidance

The `ci-review` role is fundamentally different from the other four roles: it is
triggered by a **CI failure event**, not a human mention in a comment. This means:

- **No issue context** — there is no issue number, title, body, or labels to
  inject. The prompt receives the failing workflow name, failed job names, and
  a run URL instead.
- **No `@jules-ci-review` mention guard** — the `workflow_run` trigger cannot
  collide with `issue_comment`-based `!contains` guards. Do NOT add
  `!contains(github.event.comment.body, '@jules-ci-review')` to other templates.
- **Different placeholders** — the template uses three placeholders:
  `[SECRET_NAME]`, `[PROMPT CONTENT]`, and `[CI_WORKFLOW_NAMES]` (a JSON array
  of workflow name strings, e.g. `["CI", "Tests"]`).

**Loop prevention** — The template's `if` guard excludes `main` and any branch
starting with `jules/`. If Jules creates fix branches with a `jules/` prefix, its
own PRs will not re-trigger the workflow. Verify this convention holds for the
Jules action version in use.

The prompt should include:

- **Project context** — enough for Jules to navigate the repo (same as other roles).
- **CI workflow descriptions** — what each monitored workflow does and how to
  reproduce its failure locally (e.g. `pixi run validate-skills`).
- **Failure context** — injected by GitHub Actions; keep these interpolations verbatim:
  - `${{ github.event.workflow_run.name }}` — the failing workflow name
  - `${{ github.event.workflow_run.head_branch }}` — the branch that triggered it
  - `${{ steps.failure.outputs.failed_jobs }}` — comma-separated failed job names
  - `${{ steps.failure.outputs.run_url }}` — link to the failed run
- **Diagnosis process** — branch on the workflow name to guide Jules toward the
  right reproduction and fix strategy for each CI check.
- **Fix constraints** — minimal change only; do not modify validation rules unless
  they are the root cause.

**Instructions block for ci-review** should end with:
"Open a pull request with the fix when complete."

---

### Presenting the drafts

Show all requested draft prompts to the user before writing any files. For each:

- State what role/persona was assigned.
- Flag any decisions where the best choice was unclear.
- Highlight gaps (e.g. no writing standards found in existing docs — ask the user
  to describe their preferred style before continuing).

Wait for targeted feedback or approval before writing any files.

---

## Phase 3 — Write the finished workflows

Once the user approves, write only the workflow file(s) requested in Phase 0.

Read the relevant template from `templates/<workflow>-dispatch.yml.tmpl`,
located in the same directory as this SKILL.md — not the project's working
directory.
Replace `[PROMPT CONTENT]` with the approved prompt, indented **12 spaces** (the
YAML literal block scalar level in the template). Replace `[SECRET_NAME]` with
the secret name from Phase 0. Reproduce all other YAML exactly — do not reformat,
reorder, or simplify it.

### `if` condition rules — apply to every template

Every workflow guards against **all other `@jules-*` handles** to prevent
double-firing when multiple handles appear in one comment. The current handle set
is: `@jules-swe`, `@jules-security`, `@jules-docs`, `@jules-infra`.

- `author_association` must be `OWNER` or `MEMBER` only — no `COLLABORATOR`.
- The correct pattern for the existing workflows:
  - **SWE**: triggers on `@jules-swe`; guards against security, docs, infra
  - **Security**: triggers on `@jules-security`; guards against swe, docs, infra
  - **Docs**: triggers on `@jules-docs`; guards against swe, security, infra
  - **Infra**: triggers on `@jules-infra`; guards against swe, security, docs

**Maintenance note — adding a new `issue_comment` workflow:** Every time a new
`@jules-*` handle is added for an `issue_comment`-triggered workflow, all
*existing* `issue_comment` templates must be updated with a new `!contains` guard
for the new handle. The templates in `templates/` are the canonical
source — update them, then regenerate any deployed workflows from them.

**Exception — `ci-review`:** The `jules-ci-review-dispatch.yml.tmpl` template
uses `workflow_run` and does NOT use `!contains` guards. Do NOT add a guard for
`@jules-ci-review` to the other templates.

### Injection prevention — all issue_comment templates use this

Every template uses a randomised heredoc delimiter (`openssl rand -hex 8`) when
writing `title` and `body` to `$GITHUB_OUTPUT`. This prevents a crafted issue
title or body containing a fixed delimiter string on its own line from breaking
out of the heredoc and injecting arbitrary output. Never use a fixed string like
`ISSUE_EOF` as a heredoc delimiter in these workflows.
