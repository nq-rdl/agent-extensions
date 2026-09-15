---
icon: lucide/bot
---

# Codex

All 36 subject bundles have native Codex packages. Canonical procedures remain in
`skills/`; optional worker outlines remain in `references/subagent.rst`. Neither
publication target installs standalone named agents. Oh My Pi is out of scope.

## Install

```bash
codex plugin marketplace add nq-rdl/agent-extensions
codex plugin list --marketplace rdl-agent-extensions --available --json
codex plugin add go@rdl-agent-extensions --json
```

Until the integration reaches `main`, select a pushed branch or commit explicitly:

```bash
codex plugin marketplace add nq-rdl/agent-extensions --ref <branch-or-sha> --json
```

Start a new session. Skills use qualified names such as `$go:naming`. Existing
explicit-only invocation settings remain intact; those skills are installed but
omitted from automatic skill selection. [Bundle listings](bundles.md) show the
available entrypoints.

## Strict packaging

The registry produces two independent, self-contained trees:

| Target | Plugin root | Skill name |
|---|---|---|
| Claude Code | `plugins/<subject>/` | Copy omits `name:` to retain namespaced autocomplete |
| Codex | `dist/codex/plugins/<subject>/` | Copy explicitly sets `name: <leaf>` |

Both start from `skills/<source>/`, using the registry's source-to-leaf mapping.
Codex packages use `.codex-plugin/plugin.json`. Identity, version, interface metadata and component
selection come from the registry. Root `mcp.json` and compatibility `.mcp.json`
carry equivalent server definitions.

Codex copies retain references, scripts, templates, executable modes, licenses,
and required runtime resources. The packager rejects source symlinks and removes
stale packages and agent directories. `--check` compares bytes and executable
modes without rewriting output.

Claude-authoring skills still describe Claude Code. Their native entrypoints
clarify that Claude configuration and API examples are artifacts to author, not
Codex tools. The `codex` companion bundle has explicit host-specific entrypoints
under canonical `references/codex.rst`; the registry selects them. Its vendored
Node runtime remains shared, with native manifest detection. Transfer imports an
explicit Claude transcript; it does not interpret a Codex transcript as Claude.

In ordinary shell calls, derive `PLUGIN_ROOT` from the installed skill path.
Codex supplies that environment variable to hooks, but not automatically to the
skill's shell commands. `$ARGUMENTS` denotes user input, not an injected variable.

### Pinned runtime format decision

Codex 0.154.0 suppresses plugin hooks when it recognizes a portable root
`plugin.json`. The native format passes real `hooks/list` discovery, so these
packages deliberately omit the portable root manifest. Current OpenAI packaging
docs describe portable overlays, but changing formats requires a passing runtime
hook test first. Explicit skill names and self-contained files remain mandatory.

## MCP

| Bundle | Transport | Prerequisites and verification |
|---|---|---|
| `playwright` | Local stdio; pinned `@playwright/mcp@0.0.70` | Node/npm, browser dependencies; initialize and list tools with the live smoke check |
| `lucid` | Hosted HTTPS at `https://mcp.lucid.app/mcp` | User authentication and Lucid access; a credential-free probe verifies only the authentication boundary |

Enable MCP independently through `targets.codex.components.mcp` and provide an
explicit `mcpConfig` source. Empty or malformed servers, unsafe paths, and unpinned
npx packages fail package validation. Apps are not enabled: registered app mappings
require a separate integration.

## Hooks

Codex uses explicit native command-hook definitions under
`hooks/codex/<subject>/hooks.json`, copied into each selected package. Shared
implementations remain under `hooks/`; `hooks/codex/adapter.sh` translates native
payloads where needed. Users must enable hooks and review/trust them in Codex's
`/hooks` interface. Installation does not grant hook trust.

| Bundle | Native behavior | Boundary |
|---|---|---|
| `claude-code` | Skill-audit reminder after `apply_patch` | Reads changed-file headers; advisory |
| `redhat` | Session preflight and shell credential/fetch guard | Native shell payloads; legacy `ask` becomes a supported denial with a recovery path |
| `sql-code` | Session status and protection of authoritative review/config patch paths | Draft patches pass; authoritative documents require whole-document checking and sanctioned rendering |
| `opencode-dev` | Documentation-verification context on matching prompts | Advisory |
| `speckit-dev` | Publishing-target context on matching prompts | Advisory |
| `tech-writing` | House-style/Stylepedia reminder for explicit writing skills | Advisory; Claude agent-based Stop/SubagentStop review is not executable in Codex |
| `codex` | Session guidance for companion jobs and transcript import | Claude session lifecycle and automatic stop-review hooks are not installed |

The SQL patch guard does not intercept shell writes. Validate complete review
records with the installed `sqlreview.sh check` before publishing them, then use
`sqlreview.sh render`. Hooks are workflow guardrails, not a security boundary.
Native adapters never translate an unsupported decision into automatic approval.

`$codex:setup` checks the independent CLI's installation and authentication.
Its native description reflects that scope. Review-gate flags are rejected before
the companion runs: the automatic stop-review hook belongs to Claude Code.

See the [Codex hook contract](https://developers.openai.com/codex/hooks) for
supported events, payloads, trust, and tool-coverage limits.

## Validation

All repository Python runs through Pixi:

```bash
pixi run bash scripts/sync-plugins.sh
pixi run python3 scripts/generate_manifests.py .
pixi run python3 scripts/generate_bundles_doc.py .
pixi run python3 scripts/codex_package.py . --validate
pixi run bash scripts/sync-plugins.sh --check
pixi run bash scripts/validate-plugins.sh
bash scripts/smoke-codex-marketplace.sh
pixi run python3 scripts/check_codex_runtime.py .
```

The lifecycle test installs every bundle into an isolated `CODEX_HOME`, verifies
fresh-session discovery and complete cached packages, removes everything, and
reinstalls. A separate fixture verifies version replacement updates fresh-session discovery. It covers MCP-only packages and preserves explicit-only skill policy.
Native hook tests use copied caches with spaces in their paths and verify actual
allow/deny/context outputs. No test installs this catalog into the contributor's
active session.

Use the optional network check for actual MCP initialization and endpoint probing:

```bash
pixi run python3 scripts/check_codex_runtime.py . --live-mcp
```

To test a pushed ref against the local expected artifacts:

```bash
CODEX_MARKETPLACE_SOURCE=nq-rdl/agent-extensions \
CODEX_MARKETPLACE_REF=<commit-or-tag> \
  bash scripts/smoke-codex-marketplace.sh
```

Packaging, parser discovery and connection probes do not establish model task
quality. Record authenticated execution against representative positive and
negative cases before claiming behavioral acceptance or public submission readiness.

## Directory readiness

The [generated readiness report](codex-directory.md) lists per-bundle blockers and
submission routes. Build deterministic archives and SHA-256 checksums with:

```bash
pixi run python3 scripts/codex_directory.py . --write-report
pixi run python3 scripts/codex_directory.py . --archives dist/codex/archives
```

`--require-ready` fails until all recorded submission blockers are resolved.
Publisher-approved branding, privacy/terms URLs, verified publisher identity,
behavioral evidence, and MCP ownership/authentication cannot be inferred from a
successful local package test. Existing explicit-only skills retain their policy;
the directory's invocation-policy constraint requires a deliberate publisher decision.

Public submission is separate from repository distribution. Local Playwright MCP
needs an approved local-runtime submission route or a public deployment; Lucid
requires authorization and domain verification by its service owner. See
[OpenAI submission requirements](https://developers.openai.com/plugins/deploy/submission).
