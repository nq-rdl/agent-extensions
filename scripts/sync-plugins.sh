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
import re
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


def normalize(member):
    # Mirror scripts/_registry.py::normalize_member (the heredoc boundary makes
    # importing it awkward — keep the two in step). A bundle skill member is
    # either a flat string `<name>` (source == leaf) or an explicit
    # {source, leaf} mapping packaging the flat upstream skills/<source>/ under a
    # different leaf, so Claude Code invokes `<pluginName>:<leaf>` (Option-2
    # grouping, spec §3 / CONTRIBUTING §6). Returns (source, leaf), or None if
    # malformed — sync stays resilient and warns rather than aborting.
    if isinstance(member, str):
        return member, member
    if isinstance(member, dict):
        source, leaf = member.get("source"), member.get("leaf")
        if isinstance(source, str) and source and isinstance(leaf, str) and leaf:
            return source, leaf
    return None


def reconcile_skill_name(dst: Path, leaf: str) -> None:
    # Claude Code invokes a plugin skill by its LEAF folder (<plugin>:<leaf>), but
    # the frontmatter `name:` is what it shows as the label in /-autocomplete and
    # `/help` listings. The flat upstream skill keeps its catalog-wide name (e.g.
    # `go-gh`); copied verbatim, that label disagrees with the invocation — the
    # user typing `/go` sees `go-gh` instead of `go:gh`. Rewrite the
    # COPY's `name:` to the leaf so label == invocation, matching the convention
    # every working plugin follows (folder == name). The canonical skills/ tree is
    # never touched — it stays flat with the upstream name; only this derivative
    # plugin copy is reconciled. Idempotent for flat members (name already == leaf).
    skill_md = dst / "SKILL.md"
    if not skill_md.is_file():
        return
    text = skill_md.read_text()
    parts = text.split("---\n", 2)
    if len(parts) < 3 or parts[0].strip():
        return  # no leading YAML frontmatter block — nothing to reconcile
    new_fm, n = re.subn(r"(?m)^name:.*$", f"name: {leaf}", parts[1], count=1)
    if n == 0:
        new_fm = f"name: {leaf}\n" + parts[1]  # frontmatter had no name: key — add one
    if new_fm != parts[1]:
        parts[1] = new_fm
        skill_md.write_text("---\n".join(parts))


def sync_skill(plugin: str, source: str, leaf: str, bundle_file: Path) -> None:
    src = repo / "skills" / source
    dst = repo / "plugins" / plugin / "skills" / leaf
    if not src.is_dir():
        warn(
            bundle_file,
            f"Skill '{source}' has no source skills/{source}/ — skipped. "
            "Point registry/bundles at an existing skill or remove the entry.",
        )
        return
    if dst.is_symlink() or dst.is_file():
        dst.unlink()
    elif dst.exists():
        shutil.rmtree(dst)
    dst.parent.mkdir(parents=True, exist_ok=True)
    shutil.copytree(src, dst, symlinks=False)
    reconcile_skill_name(dst, leaf)
    print(f"  ✓ skill {source} -> {leaf}" if source != leaf else f"  ✓ skill {source}")


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

    # Normalize each member to (source, leaf); a malformed member is warned about
    # and dropped so the sync stays resilient. validate.yml's check_grouping is
    # the authoritative gate that fails the PR on a malformed member.
    norm_skills = []
    for member in skills:
        sl = normalize(member)
        if sl is None:
            warn(
                bundle_file,
                f"Malformed skill member {member!r} — expected a string or a "
                "{source, leaf} mapping; skipped.",
            )
            continue
        norm_skills.append(sl)

    # Keep set = registry entries that still have a canonical source, keyed by
    # LEAF (the plugin tree is keyed by leaf). A skill or agent removed upstream
    # but still listed in the bundle has no source, so its stale plugin copy is
    # pruned here (and sync_skill/sync_agent below warns about the dangling
    # registry reference). Building `keep` from the raw registry list instead
    # would preserve orphaned copies forever — the issue #100 failure mode
    # (audit finding #2).
    present_skill_leaves = {
        leaf for (source, leaf) in norm_skills if (repo / "skills" / source).is_dir()
    }
    present_agents = [
        a for a in agents if (repo / "agents" / a / "agent.md").is_file()
    ]

    prune_entries(repo / "plugins" / plugin / "skills", present_skill_leaves)
    prune_entries(
        repo / "plugins" / plugin / "agents", {f"{a}.md" for a in present_agents}
    )

    for source, leaf in norm_skills:
        sync_skill(plugin, source, leaf, bundle_file)
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
