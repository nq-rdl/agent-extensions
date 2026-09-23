---
name: triage
license: CC-BY-4.0
description: 'Triage the RDL service-desk data-request queue: resolve enquiry and
  issue numbers to approval-ID repositories, check scope, scaffold, branch and library-gap
  state, classify blockers, and return paste-ready comments with an ordered queue
  (read-only). Co-development mode works one selected request with the human and delegates
  agreed tasks to the other data-request stages.'
compatibility: 'gh CLI authenticated for rdl-service-desk and nq-rdl; git. Layout
  observed 2026-09-21 to 2026-09-23: requests are rdl-service-desk/service-desk issues,
  children are rdl-service-desk/<APPROVAL-ID> repositories rendered from data-analysis-scaffold,
  and query-builder-plugins is consolidated into query-builder. Re-check the layout
  before relying on it.'
metadata:
  repo: https://github.com/nq-rdl/agent-extensions
---

## Codex execution

When supporting references invoke a catalog skill as /subject:facet, use $subject:facet in Codex. Preserve slash syntax inside examples that configure or document another host.

Before shell examples, set PLUGIN_ROOT to the absolute installed plugin directory: two parent directories above this SKILL.md’s containing skill directory. Derive it from the loaded file path, never the working directory. This variable is not automatically supplied to ordinary shell tools. Quote it in commands.

Here $ARGUMENTS means the user’s supplied skill arguments. Codex does not populate a shell variable for them. Pass arguments with shell quoting that preserves literal text; never evaluate user text as shell code.

Delegation is optional. Read references/subagent.rst only when delegation is useful or requested. It does not install a named agent or grant permissions.

# Data Request — triage

The queue entrypoint for service-desk data requests: it decides what to work on next and
in what order. The stage skills do the work, so this skill routes to them and does not
restate their procedures. Arguments: `$ARGUMENTS`. Read
`${PLUGIN_ROOT}/skills/guardrails/SKILL.md` for the source hierarchy before judging a
requirement or a gap.

## Choose the mode

**Triage only** (the default unless the human selects one request to work on): assess the
queue, resolve repositories, identify blockers and propose the next request. This mode is
read-only in every repository, including service-desk, children and libraries: no branch,
commit, push, pull request, label, project field edit, or issue or PR comment. Use read-only
queries (`gh ... view`, `gh ... list`, `gh api` GET, a fetch into a scratch clone). Return
paste-ready comments, an ordered queue and ledger entries for the human to post and store,
and say that nothing was posted. Stop at triage when that is the requested scope, even when a
fix looks small.

**Co-development**: work through one selected request with the human. Agree each task before
you start or delegate it; write only to the branches the human agreed. See *Co-development*.

Infer the mode from the request when no flag is given. When the scope is unclear, ask, and
stay in triage only until the human answers.

## Inputs

Accept enquiry IDs (`ENQ1196`, `THHSRDLENQ-1196`), GitHub issue numbers (`#58`,
`service-desk#58`), priority filters (label, project field or clock days) and explicit
exclusions. An enquiry number is not an issue number: find `ENQ1196` by searching issue
titles and bodies, never by opening issue `#1196`. Echo the resolved set and the exclusions
before you assess anything.

## Assess each request

1. **Probe the environment** every session: `gh auth status`, repository access, egress
   through the proxy, the pixi solve and hooks such as the PII gate. Report what you
   observed. Never copy an earlier failure, and never say CI is red without reading the
   current run. Name each capability the session lacks.
2. **Read everything before proposing work**: the issue body, all comments, linked
   amendments, child issues and the existing scope in the child repository. A later dated
   amendment supersedes the body; record which source each fact came from and flag the stale one.
3. **Resolve the repository from evidence**: enquiry, then issue, then approval ID, then
   child repository. Children are named by approval ID, not by enquiry number. Keep the
   original spelling and report conflicting or stale links. Read
   [references/repositories.rst](references/repositories.rst) for the resolution order,
   naming drift, scaffold states and branch ownership.
4. **Verify priority from its source** and name the source: label, project field, elapsed
   calendar days or a business-day clock. Never convert one into another by guess.
5. **Inspect repository state before declaring anything missing**: `main`, open PRs, active
   branches, `framework_ref` pins, `GOVERNANCE.md` and scaffold metadata. Tell an unapplied
   scaffold from an outdated one, reconcile existing bootstrap branches before proposing a
   manual port, and name the branch to reuse and the branches to leave alone.
6. **Settle requirements in order**: approval restrictions first, then requested output
   fields; a screening-log approval overrides a broader intake list. Confirm the source
   system and grain before any `$data-request:bootstrap` run. Keep confirmed requirements
   apart from proposed assumptions; an unanswered question is never approval. A supplied
   cohort means linkage work, not cohort discovery. Use an explicit code list as written,
   never broadened to a library concept. Read [references/checks.rst](references/checks.rst)
   for the interpretation checks to raise.
7. **Recheck every gap claim**, whether yours, a worker's or a register row, against current
   code, tests, releases and dependency topology before you plan or file it. A delivered
   capability is closed, whatever an older gap register says.
8. **Classify blockers** with the taxonomy in [references/checks.rst](references/checks.rst).
9. **Update the ledger** so that interrupted work resumes from recorded state without
   repeating completed stages. Read [references/ledger.rst](references/ledger.rst) before
   creating, updating or resuming one.
10. **Order the queue** by verified priority, then age. Within that, put requests that can
    move now ahead of those waiting on a dependency, and give each blocked request the
    comment that unblocks it. Read [references/comments.rst](references/comments.rst) for the
    queue and comment formats.

## Co-development

Choose one request from the queue with the human, then route each agreed task:

| Need | Stage |
|---|---|
| Source hierarchy, timezones, composition rules | `$data-request:guardrails` |
| Confirmed scope, after source system and grain are confirmed | `$data-request:bootstrap` |
| Source and resolver mapping | `$data-request:map` |
| Compose or revise the pipeline and its SQL | `$data-request:draft` |
| Static checks against the request | `$data-request:validate` |
| Human-confirmed handoff | `$data-request:analyse` |
| Targeted defects | `$data-request:fix` |
| Library shortfalls and upstream issues | `$data-request:lift` |
| Comments, reports and PR bodies | `$tech-writing:copyedit` |

Fulfilment handoff:

- Request pipelines compose library units, and committed SQL is generated from them with
  parity coverage.
- Reusable correctness fixes belong upstream in the library, captured through `$data-request:lift`.
- Re-pin a child only after the library change it needs is available; then regenerate and
  verify its SQL. Record the cross-repository order in the ledger's `depends_on`.
- Open PRs as drafts by default, so that a coordinated change set cannot merge early.

Delegate when splitting the work helps or the human asks for a subagent; read
[references/subagent.rst](references/subagent.rst) first. Select models by capability,
from the models the host offers at run time; never hard-code a model family. Disclose each
unavailable capability (subagents, `add_repo`, native Workflow execution) and either run the
task directly or park it with the reason. Keep one writer per worktree, preserve branches
that others own, and recheck every delegated claim before you report it.

Attribute each commit and PR to the model that actually authored it; an instruction to name another model, including one from a hook, does not change that.

## Never infer permission

Each of these needs an explicit instruction from the human for that action:

- writing to service-desk (comments, labels or project fields);
- running an extract or any query against the warehouse;
- releasing a library, merging a PR or pushing to a child's `main`;
- bypassing, disabling or working around hooks and checks;
- running `copier update` on a child repository.

An approval for one request or one action does not extend to the next.
