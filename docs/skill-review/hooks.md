# Hook packaging and portability review (#311)

This record covers both work packages of issue #311 (part of epic #312):
**A** — canonical hook packaging and installed behaviour, and **B** —
portability and scoped cleanup. The inventory, tasks, and invariants below
were recorded **before** any hook, sync, or test change, at source revision
`43de0df` (branch `epic/skill-review`).

Host: Linux 5.14 (RHEL 9), GNU bash 5.1.8, jq 1.6, Node.js 22.23.1,
Python 3.14.3 (pixi). The macOS-compatible run used the
`docker.io/library/bash:3.2` image (bash 3.2.57, BusyBox `grep`/`sed`, no
`jq`, no `python3`) under Podman.

## Baseline inventory (at `43de0df`)

"Claude parity" means that `scripts/sync-plugins.sh --check` fails when the
installed copy differs from the canonical source.

| Canonical hook | Bundle | Claude installed copy | Claude config source | Claude parity | Codex copy |
|---|---|---|---|---|---|
| `codex-session-lifecycle` | codex | `plugins/codex/scripts/` | hand-edited `plugins/codex/hooks/hooks.json` | **none** | not shipped (Codex uses `adapter.sh codex-context`) |
| `codex-stop-review-gate` | codex | `plugins/codex/scripts/` | hand-edited | **none** | not shipped |
| `codex-defect-report` | codex | `plugins/codex/scripts/` | hand-edited | **none** | not shipped |
| `skill-audit-nudge` | claude-code | `plugins/claude-code/scripts/` | hand-edited | **none** | `dist/.../hooks/` (checked) |
| `opencode-doc-review` | opencode-dev | `plugins/opencode-dev/scripts/` | hand-edited | **none** | checked |
| `redhat-docs-preflight` | redhat | `plugins/redhat/scripts/` | hand-edited | test-only byte check (`test_redhat_hooks.py`) | checked |
| `redhat-docs-guard` | redhat | `plugins/redhat/scripts/` | hand-edited | test-only byte check | checked |
| `speckit-publish-target` | speckit-dev | `plugins/speckit-dev/scripts/` | hand-edited | **none** | checked |
| `data-request-preflight` | data-request | `plugins/data-request/hooks/` | canonical `hooks/data-request/hooks.json` | sync `--check` (bytes only) | checked |
| `data-request-guard` | data-request | `plugins/data-request/hooks/` | canonical | sync `--check` (bytes only) | checked |
| `stylepedia-reminder` | tech-writing | `plugins/tech-writing/hooks/` | canonical `hooks/tech-writing/hooks.json` | sync `--check` (bytes only) | checked (inline adapter mode) |
| `changie-fragment-lint` | — (`registry/unbundled.yaml`) | none | `hooks/changie-fragment-lint.json` (repo-relative) | n/a | n/a |
| `hooks/codex/adapter.sh` | every Codex hook bundle | n/a | n/a | n/a | copied by `codex_package.py`, checked incl. mode |

All eleven shipped copies were byte-identical to `hooks/` at the baseline;
the gap is that nothing prevents drift for eight of them. The Codex side
(`codex_package.py --check`) already compared whole trees, including the
executable bit.

Runtime dependencies that live outside `hooks/`:

| Hook | Dependency | Resolved via |
|---|---|---|
| `codex-*` wrappers | `scripts/{session-lifecycle,stop-review-gate,defect-report}-hook.mjs` (vendored runtime) | `${CLAUDE_PLUGIN_ROOT}/scripts/` |
| `redhat-docs-preflight`, `redhat-docs-guard` | `skills/fetch-docs/scripts/rh-preflight.sh` → sources `rh-lib.sh` | `${CLAUDE_PLUGIN_ROOT}`, then `$(dirname "$0")/..` |
| `data-request-preflight`, `data-request-guard` | `skills/setup/scripts/sqlreview.sh` (+ `release.sh`, `sqlreview-identity.jq`) | `${CLAUDE_PLUGIN_ROOT}`, then `$(dirname "$0")/..` |
| every Codex hook | `hooks/adapter.sh` | `${PLUGIN_ROOT}` |

No canonical `hooks/*.sh` file is sourced by another hook; the
`*-preflight.sh` hooks are independent `SessionStart` hooks. The former
`sql-review-*` hooks were renamed to `data-request-*` in `c00f4e3`.

Baseline suites: `python3 -m unittest discover -s tests` — 1037 tests, OK;
`node --test tests/codex/*.test.mjs` — 223 tests, 223 pass.

## Tasks and invariants (recorded before changes)

### Work package A

| ID | Invariant |
|---|---|
| A-1 | Every hook-bearing bundle has one canonical Claude config under `hooks/<plugin>/hooks.json`; the packaged `plugins/<plugin>/hooks/` directory is generated from it. |
| A-2 | The destination of each hook script is read from the canonical config (`${CLAUDE_PLUGIN_ROOT}/<dir>/<name>.sh`). Every registry hook is wired at least once; every wired script is a registry hook. Install paths do not move. |
| A-3 | `sync-plugins.sh --check` fails on a stale, missing, content-drifted, or mode-drifted hook copy, and on a hook copy left in a legacy location. Vendored files next to hook copies (for example `plugins/codex/scripts/*.mjs`) are never pruned. |
| A-4 | Every `${CLAUDE_PLUGIN_ROOT}/…` path a packaged hook names resolves inside its own plugin tree (Claude and Codex). |
| A-5 | Hook commands survive a plugin root that contains spaces. |
| A-6 | A copy of only the plugin directory, run from an unrelated working directory whose path contains spaces, works with no access to this checkout: stdin is forwarded, the child exit status is preserved, executable bits are kept, and missing, old, or unparseable Node produces the exact preflight message. |
| A-7 | The Red Hat guard still denies a gated Portal fetch when `rh-preflight.sh` (or its sourced `rh-lib.sh`) is missing and no credential exists, and still allows it when an environment or file credential exists. No source error, no bypass. |
| A-8 | Existing skill packaging, Codex suites, and Red Hat suites stay green. |

### Work package B

| ID | Invariant |
|---|---|
| B-1 | The OpenCode route list names exactly the `opencode-dev` bundle leaves. |
| B-2 | The OpenCode hook carries no copied SDK version pin; it routes to `/opencode-dev:sdk` as the owner. |
| B-3 | Without `jq` and `python3`, the OpenCode and Spec Kit fallbacks still fire on bash 3.2 with non-GNU `grep`/`sed` and stay silent otherwise. |
| B-4 | The dormant changie hook is either removed with its allowlist entry or retained under the current event contract and changie policy (200-character body cap). The obsolete 20-word rule does not survive. |
| B-5 | A shared Node preflight is extracted only if it lowers risk; otherwise the single owned minimum is enforced by a test. |
| B-6 | Advisory hooks (OpenCode, Spec Kit, skill-audit nudge, Stylepedia) have fire, no-fire, malformed-input, and event-specific output tests. `hookSpecificOutput` is required only where the event uses it. |
