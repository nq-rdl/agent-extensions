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
# canonical skills/ or agents/ trees change. Run it whenever you add or edit
# a skill or agent.
#
# It also owns the two LIVE cc-web-setup SessionStart hook copies under this
# repo's own .claude/scripts/ (install-deps.sh, announce-capabilities.sh): it
# rewrites them from canonical skills/cc-web-setup/assets/ on a normal run and
# drift-checks them (bytes + exec mode) under --check. See issue #166 — the
# live copies are invoked directly from .claude/settings.json, so the exec bit
# matters and they must not silently diverge from canonical.
#
# Resilience: a bundle that references a skill/agent with no source (e.g. a
# rename or removal that landed before the registry was updated) is reported
# as a ::warning:: and skipped — this script never aborts. The authoritative
# gate is validate.yml's `validate-bundles` job, which fails the PR so a human
# reconciles the registry in the same change (see issue #83). Stale plugin
# copies — skills/agents no longer named by the registry — are pruned so
# renamed or dropped entries do not linger in the installed plugin tree.
#
# Usage:
#   scripts/sync-plugins.sh           # sync every bundle in registry/
#   scripts/sync-plugins.sh swe       # sync only the named bundle(s)
#   scripts/sync-plugins.sh --check   # report (don't fix) any plugin copy or
#                                     # live .claude/scripts/ cc-web-setup hook
#                                     # that has drifted from its canonical
#                                     # source; exits non-zero on drift (CI /
#                                     # hook gate)

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
    # skills/agents that were renamed or dropped upstream so they do not linger
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
    # grouping, spec §3 / CONTRIBUTING §6). Returns (source, leaf), or None if
    # malformed — sync stays resilient and warns rather than aborting.
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


def sync_agent(plugin: str, agent: str, bundle_file: Path) -> None:
    src = repo / "agents" / agent / "agent.md"
    dst = repo / "plugins" / plugin / "agents" / f"{agent}.md"
    if not src.is_file():
        warn(
            bundle_file,
            f"Agent '{agent}' has no source agents/{agent}/agent.md — skipped.",
        )
        return
    if check:
        if not dst.is_file():
            drift.append(f"plugins/{plugin}/agents/{agent}.md: missing — run sync-plugins.sh")
        elif dst.read_bytes() != src.read_bytes():
            drift.append(
                f"plugins/{plugin}/agents/{agent}.md: content differs from "
                f"agents/{agent}/agent.md"
            )
        return
    dst.parent.mkdir(parents=True, exist_ok=True)
    if dst.is_symlink() or dst.exists():
        dst.unlink()
    shutil.copyfile(src, dst)
    print(f"  ✓ agent {agent}")


def sync_hooks() -> None:
    """Own this repo's LIVE cc-web-setup SessionStart hook copies (issue #166).

    .claude/scripts/{install-deps,announce-capabilities}.sh are byte-identical
    copies of the canonical skills/cc-web-setup/assets/ engine, but unlike the
    plugin trees they are invoked DIRECTLY from .claude/settings.json
    ("$CLAUDE_PROJECT_DIR"/.claude/scripts/install-deps.sh) — so the executable
    bit is load-bearing. Before this, no generator owned them: you hand-copied
    after editing canonical, and nothing caught silent drift. This makes sync
    write them from canonical (carrying the exec bit) and the --check gate flag
    any divergence in bytes OR permission mode.

    .claude/scripts/install-deps.local.sh is the repo-local project seam — it
    has NO canonical source and is intentionally excluded (we only iterate the
    two named engine files below).
    """
    src_dir = repo / "skills" / "cc-web-setup" / "assets"
    dst_dir = repo / ".claude" / "scripts"
    for name in ("install-deps.sh", "announce-capabilities.sh"):
        src = src_dir / name
        dst = dst_dir / name
        if not src.is_file():
            warn(
                src_dir / name if src_dir.exists() else repo,
                f"cc-web-setup hook '{name}' has no canonical source "
                f"skills/cc-web-setup/assets/{name} — skipped.",
            )
            continue
        if check:
            if not dst.is_file():
                drift.append(f".claude/scripts/{name}: missing — run sync-plugins.sh")
            elif dst.read_bytes() != src.read_bytes():
                drift.append(
                    f".claude/scripts/{name}: content differs from "
                    f"skills/cc-web-setup/assets/{name}"
                )
            else:
                srcmode = src.stat().st_mode & 0o777
                dstmode = dst.stat().st_mode & 0o777
                if srcmode != dstmode:
                    drift.append(
                        f".claude/scripts/{name}: mode {oct(dstmode)} differs from "
                        f"canonical {oct(srcmode)} — run sync-plugins.sh"
                    )
            continue
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(src, dst)  # bytes
        shutil.copymode(src, dst)  # carry the exec bit — the live hook is exec'd directly
        print(f"  ✓ hook {name} -> .claude/scripts/{name}")


# Only sync the live .claude/scripts/ hooks when their owning bundle is in scope.
# The cc-web-setup skill lives in registry/bundles/claude-code.yaml, whose
# pluginName is "claude-code". An unscoped run (no bundle args) covers them, and
# CI/pre-commit run `--check` unscoped, so the hooks are always gated there.
hooks_in_scope = (not selected) or ("claude-code" in selected)


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

# After the bundle loop so live-hook drift folds into `drift` and is reported by
# the existing exit logic below. Scoped runs that exclude claude-code skip it.
if hooks_in_scope:
    sync_hooks()

if check:
    if drift:
        print(
            "::error::plugin trees and .claude/scripts hooks are out of sync with "
            "canonical skills/ and agents/.",
            file=sys.stderr,
        )
        print(
            "The plugins/ copies are derived from skills/ and agents/; refresh them with:",
            file=sys.stderr,
        )
        print(
            "  bash scripts/sync-plugins.sh   (then commit the updated plugins/ tree)",
            file=sys.stderr,
        )
        for d in drift:
            print(f"  - {d}", file=sys.stderr)
        sys.exit(1)
    print(
        "plugin trees and .claude/scripts hooks are in sync with canonical "
        "skills/ and agents/."
    )
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
