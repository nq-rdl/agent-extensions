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
import json
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
    # grouping, spec §3 / docs/authoring-skills.md "How grouping is expressed" (grouping
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


# ── Hooks ────────────────────────────────────────────────────────────────────
# Canonical mapping (#311): hooks/<plugin>/hooks.json is the Claude config and
# the bundle's `hooks:` list names the shell hooks it ships. The config's
# quoted "${CLAUDE_PLUGIN_ROOT}/<dir>/<name>.sh" paths fix where each hook is
# installed, so install paths never move. plugins/<plugin>/hooks/ is owned
# outright (config + any hooks installed there); a hook installed elsewhere
# (the Codex runtime's scripts/) is owned file by file, so vendored neighbours
# are never pruned. Mapping errors are fatal in both modes.
CANONICAL_HOOKS = (
    {p.stem for p in (repo / "hooks").glob("*.sh")} if (repo / "hooks").is_dir() else set()
)
QUOTED_ROOT = re.compile(
    r'"\$\{CLAUDE_PLUGIN_ROOT\}(?:/([A-Za-z0-9._/-]+)"|"/([A-Za-z0-9._/-]+))'
)
PLUGIN_ROOT_REF = re.compile(
    r"\$\{CLAUDE_PLUGIN_ROOT(?::-[^}]*)?\}/([A-Za-z0-9._-]+(?:/[A-Za-z0-9._-]+)*)"
)
hook_errors = []
hook_ref_jobs = []  # (plugin, {name: rel}, {leaf: source}) resolved after skill sync


def hook_error(bundle_file, message):
    hook_errors.append(f"{bundle_file.relative_to(repo)}: {message}")


def file_state(path):
    return path.read_bytes(), bool(path.stat().st_mode & 0o111)


def compare_hook_tree(expected, actual):
    # Like compare_trees, plus the executable bit: an installed hook invoked by
    # path needs it, and the Codex packager already treats it as content.
    if not actual.is_dir():
        return ["missing hooks directory — run sync-plugins.sh"]
    exp = {p.relative_to(expected) for p in expected.rglob("*") if p.is_file()}
    act = {p.relative_to(actual) for p in actual.rglob("*") if p.is_file()}
    msgs = [f"missing file {rel}" for rel in sorted(exp - act)]
    msgs += [f"stale file {rel}" for rel in sorted(act - exp)]
    msgs += [
        f"content or executable mode differs: {rel}"
        for rel in sorted(exp & act)
        if file_state(expected / rel) != file_state(actual / rel)
    ]
    return msgs


def hook_destinations(bundle_file, config, hook_names):
    # Return {hook name: plugin-relative destination} read from the config.
    try:
        data = json.loads(config.read_text())
    except (OSError, json.JSONDecodeError) as exc:
        hook_error(bundle_file, f"{config.relative_to(repo)} is not valid JSON: {exc}")
        return None
    commands = []
    for groups in (data.get("hooks") or {}).values():
        for group in groups if isinstance(groups, list) else []:
            for h in (group or {}).get("hooks") or []:
                if isinstance(h, dict) and isinstance(h.get("command"), str):
                    commands.append(h["command"])
    dest = {}
    for command in commands:
        quoted = QUOTED_ROOT.findall(command)
        if command.count("${CLAUDE_PLUGIN_ROOT}") != len(quoted):
            hook_error(
                bundle_file,
                f"hook command {command!r} must quote the plugin root "
                '(bash "${CLAUDE_PLUGIN_ROOT}/<dir>/<name>.sh") so installs '
                "under a path with spaces still run",
            )
            continue
        for rel in (a or b for a, b in quoted):
            parts = rel.split("/")
            if len(parts) != 2 or not rel.endswith(".sh"):
                hook_error(bundle_file, f"hook command path {rel} must be <dir>/<hook>.sh")
                continue
            name = parts[1][: -len(".sh")]
            if name not in hook_names:
                hook_error(bundle_file, f"hook command runs {rel}, but '{name}' is not in the bundle's hooks: list")
            elif dest.setdefault(name, rel) != rel:
                hook_error(bundle_file, f"hook '{name}' is wired at both {dest[name]} and {rel}")
    for name in hook_names:
        if name not in dest:
            hook_error(bundle_file, f"hook '{name}' is listed in hooks: but no command in {config.relative_to(repo)} runs it")
    return dest


def remove(path):
    if path.is_symlink() or path.is_file():
        path.unlink()
    elif path.exists():
        shutil.rmtree(path)


def sync_hooks(plugin, hook_names, bundle_file, leaves):
    config = repo / "hooks" / plugin / "hooks.json"
    plugin_dir = repo / "plugins" / plugin
    owned = plugin_dir / "hooks"
    if not config.is_file():
        if hook_names:
            hook_error(bundle_file, f"bundle lists hooks {hook_names} but hooks/{plugin}/hooks.json does not exist")
        elif owned.exists() or owned.is_symlink():
            if check:
                drift.append(f"plugins/{plugin}/hooks: stale (no canonical hooks/{plugin}/hooks.json)")
            else:
                remove(owned)
        return
    for name in hook_names:
        if not (repo / "hooks" / f"{name}.sh").is_file():
            hook_error(bundle_file, f"missing canonical hook hooks/{name}.sh")
            return
    dest = hook_destinations(bundle_file, config, hook_names)
    if dest is None or set(dest) != set(hook_names):
        return
    hook_ref_jobs.append((bundle_file, plugin, dest, leaves))
    installed = {plugin_dir / rel for rel in dest.values()}
    # A canonical hook copy outside its mapped destination is stale (e.g. left
    # behind after a destination change). Only canonical hook names are
    # considered, so vendored runtime files are never touched.
    for candidate in sorted(plugin_dir.glob("*/*.sh")):
        parent = candidate.parent.name
        if parent in ("hooks", "skills") or candidate.stem not in CANONICAL_HOOKS:
            continue
        if candidate not in installed:
            if check:
                drift.append(f"{candidate.relative_to(repo)}: stale hook copy (not wired by hooks/{plugin}/hooks.json)")
            else:
                candidate.unlink()
    with tempfile.TemporaryDirectory() as tmp:
        expected = Path(tmp) / "hooks"
        expected.mkdir()
        shutil.copy2(config, expected / "hooks.json")
        for name, rel in sorted(dest.items()):
            source = repo / "hooks" / f"{name}.sh"
            directory, filename = rel.split("/")
            if directory == "hooks":
                shutil.copy2(source, expected / filename)
                continue
            target = plugin_dir / rel
            if check:
                if not target.is_file():
                    drift.append(f"plugins/{plugin}/{rel}: missing hook copy — run sync-plugins.sh")
                elif file_state(source) != file_state(target):
                    drift.append(f"plugins/{plugin}/{rel}: content or executable mode differs from hooks/{name}.sh")
            else:
                target.parent.mkdir(parents=True, exist_ok=True)
                remove(target)
                shutil.copy2(source, target)
        if check:
            for difference in compare_hook_tree(expected, owned):
                drift.append(f"plugins/{plugin}/hooks: {difference}")
        else:
            remove(owned)
            shutil.copytree(expected, owned)


def check_hook_references():
    # Every ${CLAUDE_PLUGIN_ROOT}/… path a packaged hook names must exist in the
    # installed tree: a registry hook destination, a bundled skill file (mapped
    # leaf -> canonical source, so this holds before and after sync), or a
    # vendored runtime file already in the plugin tree.
    for bundle_file, plugin, dest, leaves in hook_ref_jobs:
        installed = set(dest.values())
        for name in sorted(dest):
            text = (repo / "hooks" / f"{name}.sh").read_text()
            for ref in sorted(set(PLUGIN_ROOT_REF.findall(text))):
                parts = ref.split("/")
                if ref in installed:
                    continue
                if parts[0] == "skills" and len(parts) > 1:
                    source = leaves.get(parts[1])
                    if source and (repo / "skills" / source / "/".join(parts[2:])).exists():
                        continue
                elif (repo / "plugins" / plugin / ref).exists():
                    continue
                hook_error(
                    bundle_file,
                    f"hooks/{name}.sh needs ${{CLAUDE_PLUGIN_ROOT}}/{ref}, which the "
                    f"installed plugins/{plugin} tree would not contain",
                )


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
    leaves = {}
    for member in skills:
        sl = normalize(member)
        if sl is not None:
            leaves[sl[1]] = sl[0]
    sync_hooks(plugin, list(data.get("hooks") or []), bundle_file, leaves)

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

check_hook_references()
if hook_errors:
    print("::error::hook packaging mapping is invalid (hooks/<plugin>/hooks.json + registry hooks:):", file=sys.stderr)
    for e in hook_errors:
        print(f"  - {e}", file=sys.stderr)
    sys.exit(1)

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

codex_args=()
[ "$check" = 1 ] && codex_args+=(--check)
if [ "${#args[@]}" -gt 0 ]; then codex_args+=(--bundles "${args[@]}"); fi
python3 "$REPO_ROOT/scripts/codex_package.py" "$REPO_ROOT" "${codex_args[@]}"
