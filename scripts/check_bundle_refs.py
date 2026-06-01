#!/usr/bin/env python3
"""Resolve registry bundle references against the canonical trees.

Every skill named in ``registry/bundles/*.yaml`` must resolve to
``skills/<name>/`` and every agent to ``agents/<name>/agent.md``. This logic was
previously inlined in ``.github/workflows/validate.yml``; extracting it here
makes it unit-testable and reusable (e.g. by ``sync-skills.yml`` to flag drift).

CLI:
    python3 scripts/check_bundle_refs.py [REPO_ROOT]
exits non-zero (with ``::error::`` annotations) if any reference is unresolved.
"""
from __future__ import annotations

import sys
from dataclasses import dataclass
from pathlib import Path

import yaml


@dataclass(frozen=True)
class Problem:
    bundle: str  # bundle id (or filename stem)
    kind: str  # "skill" or "agent"
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
        for name in data.get("skills") or []:
            if not (repo / "skills" / name).is_dir():
                problems.append(Problem(bundle, "skill", name, rel))
        for name in data.get("agents") or []:
            if not (repo / "agents" / name / "agent.md").is_file():
                problems.append(Problem(bundle, "agent", name, rel))
    return problems


def main(argv=None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    repo = Path(argv[0]) if argv else Path(".")
    problems = find_unresolved_refs(repo)
    for p in problems:
        loc = f" file={p.bundle_file}" if p.bundle_file else ""
        suffix = (
            f"skills/{p.name}/" if p.kind == "skill" else f"agents/{p.name}/agent.md"
        )
        print(
            f"::error{loc}::Bundle '{p.bundle}' references {p.kind} "
            f"'{p.name}' but {suffix} does not exist",
            file=sys.stderr,
        )
    if problems:
        print(f"{len(problems)} unresolved bundle reference(s)", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
