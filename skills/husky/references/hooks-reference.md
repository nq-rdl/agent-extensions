# Git Hooks Reference for Husky v9

Quick reference for all git hook types, script patterns, and migration notes.

---

## All 13 Client-Side Git Hooks

| Hook | When it runs | Exit 1 effect | Common use |
|------|-------------|---------------|------------|
| `pre-commit` | Before commit object created | Aborts commit | Lint, format, test staged files |
| `prepare-commit-msg` | Before commit msg editor opens | Aborts commit | Inject branch name or template |
| `commit-msg` | After user writes commit message | Aborts commit | commitlint, message validation |
| `post-commit` | After commit is created | No effect | Notifications, logging |
| `pre-rebase` | Before rebase starts | Aborts rebase | Warn on rebase of published branches |
| `post-rewrite` | After rebase/amend rewrites | No effect | Invalidate caches |
| `post-checkout` | After `git checkout` or `git switch` | No effect | `npm install`, generate files |
| `post-merge` | After successful merge | No effect | `npm install`, sync lockfiles |
| `pre-push` | Before push to remote | Aborts push | Full test suite, build verification |
| `pre-receive` | Server-side: before refs updated | — | (server-side only) |
| `post-receive` | Server-side: after refs updated | — | (server-side only) |
| `pre-auto-gc` | Before git garbage collection | Aborts gc | Prevent gc at bad times |
| `post-index-change` | After index is written | No effect | Trigger rebuilds |

---

## Hook Script Template

```bash
#!/usr/bin/env bash
# .husky/<hook-name>
set -euo pipefail

# Guard: skip if tool not installed
command -v npx >/dev/null 2>&1 || { echo "SKIP: npx not found"; exit 0; }

# Your hook logic here
npm test
```

Key lines:
- `#!/usr/bin/env bash` — portable shebang (works on macOS and Linux)
- `set -euo pipefail` — exit on error (`-e`), unset variable (`-u`), pipe failure (`-o pipefail`)
- `command -v <tool>` — check tool exists before calling it

---

## commit-msg Hook: Accessing the Message

The commit message file path is passed as `$1`:

```bash
#!/usr/bin/env bash
# .husky/commit-msg
set -euo pipefail

# commitlint
npx commitlint --edit "$1"

# Manual check example
MSG=$(cat "$1")
if [[ "$MSG" =~ ^WIP ]]; then
  echo "ERROR: WIP commits are not allowed"
  exit 1
fi
```

---

## pre-push Hook: Accessing Push Context

Push info is passed via stdin (oldrev, newrev, refname):

```bash
#!/usr/bin/env bash
# .husky/pre-push
set -euo pipefail

while read local_ref local_sha remote_ref remote_sha; do
  echo "Pushing $local_ref to $remote_ref"
done

npm test
```

---

## v8 → v9 Migration Notes

| Change | v8 | v9 |
|--------|----|----|
| Hook directory | `.husky/` with `_/husky.sh` sourced | `.husky/` — direct shell scripts, no `_/` sourcing |
| Config location | `package.json` `husky` key | Individual files in `.husky/` |
| Environment variable | `HUSKY_SKIP_HOOKS` | `HUSKY=0` |
| Git params | `HUSKY_GIT_PARAMS` | Native shell params (`$1`, `$2`) |
| Require shebang | No | Yes — `#!/usr/bin/env bash` or `#!/bin/sh` required |
| Init command | `npx husky install` | `npx husky init` |

**Removing the old `_/` directory:**

```bash
rm -rf .husky/_
# Remove any ". "$(dirname -- "$0")/_/husky.sh"" lines from hook files
```

---

## Monorepo Pattern

When the Node project is not at the git root:

```json
// frontend/package.json
{
  "scripts": {
    "prepare": "cd .. && husky frontend/.husky"
  }
}
```

Hook scripts must change back to the package directory:

```bash
#!/usr/bin/env bash
# frontend/.husky/pre-commit
cd frontend
npm test
```

---

## lint-staged Integration

```bash
npm install --save-dev lint-staged
```

```bash
# .husky/pre-commit
npx lint-staged
```

```json
// package.json
{
  "lint-staged": {
    "*.{js,ts,tsx}": ["eslint --fix", "git add"],
    "*.{css,scss}": "prettier --write",
    "*.md": "markdownlint"
  }
}
```

---

## commitlint Integration

```bash
npm install --save-dev @commitlint/cli @commitlint/config-conventional
echo "export default { extends: ['@commitlint/config-conventional'] };" > commitlint.config.mjs
```

```bash
# .husky/commit-msg
npx commitlint --edit "$1"
```

---

## Disabling Hooks

| Scope | Method |
|-------|--------|
| Single command | `git commit --no-verify` or `HUSKY=0 git commit` |
| Current shell session | `export HUSKY=0` then `unset HUSKY` when done |
| CI environment | Set `HUSKY: 0` in CI env vars |
| Globally (GUI) | Add `export HUSKY=0` to `~/.config/husky/init.sh` |

Note: `--no-verify` is blocked by this repo's safety hooks. Use `HUSKY=0` in CI instead.
