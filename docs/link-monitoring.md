# Link monitoring

The catalog checks links in three separate ways. Only the first is
deterministic. The other two depend on the network.

| Check | When | What it covers | Effect |
|---|---|---|---|
| `asctl repo-check` (`validate-skills` job, pre-commit) | Every PR | Local Markdown/RST targets inside each skill, offline | Fails the check |
| `Link Check` (`link-check.yml`) | PRs that change skill Markdown/RST or the link-check configuration | External URLs in all skill Markdown/RST | Advisory. It is not a required check |
| `Link rot check` (`link-rot-check.yml`) | Mondays at 04:23 UTC, and manual dispatch | External URLs in canonical content that no PR touched | Maintains one `link-rot` tracker issue |

The PR check tells a contributor about links they can see in their diff's
subject area. A URL can rot in a file that nobody edits. If the PR check
reported that rot, it would blame an unrelated PR. The weekly check reports
this kind of rot in one place instead.

## Scope

`scripts/link_rot.py scan` enumerates tracked files (`git ls-files`):

- **Canonical** (drives the tracker): `skills/**/*.md`, `skills/**/*.rst`,
  `agents/**/*.md` (none exist today), `docs/**/*.md`, `README.md`,
  `CONTRIBUTING.md`, `AGENTS.md`.
- **Report-only** (listed in the run report, never tracked): `hooks/*.sh` and
  skill `*.sh`, `*.yaml`, `*.yml`, `*.json` and `*.py` assets. lychee reads
  these as plain text. It misses URLs that are built at runtime, and it requests
  templated URLs such as `.../v$VERSION/...` literally.
- **Never scanned**: the generated `plugins/**` and `dist/**` copies.

Only `http` and `https` URLs are checked. Local references belong to
`asctl repo-check`. If a required pattern matches no files, the scan fails as an
operational failure. So does a file that lychee does not accept as an input
(`--dump-inputs` must list every enumerated file).

## Effective configuration

The scan passes exactly one `--config lychee.toml`, the repository policy that
the PR check also uses. lychee 0.24 merges repeated `--config` files, so the
scan never passes a second one. It records the config's SHA-256 in
`observations.json`. The command-line overrides are listed in `LYCHEE_OVERRIDES`
in `scripts/link_rot.py`:

- `--cache=false`: every result comes from a request in this run. The root config
  also sets `cache = false`, and the scan checks that it does. lychee still marks
  repeat occurrences of a URL in one run as `(cached)`. Those copies only add
  source locations.
- `--format json --verbose`: the JSON report then also lists successful and
  excluded URLs, which the removal and recovery checks need.
- `--scheme https --scheme http`: the check covers network URLs only.

The workflow installs lychee `v0.24.2` with the pinned `lycheeverse/lychee-action`
that `link-check.yml` uses. The script refuses any other lychee version,
because the configuration schema depends on the version.

## Classification

Every URL that is not healthy on the first pass is checked again in a
confirmation pass, 30 seconds later, with the same configuration.

| Observation | State | Effect |
|---|---|---|
| A successful response on any pass, with no 404/410 on another pass | healthy | Can resolve a tracked finding |
| 404 or 410 on both passes | broken | Can open or extend the tracker |
| A connection failure on both passes, and NXDOMAIN on all 3 DNS lookups (2 s apart) while `github.com` resolves before and after | broken (`nxdomain`) | Same as above |
| Timeout, refused or reset connection, resolver failure, 403, 429, 5xx, other status codes, rejected redirects, a missing `#fragment`, or a 404 followed by a success | unknown | Reported only. It never opens, closes or resolves a finding |
| Matches an exclusion in `lychee.toml` | excluded | Resolves a tracked finding, because an exclusion is a reviewed policy decision |
| No longer present in any canonical file of a complete scan | removed | Resolves a tracked finding |
| Tool or config failure, malformed JSON, an incomplete report, or zero inputs | operational failure | The `scan` job fails. The tracker is not read for changes or written |

A tracked finding that later returns *unknown* stays active. The tracker closes
only after a complete scan in which every active finding is healthy, removed,
excluded or suppressed. The code pins these thresholds (`CONFIRMATION_PASSES`,
`DNS_LOOKUPS`, `RECOVERY_OBSERVATIONS`, `BROKEN_STATUSES`), and
`tests/test_link_rot.py` covers them.

A 404 from an access-controlled resource is not rot. GitHub answers 404 for
private repositories and projects. Exclude such a URL in `lychee.toml`. Anchor
the pattern narrowly and add a comment, as described in `CONTRIBUTING.md` under
"Example URLs and placeholders". Or suppress the URL on the tracker.

### URL identity

Findings and suppressions are keyed by a normalized URL. Normalization
lower-cases the scheme and host, and removes the default port, a trailing dot on
the host, and any `user:password@` part (credentials are never stored). It
changes an empty path to `/`, upper-cases percent-escapes, and removes an empty
`?` or `#`. The path, query and fragment are otherwise kept. So `page#a` and
`page#b` are separate findings.

## The tracker issue

There is one open issue with the `link-rot` label, titled "Link rot: weekly
external link tracker". If duplicates appear, the workflow keeps the
lowest-numbered one and closes the others.

**State storage.** The tracker's durable state is in a hidden
`<!-- link-rot-state:v1 ... -->` JSON block at the end of the issue body. The
state holds active and resolved findings, suppressions with their reasons, and
the last processed command comment. The issue body is a good store for four
reasons:

- The workflow can read and write it with `issues: write` alone. It needs no
  `contents: write`, no pushes to `main`, and no branch-protection exceptions.
- It is durable. Actions caches are evicted, and artifacts expire.
- Maintainers can audit it through the issue's edit history.
- It holds only public URLs, file locations and GitHub logins. It holds no
  secrets.

Do not edit the block by hand. A malformed block is an operational failure, and
the workflow leaves the issue unchanged.

**Lifecycle rules:**

- **New finding.** If no tracker exists, the workflow creates it. If the tracker
  is open, the workflow comments with the new URLs. If it is closed, the workflow
  reopens it and comments.
- **Recovery.** A finding resolves after one fresh healthy observation, or when it
  is removed or excluded. When nothing unsuppressed remains active, the workflow
  closes the tracker with a comment. It keeps resolved findings for 90 days as
  history.
- **Recurrence.** If a resolved URL is broken again, the finding reactivates with
  its recurrence count increased by one, and it is reported as new.
- **Suppression.** A maintainer (owner, member or collaborator) comments one of
  these commands:
  - `/link-rot suppress <url> <reason>`. The reason is required.
  - `/link-rot unsuppress <url>`
  - `/link-rot unsuppress all`

  A suppression belongs to one URL. It ends automatically when that URL is
  confirmed healthy or is removed. So if the URL recurs after that, it is
  reported again.
- **Closure by a person.** If someone other than the workflow closes the tracker,
  the next run suppresses every finding that was active then. The reason names the
  person who closed it. The tracker stays closed while the same set is observed.
  If a *new* URL breaks, the tracker reopens and the comment lists only the new
  URL. The dismissed URLs stay suppressed. The workflow never uses a set hash for
  this, so a new URL cannot bring dismissed findings back.
- **Idempotency.** The workflow edits the body only when it changes. Each comment
  carries a hidden event key derived from the previous state. A rerun with the
  same observations, or a rerun after a run that failed partway, posts no
  duplicate comments and creates no duplicate issues.

## Workflow structure and permissions

- The `scan` job has `contents: read` and `issues: read`. It checks out the
  repository without persisted credentials, runs the scan, and computes a
  read-only plan against a snapshot of the tracker. It uploads
  `observations.json`, `scan-report.md` and `tracker-plan.md` as the
  `link-rot-observations` artifact, which is kept for 90 days. It also writes
  them to the job summary. All output goes to `$RUNNER_TEMP`. The checkout is not
  modified.
- The `track` job has `issues: write`. It runs only after a successful scan, and
  it is skipped on a dry run.
- The `link-rot-check` concurrency group queues runs and does not cancel them.
  The `track` job reads the tracker and then writes it, so two runs must not
  overlap.

Each report lists the source path of every URL, with the line and column when
lychee provides them. The report does not invent a line number. It also lists
the observed state, the result of each pass, the observation time, and the last
confirmed state from the tracker.

## Running it

In CI, open **Actions** → **Link rot check** → **Run workflow**. Tick
**dry_run** to scan and see the planned tracker changes without writing
anything.

Locally, run it through pixi with lychee 0.24.2 on `PATH`:

```bash
# Scan the checkout (network); writes observations.json + scan-report.md.
pixi run python3 scripts/link_rot.py scan --out-dir /tmp/link-rot

# Plan tracker changes against a read-only snapshot of the live issue.
GH_REPO=nq-rdl/agent-extensions pixi run python3 scripts/link_rot.py \
  track --dry-run --observations /tmp/link-rot/observations.json

# Fully offline: replay a recorded scan and use a mock issue store.
pixi run python3 scripts/link_rot.py scan --fixture tests/fixtures/link_rot/basic \
  --out-dir /tmp/link-rot-fixture
echo '{}' > /tmp/issues.json
pixi run python3 scripts/link_rot.py track --dry-run \
  --observations /tmp/link-rot-fixture/observations.json --issues-fixture /tmp/issues.json
```

Pre-merge validation uses fixtures only (`tests/test_link_rot.py`). Record the
first scheduled or manually dispatched run after merge separately, with its
actual results. The live internet does not have to be clean for that run to
count.
