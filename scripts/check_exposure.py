#!/usr/bin/env python3
"""Find canonical content that no bundle exposes (the reverse of check_bundle_refs).

``check_bundle_refs.py`` checks the FORWARD direction: every skill/agent named
in ``registry/bundles/*.yaml`` must resolve to something on disk. This module
checks the REVERSE direction: every skill authored under ``skills/<name>/``,
every agent under ``agents/<name>/agent.md``, and every hook under
``hooks/<name>.sh`` must be *referenced* by at least one bundle — otherwise it
is authored but never shipped in any plugin, which is easy to miss because
nothing else in the pipeline fails.

An orphan can be deliberate (repo-internal tooling that is never meant to ship
in a plugin, e.g. a dev-only hook). ``registry/unbundled.yaml`` is a reviewable
allowlist for exactly those cases; an allowlist entry that no longer matches
anything on disk, or that a bundle now references anyway, is itself flagged as
stale so the allowlist cannot silently rot.

``mcp`` and ``prompt`` kinds are collected for completeness (there is currently
no canonical ``mcp/<name>/`` server tree and no ``prompts/`` directory in this
repo), but with nothing on disk to enumerate they never produce orphans today.

CLI:
    python3 scripts/check_exposure.py [REPO_ROOT] [--warn]
Without ``--warn`` this exits non-zero (with ``::error::`` annotations) if any
canonical item is unreferenced or any allowlist entry is stale. With
``--warn`` it prints friendly ``hint:`` lines instead and always exits 0 (a
local, non-blocking reminder — CI runs the strict form).
"""
from __future__ import annotations

import sys
from dataclasses import dataclass
from pathlib import Path

import yaml

from _registry import normalize_member

KINDS = ("skill", "agent", "hook", "mcp", "prompt")


@dataclass(frozen=True)
class Orphan:
    kind: str  # one of KINDS
    name: str
    path: str = ""  # repo-relative canonical path, for CI annotations


def collect_bundle_refs(repo) -> dict[str, set[str]]:
    """Union, across every ``registry/bundles/*.yaml``, the names referenced per kind.

    Skills are keyed by their SOURCE (the canonical ``skills/<source>/`` dir),
    never the leaf — a member's leaf is plugin-local naming and does not
    identify the canonical item.
    """
    repo = Path(repo)
    refs: dict[str, set[str]] = {kind: set() for kind in KINDS}
    bundles_dir = repo / "registry" / "bundles"
    if not bundles_dir.is_dir():
        return refs
    bundle_files = sorted(
        list(bundles_dir.glob("*.yaml")) + list(bundles_dir.glob("*.yml"))
    )
    for bundle_file in bundle_files:
        with bundle_file.open() as fh:
            data = yaml.safe_load(fh) or {}
        for member in data.get("skills") or []:
            try:
                source, _leaf = normalize_member(member)
            except ValueError:
                continue
            refs["skill"].add(source)
        for name in data.get("agents") or []:
            refs["agent"].add(name)
        for name in data.get("hooks") or []:
            refs["hook"].add(name)
        for name in data.get("mcp") or []:
            refs["mcp"].add(name)
        for name in data.get("prompts") or []:
            refs["prompt"].add(name)
    return refs


def collect_canonical(repo) -> dict[str, dict[str, str]]:
    """Return, per kind, a ``{name: repo-relative path}`` map of on-disk identities."""
    repo = Path(repo)
    canonical: dict[str, dict[str, str]] = {kind: {} for kind in KINDS}

    skills_dir = repo / "skills"
    if skills_dir.is_dir():
        for d in sorted(skills_dir.iterdir()):
            if d.is_dir() and (d / "SKILL.md").is_file():
                canonical["skill"][d.name] = f"skills/{d.name}/"

    agents_dir = repo / "agents"
    if agents_dir.is_dir():
        for d in sorted(agents_dir.iterdir()):
            if d.is_dir() and (d / "agent.md").is_file():
                canonical["agent"][d.name] = f"agents/{d.name}/agent.md"

    hooks_dir = repo / "hooks"
    if hooks_dir.is_dir():
        for f in sorted(hooks_dir.glob("*.sh")):
            canonical["hook"][f.stem] = f"hooks/{f.name}"

    mcp_dir = repo / "mcp"
    if mcp_dir.is_dir():
        for d in sorted(mcp_dir.iterdir()):
            if d.is_dir():
                canonical["mcp"][d.name] = f"mcp/{d.name}/"

    prompts_dir = repo / "prompts"
    if prompts_dir.is_dir():
        for p in sorted(prompts_dir.iterdir()):
            canonical["prompt"][p.name] = f"prompts/{p.name}"

    return canonical


def load_allowlist(repo) -> tuple[set[tuple[str, str]], list[dict]]:
    """Parse ``registry/unbundled.yaml``. Returns (allowed set, raw entries).

    A ``(kind, name)`` pair enters ``allowed`` (and therefore suppresses the
    orphan) only when both are non-empty strings; the ``reason`` requirement is
    validated separately by :func:`find_allowlist_problems`, which fails the
    strict check on a missing reason so a malformed entry can never *silently*
    suppress a genuine orphan. Missing file => empty allowlist.
    """
    repo = Path(repo)
    path = repo / "registry" / "unbundled.yaml"
    if not path.is_file():
        return set(), []
    with path.open() as fh:
        data = yaml.safe_load(fh) or {}
    entries = data.get("unbundled") or []
    allowed = set()
    for entry in entries:
        if not isinstance(entry, dict):
            continue
        kind = entry.get("kind")
        name = entry.get("name")
        if isinstance(kind, str) and kind and isinstance(name, str) and name:
            allowed.add((kind, name))
    return allowed, entries


def find_unexposed(repo) -> list[Orphan]:
    """Return an Orphan for every canonical item referenced by no bundle and not allowlisted."""
    repo = Path(repo)
    refs = collect_bundle_refs(repo)
    canonical = collect_canonical(repo)
    allowed, _entries = load_allowlist(repo)
    orphans: list[Orphan] = []
    for kind in KINDS:
        for name, path in canonical[kind].items():
            if name in refs[kind]:
                continue
            if (kind, name) in allowed:
                continue
            orphans.append(Orphan(kind, name, path))
    return orphans


def find_stale_allowlist_entries(repo) -> list[str]:
    """Return a message per allowlist entry that no longer needs to exist.

    Stale means either: (a) the entry no longer matches anything canonical on
    disk, or (b) a bundle now references it anyway, so the exemption is dead
    weight.
    """
    repo = Path(repo)
    refs = collect_bundle_refs(repo)
    canonical = collect_canonical(repo)
    allowed, _entries = load_allowlist(repo)
    messages: list[str] = []
    for kind, name in sorted(allowed):
        if kind not in canonical:
            messages.append(
                f"registry/unbundled.yaml lists unknown kind '{kind}' for '{name}'"
            )
            continue
        if name not in canonical[kind]:
            messages.append(
                f"registry/unbundled.yaml allowlists {kind} '{name}' but it no longer "
                "exists on disk — remove the stale entry"
            )
        elif name in refs[kind]:
            messages.append(
                f"registry/unbundled.yaml allowlists {kind} '{name}' but a bundle now "
                "references it — remove the stale entry"
            )
    return messages


def find_allowlist_problems(repo) -> list[str]:
    """Return a message per structurally-invalid ``registry/unbundled.yaml`` entry.

    Every entry must be a mapping with a non-empty ``kind``, ``name``, and
    ``reason``. The ``reason`` requirement is load-bearing: without it the
    allowlist becomes a friction-free way to silence the exposure check
    ("wiring it up is inconvenient") rather than a deliberate, reviewable
    exemption. A malformed entry is reported here — and so fails the strict
    check — instead of quietly suppressing a genuine orphan.
    """
    _allowed, entries = load_allowlist(repo)
    messages: list[str] = []
    for i, entry in enumerate(entries):
        if not isinstance(entry, dict):
            messages.append(
                f"registry/unbundled.yaml entry #{i + 1} must be a mapping with "
                "'kind', 'name', and 'reason'"
            )
            continue
        kind = entry.get("kind")
        name = entry.get("name")
        reason = entry.get("reason")
        label = f"{kind or '?'} '{name or '?'}'"
        if not (isinstance(kind, str) and kind.strip()):
            messages.append(f"registry/unbundled.yaml entry {label} is missing a 'kind'")
        if not (isinstance(name, str) and name.strip()):
            messages.append(f"registry/unbundled.yaml entry {label} is missing a 'name'")
        if not (isinstance(reason, str) and reason.strip()):
            messages.append(
                f"registry/unbundled.yaml entry {label} is missing a 'reason' — "
                "every exemption must document why the item is not bundled"
            )
    return messages


def main(argv=None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    warn = "--warn" in argv
    positional = [a for a in argv if a != "--warn"]
    repo = Path(positional[0]) if positional else Path(".")

    orphans = find_unexposed(repo)
    allowlist_problems = find_allowlist_problems(repo) + find_stale_allowlist_entries(repo)

    if warn:
        for o in orphans:
            print(
                f"hint: {o.name} ({o.kind}) is authored under {o.path} but no bundle "
                "references it yet — add it to a registry/bundles/*.yaml "
                f"{o.kind}s list, or to registry/unbundled.yaml with a reason.",
                file=sys.stderr,
            )
        for msg in allowlist_problems:
            print(f"hint: {msg}", file=sys.stderr)
        return 0

    for o in orphans:
        print(
            f"::error file={o.path}::{o.name} ({o.kind}) is authored under {o.path} "
            f"but no bundle references it — add it to a registry/bundles/*.yaml "
            f"{o.kind}s list, or to registry/unbundled.yaml with a reason.",
            file=sys.stderr,
        )
    for msg in allowlist_problems:
        print(f"::error::{msg}", file=sys.stderr)

    total = len(orphans) + len(allowlist_problems)
    if total:
        print(f"{total} exposure problem(s)", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
