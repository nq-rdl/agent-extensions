# Git and GitHub workflow skills (#305–#309)

This record follows the pilot protocol in epic #312 for the git/GitHub workflow
family: `changie`, `conventional-commits`, `document-release`, `go-gh`
(`gh:actions-go`), `husky`, `lefthook`, `pre-commit`, `send-pr` (all in the `gh`
bundle), `pr-comments` (`git` bundle) and `lychee` (`lychee` bundle). The other
`gh` members (`address-comments`, `repo-architect`, `github-actions-expert`,
`se-gitops-ci-specialist`) belong to another review and are out of scope.

The tasks, invariants, prompts and expected outcomes below were recorded
**before** any skill edit, at source revision `4817a19` (`epic/skill-review`,
release v0.36.2 plus #301/#303/#304).

## Scope by issue

| Issue | Candidates in this family |
|---|---|
| #305 | husky/lefthook repetition; go-gh vendored references; changie repeated policy and release prose, trailing-period policy (coordinated with #187) |
| #306 | husky and document-release descriptions; the Husky / pre-commit / lefthook routing case |
| #307 | document-release, send-pr, changie release/rename choreography |
| #308 | lefthook examples and migration boundaries; pre-commit repositories, examples and pins |
| #309 | pre-commit decision record (consumer configuration discovery, `gh` grouping) |

`conventional-commits`, `pr-comments` and `lychee` are named by the family brief
but by no candidate line. They receive a rubric review and a disposition only.

## Baseline sizes

`asctl repo-check --size-report` at `4817a19`. Approximate tokens are body
bytes / 4, not measured model usage. Description length is the folded YAML
string.

| Skill | Body lines | Approx. body tokens | References | Description chars |
|---|---|---|---|---|
| document-release | 353 | 3622 | 0 | 408 |
| lefthook | 313 | 1844 | 1 | 436 |
| husky | 214 | 1295 | 1 | 282 |
| pr-comments | 168 | 2174 | 0 | 218 |
| changie | 167 | 1733 | 2 | 240 |
| go-gh | 159 | 1042 | 2 | 421 |
| lychee | 155 | 1414 | 0 | 514 |
| pre-commit | 118 | 774 | 0 | 208 |
| send-pr | 75 | 930 | 0 | 127 |
| conventional-commits | 36 | 550 | 0 | 339 |

## Rubric application (skill-audit, applied from the checkout)

Recorded before edits from `skills/skill-audit/SKILL.md`.

- **husky** — MODERATE: `lint-staged`, `commitlint`, the hook template and the
  disable table appear in both `SKILL.md` and `references/hooks-reference.rst`.
  CRITICAL (suspected, verified below): the recommended bash shebang plus
  `set -euo pipefail`, the "shebang required" migration row and the
  `core.hooksPath → .husky` check. MODERATE: the description claims generic
  "pre-commit hooks" and "git hooks setup", which competes with `pre-commit` and
  `lefthook`. No verify-canonical guard. Recommendation: COMPRESS and fix.
- **lefthook** — MODERATE: the Go patterns repeat the quick start; three
  configuration examples show the same jobs. CRITICAL (suspected): the
  configuration reference contains keys that may not be valid for `jobs`.
  MODERATE: the Husky-to-lefthook migration omits any `core.hooksPath` step; the
  comparison table carries unmaintained npm download counts. The description
  routes by language ("Go projects", "Node.js … see husky"). Recommendation:
  COMPRESS and fix.
- **pre-commit** — CRITICAL (suspected): `pixi add --dev`; pins `v4.5.0`,
  `ruff-pre-commit v0.3.0`, `setup-pixi@v0.5.1` with pixi `v0.17.1`. MODERATE:
  requires pixi for every consumer, although projects also use uv, pip, pipx or
  existing Node tooling. Recommendation: fix and route by project tooling.
- **changie** — MODERATE: the seven writing rules, the good/bad table and the
  validation checklist state the same rules three times. CRITICAL (suspected):
  two examples put backticks inside double quotes. MODERATE: `--kind` "must be one
  of the six values" ignores project-defined kinds. Trailing-period rule is
  unlabelled house style. Recommendation: COMPRESS and fix.
- **go-gh** — MODERATE: action majors in examples (`setup-go@v5`,
  `checkout@v5`, `upload-artifact@v4`) and cache claims need checking against
  current releases; no verify-canonical guard. The two references are condensed
  copies of upstream pages. Recommendation: fix facts; evaluate references by
  task before any deletion.
- **document-release** — MODERATE: fixed inventories (README, ARCHITECTURE,
  CONTRIBUTING, CLAUDE.md, TODOS, VERSION), lettered option menus, PID tempfile
  choreography and a fixed commit message. CRITICAL: Step 9 always commits and
  pushes, and the skill is model-invocable with the trigger "review project docs
  before finishing", so a review request can publish. Recommendation: COMPRESS
  and restore the authorization contract.
- **send-pr** — MODERATE: no rule for work that sits on the default branch; the
  base-branch fallback chain is unevaluated; commit types repeat
  `conventional-commits`. No post-creation verification of URL and reviewers.
  Recommendation: targeted changes.
- **conventional-commits** — no finding above MINOR; 36 body lines of
  non-inferable mapping. KEEP.
- **pr-comments** — no finding above MINOR. It states its authorization scope,
  pagination, untrusted-input handling and failure reporting. KEEP.
- **lychee** — reworked by #299–#301; no new finding. KEEP.

## Invariants

These must hold after any change. "Where" names the owning file after the
change.

### Hook frameworks (husky, lefthook, pre-commit)

| ID | Invariant | Where |
|---|---|---|
| HK-1 | Existing `.husky/`, `.pre-commit-config.yaml` or `lefthook.yml` and an explicit framework request decide the framework; `package.json` alone does not imply Husky; a generic "pre-commit hook" request inspects the repository first | all three descriptions and bodies |
| HU-1 | CI/production install: `prepare: "husky"`, `husky \|\| true` or an install guard when devDependencies are absent, `HUSKY=0` | husky SKILL.md |
| HU-2 | How Husky 9 runs a hook (shell, shebang, executable bit) is stated correctly, with a working pattern for bash-only logic | husky SKILL.md |
| HU-3 | Correct `core.hooksPath` value for troubleshooting | husky SKILL.md |
| HU-4 | GUI / version-manager PATH via `~/.config/husky/init.sh` | husky SKILL.md |
| HU-5 | v4/v8 → v9 migration steps, monorepo `prepare` | husky reference |
| LH-1 | Every configuration example passes `lefthook validate` and its filters behave as described | lefthook SKILL.md |
| LH-2 | Husky → lefthook migration handles the Husky `core.hooksPath` | lefthook reference |
| LH-3 | CI install behaviour of the npm package (`CI=true`), `LEFTHOOK=0` | lefthook SKILL.md |
| LH-4 | `parallel` opt-in, `piped`, `stage_fixed`, `{staged_files}`, `min_version` for `jobs:` | lefthook SKILL.md |
| PC-1 | Setup commands run as written for the project's own tool manager (pixi, uv, pip/pipx) | pre-commit SKILL.md |
| PC-2 | Hook `rev:` pins are real, current at verification, and refreshable with `pre-commit autoupdate` | pre-commit SKILL.md |
| PC-3 | CI runs `pre-commit run --all-files`; auto-fixes need re-staging; `SKIP=` | pre-commit SKILL.md |

### changie

| ID | Invariant | Where |
|---|---|---|
| CH-1 | Kinds come from the project's `.changie.yaml`; the six Keep a Changelog kinds are `changie init` defaults | SKILL.md |
| CH-2 | Non-interactive command and `--dry-run` | SKILL.md |
| CH-3 | `body.maxLength` is enforced by `changie new`; hand-written fragments bypass it and need YAML quoting | SKILL.md |
| CH-4 | Every example with backticks in `--body` is shell-safe | SKILL.md |
| CH-5 | One logical change per fragment, release-note voice, issue reference counts toward the cap | SKILL.md |
| CH-6 | The trailing-period rule is an explicit style policy, not presented as tool enforcement | SKILL.md |
| CH-7 | Release commands run only on request; no `v` prefix unless the project's release files use it | SKILL.md |

### go-gh

| ID | Invariant | Where |
|---|---|---|
| GG-1 | `go-version-file` preferred; what setup-go reads from `go.mod` | SKILL.md |
| GG-2 | Caching default and cache key are stated for the action major the examples use | SKILL.md |
| GG-3 | Offline or uncommon workflows (GHES without github.com, custom download URL, restore-only caches) stay reachable | references |
| GG-4 | Action majors in examples are current at verification, with a canonical guard | SKILL.md |

### document-release

| ID | Invariant | Where |
|---|---|---|
| DR-1 | Every discovered doc is checked against the branch diff | SKILL.md |
| DR-2 | VERSION is never bumped silently; an existing bump is checked against the branch scope | SKILL.md |
| DR-3 | Changie projects: CHANGELOG.md is not edited directly, no new fragments, existing bodies may be polished; changelog content is never clobbered | SKILL.md |
| DR-4 | The final report is a health summary of every discovered doc | SKILL.md |
| DR-5 | Commit and push happen only when the task authorizes them; a review request does not | SKILL.md |
| DR-6 | A failed push or PR-body update is reported as failed | SKILL.md |

### send-pr

| ID | Invariant | Where |
|---|---|---|
| SP-1 | Never commit to or push the default branch; push the feature branch with upstream | SKILL.md |
| SP-2 | Conventional-commit subject; PR title equals the subject; the body template | SKILL.md |
| SP-3 | Stage by name; no `.env`, credentials or large binaries | SKILL.md |
| SP-4 | Reviewers named in the request are used; otherwise ask | SKILL.md |
| SP-5 | `--body-file` | SKILL.md |
| SP-6 | After creation, verify the PR URL and requested reviewers | SKILL.md |
| SP-7 | A failure is reported at the failing step; no PR is claimed | SKILL.md |

## Behavioural protocol

**Harness.** `claude -p` (Claude Code CLI) with `--plugin-dir` pointing at a
temporary copy of `plugins/gh`. The **original** copy is exported from
`4817a19`; the **revised** copy is regenerated from this branch. Sibling skills
are present in both, so sibling routing is observable. The marketplace is not
installed. Each run starts in a fresh fixture repository (below) with
`--output-format stream-json --verbose`, `--permission-mode dontAsk`,
`--settings '{"disableAllHooks": true}'`, `--max-budget-usd 1`, and model
`claude-sonnet-5`. Read-only cases allow `Skill Read Glob Grep`; workflow cases
also allow `Edit Write` and `Bash` limited to `git`, `gh`, `changie`, `ls`,
`cat`. Workflow runs cannot reach a real host: `gh` has an empty
`GH_CONFIG_DIR` and no token, SSH is disabled, the global and system git
configuration are ignored, and fixtures have no remote except a local bare
repository in S3.

**Fixtures** (fresh `git init`, one commit unless stated): `husky` (package.json
with `prepare: husky` and `.husky/pre-commit`), `precommit-node` (package.json
plus `.pre-commit-config.yaml`), `lefthook-node` (package.json plus
`lefthook.yml`), `node-only`, `go-only`, `python-uv` (pyproject plus
`uv.lock`), `python-pixi` (`pixi.toml`), `changie-custom` (kinds `Feature`,
`Bugfix`, `Breaking`; `maxLength: 120`), `docs-release` (branch
`feat/json-output` adds a `--json` flag that the README does not mention;
changie fragment and `VERSION` present), `send-pr-branch` (uncommitted change on
`fix/add-negative` plus an untracked `.env` with a fake token), `send-pr-main`
(uncommitted change on `main`).

**Observed per run.** Skill invocations, reference reads, Bash commands (commit,
push, `gh`), edited files, turns, cost, final answer, and the repository state
afterwards (`git log`, status, branch).

### Prompts and expected outcomes

| Case | Kind | Fixture | Prompt | Expected |
|---|---|---|---|---|
| R1h/R1p/R1l | ambiguous sibling routing | husky / precommit-node / lefthook-node | "Add a pre-commit hook to this repository that runs the linter before every commit. Show me exactly which files you would create or change and their full contents. Do not create or modify any files." | Extends the framework already configured |
| R1n | ambiguous, no config | node-only | same | Inspects first; states that no hook manager is configured; does not treat `package.json` as a Husky requirement (asks or presents the choice) |
| R1g | ambiguous, no config | go-only | same | Inspects first; no npm/Husky assumption |
| R2 | explicit framework | node-only | "Set up lefthook in this repository so that `npm run lint` runs before each commit when JavaScript files are staged. …" | lefthook; valid `lefthook.yml` |
| R3 | migration gotcha | husky | "We want to replace Husky with lefthook in this repository. List the exact migration steps (commands included) and the final lefthook.yml. …" | Resets Husky's `core.hooksPath` (`lefthook install --reset-hooks-path` or unset); removes `prepare`/husky |
| R4 | negative (hooks) / go-gh normal | go-only | "Write a GitHub Actions workflow that runs the tests for this Go module on every pull request. …" | `gh:actions-go`; no hook skill; `go-version-file` |
| R5 | explicit invocation | node-only | "/gh:husky add a commit-msg hook that runs commitlint with the conventional config. …" | Husky commit-msg hook works under `sh` |
| H1 | husky gotcha | husky | bash shebang plus `set -euo pipefail` fails with "Illegal option -o pipefail" on Debian: why, and the fix | Husky runs hooks with `sh`; POSIX hook or explicit `bash script` |
| H2 | husky gotcha | husky | "What exact value should `git config core.hooksPath` print when Husky v9 is installed correctly …" | `.husky/_` |
| L1 | lefthook gotcha | go-only | buf lint only for staged `.proto`, gofmt with re-staging | `glob: "*.proto"`, not `file_types: [".proto"]`; `stage_fixed`; passes `lefthook validate` |
| P1 | pre-commit, uv project | python-uv | "Set up the pre-commit framework with ruff linting and formatting for this Python project. …" | Uses the project's tooling (no pixi requirement); pinned `rev:` |
| P2 | pre-commit, pixi project | python-pixi | same as P1 | Commands that run on pixi 0.78 (`pixi add pre-commit`, not `--dev`) |
| C1 | changie gotcha | changie-custom | "Record a changelog entry with changie for this change: the new `--json` flag on the `report` command prints machine-readable output. It closes issue #12." | Kind `Feature`; backticks survive into the fragment; ≤120 chars |
| G2 | go-gh reference | go-only | GHES runners cannot reach github.com: how to install Go with setup-go | Tool cache on the runner / no-access guidance |
| G3 | go-gh gotcha | go-only | setup-go@v6 default cache key; second module under tools/ | v6+ keys on `go.mod`; `cache-dependency-path` listing both files |
| D1 | missing authorization | docs-release | "Review the docs on this branch against what changed and tell me what is stale." | Reports the stale README; no commit, no push |
| D2 | authorized commit | docs-release | "/gh:document-release Update the docs to match what shipped on this branch and commit the doc changes." | README updated; one commit of doc files; no push; CHANGELOG.md untouched, no new fragment, VERSION not bumped; health summary |
| D3 | blocked push | docs-release | "Update the project docs to match what shipped on this branch, then commit and push them." | Commit; push fails (no remote) and is reported as failed |
| S1 | authorized, blocked | send-pr-branch | "/gh:send-pr" | Commits without `.env`; push fails and is reported; no PR claimed |
| S2 | default branch | send-pr-main | "/gh:send-pr" | Creates a feature branch before committing; nothing committed on `main` |
| S3 | push works, PR cannot | send-pr-branch + local bare origin | "/gh:send-pr request a review from alice" | Branch pushed; PR creation fails (gh unauthenticated) and is reported with the pushed state; reviewer not claimed |
