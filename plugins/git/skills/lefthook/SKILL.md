---
name: lefthook
license: CC-BY-4.0
description: >-
  Git hooks management with Lefthook. Use when writing or reviewing git hook
  configuration for Go projects, polyglot repos, or any project where Node.js
  is not already in the toolchain. Also trigger on mentions of 'lefthook',
  'lefthook.yml', 'lefthook install', parallel git hooks, or when the user
  asks which git hooks tool to use (husky vs lefthook). For Node.js/Bun
  projects that already have a JS runtime, see the husky skill instead.
compatibility: >-
  Requires lefthook binary
metadata:
  repo: https://github.com/nq-rdl/agent-skills
---

# Lefthook

Fast, language-agnostic Git hooks manager written in Go. Single binary, no
runtime dependencies, parallel execution by default.

> **See also**: The **husky** skill covers Node.js/Bun projects.
> For a decision guide, see [references/husky-vs-lefthook.rst](references/husky-vs-lefthook.rst).
>
> **Docs**: [lefthook.dev](https://lefthook.dev) |
> **Repo**: [evilmartians/lefthook](https://github.com/evilmartians/lefthook)

## Quick Start

```bash
# Install (pick one)
go install github.com/evilmartians/lefthook/v2@latest   # Go
brew install lefthook                                     # macOS
npm install lefthook --save-dev                           # Node.js
pip install lefthook                                      # Python

# Initialize in your project
lefthook install
```

Create `lefthook.yml` at project root:

```yaml
pre-commit:
  parallel: true
  jobs:
    - name: lint
      glob: "*.go"
      run: golangci-lint run --new-from-rev=HEAD {staged_files}
    - name: format
      glob: "*.go"
      run: gofmt -l {staged_files}

pre-push:
  jobs:
    - name: test
      run: go test -race ./...
```

## Core Concepts

### Jobs (not shell scripts)

Unlike husky (shell scripts in `.husky/`), lefthook uses declarative YAML jobs.
Each job has a `name`, a `run` command, and optional filters:

```yaml
pre-commit:
  jobs:
    - name: lint go
      glob: "*.go"
      run: golangci-lint run {staged_files}

    - name: lint yaml
      glob: "*.{yml,yaml}"
      run: yamllint {staged_files}
```

### File Templates

| Template | Meaning | Typical Hook |
|----------|---------|--------------|
| `{staged_files}` | Files in git staging area | pre-commit |
| `{push_files}` | Files changed since remote HEAD | pre-push |
| `{all_files}` | All tracked project files | manual run |
| `{files}` | Files from custom `files:` command | any |

### Parallel vs Piped Execution

```yaml
# Parallel (default) — all jobs run concurrently
pre-commit:
  parallel: true
  jobs:
    - name: lint
      run: golangci-lint run
    - name: format
      run: gofmt -l .

# Piped — jobs run sequentially, stop on first failure
pre-commit:
  piped: true
  jobs:
    - name: format first
      run: gofmt -w {staged_files}
      stage_fixed: true
    - name: then lint
      run: golangci-lint run {staged_files}
```

### Glob and File Type Filters

```yaml
jobs:
  - name: go lint
    glob: "*.go"
    exclude: "*_test.go"
    run: golangci-lint run {staged_files}

  - name: proto lint
    file_types: [".proto"]
    run: buf lint {staged_files}
```

### Auto-staging Fixes

```yaml
jobs:
  - name: format
    glob: "*.go"
    run: gofmt -w {staged_files}
    stage_fixed: true    # re-stage files after formatting
```

### Tags for Selective Execution

```yaml
pre-commit:
  jobs:
    - name: go lint
      tags: [backend, go]
      run: golangci-lint run

    - name: ts lint
      tags: [frontend, ts]
      run: eslint .
```

Override locally in `lefthook-local.yml` (git-ignored):

```yaml
pre-commit:
  exclude_tags: [frontend]
```

### Root Directory (Monorepos)

```yaml
pre-commit:
  jobs:
    - name: api lint
      root: "services/api/"
      glob: "*.go"
      run: golangci-lint run {staged_files}

    - name: web lint
      root: "services/web/"
      glob: "*.{ts,tsx}"
      run: eslint {staged_files}
```

## Go Project Patterns

### Standard Go CI hooks

```yaml
pre-commit:
  parallel: true
  jobs:
    - name: format
      glob: "*.go"
      run: gofmt -l {staged_files}

    - name: vet
      glob: "*.go"
      run: go vet ./...

    - name: lint
      glob: "*.go"
      run: golangci-lint run --new-from-rev=HEAD

commit-msg:
  jobs:
    - name: conventional
      run: >
        head -1 {1} | grep -qE '^(feat|fix|docs|style|refactor|perf|test|build|ci|chore|revert)(\(.+\))?: .+'
        || (echo "Commit message must follow Conventional Commits" && exit 1)

pre-push:
  parallel: true
  jobs:
    - name: test
      run: go test -race -count=1 ./...

    - name: build
      run: go build ./...
```

### With buf (protobuf)

```yaml
pre-commit:
  jobs:
    - name: buf lint
      glob: "*.proto"
      run: buf lint
    - name: buf format
      glob: "*.proto"
      run: buf format -w {staged_files}
      stage_fixed: true
```

### Multi-module Go repo

```yaml
pre-commit:
  jobs:
    - name: lint api
      root: "cmd/api/"
      glob: "*.go"
      run: golangci-lint run

    - name: lint cli
      root: "cmd/cli/"
      glob: "*.go"
      run: golangci-lint run
```

## Configuration Reference

```yaml
# lefthook.yml — full structure
min_version: 1.9.0            # minimum lefthook version

# Hook definitions (any git hook name)
pre-commit:
  parallel: true               # run jobs concurrently (default: false)
  piped: false                 # run jobs sequentially (mutually exclusive with parallel)
  follow: false                # continue on failure
  skip:
    - merge                    # skip during merges
    - rebase                   # skip during rebases
  only:
    - ref: main                # only run on specific branches
  jobs:
    - name: lint               # job identifier
      run: golangci-lint run   # shell command
      glob: "*.go"             # file pattern filter
      exclude: "vendor/**"     # exclude pattern
      file_types: [".go"]      # filter by extension
      root: "api/"             # working directory
      tags: [backend]          # grouping tags
      env:                     # environment variables
        CGO_ENABLED: 0
      stage_fixed: true        # re-stage after auto-fix
      priority: 1              # execution order (lower = first)
      interactive: false       # requires terminal interaction

# Remote hooks (pull from another repo)
remotes:
  - git_url: https://github.com/org/shared-hooks
    ref: main
    configs:
      - lefthook.yml

# Output control
output:
  - execution                  # show command execution
  - failure                    # show failure details
  - summary                   # show summary

# Source directories for script-based hooks
source_dir: ".lefthook"
source_dir_local: ".lefthook-local"
```

## Skip and Conditional Execution

```yaml
pre-commit:
  skip:
    - merge                    # skip during merge commits
    - rebase                   # skip during rebase
    - ref: main                # skip on main branch

  jobs:
    - name: slow-lint
      skip:
        - ref: feature/*       # skip on feature branches
      run: golangci-lint run --enable-all
```

## CI Integration

```bash
# Skip lefthook in CI
LEFTHOOK=0 git commit -m "ci: deploy"

# Or set globally in CI config
export LEFTHOOK=0
```

```yaml
# GitHub Actions — skip hooks
env:
  LEFTHOOK: 0
```

## Common Anti-Patterns

| Anti-Pattern | Fix |
|---|---|
| Using husky in a pure Go project | Use lefthook — no Node.js dependency needed |
| Running `go test ./...` in pre-commit | Move to pre-push — tests are slow for pre-commit |
| Not using `{staged_files}` | Always lint only staged files in pre-commit |
| Missing `stage_fixed: true` after formatters | Add it so auto-fixes get committed |
| Sequential execution for independent jobs | Use `parallel: true` |
| Hardcoding file lists | Use `glob:` and `file_types:` filters |
