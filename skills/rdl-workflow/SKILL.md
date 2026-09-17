---
name: rdl-workflow
license: CC-BY-4.0
metadata:
  repo: https://github.com/nq-rdl/agent-extensions
description: Prepare, resume and handle human gates for the executable RDL house-style Workflow from brainstorming through spec-kit, SDD, review, PR and MADR archival.
compatibility: Claude Code 2.1.274 Workflow runtime; installed spec-kit, Superpowers and GitHub workflow skills
---

The executable orchestrator is `/rdl-team:house-style`, registered from
[scripts/house-style.js](scripts/house-style.js). This skill prepares its inputs
and handles interactive boundaries; do not substitute a prose-only execution.
Verify the installed Workflow API against [canonical docs](https://code.claude.com/docs/en/workflows)
before running on another version. The script is native Workflow JavaScript,
not a Node CLI. Codex has no equivalent runtime; this entrypoint is Claude-only.

Read the target project's `/speckit.workflow.guide` for its house-style decisions.
Keep existing user authorizations. Run only stages in the requested scope.
The main session runs interactive brainstorming, clarify and remediation decisions;
Workflow agents cannot ask questions mid-run. By default, return user-only commands to the human for invocation.
For agent-driven generative stages, the user can authorise `generativeMode: "direct"`.
Record that decision before execution. This mode reads the exact target command
instructions for specify, plan, tasks and analyze when Skill invocation is unavailable.
It preserves embedded human gates and tool permissions. Clarify and constitution
remain main-session decisions. Never modify command frontmatter to enable automation.

Invoke the Workflow tool with the registered name `rdl-team:house-style` and an
actual object as `args` (not a JSON-encoded string):

```json
{
  "stage": "brainstorm",
  "generativeMode": "invoke",
  "units": [{
    "id": "feature-name",
    "repo": "/absolute/target-worktree",
    "physicalWorktree": "/absolute/target-worktree",
    "branch": "main",
    "base": "origin/main",
    "checkpoint": "/absolute/target-worktree/.superpowers/rdl-workflow/feature-name.json",
    "request": "The user's requested change"
  }],
  "decisions": []
}
```

Stages, in order: `brainstorm`, `frame`, `specify`, `shape`, `execute`, `review`,
`pr`, `archive`. After each result, read its checkpoint and artifacts, handle its
`nextGate` in the main conversation, and pass the actual human answer with its
artifact/HEAD scope in `decisions`. On completion, continue to the next authorised stage if no human gate remains.
Never infer approval from elapsed time or from a `complete` status. Resume from recorded steps rather than replaying side
effects. Update the unit's `branch` after specify creates the feature branch.

Frame proposes epic units; the human approves the split. Assign each independent
unit a separate worktree and checkpoint before passing multiple units. The script
uses `parallel()` to run them and collects results for one human decision round.
Dependent units wait for their required parent artifact/commit. For specify,
start each checkout on its intended base and let spec-kit create the feature
branch; never pre-create an unused feature branch. Validate physical worktree
paths (including symlinks) before every launch: for each repo, obtain its Git
top-level directory with `git -C "$repo" rev-parse --show-toplevel`, then resolve
that directory with `cd -- "$root" && pwd -P`. Supply the result as
`physicalWorktree`; do not derive it by trimming the input path. The script
requires these identities and rejects duplicates before dispatching any agent.
Preflight rechecks the identity before writing even a checkpoint. If it changed,
refresh every unit's identity in the main session before retrying.

Brainstorm/write-plan/analyze use opus; specify/plan/tasks/execute use sonnet.
Effort intent is in prompts. SDD retains its internal task/reviewer model choices.
Review runs low passes with fixes, then high; high findings return to low after
repair. Three rounds bound a run; exhaustion returns to the human, never to PR.
The PR stage calls branch finishing and the thread-resolution skill, retaining
its PR URL. Archive requires merged-PR evidence and prepares a MADR follow-up;
opening a PR is not evidence that its spec can be retired.

On compression or a new session, read the checkpoint, validate repo/branch/HEAD,
source hashes and artifacts, then resume the first incomplete step. A stale
checkpoint requires reconciliation, not automatic replay or skipped gates.
Checkpoint writes are agent-mediated; review the recorded evidence on resume.
Full mode is the supported default. Constitution changes remain a main-session
project-governance decision, not an automatic per-feature step.
