---
name: pixi
license: CC-BY-4.0
description: >-
  Use this skill to help agents manage Python projects, dependencies, environments,
  and builds using the `pixi` package manager. Covers installation, project creation
  (pyproject.toml, workspaces, cross-compilation), managing dependencies, security,
  and migrating from other tools like uv.
metadata:
  repo: https://github.com/nq-rdl/agent-skills
---

# pixi — Package management for reproducible environments

Pixi is a fast, cross-platform, next-generation package manager that provides reproducible environments.

---

## When to use Pixi

- To create and manage reproducible development environments.
- To handle both Python and non-Python dependencies (e.g., system libraries) in the same environment.
- To manage cross-platform builds and cross-compilation.
- To migrate from `uv` or other package managers.
- When working with PyTorch, Rust, C++, or R.

## Key Concepts

- **Workspaces:** Pixi allows managing multiple projects with shared dependencies using workspaces.
- **Global Tools:** Install isolated CLI tools globally using `pixi global install`.
- **Reproducibility:** Pixi uses lockfiles (`pixi.lock`) to ensure exact versions of packages across platforms.
- **Backends:** Pixi integrates with various build backends (e.g., `pixi-build-cmake`, `pixi-build-python`).

## References

For detailed usage, consult the references:

- [Installation](references/installation.rst)
- [First Workspace](references/first_workspace.rst)
- [Python Tutorial](references/python_tutorial.rst)
- [Python - pyproject.toml](references/pyproject_toml.rst)
- [Python - PyTorch](references/pytorch.rst)
- [Rust Tutorial](references/rust.rst)
- [Global Tools Introduction](references/global_tools_introduction.rst)
- [Build - Getting Started](references/build_getting_started.rst)
- [Build - Python](references/python.rst)
- [Build - C++](references/cpp.rst)
- [Build - Workspace](references/workspace.rst)
- [Build - Advanced C++](references/advanced_cpp.rst)
- [Build - Cross Compilation](references/cross_compilation.rst)
- [Build - Backends](references/backends.rst)
- [Build - pixi-build-cmake](references/pixi-build-cmake.rst)
- [Build - pixi-build-python](references/pixi-build-python.rst)
- [Build - pixi-build-rattler-build](references/pixi-build-rattler-build.rst)
- [Build - pixi-build-r](references/pixi-build-r.rst)
- [Build - pixi-build-rust](references/pixi-build-rust.rst)
- [Key Concepts - Compilers](references/compilers.rst)
- [Deployment - Prefix](references/prefix.rst)
- [Deployment - Pixi Pack](references/pixi_pack.rst)
- [Security](references/security.rst)
- [Switching from uv](references/uv.rst)

## Examples

### Initialize a project

```bash
pixi init
```

### Add dependencies

```bash
pixi add python
pixi add numpy pandas
```

### Run a command inside the environment

```bash
pixi run python script.py
```
