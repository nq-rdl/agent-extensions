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

Mark these **always-run** `validate.yml` job names as required status checks on `main`.
`validate.yml` is scoped to `branches: [main, 'release/*']` — that filter *includes*
`main`, so every PR to `main` triggers the workflow. Combined with **no `paths:` filter**
and **no job-level `if:`** on any of these jobs, each reports a pass/fail on every PR to
`main`. (These five are what issue #221 adds; the full required set on `main` also includes
the release flow's `version-monotonic` — see [below](#deliberately-not-required) — which
is why the apply command enumerates it.)

| Required check (job `name:`)                                   | Job id in `validate.yml` |
| -------------------------------------------------------------- | ------------------------ |
| `Validate bundle references + registry consistency`            | `validate-bundles`       |
| `Validate skill + agent symlinks`                              | `validate-symlinks`      |
| `Validate Claude plugin structure, hooks, and agents`          | `validate-plugins`       |
| `Unit tests (pipeline scripts)`                                | `unit-tests`             |
| `Validate skills against the agentskills.io spec (asctl)`      | `validate-skills`        |

!!! warning "`hook-tests` was removed — un-require it on `main`"
    The `hook-tests` job (`Test SessionStart hooks (install-deps.sh)`) was deleted from
    `validate.yml` when this repo's SessionStart hooks (`.claude/scripts/`) were removed.
    A required check that never reports leaves every PR stuck at *"Expected — Waiting for
    status to be reported."* An admin **must** drop `Test SessionStart hooks
    (install-deps.sh)` from `main`'s required status checks (**Settings → Branches →
    `main` → Edit**, or re-run the [apply command](#applying-the-setting) below, whose
    `checks` array no longer lists it). See
    [Maintenance: names are coupled to `validate.yml`](#maintenance-names-are-coupled-to-validateyml).

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
listed here so the two lists don't contradict each other, **and** because the apply
command below rewrites the whole required-check set, so it has to include
`version-monotonic` or applying it would drop the guard.

## Applying the setting

Prefer a `PATCH` to the granular `required_status_checks` sub-resource over a full
`PUT .../protection` (which would replace the *entire* config and must re-send every
rule). The `PATCH` leaves the review and conversation-resolution rules untouched and
**omits `strict`**, so it does not touch "require branches to be up to date before
merging" (see the note below). Branch protection must already exist on `main` (it does),
or the `PATCH` 404s.

!!! warning "The `checks` array replaces the entire required-check set"
    The `checks` you send **become** the required-check list — the `PATCH` is not
    additive, so any check you omit is **dropped**. The snippet below therefore also
    lists `version-monotonic` (the release-flow stale-PR guard required by
    `docs/releasing.md`); leaving it out would silently un-require it and make stale
    release PRs mergeable again. The GitHub **UI** path is additive by contrast — ticking
    a box adds a check without removing the others.

Via the GitHub UI (additive): **Settings → Branches → `main` → Edit → Require status
checks to pass before merging**, then add each job name from the
[required-checks table](#required-checks). Leave the release flow's `version-monotonic`
in place if it is already there.

Via the API (`gh` or `curl`, needs repo-admin):

```bash
gh api -X PATCH \
  repos/nq-rdl/agent-extensions/branches/main/protection/required_status_checks \
  -f 'checks[][context]=Validate bundle references + registry consistency' \
  -f 'checks[][context]=Validate skill + agent symlinks' \
  -f 'checks[][context]=Validate Claude plugin structure, hooks, and agents' \
  -f 'checks[][context]=Unit tests (pipeline scripts)' \
  -f 'checks[][context]=Validate skills against the agentskills.io spec (asctl)' \
  -f 'checks[][context]=version-monotonic'   # release-flow guard (docs/releasing.md) — omit and it is dropped
```

The `PATCH` above deliberately does **not** send `strict` ("require branches to be up to
date before merging"), so it leaves that setting exactly as it is. That is on purpose:
`strict` is owned by the release flow — [`docs/releasing.md`](releasing.md#repo-settings-prerequisites-one-time)
wants it **on** so the `version-monotonic` guard stays binding against a moving base, and
sending `strict=false` here would silently turn it off. To manage `strict` in the same
call, add a **typed** boolean field (`gh api` needs `-F`, not `-f`, for booleans):
`-F 'strict=true'` (or `-F 'strict=false'`) — weigh the rebase friction `strict=true`
adds to every PR before enabling it.

## Maintenance: names are coupled to `validate.yml`

A required status check is matched by the **exact job `name:`** string. Renaming a job in
`validate.yml` (or dropping its `name:`) silently drops the requirement — the old name
stops reporting, the new name is not required, and the gate quietly disappears while
still showing green. When you rename, add, or remove an always-run `validate.yml` job:

1. Update this page's [required-checks table](#required-checks).
2. Update the required status checks on `main` to match (UI or the `gh api` call above).

This coupling is also flagged in `AGENTS.md` next to the CI job list.
