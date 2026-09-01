#!/usr/bin/env python3
"""Three-way registry consistency check (audit finding #8).

For each published target, three things must agree:

  registry/bundles/<b>.yaml  ↔  target marketplace.json  ↔  target plugin manifest

This generalises the issue #100 failure mode beyond skills: it catches a retired
bundle still listed in the marketplace, a published plugin with no bundle, or an
orphaned plugins/<name>/ directory. Only entries with a local source
(``./plugins/<name>``) are compared; any non-local source is skipped.

CLI:
    python3 scripts/check_consistency.py [REPO_ROOT]
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import yaml

LOCAL_PREFIX = "./plugins/"
TARGETS = {
    "claude": (Path(".claude-plugin/marketplace.json"), ".claude-plugin"),
    "codex": (Path(".agents/plugins/marketplace.json"), ".codex-plugin"),
}


def _local_source(entry: dict) -> str | None:
    source = entry.get("source")
    if isinstance(source, str) and source.startswith(LOCAL_PREFIX):
        return source
    if (
        isinstance(source, dict)
        and source.get("source") == "local"
        and isinstance(source.get("path"), str)
        and source["path"].startswith(LOCAL_PREFIX)
    ):
        return source["path"]
    return None


def find_consistency_issues(repo) -> list[str]:
    repo = Path(repo)

    bundle_plugins: dict[str, dict[str, str]] = {target: {} for target in TARGETS}
    bundles_dir = repo / "registry" / "bundles"
    for bf in sorted(list(bundles_dir.glob("*.yaml")) + list(bundles_dir.glob("*.yml"))):
        with bf.open() as fh:
            data = yaml.safe_load(fh) or {}
        for target in TARGETS:
            config = (data.get("targets") or {}).get(target) or {}
            if config.get("enabled"):
                plugin = config.get("pluginName") or data.get("id") or bf.stem
                bundle_plugins[target][plugin] = bf.stem

    issues: list[str] = []
    plugins_root = repo / "plugins"
    for target, (marketplace_rel, manifest_dir) in TARGETS.items():
        local_marketplace: dict[str, str] = {}
        mkt_path = repo / marketplace_rel
        if mkt_path.is_file():
            mkt = json.loads(mkt_path.read_text())
            for entry in mkt.get("plugins", []):
                source = _local_source(entry)
                if source:
                    name = entry["name"]
                    expected_source = f"{LOCAL_PREFIX}{name}"
                    if source != expected_source:
                        issues.append(
                            f"{target} marketplace plugin '{name}' source is '{source}', "
                            f"expected '{expected_source}'"
                        )
                    if name in local_marketplace:
                        issues.append(
                            f"{target} marketplace contains duplicate local plugin '{name}'"
                        )
                    local_marketplace[name] = source

        plugin_dirs: set[str] = set()
        if plugins_root.is_dir():
            for plugin_dir in plugins_root.iterdir():
                target_manifest_dir = plugin_dir / manifest_dir
                if not target_manifest_dir.is_dir():
                    continue
                plugin_dirs.add(plugin_dir.name)
                manifest = target_manifest_dir / "plugin.json"
                if not manifest.is_file():
                    issues.append(f"{manifest.relative_to(repo)} is missing")

        configured = bundle_plugins[target]
        for plugin, stem in sorted(configured.items()):
            if plugin not in local_marketplace:
                issues.append(
                    f"{target} bundle '{stem}' (plugin '{plugin}') has no marketplace.json entry"
                )
            if plugin not in plugin_dirs:
                issues.append(
                    f"{target} bundle '{stem}' (plugin '{plugin}') has no "
                    f"plugins/{plugin}/{manifest_dir}/ directory"
                )
        for name in sorted(local_marketplace):
            if name not in configured:
                issues.append(
                    f"{target} marketplace plugin '{name}' has no enabled bundle in "
                    "registry/bundles/"
                )
        for name in sorted(plugin_dirs):
            if name not in configured:
                issues.append(
                    f"plugins/{name}/{manifest_dir}/ has no enabled {target} bundle in "
                    "registry/bundles/"
                )
    return issues


def main(argv=None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    repo = Path(argv[0]) if argv else Path(".")
    issues = find_consistency_issues(repo)
    for msg in issues:
        print(f"::error::{msg}", file=sys.stderr)
    if issues:
        print(f"{len(issues)} registry/marketplace/plugins consistency issue(s)", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
