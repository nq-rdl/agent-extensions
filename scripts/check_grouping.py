#!/usr/bin/env python3
"""Enforce the Option-2 skill-grouping contract (spec §3 / CONTRIBUTING §6).

A bundle skill member is either a flat string ``<leaf>`` (``source == leaf``) or
an explicit ``{source, leaf}`` mapping that packages the flat upstream skill
``skills/<source>/`` under a different leaf (e.g. ``go-gh`` -> ``go:gh``).
``sync-plugins.sh`` copies ``skills/<source>/`` ->
``plugins/<pluginName>/skills/<leaf>/`` and Claude Code invokes
``<pluginName>:<leaf>`` — the leaf *folder* name drives invocation. The
frontmatter ``name`` is the label Claude Code shows in /-autocomplete and
listings, so it must agree with the leaf or the user sees the wrong command
(``/go`` would otherwise recommend ``go-gh`` instead of ``go:gh``). On copy,
``sync-plugins.sh`` reconciles the plugin copy's ``name`` to the leaf, and
``validate-plugins.sh`` guards that name == leaf.

Grouping is owned here in the registry, so the upstream ``skills/`` tree stays
flat: there are no upstream group folders; the frontmatter ``name`` reconcile
happens on the derivative plugin copy, never the canonical source. This checker
asserts, per enabled Claude bundle:

  * ``pluginName`` is unique across all bundles.
  * every member has a valid shape (a string, or a ``{source, leaf}`` mapping
    with non-empty string values).
  * no duplicate leaf within a bundle (two members must not collide on the same
    ``plugins/<pluginName>/skills/<leaf>/`` destination).

Source-existence is checked separately by ``check_bundle_refs.py``; this checker
only validates *grouping*, so the two report independent, non-duplicated
failures.

CLI:
    python3 scripts/check_grouping.py [REPO_ROOT]
exits non-zero (with ``::error::`` annotations) on any contract violation.
"""
from __future__ import annotations

import sys
from pathlib import Path

import yaml

from _registry import normalize_member


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
            try:
                _source, leaf = normalize_member(member)
            except ValueError as exc:
                issues.append(f"{bf.stem}: {exc}")
                continue
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
