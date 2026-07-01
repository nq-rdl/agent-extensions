---
name: cc-agent-create
license: CC-BY-4.0
description: >-
  Add a new subagent to this agent-extensions catalog and take it all the way
  to a CI-green, commit-ready change. Use when the user wants to create, add,
  import, adapt, or normalize a catalog agent — a subagent authored under
  agents/<name>/agent.md — including adapting an upstream github/awesome-copilot
  .agent.md into repo conventions, or writing one from scratch. Walks the full
  registry → plugin-tree → manifest → changelog → validation pipeline: writes
  agents/<name>/agent.md, registers it in a registry bundle, runs sync-plugins,
  generate_manifests, changie, and validate-plugins. A session-scoped Stop hook
  it installs (and tears down) keeps the turn alive until the agent is fully
  wired, so the session cannot end with a half-wired agent. Covers both
  import-and-normalize (the common path) and from-scratch authoring.
argument-hint: "Which agent to add? (name + one-line purpose, or an upstream .agent.md URL to import — e.g. 'import github/awesome-copilot terraform-reviewer')"
user-invocable: true
metadata:
  repo: https://github.com/nq-rdl/agent-extensions
---

# Create a catalog agent

This skill guides a contributor (and Claude) through adding a **subagent** to this
`agent-extensions` catalog: authoring `agents/<name>/agent.md` and wiring it through
the registry → plugin-tree → manifest → changelog → validation pipeline until CI is
green. The deterministic wiring is done by **calling the repo's existing scripts** —
this skill's value-add is the judgment they can't provide: a strong triggering
`description`, a minimal `tools` list, clean normalization of messy upstream
frontmatter, and the right bundle.

> Authoritative details live in `references/`. Read the matching reference before the
> step that uses it — the frontmatter contract and the wiring pipeline are strictly
> gated by CI, and getting them wrong is the common failure.

**Scope (v1).** This adds *an agent to an existing bundle*. It does **not** create a
new bundle/plugin, and it is not a repo-agnostic "make an agent anywhere" tool.

---

## Two modes

| Mode | Use when | Primary path |
|------|----------|--------------|
| **Import-and-normalize** | Adapting an upstream `.agent.md` (≈30 of 31 catalog agents come from `github/awesome-copilot`) | `WebFetch` the source, normalize per `references/normalization.rst` |
| **From-scratch** | No upstream; you are writing the agent fresh | fill `assets/agent.md.template` |

Detect the mode from the request: a URL or "import/adapt <source>" ⇒ import; a bare
name + purpose ⇒ from-scratch. When unsure, ask.

---

## Before you start

- **Be at the repo root.** These scripts assume the working directory is the repo
  root (they resolve paths relative to it). Confirm `registry/bundles/` and `scripts/`
  are present before arming the guard.
- **Know the target bundle.** List `registry/bundles/*.yaml` and pick the subject the
  agent belongs to (e.g. `claude-code`, `go`, `terraform`). One bundle = one plugin.

---

## The guided pipeline

Create a **`TodoWrite` list with these nine items**, then work them top-to-bottom.
Each item names the reference or asset to read for it. The Stop hook installed in
step 2 keeps the turn alive until steps 3–8 verify, so do not skip ahead.

1. **Intake.** Detect the mode. Collect: `name` (kebab-case — becomes the directory
   `agents/<name>/`), a one-line purpose, the **target bundle** (show the list from
   `registry/bundles/`), a minimal `tools` list, and a `color` from the palette
   already in use. If importing: the upstream URL (or pasted content) and its license.
   - **Name collision:** if `agents/<name>/` already exists, stop and offer a new name
     or "edit the existing agent instead."

2. **Arm the guard.** Read `assets/session-hooks.json`, substitute `__AGENT_NAME__`
   with the agent `name` and `__BUNDLE__` with the target bundle, and **merge** the
   `hooks` object into `.claude/settings.local.json` (gitignored) — *never clobbering
   existing hooks*. The entries carry the marker `rdl-agent-create-guard` so teardown
   (step 9) removes exactly what you added. Tell the user the guard is active.
   - See `references/pipeline.rst` (`session guard`) for the merge/teardown mechanics
     and `assets/session-hooks.json` for what the two hooks do.

3. **Author** `agents/<name>/agent.md` per `references/frontmatter-contract.rst`.
   - *Import:* `WebFetch` the upstream (fall back to pasted content if the fetch
     fails; if neither is available, stop). Normalize it per
     `references/normalization.rst`: strip VS Code tool namespaces, map tools to
     Claude Code's, normalize `$ARGUMENTS` / tool-invocation prose, **retain the
     methodology and checklists verbatim**, add the `<!-- Derived from … -->`
     provenance comment, set `license` to the upstream's (MIT for awesome-copilot),
     and set `metadata.upstream` + `metadata.repo`.
   - *From-scratch:* fill `assets/agent.md.template` — a strong triggering
     `description` in the "Delegate to this agent when…" voice, and a focused
     system-prompt body. Omit `metadata.upstream`.
   - The `PostToolUse` hook fires on writes to `agents/*/agent.md` and adds a factual
     note listing the remaining wiring steps.

4. **Wire.** Add `<name>` to the `agents:` list of `registry/bundles/<bundle>.yaml`.
   Idempotent — skip if it is already present.

5. **Sync.** `bash scripts/sync-plugins.sh <bundle>` → produces the self-contained
   copy `plugins/<bundle>/agents/<name>.md`.

6. **Generate + consistency.** `python3 scripts/generate_manifests.py .`, then
   `python3 scripts/check_bundle_refs.py .` and `python3 scripts/check_consistency.py .`.
   For a pure agent addition the manifests are often unchanged, but the checks still
   gate registry ↔ plugins ↔ marketplace consistency. See `references/pipeline.rst`.

7. **Changie.** `changie new` — add a fragment describing the added agent (`kind:
   Added`). If the `changie` binary is missing, hand-write an equivalent fragment
   under `.changes/unreleased/` matching the format of the files already there. Name
   the agent in the fragment body (the Stop hook looks for it).

8. **Validate.** `bash scripts/validate-plugins.sh` — must exit 0. This also runs the
   agent-frontmatter check (every `agents/<name>/agent.md` has `name` + `description`).
   Fix any failure and re-run until green; the Stop hook keeps guarding until then.

9. **Disarm.** Remove only the `rdl-agent-create-guard` entries you added from
   `.claude/settings.local.json`; leave any pre-existing hooks intact. Print a diff
   summary of the files created/changed for the contributor to review and commit.

> **Do not commit or push** unless the contributor asks — leave the change in the
> working tree for review.

---

## Error handling

| Situation | Handling |
|-----------|----------|
| `agents/<name>/` already exists | Stop; offer a new name or "edit existing." |
| Agent already in the bundle | Skip the wire step (idempotent). |
| Upstream fetch fails | Fall back to pasted content; if neither, stop. |
| `validate-plugins.sh` fails | Surface the output, fix the cause, re-run. The Stop hook keeps guarding until green. |
| `changie` binary missing | Install it, or hand-write a fragment under `.changes/unreleased/`. |
| Not at the repo root | Detect before arming the guard; `cd` to the repo root first. |
| Pre-existing `settings.local.json` hooks | Merge, never clobber; teardown removes only the marked entries. |

---

## Reference files

| File | Contents |
|------|----------|
| [references/frontmatter-contract.rst](references/frontmatter-contract.rst) | The exact `agent.md` frontmatter schema, field-by-field, with the CI rules |
| [references/normalization.rst](references/normalization.rst) | Upstream `.agent.md` → repo `agent.md` conversion rules |
| [references/pipeline.rst](references/pipeline.rst) | Each wiring command in order, the artifact it produces, and the CI gate it satisfies; plus the session-guard mechanics |

## Asset files

| File | What it is |
|------|-----------|
| [assets/agent.md.template](assets/agent.md.template) | Fill-in skeleton for from-scratch authoring, matching the frontmatter contract |
| [assets/session-hooks.json](assets/session-hooks.json) | Parameterized Stop + PostToolUse hooks; substitute `__AGENT_NAME__`/`__BUNDLE__`, merge into `.claude/settings.local.json` |
