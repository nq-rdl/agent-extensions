---
name: go-gh
license: MIT
description: >-
  GitHub Actions CI/CD for Go projects. Use when writing or reviewing GitHub
  Actions workflows that build, test, lint, or release Go code — including
  actions/setup-go configuration, Go version matrix, dependency caching,
  go.mod/go.work version files, artifact uploads, and monorepo cache strategies.
  Also trigger when the user asks about CI for Go, GitHub Actions Go templates,
  or how to test Go on multiple versions in CI.
metadata:
  repo: https://github.com/nq-rdl/agent-skills
---

# GitHub Actions for Go

Set up, build, test, and ship Go projects in GitHub Actions using
[`actions/setup-go`](https://github.com/actions/setup-go) (v5+).

> **Reference docs** — detailed examples live in `references/`:
> - `advanced-usage.rst` — version strategies, caching, custom mirrors
> - `build-test.rst` — full workflow patterns, matrix, artifacts

## Quick Start

Minimal CI workflow:

```yaml
name: Go CI
on: [push, pull_request]
jobs:
  build:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v5
      - uses: actions/setup-go@v5
        with:
          go-version-file: go.mod
      - run: go build -v ./...
      - run: go test -v ./...
```

## Core Guidelines

### 1. Prefer `go-version-file` over hardcoded versions

Let `go.mod` (or `go.work`, `.go-version`) be the single source of truth:

```yaml
- uses: actions/setup-go@v5
  with:
    go-version-file: go.mod   # reads toolchain or go directive
```

Only hardcode for matrix strategies or versions not tracked in module files.

### 2. Version specification

| Format | Meaning | Example |
|--------|---------|---------|
| `1.25.5` | Exact patch | Reproducible builds |
| `1.25` | Latest patch of minor | Pre-installed on runners = fast |
| `^1.25.1` | SemVer range | Flexible matching |
| `stable` | Latest stable release | Always current |
| `oldstable` | Previous minor's latest patch | Compatibility testing |
| `1.25.0-rc.2` | Pre-release | Beta/RC testing |

### 3. Matrix testing across versions

```yaml
strategy:
  matrix:
    go-version: ['1.24', '1.25']
    os: [ubuntu-latest, macos-latest, windows-latest]
steps:
  - uses: actions/checkout@v5
  - uses: actions/setup-go@v5
    with:
      go-version: ${{ matrix.go-version }}
  - run: go test -v ./...
```

### 4. Caching is automatic

`actions/setup-go` v5+ caches `~/go/pkg/mod` and `~/.cache/go-build` automatically
using `go.sum` as the cache key. Override for special cases:

```yaml
# Monorepo — point to the right go.sum
- uses: actions/setup-go@v5
  with:
    go-version-file: go.mod
    cache-dependency-path: subdir/go.sum

# Multi-module — glob or multi-line
- uses: actions/setup-go@v5
  with:
    go-version-file: go.mod
    cache-dependency-path: |
      go.sum
      tools/go.sum

# Disable cache entirely
- uses: actions/setup-go@v5
  with:
    go-version-file: go.mod
    cache: false
```

### 5. Build and test pattern

Standard CI job structure:

```yaml
steps:
  - uses: actions/checkout@v5
  - uses: actions/setup-go@v5
    with:
      go-version-file: go.mod
  - name: Install dependencies
    run: go mod download
  - name: Build
    run: go build -v ./...
  - name: Test
    run: go test -v -race -coverprofile=coverage.out ./...
  - name: Upload coverage
    uses: actions/upload-artifact@v4
    with:
      name: coverage
      path: coverage.out
```

### 6. Test result artifacts

Export JSON test output for downstream analysis:

```yaml
- name: Test with JSON output
  run: go test -json ./... > test-results.json
- name: Upload test results
  uses: actions/upload-artifact@v4
  with:
    name: test-results-${{ matrix.go-version }}
    path: test-results.json
```

### 7. Use outputs for downstream steps

```yaml
- uses: actions/setup-go@v5
  id: setup
  with:
    go-version: '^1.24'
- run: echo "Installed ${{ steps.setup.outputs.go-version }}"
- run: echo "Cache hit: ${{ steps.setup.outputs.cache-hit }}"
```

## Common Anti-Patterns

| Anti-Pattern | Fix |
|---|---|
| Hardcoding `go-version: '1.25.3'` everywhere | Use `go-version-file: go.mod` |
| Running `go get .` for dependencies | Use `go mod download` (doesn't modify go.mod) |
| No `-race` flag in CI tests | Add `-race` — CI has the CPU budget |
| Caching `vendor/` manually | Let setup-go handle module cache automatically |
| Using `actions/setup-go@v4` | Upgrade to v5+ for automatic caching |
| No `actions/checkout` before setup-go | Always checkout first |

## External References

- [actions/setup-go — Advanced Usage](https://github.com/actions/setup-go/blob/main/docs/advanced-usage.md)
- [GitHub Docs — Build and test Go](https://docs.github.com/en/actions/tutorials/build-and-test-code/go)
