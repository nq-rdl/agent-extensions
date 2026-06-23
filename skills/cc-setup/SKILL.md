---
name: cc-setup
license: CC-BY-4.0
description: >-
  Onboard a user onto the RDL team's Claude Code setup. Use when the user wants to
  "set up Claude Code", "set up my .claude", "onboard onto the RDL Claude Code
  setup", "install the forced-eval hook", or "configure Claude Code for the team".
  Asks whether to configure a project-local `.claude/` or the user's global
  `~/.claude/`, then installs the team's `forced-eval-hook.sh` (a UserPromptSubmit
  hook that surfaces available skills as advisory context) and wires it into the
  chosen scope's `settings.json` idempotently. The minimal first step of RDL
  Claude Code onboarding — later passes will guide the wider settings surface.
argument-hint: "Set up Claude Code for the RDL team? (say 'project' for this repo's .claude/, or 'global' for ~/.claude/)"
user-invocable: true
metadata:
  repo: https://github.com/nq-rdl/agent-extensions
---

# RDL team Claude Code setup

Your job is to onboard the user onto the RDL team's Claude Code configuration. This
first pass does one concrete thing: install the team's **`forced-eval-hook.sh`** and
wire it as a `UserPromptSubmit` hook in the scope the user chooses. The hook script
ships in this skill's `assets/` directory; you copy it into the target `.claude/` and
merge the settings idempotently.

> **Scope.** This is deliberately minimal — the hook is the floor, not the ceiling.
> Do not configure model, permissions, MCP servers, or other settings here unless the
> user explicitly asks. A future pass will turn this into a fuller guided tour of the
> Claude Code settings surface.

## What the hook does

`forced-eval-hook.sh` is a `UserPromptSubmit` hook. When a prompt expresses intent to
*use* a skill (an action verb sits near "skill"/"skills"), it discovers the available
skills and slash commands — standalone (`~/.claude/skills/*/SKILL.md`) and plugin
(`~/.claude/plugins/installed_plugins.json`) — and emits them as **advisory context**
so the model considers them. It is a silent no-op otherwise. The framing is
descriptive; it does not coerce a fixed activation sequence. It uses `jq` when present
and degrades gracefully without it.

## Phase 0 — Choose the scope

Ask the user **where** to install (unless they already said in the invocation):

| Scope | Install the script to | Wire the hook in | Use when |
|---|---|---|---|
| **project** | `<repo>/.claude/hooks/forced-eval-hook.sh` | `<repo>/.claude/settings.json` | configuring one repo; the setting can be committed and shared with the team |
| **global** | `~/.claude/hooks/forced-eval-hook.sh` | `~/.claude/settings.json` | the user wants the hook on every project they open |

Notes:
- For **project** scope, default to `.claude/settings.json` (committed, team-shared).
  If the user wants it personal/uncommitted, use `.claude/settings.local.json` instead
  (same `hooks` block; gitignored).
- Confirm the project root has a `.git` directory before treating it as the project
  scope target.

## Phase 1 — Install the hook script

Copy `assets/forced-eval-hook.sh` from this skill into the chosen `hooks/` directory,
creating it if absent, and make it executable:

```bash
# project scope
mkdir -p .claude/hooks
cp <this skill's assets>/forced-eval-hook.sh .claude/hooks/forced-eval-hook.sh
chmod +x .claude/hooks/forced-eval-hook.sh
```

```bash
# global scope
mkdir -p "$HOME/.claude/hooks"
cp <this skill's assets>/forced-eval-hook.sh "$HOME/.claude/hooks/forced-eval-hook.sh"
chmod +x "$HOME/.claude/hooks/forced-eval-hook.sh"
```

Resolve `<this skill's assets>` to this skill's own `assets/` directory. On an
installed plugin the skill lives in the plugin cache — locate it rather than guessing:

```bash
SRC="$(find "$HOME/.claude/plugins" -path '*/cc-setup/assets/forced-eval-hook.sh' 2>/dev/null | head -1)"
# Fallback: the absolute path of the assets/ directory beside this SKILL.md.
SRC="${SRC:-<absolute path to this skill>/assets/forced-eval-hook.sh}"
```

If the target file already exists and differs, show the diff and ask before overwriting.

## Phase 2 — Wire the `UserPromptSubmit` hook

Merge this block into the chosen `settings.json` (`command` path matches Phase 1's
install location). **Show the diff before writing**, and merge idempotently — never
clobber existing keys, and dedupe by exact `command` string so re-running is a no-op.

Shell-form hook commands run via `sh -c`, so keep the variable **double-quoted inside
the JSON string** (`"$CLAUDE_PROJECT_DIR"` / `"$HOME"`) — an unquoted path that contains
spaces would word-split and the hook would fail to launch.

Project scope (`.claude/settings.json`) — use `$CLAUDE_PROJECT_DIR` so the path is
portable:

```json
{
  "hooks": {
    "UserPromptSubmit": [
      {
        "hooks": [
          {
            "type": "command",
            "command": "\"$CLAUDE_PROJECT_DIR\"/.claude/hooks/forced-eval-hook.sh",
            "timeout": 10
          }
        ]
      }
    ]
  }
}
```

Global scope (`~/.claude/settings.json`) — use `$HOME`:

```json
{
  "hooks": {
    "UserPromptSubmit": [
      {
        "hooks": [
          {
            "type": "command",
            "command": "\"$HOME\"/.claude/hooks/forced-eval-hook.sh",
            "timeout": 10
          }
        ]
      }
    ]
  }
}
```

Merge rules when the file already exists:
- Parse the existing JSON. If `hooks.UserPromptSubmit` exists, append this rule group
  to it **only if** no group already references `forced-eval-hook.sh`.
- If `hooks` or `hooks.UserPromptSubmit` is absent, create it.
- Leave every other key untouched.

## Phase 3 — Verify

- `jq . <settings file>` parses without error.
- The installed script is executable (`test -x <path>` succeeds).
- Optional smoke test — the hook is a no-op unless intent is detected:
  ```bash
  printf '{"prompt":"please use a skill"}' | <installed forced-eval-hook.sh>
  ```
  expect it to emit the skill catalogue (or exit 0 quietly if no skills are installed);
  `printf '{"prompt":"hello"}' | <script>` should exit 0 with no output.

## Phase 4 — Summarize

Tell the user, concisely:
- The scope chosen, the script path installed, and the settings file touched.
- That the hook only fires when a prompt expresses intent to use a skill — it is a
  silent no-op otherwise.
- For **project** scope: commit `.claude/hooks/forced-eval-hook.sh` and the settings
  change so the team picks them up (or note it is personal if they chose
  `settings.local.json`).
- That this is the first onboarding step; more RDL Claude Code configuration can follow.
