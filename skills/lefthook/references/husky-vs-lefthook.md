# Husky vs Lefthook — Decision Guide

> This is a **guide**, not a strict rule. Use the checklists to inform the
> decision, then apply project-specific judgement.

## Quick Decision Checklist

### Use Husky when:

- [ ] Project already has `package.json` (Node.js, Bun, Deno)
- [ ] Team uses npm/pnpm/bun for dependency management
- [ ] Full-stack app with JS/TS frontend + Go/Python backend
- [ ] Already using lint-staged for staged file linting
- [ ] Team is familiar with husky and `.husky/` conventions
- [ ] Project uses commitlint (npm package)

**Why**: Husky's `prepare` script runs on `npm install` — zero extra setup for
the team. Adding lefthook to a project that already has Node.js is an
unnecessary second tool.

**Example**: Bun + Go API monorepo

```
my-app/
├── package.json          # bun manages frontend + husky
├── .husky/
│   ├── pre-commit        # npx lint-staged
│   └── commit-msg        # npx commitlint --edit
├── frontend/             # React/Svelte
└── services/api/         # Go
```

Husky runs `lint-staged` for the frontend, and the pre-commit hook can also
call `go vet` and `golangci-lint` for the backend — no lefthook needed.

```bash
# .husky/pre-commit
#!/usr/bin/env bash
set -euo pipefail

# Frontend (JS/TS)
npx lint-staged

# Backend (Go)
cd services/api && go vet ./... && golangci-lint run --new-from-rev=HEAD
```

### Use Lefthook when:

- [ ] Pure Go project (no `package.json`)
- [ ] Pure Python, Ruby, or Rust project
- [ ] Polyglot repo where no single language dominates
- [ ] Performance matters (large repo, many hooks)
- [ ] Team wants parallel hook execution out of the box
- [ ] No Node.js in the project toolchain
- [ ] Monorepo with multiple Go modules

**Why**: Lefthook is a single Go binary — no runtime dependencies. Installing
`npm` + `husky` just for git hooks in a Go project adds an entire ecosystem
the project doesn't otherwise need.

**Example**: Pure Go service

```
my-service/
├── go.mod
├── lefthook.yml          # all hooks in one file
├── cmd/
└── internal/
```

```yaml
# lefthook.yml
pre-commit:
  parallel: true
  jobs:
    - name: format
      glob: "*.go"
      run: gofmt -l {staged_files}
    - name: vet
      run: go vet ./...
    - name: lint
      run: golangci-lint run --new-from-rev=HEAD

pre-push:
  jobs:
    - name: test
      run: go test -race ./...
```

### Either works for:

- [ ] Small project with simple hooks (1-2 pre-commit checks)
- [ ] Team has no strong preference
- [ ] Solo developer project

In these cases, pick whichever the team already knows.

## Feature Comparison

| Feature | Husky v9 | Lefthook v2 |
|---------|----------|-------------|
| **Language** | JavaScript (npm) | Go (single binary) |
| **Config format** | Shell scripts in `.husky/` | YAML (`lefthook.yml`) |
| **Auto-install** | `prepare` script on `npm install` | `lefthook install` (manual or npm postinstall) |
| **Parallel execution** | No (sequential) | Yes (default) |
| **Staged file passing** | Via lint-staged (separate dep) | Built-in `{staged_files}` template |
| **Auto-stage fixes** | Via lint-staged | Built-in `stage_fixed: true` |
| **Glob filtering** | Via lint-staged | Built-in `glob:` / `file_types:` |
| **Monorepo support** | Manual `cd` in scripts | Built-in `root:` directive |
| **Tag-based filtering** | No | Yes (`tags:` + `exclude_tags:`) |
| **Local overrides** | No standard mechanism | `lefthook-local.yml` (git-ignored) |
| **Remote hooks** | No | Yes (`remotes:` pulls from git repos) |
| **Skip in CI** | `HUSKY=0` | `LEFTHOOK=0` |
| **Runtime dependency** | Node.js | None |
| **npm weekly downloads** | ~5M | ~400K |
| **Performance** | ~1ms (shell) + Node.js startup | ~1ms (native binary) |

## Migration Paths

### Husky to Lefthook

1. Install lefthook: `go install github.com/evilmartians/lefthook/v2@latest`
2. Convert `.husky/` scripts to `lefthook.yml` jobs
3. Remove husky: `npm uninstall husky && rm -rf .husky`
4. Remove `prepare` script from `package.json`
5. Run `lefthook install`

**Before** (husky):
```bash
# .husky/pre-commit
#!/usr/bin/env bash
set -euo pipefail
npx lint-staged
```

**After** (lefthook):
```yaml
# lefthook.yml
pre-commit:
  parallel: true
  jobs:
    - name: lint js
      glob: "*.{js,ts,tsx}"
      run: eslint --fix {staged_files}
      stage_fixed: true
    - name: format
      glob: "*.{css,md,json}"
      run: prettier --write {staged_files}
      stage_fixed: true
```

### Lefthook to Husky

Rarely needed, but if the project adopts Node.js:

1. `npm install --save-dev husky lint-staged`
2. `npx husky init`
3. Convert `lefthook.yml` jobs to `.husky/` scripts + lint-staged config
4. Remove lefthook: `lefthook uninstall && rm lefthook.yml`

## Architecture Decision Record Template

When documenting the choice for a project:

```markdown
## ADR: Git Hooks Tool Selection

**Status**: Accepted
**Date**: YYYY-MM-DD

**Context**: [Describe the project stack and team]

**Decision**: Use [husky/lefthook] because:
- [Primary reason from the checklist above]
- [Secondary reason]

**Consequences**:
- [What this means for the team/workflow]
```
