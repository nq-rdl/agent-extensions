# RDL house-style workflow

The `rdl-team` plugin connects repository selection, spec-kit shaping and Superpowers implementation.
Claude Code runs the executable `/rdl-team:house-style` Workflow.
The `/rdl-team:workflow` skill prepares inputs and handles human decisions between stages.
The task adapter also ships in the Codex package.

## Requirements

The workflow targets Claude Code 2.1.274 and its native Workflow API.
Install spec-kit in each target repository.
Install Superpowers and the required GitHub workflow skills from their upstream marketplaces.
The workflow checks stage dependencies and reports missing components before proceeding.

The script uses `agent()`, `pipeline()`, `parallel()` and named phases.
It has no direct filesystem access. Its agents write checkpoints and artifacts.
Claude Code cannot request user input inside a Workflow run.
Each invocation therefore completes one stage and returns any human decision to the main session.
See the [runtime documentation](https://code.claude.com/docs/en/workflows).

## Switch repositories

From a session started in your home directory, invoke `/rdl-team:switch-repo` with a sibling repository path.
The skill registers the directory, checks command discovery and selects the target working directory.
If directory registration requires `/add-dir`, the skill provides the command for you to run.

Added repositories remain loaded. Use the target-qualified spec-kit command shown by Claude Code.
A bare command name can select another repository’s skill.
If the host cannot distinguish commands, the skill stops before creating a spec.
Switch back by invoking the skill with the previous repository or asking it to go back.

Directory loading does not replace the launch project’s permissions, configuration or MCP servers.
See [additional-directory skill loading](https://code.claude.com/docs/en/skills).
The acceptance check is A → B → A, with each read-only prerequisite check reporting its target repository.

## Run stages

Invoke `/rdl-team:workflow` with the feature request and target repository.
The skill supplies structured arguments to `/rdl-team:house-style`.
It records real human decisions and resumes incomplete work from the checkpoint.

| Stage | Result | Model |
| --- | --- | --- |
| Brainstorm | Design draft and questions for the main session | opus |
| Frame | Plan and proposed epic split for approval | opus |
| Specify | Feature spec, followed by human clarification | sonnet |
| Shape | Plan, tasks and analysis for remediation decisions | sonnet, then opus |
| Execute | Adapted SDD plan and tested implementation | sonnet |
| Review | Low review until clear, then a high pass | sonnet, then opus |
| PR | Branch finishing and requested review-thread resolution | sonnet |
| Archive | MADR document after verified merge | sonnet |

By default, the workflow returns user-only spec-kit commands for human invocation.
For agent-driven generative stages, authorise `generativeMode: "direct"` and record that decision.
This mode follows the target command files for specify, plan, tasks and analyze.
It preserves tool permissions and embedded human gates. Clarify remains interactive.
Routine features retain the existing constitution. Constitution changes require a separate project decision.

Independent epic units run concurrently in separate worktrees.
Dependent units wait for the required parent artifact or commit.
Start specify from the intended base: spec-kit creates the feature branch from current HEAD.
After specify, update the workflow unit’s branch to that feature branch.

SDD chooses its own per-task models.
The orchestrator selects only phase models and expresses effort intent in prompts.
Review stops after three rounds if findings remain.
PR creation, merge and worktree cleanup retain their separate authorization boundaries.

## Bridge tasks

Invoke `/rdl-team:task-bridge` with the feature’s `tasks.md` and `plan.md`.
The adapter emits numbered `## Task N` sections and `## Global Constraints`.
It retains source task IDs, completion, phase metadata and the original documents.
Completed tasks are marked for verification only.

The generated filename includes the feature name and a hash of the absolute task-file path.
This prevents different `tasks.md` files from sharing an SDD workspace basename.
On resume, reconcile changed source tasks with the ledger before replacing the generated plan.
The skill checks the installed `task-brief` and `sdd-workspace` helpers before implementation.

After implementation and review, the handoff uses `superpowers:finishing-a-development-branch`.
Optional GitHub task persistence uses the project’s installed `speckit.taskstoissues` command and its configured hooks.
It runs only when issue creation is requested.

## Resume and validation limits

Each unit has a repository-local JSON checkpoint under `.superpowers/rdl-workflow/`.
It records identity, branch, base, HEAD, source hashes, completed steps, decisions, artifacts and the next gate.
Resume validates those fields against the checkout before continuing.
A checkpoint is an agent-written record, not proof that an action succeeded.

Automated tests exercise adapter output and Workflow control flow with deterministic host stubs.
They cover cancellation, gates, fan-out, model routing and bounded review escalation.
They do not prove live agent compliance, slash-command discovery or third-party helper compatibility.
Run the repository-switch acceptance check and a disposable end-to-end feature in the installed Claude environment.

The plugin manifest references the script inside its generated skill copy.
No contributor `.claude/` configuration is required.
Codex receives the task adapter, but excludes the Claude-only switch and Workflow entrypoints.
