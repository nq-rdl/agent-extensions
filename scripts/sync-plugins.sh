#!/bin/bash
# Re-sync plugins/<bundle>/{skills,agents}/ from the canonical skills/ and
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
# Usage:
#   scripts/sync-plugins.sh           # sync every bundle in registry/
#   scripts/sync-plugins.sh swe       # sync only the named bundle(s)

set -euo pipefail

REPO_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$REPO_ROOT"

bundles_arg="$*"

python3 - "$bundles_arg" <<'PY'
import os
import shutil
import sys
from pathlib import Path

import yaml

repo = Path.cwd()
selected = sys.argv[1].split() if sys.argv[1] else []

bundle_files = sorted((repo / "registry" / "bundles").glob("*.yaml"))
if selected:
    wanted = set(selected)
    bundle_files = [f for f in bundle_files if f.stem in wanted]
    missing = wanted - {f.stem for f in bundle_files}
    if missing:
        sys.exit(f"::error::Unknown bundle(s): {', '.join(sorted(missing))}")

errors = []

def sync_skill(bundle: str, skill: str) -> None:
    src = repo / "skills" / skill
    dst = repo / "plugins" / bundle / "skills" / skill
    if not src.is_dir():
        errors.append(f"missing skills/{skill} (referenced by {bundle})")
        return
    if dst.exists() or dst.is_symlink():
        if dst.is_symlink() or dst.is_file():
            dst.unlink()
        else:
            shutil.rmtree(dst)
    dst.parent.mkdir(parents=True, exist_ok=True)
    shutil.copytree(src, dst, symlinks=False)
    print(f"  ✓ skill {skill}")

def sync_agent(bundle: str, agent: str) -> None:
    src = repo / "agents" / agent / "agent.md"
    dst = repo / "plugins" / bundle / "agents" / f"{agent}.md"
    if not src.is_file():
        errors.append(f"missing agents/{agent}/agent.md (referenced by {bundle})")
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
    print(f"Syncing {bundle}")
    for skill in data.get("skills") or []:
        sync_skill(bundle, skill)
    for agent in data.get("agents") or []:
        sync_agent(bundle, agent)

if errors:
    print("::error::sync-plugins encountered missing sources:", file=sys.stderr)
    for e in errors:
        print(f"  - {e}", file=sys.stderr)
    sys.exit(1)

print("Done.")
PY
