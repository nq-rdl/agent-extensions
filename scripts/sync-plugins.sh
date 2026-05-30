#!/bin/bash
# Re-sync plugins/<plugin>/{skills,agents}/ from the canonical skills/ and
# agents/ trees, driven by registry/bundles/<bundle>.yaml.
#
# Why this exists: Claude Code installs a plugin by `cp -R`-ing its source
# into a per-user cache. Symlinks are preserved verbatim, so any link whose
# target sits *outside* the copied subtree dangles after install (issue #83).
# The fix is to vendor real copies of every skill and agent into each
# plugin's tree on `main` so the install is self-contained.
#
# This script is the canonical way to refresh those copies after the
# upstream skills/ or agents/ change. Run it whenever you bump the skills
# sync or add/edit an agent.
#
# Resilience: a bundle that references a skill/agent with no source (e.g. an
# upstream rename or removal that landed before the registry was updated) is
# reported as a ::warning:: and skipped — this script never aborts the sync.
# The authoritative gate is validate.yml's `validate-bundles` job, which fails
# the PR so a human reconciles the registry in the same change (see issue #83
# and the sync-skills.yml decoupling). Stale plugin copies — skills/agents no
# longer named by the registry — are pruned so renamed or dropped entries do
# not linger in the installed plugin tree.
#
# Usage:
#   scripts/sync-plugins.sh           # sync every bundle in registry/
#   scripts/sync-plugins.sh swe       # sync only the named bundle(s)

set -euo pipefail

REPO_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$REPO_ROOT"

bundles_arg="$*"

python3 - "$bundles_arg" <<'PY'
import shutil
import sys
from pathlib import Path

import yaml

repo = Path.cwd()
selected = sys.argv[1].split() if sys.argv[1] else []

bundle_files = sorted((repo / "registry" / "bundles").glob("*.yaml"))
if selected:
    wanted_bundles = set(selected)
    bundle_files = [f for f in bundle_files if f.stem in wanted_bundles]
    missing = wanted_bundles - {f.stem for f in bundle_files}
    if missing:
        sys.exit(f"::error::Unknown bundle(s): {', '.join(sorted(missing))}")

warnings = 0


def warn(bundle_file: Path, message: str) -> None:
    global warnings
    warnings += 1
    print(f"::warning file={bundle_file.relative_to(repo)}::{message}", file=sys.stderr)


def prune_entries(parent: Path, keep: set) -> None:
    # The registry is the source of truth. Remove derivative plugin copies for
    # skills/agents that were renamed or dropped upstream so they do not linger
    # in the installed plugin tree.
    if not parent.exists():
        return
    for child in sorted(parent.iterdir()):
        if child.name in keep:
            continue
        if child.is_symlink() or child.is_file():
            child.unlink()
        else:
            shutil.rmtree(child)
        print(f"  - pruned stale {child.relative_to(repo)}")


def sync_skill(plugin: str, skill: str, bundle_file: Path) -> None:
    src = repo / "skills" / skill
    dst = repo / "plugins" / plugin / "skills" / skill
    if not src.is_dir():
        warn(
            bundle_file,
            f"Skill '{skill}' has no source skills/{skill}/ — skipped. "
            "Point registry/bundles at an existing skill or remove the entry.",
        )
        return
    if dst.is_symlink() or dst.is_file():
        dst.unlink()
    elif dst.exists():
        shutil.rmtree(dst)
    dst.parent.mkdir(parents=True, exist_ok=True)
    shutil.copytree(src, dst, symlinks=False)
    print(f"  ✓ skill {skill}")


def sync_agent(plugin: str, agent: str, bundle_file: Path) -> None:
    src = repo / "agents" / agent / "agent.md"
    dst = repo / "plugins" / plugin / "agents" / f"{agent}.md"
    if not src.is_file():
        warn(
            bundle_file,
            f"Agent '{agent}' has no source agents/{agent}/agent.md — skipped.",
        )
        return
    dst.parent.mkdir(parents=True, exist_ok=True)
    if dst.is_symlink() or dst.exists():
        dst.unlink()
    shutil.copyfile(src, dst)
    print(f"  ✓ agent {agent}")


for bundle_file in bundle_files:
    with bundle_file.open() as f:
        data = yaml.safe_load(f) or {}
    bundle = bundle_file.stem
    claude = (data.get("targets") or {}).get("claude") or {}
    if not claude.get("enabled"):
        print(f"Skipping {bundle} (claude target disabled)")
        continue
    plugin = claude.get("pluginName") or data.get("id") or bundle
    print(f"Syncing {bundle} -> plugins/{plugin}")

    skills = list(data.get("skills") or [])
    agents = list(data.get("agents") or [])

    prune_entries(repo / "plugins" / plugin / "skills", set(skills))
    prune_entries(repo / "plugins" / plugin / "agents", {f"{a}.md" for a in agents})

    for skill in skills:
        sync_skill(plugin, skill, bundle_file)
    for agent in agents:
        sync_agent(plugin, agent, bundle_file)

if warnings:
    print(
        f"::warning::sync-plugins completed with {warnings} unresolved registry "
        "reference(s); validate-bundles will fail the PR until the registry is "
        "reconciled.",
        file=sys.stderr,
    )
print("Done.")
PY
