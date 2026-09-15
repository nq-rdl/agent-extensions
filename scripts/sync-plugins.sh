#!/bin/bash
# Refresh self-contained plugin skill and hook copies from the registry.
# Skills include optional references/subagent.rst delegation outlines.
# Missing sources warn; reference validation is the authoritative failure gate.
# Stale skill copies and retired generated agents/ trees are pruned.
# Usage: sync-plugins.sh [--check] [bundle ...]

set -euo pipefail

REPO_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$REPO_ROOT"

check=0
args=()
for a in "$@"; do
  if [ "$a" = "--check" ]; then
    check=1
  else
    args+=("$a")
  fi
done
bundles_arg="${args[*]:-}"

python3 - "$check" "$bundles_arg" <<'PY'
import re
import shutil
import sys
import tempfile
from pathlib import Path

import yaml

repo = Path.cwd()
check = sys.argv[1] == "1"
selected = sys.argv[2].split() if sys.argv[2] else []

bundle_files = sorted((repo / "registry" / "bundles").glob("*.yaml"))
if selected:
    wanted_bundles = set(selected)
    bundle_files = [f for f in bundle_files if f.stem in wanted_bundles]
    missing = wanted_bundles - {f.stem for f in bundle_files}
    if missing:
        sys.exit(f"::error::Unknown bundle(s): {', '.join(sorted(missing))}")

warnings = 0

# In --check mode we record (never fix) every place a plugin copy diverges from
# its canonical source, then exit non-zero so CI/hooks fail until the author
# reruns the sync. Nothing on disk is modified.
drift = []


def compare_trees(expected: Path, actual: Path):
    # Differences between the expected skill tree (canonical copy + name strip)
    # and the actual plugin copy: missing files, stale files, or differing bytes.
    if not actual.exists():
        return ["missing skill copy — run sync-plugins.sh"]
    msgs = []
    exp_files = {p.relative_to(expected) for p in expected.rglob("*") if p.is_file()}
    act_files = {p.relative_to(actual) for p in actual.rglob("*") if p.is_file()}
    for rel in sorted(exp_files - act_files):
        msgs.append(f"missing file {rel}")
    for rel in sorted(act_files - exp_files):
        msgs.append(f"stale file {rel}")
    for rel in sorted(exp_files & act_files):
        if (expected / rel).read_bytes() != (actual / rel).read_bytes():
            msgs.append(f"content differs: {rel}")
    return msgs


def warn(bundle_file: Path, message: str) -> None:
    global warnings
    warnings += 1
    print(f"::warning file={bundle_file.relative_to(repo)}::{message}", file=sys.stderr)


def prune_entries(parent: Path, keep: set) -> None:
    # The registry is the source of truth. Remove derivative plugin copies for
    # skills that were renamed or dropped upstream so they do not linger
    # in the installed plugin tree.
    if not parent.exists():
        return
    for child in sorted(parent.iterdir()):
        if child.name in keep:
            continue
        if check:
            drift.append(
                f"{child.relative_to(repo)}: stale (not named by the registry; "
                "would be pruned by sync-plugins.sh)"
            )
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
    # grouping, spec §3 / CONTRIBUTING "How grouping is expressed" (grouping
    # rule 6)). Returns (source, leaf), or None if malformed — sync stays
    # resilient and warns rather than aborting.
    if isinstance(member, str):
        return member, member
    if isinstance(member, dict):
        source, leaf = member.get("source"), member.get("leaf")
        if isinstance(source, str) and source and isinstance(leaf, str) and leaf:
            return source, leaf
    return None


def strip_skill_name(dst: Path) -> None:
    """Delete the plugin copy's SKILL.md frontmatter ``name:`` line.

    Claude Code computes a plugin skill's invocation id as ``<plugin>:<leaf>``
    (the LEAF folder always drives invocation). The label it shows in
    /-autocomplete and listings, however, is::

        userFacingName = frontmatter.name || "<plugin>:<leaf>"

    i.e. a frontmatter ``name:`` *overrides* the namespaced id with a bare,
    un-prefixed string. So **any** ``name:`` value — the upstream ``go-gh`` or
    the leaf ``gh`` — makes ``/go`` list a bare ``go-gh`` / ``gh`` instead of
    ``go:gh``. (This is why both the byte-identical copy and the earlier
    name==leaf rewrite were wrong; see issue #112.) The only way to get the
    namespaced label is to carry **no** ``name:`` at all, letting Claude Code
    fall back to ``<plugin>:<leaf>``.

    So the plugin copy must drop its frontmatter ``name:`` line. Only the
    derivative copy is touched; the canonical ``skills/`` tree stays flat with
    its upstream name. A SKILL.md with no frontmatter, or no ``name:`` key, is
    left untouched. Idempotent.
    """
    skill_md = dst / "SKILL.md"
    if not skill_md.is_file():
        return
    text = skill_md.read_text()
    parts = text.split("---\n", 2)
    if len(parts) < 3 or parts[0].strip():
        return  # no leading YAML frontmatter block — nothing to strip
    # Drop the top-level ``name:`` key. Upstream skill names are always simple
    # one-line scalars, but handle a block/folded scalar (``name: |`` / ``name:
    # >``) too: remove the key line *and* its indented continuation body, so the
    # strip can never leave orphaned lines that corrupt the frontmatter. Every
    # other key, comment, and the body are preserved byte-for-byte.
    lines = parts[1].splitlines(keepends=True)
    out, i, removed = [], 0, False
    while i < len(lines):
        if not removed and re.match(r"^name:(\s|$)", lines[i]):
            removed = True
            value = lines[i].split(":", 1)[1].strip()
            i += 1
            if value[:1] in ("|", ">"):  # block/folded scalar — skip its body
                while i < len(lines) and (
                    lines[i].strip() == "" or lines[i][:1] in (" ", "\t")
                ):
                    i += 1
            continue
        out.append(lines[i])
        i += 1
    if removed:
        parts[1] = "".join(out)
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
    if check:
        # Build what the plugin copy *should* be (canonical copy + name strip) in
        # a throwaway temp dir, then compare — never touch plugins/.
        with tempfile.TemporaryDirectory() as td:
            expected = Path(td) / leaf
            shutil.copytree(src, expected, symlinks=False)
            strip_skill_name(expected)
            for d in compare_trees(expected, dst):
                drift.append(f"plugins/{plugin}/skills/{leaf}: {d}")
        return
    if dst.is_symlink() or dst.is_file():
        dst.unlink()
    elif dst.exists():
        shutil.rmtree(dst)
    dst.parent.mkdir(parents=True, exist_ok=True)
    shutil.copytree(src, dst, symlinks=False)
    strip_skill_name(dst)
    print(f"  ✓ skill {source} -> {leaf}" if source != leaf else f"  ✓ skill {source}")


def sync_hooks(plugin, hook_names):
    # Opt-in: canonical bundle config owns the entire packaged hooks directory.
    # Existing bundles without this source keep their current hook packaging.
    config = repo / "hooks" / plugin / "hooks.json"
    if not config.is_file():
        return
    with tempfile.TemporaryDirectory() as tmp:
        expected = Path(tmp) / "hooks"
        expected.mkdir()
        shutil.copy2(config, expected / "hooks.json")
        for name in hook_names:
            source = repo / "hooks" / f"{name}.sh"
            if not source.is_file():
                sys.exit(f"::error::Missing canonical hook: {source}")
            shutil.copy2(source, expected / source.name)
        dst = repo / "plugins" / plugin / "hooks"
        if check:
            for difference in compare_trees(expected, dst):
                drift.append(f"plugins/{plugin}/hooks: {difference}")
        else:
            if dst.is_symlink():
                dst.unlink()
            elif dst.exists():
                shutil.rmtree(dst)
            shutil.copytree(expected, dst)


for bundle_file in bundle_files:
    with bundle_file.open() as f:
        data = yaml.safe_load(f) or {}
    bundle = bundle_file.stem
    claude = (data.get("targets") or {}).get("claude") or {}
    if not claude.get("enabled"):
        print(f"Skipping {bundle} (claude target disabled)")
        continue
    plugin = claude.get("pluginName") or data.get("id") or bundle
    print(f"{'Checking' if check else 'Syncing'} {bundle} -> plugins/{plugin}")

    sync_hooks(plugin, list(data.get("hooks") or []))

    skills = list(data.get("skills") or [])
    if data.get("agents"):
        sys.exit(f"::error::{bundle_file}: agents are retired; use skills with references/subagent.rst")

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
    # LEAF (the plugin tree is keyed by leaf). A skill removed upstream
    # but still listed in the bundle has no source, so its stale plugin copy is
    # pruned here (and sync_skill below warns about the dangling
    # registry reference). Building `keep` from the raw registry list instead
    # would preserve orphaned copies forever — the issue #100 failure mode
    # (audit finding #2).
    present_skill_leaves = {
        leaf for (source, leaf) in norm_skills if (repo / "skills" / source).is_dir()
    }
    prune_entries(repo / "plugins" / plugin / "skills", present_skill_leaves)
    # Remove the retired generated agent tree, including empty directories.
    legacy = repo / "plugins" / plugin / "agents"
    if legacy.exists() or legacy.is_symlink():
        if check:
            drift.append(f"{legacy.relative_to(repo)}: retired agent tree — run sync-plugins.sh")
        elif legacy.is_symlink() or legacy.is_file():
            legacy.unlink()
        else:
            shutil.rmtree(legacy)

    for source, leaf in norm_skills:
        sync_skill(plugin, source, leaf, bundle_file)

if check:
    if drift:
        print(
            "::error::plugin trees are out of sync with canonical skills/.",
            file=sys.stderr,
        )
        print(
            "The plugins/ copies are derived from skills/; refresh "
            "them with:",
            file=sys.stderr,
        )
        print(
            "  bash scripts/sync-plugins.sh   (then commit the updated plugins/ tree)",
            file=sys.stderr,
        )
        for d in drift:
            print(f"  - {d}", file=sys.stderr)
        sys.exit(1)
    print("plugin trees are in sync with canonical skills/.")
    sys.exit(0)

if warnings:
    print(
        f"::warning::sync-plugins completed with {warnings} unresolved registry "
        "reference(s); validate-bundles will fail the PR until the registry is "
        "reconciled.",
        file=sys.stderr,
    )
print("Done.")
PY
