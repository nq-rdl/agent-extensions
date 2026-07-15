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

A canonical item's *identity* is the name a bundle references, which is not
always the on-disk basename:

  * skill  — ``skills/<name>/SKILL.md``   -> ``<name>`` (a dir without the
    SKILL.md marker is not a skill and is invisible here)
  * agent  — ``agents/<name>/agent.md``   -> ``<name>``
  * hook   — ``hooks/<name>.sh``          -> ``<name>``
  * mcp    — ``mcp/<name>-go/``           -> ``<name>``: the ``-go`` suffix is a
    directory-naming convention (AGENTS.md, mcp/README.md "Layout"), while a
    bundle's ``mcp:`` key holds the *server* name from ``.mcp.json``
    (``mcp: [lucid]``). Stripping it keeps the two namespaces comparable.
  * prompt — ``prompts/<name>.md``        -> ``<name>``

``mcp`` and ``prompt`` enumerate nothing today (``mcp/`` holds only README.md +
.gitignore, and there is no ``prompts/`` directory), so they cannot produce an
orphan yet; the identity mappings above are what they will use when they do.

CLI:
    python3 scripts/check_exposure.py [REPO_ROOT] [--warn]
Without ``--warn`` this exits non-zero (with ``::error::`` annotations) if any
canonical item is unreferenced, or any allowlist entry is stale or malformed.
With ``--warn`` it prints friendly ``hint:`` lines instead and exits 0 — a
local, non-blocking reminder; CI runs the strict form as the hard gate.
"""
from __future__ import annotations

import sys
from dataclasses import dataclass
from pathlib import Path

import yaml

from _registry import normalize_member

KINDS = ("skill", "agent", "hook", "mcp", "prompt")

# The bundle-YAML list key that exposes each kind. Not derivable by appending
# "s" to the kind — `mcp:` is singular in the bundle schema — so this map is the
# single source of truth for both reading refs and telling a contributor which
# key to add an orphan to.
BUNDLE_KEY = {
    "skill": "skills",
    "agent": "agents",
    "hook": "hooks",
    "mcp": "mcp",
    "prompt": "prompts",
}


@dataclass(frozen=True)
class Orphan:
    kind: str  # one of KINDS
    name: str
    path: str = ""  # repo-relative canonical path, for CI annotations


class RegistryError(Exception):
    """The registry could not be read, so no verdict can be reached.

    Distinct from a *finding*: a finding is a fact about the repo, this is the
    check being unable to look. :func:`main` renders it — as a hard ``::error::``
    in strict mode, a ``hint:`` under ``--warn`` — so the raiser carries only the
    message and the optional file to anchor it to.
    """

    def __init__(self, message: str, file: Path | None = None):
        super().__init__(message)
        self.file = file


def _require_dir(path: Path, premise: str) -> Path:
    """Fail loudly when a directory the check depends on is absent.

    A gate must never mistake "I read nothing" for "there is nothing wrong".
    Pointed at a non-repo-root, every lookup below would come back empty on
    *both* sides of the comparison, the orphan loop would iterate zero times,
    and the check would report success without having examined anything.
    """
    if not path.is_dir():
        raise RegistryError(
            f"{path} does not exist — check_exposure.py was pointed at a directory "
            f"that is not the repo root. Refusing to report success without "
            f"reading {premise}."
        )
    return path


def _load_yaml(path: Path) -> dict:
    """Parse a registry YAML file into a mapping, or fail loudly.

    Same reasoning as :func:`_require_dir`: an unreadable or malformed registry
    file is a broken invocation, not an empty one. Swallowing it would drop the
    bundle's refs and misreport its skills as orphans.
    """
    try:
        with path.open() as fh:
            data = yaml.safe_load(fh)
    except (OSError, yaml.YAMLError) as exc:
        raise RegistryError(f"cannot read {path}: {exc}", file=path) from exc
    if data is None:
        return {}
    if not isinstance(data, dict):
        raise RegistryError(
            f"{path} must be a YAML mapping, got {type(data).__name__}", file=path
        )
    return data


def _as_mapping(value, path: Path, key: str) -> dict:
    """Coerce a registry value to a mapping, or fail loudly.

    ``_load_yaml`` only vouches for the top level, so every nested access needs
    its own guard: a scalar reaching ``.get()`` raises AttributeError from
    *inside* the check, past :func:`main`'s ``except RegistryError`` — which is
    how a half-written ``targets:`` used to traceback out of the ``--warn`` path
    that promises to never block a commit.
    """
    if value is None:
        return {}
    if not isinstance(value, dict):
        raise RegistryError(
            f"{path}: '{key}' must be a mapping, got {type(value).__name__}", file=path
        )
    return value


def _as_list(value, path: Path, key: str) -> list:
    """Coerce a registry value to a list, or fail loudly.

    Rejecting a bare string matters as much as rejecting an int: ``skills: demo``
    is iterable, so it would silently read as the four members ``d``, ``e``,
    ``m``, ``o`` rather than crashing — a wrong answer, which is worse than a
    loud one.
    """
    if value is None:
        return []
    if not isinstance(value, list):
        raise RegistryError(
            f"{path}: '{key}' must be a list, got {type(value).__name__}", file=path
        )
    return value


def collect_bundle_refs(repo) -> dict[str, set[str]]:
    """Union, across every enabled ``registry/bundles/*.yaml``, the names referenced per kind.

    Skills are keyed by their SOURCE (the canonical ``skills/<source>/`` dir),
    never the leaf — a member's leaf is plugin-local naming and does not
    identify the canonical item.
    """
    repo = Path(repo)
    refs: dict[str, set[str]] = {kind: set() for kind in KINDS}
    bundles_dir = _require_dir(repo / "registry" / "bundles", "the bundle registry")
    bundle_files = sorted(
        list(bundles_dir.glob("*.yaml")) + list(bundles_dir.glob("*.yml"))
    )
    for bundle_file in bundle_files:
        data = _load_yaml(bundle_file)
        targets = _as_mapping(data.get("targets"), bundle_file, "targets")
        claude = _as_mapping(targets.get("claude"), bundle_file, "targets.claude")
        if not claude.get("enabled"):
            # A disabled bundle syncs no plugin tree (sync-plugins.sh) and
            # generates no manifest (generate_manifests.py), so it ships
            # nothing — its refs expose nothing. Matches check_grouping.py and
            # check_consistency.py, which skip disabled bundles the same way:
            # `not enabled`, not `enabled is False`, so a bundle that omits the
            # targets block reads as disabled here too.
            continue
        for member in _as_list(
            data.get(BUNDLE_KEY["skill"]), bundle_file, BUNDLE_KEY["skill"]
        ):
            try:
                source, _leaf = normalize_member(member)
            except ValueError:
                # Malformed member shapes are check_grouping.py's to report
                # (see check_bundle_refs.py) — skipping here is fail-closed:
                # the skill it named simply reads as unexposed.
                continue
            refs["skill"].add(source)
        for kind in ("agent", "hook", "mcp", "prompt"):
            for name in _as_list(
                data.get(BUNDLE_KEY[kind]), bundle_file, BUNDLE_KEY[kind]
            ):
                refs[kind].add(name)
    return refs


def collect_canonical(repo) -> dict[str, dict[str, str]]:
    """Return, per kind, a ``{name: repo-relative path}`` map of on-disk identities.

    See the module docstring for the identity rules. Each path names a real
    *file* wherever one identifies the item, because it is used as the
    ``::error file=...::`` anchor and GitHub only renders an annotation inline
    when it points at a file. ``mcp`` is the exception — a server is a whole
    module directory with no single defining file.
    """
    repo = Path(repo)
    canonical: dict[str, dict[str, str]] = {kind: {} for kind in KINDS}

    skills_dir = _require_dir(repo / "skills", "the canonical skills tree")
    for d in sorted(skills_dir.iterdir()):
        if d.is_dir() and (d / "SKILL.md").is_file():
            canonical["skill"][d.name] = f"skills/{d.name}/SKILL.md"

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
                canonical["mcp"][d.name.removesuffix("-go")] = f"mcp/{d.name}/"

    prompts_dir = repo / "prompts"
    if prompts_dir.is_dir():
        for p in sorted(prompts_dir.glob("*.md")):
            canonical["prompt"][p.stem] = f"prompts/{p.name}"

    return canonical


def _nonblank(value) -> bool:
    return isinstance(value, str) and bool(value.strip())


def load_allowlist(repo) -> tuple[set[tuple[str, str]], list[dict]]:
    """Parse ``registry/unbundled.yaml``. Returns (allowed set, raw entries).

    A ``(kind, name)`` pair suppresses its orphan only when the entry is
    *complete* — non-blank ``kind``, ``name``, and ``reason``. Validating the
    reason here, at the point of the suppression decision rather than only in
    :func:`find_allowlist_problems`, is what makes the requirement real: an
    entry that skips the reason both fails the strict check *and* keeps
    flagging its orphan, so the two messages agree instead of the CI output
    naming only the allowlist entry while quietly hiding what it exempted.
    Missing file => empty allowlist.
    """
    repo = Path(repo)
    path = repo / "registry" / "unbundled.yaml"
    if not path.is_file():
        return set(), []
    data = _load_yaml(path)
    entries = _as_list(data.get("unbundled"), path, "unbundled")
    allowed = set()
    for entry in entries:
        if not isinstance(entry, dict):
            continue
        kind, name, reason = entry.get("kind"), entry.get("name"), entry.get("reason")
        if _nonblank(kind) and _nonblank(name) and _nonblank(reason):
            allowed.add((kind.strip(), name.strip()))
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

    Stale means: (a) the entry names a kind that does not exist, (b) it no
    longer matches anything canonical on disk, or (c) a bundle now references
    it anyway, so the exemption is dead weight. Only complete entries reach
    here — :func:`load_allowlist` drops incomplete ones, which
    :func:`find_allowlist_problems` reports instead.
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
    """Return a message per missing field across ``registry/unbundled.yaml``.

    One entry can yield several messages (a bare ``{}`` is missing all three
    fields). Every entry must be a mapping with a non-empty ``kind``, ``name``,
    and ``reason``. The ``reason`` requirement exists to force an exemption to
    state its case in the diff, where a reviewer sees it, rather than letting
    the allowlist become a frictionless way to silence the check ("wiring it up
    is inconvenient"). Nothing validates that the reason is a *good* one — that
    is the reviewer's job; this only guarantees there is something to review.
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
        kind, name, reason = entry.get("kind"), entry.get("name"), entry.get("reason")
        label = f"{kind or '?'} '{name or '?'}'"
        if not _nonblank(kind):
            messages.append(f"registry/unbundled.yaml entry {label} is missing a 'kind'")
        if not _nonblank(name):
            messages.append(f"registry/unbundled.yaml entry {label} is missing a 'name'")
        if not _nonblank(reason):
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

    try:
        orphans = find_unexposed(repo)
        allowlist_problems = find_allowlist_problems(repo) + find_stale_allowlist_entries(
            repo
        )
    except RegistryError as exc:
        # --warn is a local pre-commit reminder and must not block a commit over
        # a half-written registry YAML; CI's strict run still fails on it.
        if warn:
            print(f"hint: {exc}", file=sys.stderr)
            return 0
        anchor = f" file={exc.file}" if exc.file else ""
        print(f"::error{anchor}::{exc}", file=sys.stderr)
        return 1

    if warn:
        for o in orphans:
            print(
                f"hint: {o.name} ({o.kind}) is authored at {o.path} but no bundle "
                "references it yet — add it to a registry/bundles/*.yaml "
                f"`{BUNDLE_KEY[o.kind]}:` list, or to registry/unbundled.yaml "
                "with a reason.",
                file=sys.stderr,
            )
        for msg in allowlist_problems:
            print(f"hint: {msg}", file=sys.stderr)
        return 0

    for o in orphans:
        print(
            f"::error file={o.path}::{o.name} ({o.kind}) is authored at {o.path} "
            f"but no bundle references it — add it to a registry/bundles/*.yaml "
            f"`{BUNDLE_KEY[o.kind]}:` list, or to registry/unbundled.yaml with a reason.",
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
