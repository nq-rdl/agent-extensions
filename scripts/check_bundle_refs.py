#!/usr/bin/env python3
"""Resolve registry bundle references against the canonical trees.

Every skill named in ``registry/bundles/*.yaml`` must resolve to
``skills/<name>/``. Standalone agent declarations are rejected. This logic was
previously inlined in ``.github/workflows/validate.yml``; extracting it here
makes it unit-testable and reusable.

CLI:
    python3 scripts/check_bundle_refs.py [REPO_ROOT]
exits non-zero (with ``::error::`` annotations) if any reference is unresolved.
"""
from __future__ import annotations

import sys
from dataclasses import dataclass
from pathlib import Path

import yaml

from _registry import normalize_member


@dataclass(frozen=True)
class Problem:
    bundle: str  # bundle id (or filename stem)
    kind: str  # "skill" or "retired-agent"
    name: str
    bundle_file: str = ""  # path relative to repo root, for CI annotations


def find_unresolved_refs(repo) -> list[Problem]:
    """Return a Problem for every bundle ref that does not resolve on disk."""
    repo = Path(repo)
    problems: list[Problem] = []
    bundles_dir = repo / "registry" / "bundles"
    bundle_files = sorted(
        list(bundles_dir.glob("*.yaml")) + list(bundles_dir.glob("*.yml"))
    )
    for bundle_file in bundle_files:
        with bundle_file.open() as fh:
            data = yaml.safe_load(fh) or {}
        bundle = data.get("id") or bundle_file.stem
        rel = str(bundle_file.relative_to(repo))
        for member in data.get("skills") or []:
            # A member is flat ``<name>`` or an explicit ``{source, leaf}`` map;
            # either way it resolves against the FLAT upstream skills/<source>/.
            # Malformed shapes are check_grouping.py's to report, so skip them
            # here (keeps the two checkers' failures independent, as the docstring
            # promises) rather than crashing on bad input.
            try:
                source, _leaf = normalize_member(member)
            except ValueError:
                continue
            if not (repo / "skills" / source).is_dir():
                problems.append(Problem(bundle, "skill", source, rel))
        if data.get("agents"):
            problems.append(Problem(bundle, "retired-agent", "agents", rel))
    return problems


def main(argv=None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    repo = Path(argv[0]) if argv else Path(".")
    problems = find_unresolved_refs(repo)
    for p in problems:
        loc = f" file={p.bundle_file}" if p.bundle_file else ""
        if p.kind == "retired-agent":
            message = "Standalone agents are retired; use skills with references/subagent.rst"
        else:
            message = (f"Bundle '{p.bundle}' references skill '{p.name}' but "
                       f"skills/{p.name}/ does not exist")
        print(f"::error{loc}::{message}", file=sys.stderr)
    if problems:
        print(f"{len(problems)} unresolved bundle reference(s)", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
