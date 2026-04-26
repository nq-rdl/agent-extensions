---
name: husky
license: CC-BY-4.0
description: >-
  Manage Git hooks with husky v9. Use when the user asks about git hooks
  setup, pre-commit hooks, commit-msg hooks, husky configuration, the
  prepare script, or CI integration for git hooks. Trigger on mentions of
  'husky', '.husky/', 'prepare script', or git hook lifecycle management.
compatibility: >-
  Requires Node.js runtime and npm
metadata:
  repo: https://github.com/nq-rdl/agent-skills
---

# Husky Skill

Opinionated guidance for husky v9 git hooks management. Covers installation, hook authoring, CI integration, and real-world patterns.

---

## Overview

Husky uses Git's native `core.hooksPath` to run shell scripts from `.husky/` on git events (commit, push, merge, etc.). It has no runtime dependencies, runs in ~1ms, and supports all 13 client-side git hooks.

**When to use husky:**
- Enforce code quality checks before commits (lint, format, test)
- Validate commit messages (commitlint)
- Run pre-push checks
- Automate team-wide git workflow policies

> **Not using Node.js?** For pure Go, Python, or polyglot projects without
> `package.json`, consider the **lefthook** skill instead — a Go binary with
> no runtime dependencies. It includes a husky-vs-lefthook decision guide
> with checklists.

---

## Installation and Setup

```bash
npm install --save-dev husky
npx husky init
```

`npx husky init` does two things:
1. Creates `.husky/pre-commit` with a sample `npm test` script
2. Adds `"prepare": "husky"` to `package.json`

The `prepare` script runs automatically on `npm install`, so all team members get hooks installed when they set up the project.

**Manual setup (without `npx husky init`):**

```bash
npm install --save-dev husky
# Add to package.json scripts:
# "prepare": "husky"
# Then create hooks manually in .husky/
```

---

## The `prepare` Script

```json
{
  "scripts": {
    "prepare": "husky"
  }
}
```

This is the canonical pattern — husky runs during `npm install` to configure `core.hooksPath`.

**For CI/production environments** where `npm install` runs but hooks should not be installed:

```json
{
  "scripts": {
    "prepare": "husky || true"
  }
}
```

Or use an install guard in `.husky/install.mjs`:

```js
// Skip husky in CI or production
if (process.env.CI === 'true' || process.env.NODE_ENV === 'production') process.exit(0)
const husky = await import('husky')
husky.default()
```

Then update `prepare`:
```json
"prepare": "node .husky/install.mjs"
```

---

## Creating Hooks

Hook files live in `.husky/` and are plain shell scripts. No JSON config needed.

```bash
# Create a pre-commit hook
cat > .husky/pre-commit << 'EOF'
#!/usr/bin/env bash
set -euo pipefail
npm test
EOF
chmod +x .husky/pre-commit
```

**Common hooks:**

| Hook | Trigger | Typical Use |
|------|---------|-------------|
| `pre-commit` | Before commit is created | Lint, test, validate |
| `commit-msg` | After commit message written | commitlint validation |
| `pre-push` | Before push to remote | Full test suite, build |
| `post-merge` | After merge completes | `npm install` to sync deps |
| `post-checkout` | After branch switch | `npm install` to sync deps |
| `prepare-commit-msg` | Before commit message editor | Prepend branch name to message |

---

## Common Hook Patterns

### lint-staged (lint only staged files)

```bash
# .husky/pre-commit
npx lint-staged
```

```json
// package.json
{
  "lint-staged": {
    "*.{js,ts}": "eslint --fix",
    "*.{css,md}": "prettier --write"
  }
}
```

### commitlint (enforce commit message format)

```bash
# .husky/commit-msg
npx commitlint --edit $1
```

### Marketplace validation (this repo's pattern)

```bash
# .husky/pre-commit
#!/usr/bin/env bash
set -euo pipefail

if command -v claude >/dev/null 2>&1; then
  claude plugin validate . || {
    echo "FAIL: Marketplace validation failed."
    exit 1
  }
fi
```

See this repo's actual `.husky/pre-commit` for a full real-world example combining marketplace validation with lychee link checking.

---

## CI/CD Integration

**Skip hooks in CI** by setting `HUSKY=0`:

```yaml
# GitHub Actions
env:
  HUSKY: 0
```

```bash
# Shell one-liner
HUSKY=0 npm install
```

**Skip a single command** (not recommended — prefer CI env var):

```bash
git commit --no-verify -m "chore: skip hooks"
# or
HUSKY=0 git commit -m "chore: skip hooks"
```

---

## Hook Script Best Practices

1. **Always start with `set -euo pipefail`** — exits immediately on error, unset variables, or pipe failure.

2. **Use `#!/usr/bin/env bash`** — portable shebang that works on macOS and Linux.

3. **Guard optional tools with `command -v`** — skip gracefully if a tool is not installed:
   ```bash
   command -v node >/dev/null 2>&1 || { echo "SKIP: node not found"; exit 0; }
   ```

4. **Use non-zero exit codes to abort the git operation** — exit 1 cancels the commit/push.

5. **Keep hooks fast** — pre-commit hooks run on every commit; slow hooks hurt developer experience. Prefer lint-staged over full linting.

---

## Node Version Manager Integration

When using nvm/fnm/volta, GUI git clients may not source shell init files. Fix by adding your NVM init to `~/.config/husky/init.sh`:

```bash
# ~/.config/husky/init.sh
export NVM_DIR="$HOME/.nvm"
[ -s "$NVM_DIR/nvm.sh" ] && \. "$NVM_DIR/nvm.sh"
```

---

## Troubleshooting

**Hooks not running:**
- Verify `core.hooksPath` is set: `git config core.hooksPath` → should show `.husky`
- Check hook files are executable: `ls -la .husky/` → look for `rwxr-xr-x`
- Re-run `npm install` to trigger the `prepare` script

**`command not found` in hook:**
- Tool is not on PATH in the hook's environment (common with GUI clients)
- Fix: add sourcing to `~/.config/husky/init.sh`

**Hooks blocked by `--no-verify`:**
- This repo's safety hooks block `--no-verify` usage — use `HUSKY=0` in CI instead

**Hooks installed but not executing:**
- Check shebang line is correct: `#!/usr/bin/env bash` (not `#!/bin/sh` on macOS)

---

## Reference Files

- [`references/hooks-reference.rst`](references/hooks-reference.rst) — All 13 git hook types, v8→v9 migration notes, script patterns, and monorepo setup.
