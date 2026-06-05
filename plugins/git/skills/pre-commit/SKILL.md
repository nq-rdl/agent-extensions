---
name: pre-commit
license: CC-BY-4.0
description: >-
  Manage Git hooks with Python's pre-commit framework, using pixi. Use when the
  user asks about pre-commit, .pre-commit-config.yaml, Python git hooks, or
  wants to set up linting/formatting hooks via pre-commit.
compatibility: >-
  Requires pixi package manager
metadata:
  repo: https://github.com/nq-rdl/agent-skills
---

# Pre-commit

A framework for managing and maintaining multi-language pre-commit hooks. It handles the installation and execution of hooks, isolating their dependencies so developers don't need to install tools globally.

> **See also**: For Node.js/Bun projects, consider **husky**. For pure Go or language-agnostic projects needing a fast single binary, consider **lefthook**.

## Quick Start (with Pixi)

Instead of using `pip`, we use `pixi` to install and run `pre-commit` to ensure reproducible environments.

```bash
# Add pre-commit as a development dependency
pixi add --dev pre-commit
```

Create `.pre-commit-config.yaml` at project root:

```yaml
repos:
  - repo: https://github.com/pre-commit/pre-commit-hooks
    rev: v4.5.0
    hooks:
      - id: trailing-whitespace
      - id: end-of-file-fixer
      - id: check-yaml

  # Python specific hooks example
  - repo: https://github.com/astral-sh/ruff-pre-commit
    rev: v0.3.0
    hooks:
      - id: ruff
        args: [ --fix ]
      - id: ruff-format
```

## Installation and Workflow

After configuring `.pre-commit-config.yaml`, install the git hook scripts:

```bash
# Install the hooks to your .git/hooks directory
pixi run pre-commit install
```

Now `pre-commit` will run automatically on `git commit`.

### Running manually

It's useful to run the hooks against all files, especially after initial setup or when adding new hooks:

```bash
# Run against all files
pixi run pre-commit run --all-files

# Run a specific hook against all files
pixi run pre-commit run trailing-whitespace --all-files
```

## Advanced Patterns

### Local Hooks

Sometimes you want to run a local script or tool instead of pulling from a remote repository.

```yaml
repos:
  - repo: local
    hooks:
      - id: my-local-script
        name: Run local checks
        entry: ./scripts/check.sh
        language: script
        types: [shell]
```

### Skipping Hooks

You can temporarily bypass hooks (not recommended for general use, but useful for emergencies):

```bash
# Using standard git bypass
git commit --no-verify

# Or skipping specific hooks via environment variable
SKIP=check-yaml,ruff git commit -m "foo"
```

In CI pipelines, it's generally better to run `pre-commit run --all-files` explicitly rather than relying on git hook triggers.

### CI Integration

```yaml
# GitHub Actions example
- name: Set up pixi
  uses: prefix-dev/setup-pixi@v0.5.1
  with:
    pixi-version: v0.17.1

- name: Run pre-commit
  run: pixi run pre-commit run --all-files
```

## Common Issues

**Hooks fail due to missing dependencies:**
Pre-commit creates isolated environments for each hook. If a hook needs additional dependencies (like `pylint` needing specific packages to typecheck against), add them to `additional_dependencies`:

```yaml
- repo: https://github.com/PyCQA/pylint
  rev: v3.0.3
  hooks:
    - id: pylint
      additional_dependencies: [ requests, click ]
```

**Auto-fixes aren't committed:**
When a hook auto-fixes a file (like a formatter), it fails the commit. You must `git add` the modified files and run `git commit` again.
