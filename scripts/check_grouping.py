#!/usr/bin/env python3
"""Enforce the cross-repo skill-grouping contract (spec §3 / CONTRIBUTING §6).

A bundle skill member is either flat ``<leaf>`` (e.g. ``go-gh``) or grouped
``<group>/<leaf>`` (e.g. ``go/gh``). Claude Code invokes ``<pluginName>:<leaf>``,
and ``sync-plugins.sh`` copies ``skills/<group>/<leaf>/`` into
``plugins/<pluginName>/skills/<leaf>/`` (dropping the ``<group>/`` prefix). For
that to be coherent, this checker asserts, per enabled Claude bundle:

  * ``pluginName`` is unique across all bundles.
  * grouped member ``g/l``: ``g == pluginName``; the group folder ``skills/g/``
    has no direct ``SKILL.md`` (a flat skill is never descended into); and
    ``skills/g/l/SKILL.md`` frontmatter ``name == l``.
  * flat member ``m``: ``skills/m/SKILL.md`` frontmatter ``name == m``.
  * no duplicate leaf within a bundle (two members must not collide on the same
    ``plugins/<pluginName>/skills/<leaf>/`` destination).

Source-existence is checked separately by ``check_bundle_refs.py``; this checker
only validates *grouping* and is silent about members whose source is absent
(so the two checkers report independent, non-duplicated failures).

CLI:
    python3 scripts/check_grouping.py [REPO_ROOT]
exits non-zero (with ``::error::`` annotations) on any contract violation.
"""
from __future__ import annotations

import sys
from pathlib import Path

import yaml


def _frontmatter_name(skill_md: Path) -> str | None:
    """Return the ``name`` from a SKILL.md's YAML frontmatter, or None if the
    file/frontmatter/name is absent or unparseable (existence is another
    checker's job — we only compare names when we can read one)."""
    if not skill_md.is_file():
        return None
    text = skill_md.read_text(encoding="utf-8")
    if not text.startswith("---\n"):
        return None
    parts = text.split("---\n", 2)
    if len(parts) < 3:
        return None
    try:
        return (yaml.safe_load(parts[1]) or {}).get("name")
    except yaml.YAMLError:
        return None


def find_grouping_issues(repo) -> list[str]:
    repo = Path(repo)
    issues: list[str] = []
    seen_plugin: dict[str, str] = {}  # pluginName -> first bundle stem
    bundles_dir = repo / "registry" / "bundles"
    for bf in sorted(
        list(bundles_dir.glob("*.yaml")) + list(bundles_dir.glob("*.yml"))
    ):
        with bf.open() as fh:
            data = yaml.safe_load(fh) or {}
        claude = (data.get("targets") or {}).get("claude") or {}
        if not claude.get("enabled"):
            continue
        plugin = claude.get("pluginName") or data.get("id") or bf.stem
        if plugin in seen_plugin:
            issues.append(
                f"pluginName '{plugin}' used by both '{seen_plugin[plugin]}' "
                f"and '{bf.stem}' — pluginName must be unique across bundles"
            )
        else:
            seen_plugin[plugin] = bf.stem

        leaves: set[str] = set()
        for member in data.get("skills") or []:
            if "/" in member:
                group, leaf = member.split("/", 1)
                if group != plugin:
                    issues.append(
                        f"{bf.stem}: member '{member}' group '{group}' != "
                        f"pluginName '{plugin}'"
                    )
                if (repo / "skills" / group / "SKILL.md").is_file():
                    issues.append(
                        f"{bf.stem}: group folder skills/{group}/ has a direct "
                        "SKILL.md — a flat skill must not be descended into as a group"
                    )
                name = _frontmatter_name(repo / "skills" / group / leaf / "SKILL.md")
                if name is not None and name != leaf:
                    issues.append(
                        f"{bf.stem}: skills/{member}/ frontmatter name '{name}' "
                        f"!= leaf '{leaf}'"
                    )
            else:
                leaf = member
                name = _frontmatter_name(repo / "skills" / member / "SKILL.md")
                if name is not None and name != member:
                    issues.append(
                        f"{bf.stem}: skills/{member}/ frontmatter name '{name}' "
                        f"!= '{member}'"
                    )
            if leaf in leaves:
                issues.append(f"{bf.stem}: duplicate leaf '{leaf}' within the bundle")
            leaves.add(leaf)
    return issues


def main(argv=None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    repo = Path(argv[0]) if argv else Path(".")
    issues = find_grouping_issues(repo)
    for msg in issues:
        print(f"::error::{msg}", file=sys.stderr)
    if issues:
        print(f"{len(issues)} grouping contract violation(s)", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
