---
icon: lucide/sparkles
---

# Gemini CLI

How agent-extensions packages skills for Gemini CLI as a single extension.

## Architecture

Gemini CLI uses a **single extension** model — one `gemini-extension.json` manifest with all skills in a `skills/` directory:

```text
gemini/
  gemini-extension.json      ← extension manifest
  GEMINI.md                  ← context file (loaded at session start)
  skills/
    tdd -> ../../skills/skills/tdd
    ansible -> ../../skills/skills/ansible
    r-expert -> ../../skills/skills/r-expert
    ... (41 total)
```

## How it works

1. **Extension manifest** (`gemini/gemini-extension.json`) declares the extension name, version, and a `contextFileName` pointing to `GEMINI.md`.

2. **Context file** (`gemini/GEMINI.md`) is loaded at session start and provides the model with an overview of available skills grouped by bundle.

3. **Skill symlinks** (`gemini/skills/<name>`) are relative symlinks into the `skills/` submodule. The symlink path is `../../skills/skills/<name>` (two levels up from the skill directory to the repo root, then into the submodule).

4. **Skill discovery** is automatic — Gemini CLI recursively finds `SKILL.md` files under `skills/` and activates them when the model identifies a relevant task.

## Install

### Local development

```bash
# Clone the repo and link the extension
git clone git@github.com:nq-rdl/agent-extensions.git
cd agent-extensions
git submodule update --init
gemini extensions link gemini/
```

### Remote install (Phase 2)

Gemini CLI expects `gemini-extension.json` at the repository root for `gemini extensions install`. Since our repo has `.claude-plugin/marketplace.json` at root for Claude, remote install requires either:

- A **mirror repo** (`nq-rdl/gemini-agent-extensions`) with `gemini-extension.json` at root
- A **GitHub Release archive** containing the extension as a self-contained tarball

This is planned for Phase 2. See [Deployment Phases](DEPLOYMENT_PHASES.md).

## Why one extension instead of bundles

Gemini CLI has no marketplace or bundle concept — each extension is a single installable unit. Splitting into 6 extensions would mean 6 separate repos to manage. Since skills auto-activate based on task context, having all 41 loaded adds no noise — unused skills simply never trigger.

## Update workflow

When skills are updated in the `nq-rdl/agent-skills` submodule:

1. Pull the latest agent-extensions repo.
2. Run `git submodule update --init` to refresh skills.
3. Restart the Gemini CLI session — extensions reload on startup.

## Gallery discovery

To list the extension in the [Gemini CLI gallery](https://geminicli.com/extensions/browse/), the extension repository needs:

- The `gemini-cli-extension` topic on the GitHub repo
- A tagged release
- `gemini-extension.json` at the repo root

This applies to the future mirror repo, not the monorepo.
