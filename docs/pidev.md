---
icon: lucide/box
---

# pi.dev

How agent-extensions packages skills for pi.dev as a single package.

## Architecture

pi.dev uses a **package** model — a `package.json` with a `pi` key that declares skill directories:

```text
pidev/
  package.json               ← package manifest with "pi" key
  skills/
    tdd -> ../../skills/skills/tdd
    ansible -> ../../skills/skills/ansible
    r-expert -> ../../skills/skills/r-expert
    ... (41 total)
```

## How it works

1. **Package manifest** (`pidev/package.json`) declares the package name (`@nq-rdl/agent-extensions`), version, and a `pi.skills` array pointing to `./skills`.

2. **Convention directory** — pi.dev automatically discovers `SKILL.md` folders under `skills/` when the `pi.skills` path is set. No per-skill registration needed.

3. **Skill symlinks** (`pidev/skills/<name>`) are relative symlinks into the `skills/` submodule. The symlink path is `../../skills/skills/<name>` (two levels up from the skill directory to the repo root, then into the submodule).

4. **On install**, pi.dev loads skills from the package directory. For git and local installs, symlinks are followed directly.

## Install

### Local path

```bash
# Clone the repo and install the package
git clone git@github.com:nq-rdl/agent-extensions.git
cd agent-extensions
git submodule update --init

# Global install
pi install ./pidev

# Project-scoped install
pi install -l ./pidev
```

### Git install

```bash
pi install git:github.com/nq-rdl/agent-extensions
```

### npm (future)

Once published to npm:

```bash
pi install npm:@nq-rdl/agent-extensions
```

## Why one package instead of bundles

pi.dev installs packages as atomic units — there is no marketplace or bundle selection mechanism. Splitting into 6 packages would mean 6 npm packages to publish and version. Since pi.dev loads skills on demand based on task context, having all 41 in one package has no performance cost.

## Update workflow

When skills are updated in the `nq-rdl/agent-skills` submodule:

1. Pull the latest agent-extensions repo.
2. Run `git submodule update --init` to refresh skills.
3. For local installs, skills update immediately (symlinks resolve to the submodule).
4. For git installs, run `pi update` to pull the latest commit.

## Package filtering

pi.dev supports filtering which skills load from a package. In `settings.json`:

```json
{
  "packages": [
    {
      "source": "./pidev",
      "skills": ["skills/tdd", "skills/go-secure", "!skills/r-*"]
    }
  ]
}
```

This lets users install the full package but only activate the skills they need — achieving bundle-like granularity without splitting the package.

## Gallery discovery

To appear in the pi.dev package gallery, add the `pi-package` keyword to `package.json` (already included) and publish to npm.
