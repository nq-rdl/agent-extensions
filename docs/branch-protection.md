# Branch protection: required status checks on `main`

`main`'s classic branch protection requires one approving review and conversation
resolution, but historically had **no required status checks** — so a PR with red CI
could still be merged once approved (issue #221, a follow-up to #176). CI was advisory
at the merge button. This page records which checks gate `main`, why the others are
deliberately left optional, and how to apply the setting.

Required status checks are a GitHub **repo setting**, not a repo artifact — there is no
`.github/settings.yml` (Safe Settings) or ruleset file that owns them. This page is the
source of truth an admin applies by hand, the same way `docs/releasing.md` records the
other one-time `main` settings from #175 / #176.

## Required checks

Mark exactly these **always-run** `validate.yml` job names as required status checks on
`main`. Each runs on every PR to `main` with no workflow-level `paths:`/`branches:`
filter and no job-level `if:`, so it reports a pass/fail on every PR:

| Required check (job `name:`)                                   | Job id in `validate.yml` |
| -------------------------------------------------------------- | ------------------------ |
| `Validate bundle references + registry consistency`            | `validate-bundles`       |
| `Validate skill + agent symlinks`                              | `validate-symlinks`      |
| `Validate Claude plugin structure, hooks, and agents`          | `validate-plugins`       |
| `Unit tests (pipeline scripts)`                                | `unit-tests`             |
| `Test cc-web-setup SessionStart hook (install-deps.sh)`        | `hook-tests`             |
| `Validate skills against the agentskills.io spec (asctl)`      | `validate-skills`        |

!!! note "`hook-tests` is required too"
    Issue #221's proposal listed five checks as an illustrative example (*"e.g."*) and
    omitted `hook-tests`. It is an always-run `validate.yml` gate like the others — it
    exercises the `cc-web-setup` SessionStart hook — so it belongs in the required set.
    The rule is "**every always-run `validate.yml` job**," not "the five that were typed
    out."

## Deliberately *not* required

Requiring a check that never reports on a given PR leaves that PR stuck forever at
*"Expected — Waiting for status to be reported."* The failure mode depends on **how** a
check goes absent:

- **Workflow-level filter → no check is created → PR hangs if required.** A `paths:` or
  `branches:` filter that excludes the PR means the workflow never triggers, so GitHub
  never sees a check of that name.
- **Job-level `if:` skip → a `skipped` check *is* created → counts as passing.** The
  workflow triggers, the job is skipped, and branch protection treats a `skipped`
  required check as a pass.

Against that, the excluded checks and why:

| Check                    | Workflow             | Why not required                                                                                                                                                             |
| ------------------------ | -------------------- | -------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `check-links`            | `link-check.yml`     | **Workflow-level `paths: [skills/**/*.md]` filter.** A PR that touches no skill markdown produces **no check** — requiring it would hang every non-skill PR. The real trap. |
| `check-changie-fragment` | `changelog-check.yml`| Job-level `if:` skips on `skip-changelog` / dependabot. It reports `skipped` = pass, so requiring it is harmless but pointless. `changelog-check.yml` is the real gate.      |
| `version-monotonic`      | `release-pr-guard.yml`| Job-level `if:` limits it to `release/v*` PRs. See below — it is required, but as a **release-flow** setting owned by `docs/releasing.md`, not as a general validate gate. |
| `scan`                   | `skillspector.yml`   | Informational by design — the workflow never fails the PR (SARIF upload to code scanning). Keep it non-required.                                                            |

`version-monotonic` **is** marked required — that decision lives in
[`docs/releasing.md`](releasing.md#repo-settings-prerequisites-one-time) alongside the
"require branches to be up to date before merging" requirement it depends on. It is
listed here only so the two lists don't contradict each other.

## Applying the setting

The surgical, non-destructive call is a `PATCH` to the granular
`required_status_checks` sub-resource — it leaves the existing review and
conversation-resolution rules untouched (a full `PUT .../protection` would replace the
*entire* config and must re-send every rule). Branch protection must already exist on
`main` (it does), or the `PATCH` 404s.

Via the GitHub UI: **Settings → Branches → `main` → Edit → Require status checks to
pass before merging**, then add each job name from the [required-checks table](#required-checks).

Via the API (`gh` or `curl`, needs repo-admin):

```bash
gh api -X PATCH \
  repos/nq-rdl/agent-extensions/branches/main/protection/required_status_checks \
  -f 'strict=false' \
  -f 'checks[][context]=Validate bundle references + registry consistency' \
  -f 'checks[][context]=Validate skill + agent symlinks' \
  -f 'checks[][context]=Validate Claude plugin structure, hooks, and agents' \
  -f 'checks[][context]=Unit tests (pipeline scripts)' \
  -f 'checks[][context]=Test cc-web-setup SessionStart hook (install-deps.sh)' \
  -f 'checks[][context]=Validate skills against the agentskills.io spec (asctl)'
```

`strict` = "require branches to be up to date before merging." The release flow wants it
**on** so the `version-monotonic` guard is binding against a moving base
(`docs/releasing.md`); weigh that against the rebase friction it adds to every PR before
flipping it to `true`.

## Maintenance: names are coupled to `validate.yml`

A required status check is matched by the **exact job `name:`** string. Renaming a job in
`validate.yml` (or dropping its `name:`) silently drops the requirement — the old name
stops reporting, the new name is not required, and the gate quietly disappears while
still showing green. When you rename, add, or remove an always-run `validate.yml` job:

1. Update this page's [required-checks table](#required-checks).
2. Update the required status checks on `main` to match (UI or the `gh api` call above).

This coupling is also flagged in `AGENTS.md` next to the CI job list.
