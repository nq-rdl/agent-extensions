#!/usr/bin/env python3
"""Three-way registry consistency check (audit finding #8).

For a Claude-targeted bundle to be coherent, three things must agree:

  registry/bundles/<b>.yaml  ↔  .claude-plugin/marketplace.json  ↔  plugins/<p>/

This generalises the issue #100 failure mode beyond skills: it catches a retired
bundle still listed in the marketplace, a published plugin with no bundle, or an
orphaned plugins/<name>/ directory. Marketplace entries with a non-local source
(e.g. an external github plugin like worktrunk) are ignored.

CLI:
    python3 scripts/check_consistency.py [REPO_ROOT]
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import yaml

LOCAL_PREFIX = "./plugins/"


def find_consistency_issues(repo) -> list[str]:
    repo = Path(repo)

    # Enabled Claude-target bundles, keyed by plugin name.
    bundle_plugins: dict[str, str] = {}
    for bf in sorted((repo / "registry" / "bundles").glob("*.yaml")):
        with bf.open() as fh:
            data = yaml.safe_load(fh) or {}
        claude = (data.get("targets") or {}).get("claude") or {}
        if not claude.get("enabled"):
            continue
        plugin = claude.get("pluginName") or data.get("id") or bf.stem
        bundle_plugins[plugin] = bf.stem

    # Marketplace plugins published from a LOCAL source (./plugins/<name>).
    local_marketplace: set[str] = set()
    mkt_path = repo / ".claude-plugin" / "marketplace.json"
    if mkt_path.is_file():
        mkt = json.loads(mkt_path.read_text())
        for entry in mkt.get("plugins", []):
            src = entry.get("source")
            if isinstance(src, str) and src.startswith(LOCAL_PREFIX):
                local_marketplace.add(entry["name"])

    # plugins/<name>/ directories that look like real plugins.
    plugin_dirs: set[str] = set()
    plugins_root = repo / "plugins"
    if plugins_root.is_dir():
        plugin_dirs = {
            d.name for d in plugins_root.iterdir() if (d / ".claude-plugin").is_dir()
        }

    issues: list[str] = []
    for plugin, stem in sorted(bundle_plugins.items()):
        if plugin not in local_marketplace:
            issues.append(
                f"bundle '{stem}' (plugin '{plugin}') has no marketplace.json entry"
            )
        if plugin not in plugin_dirs:
            issues.append(
                f"bundle '{stem}' (plugin '{plugin}') has no plugins/{plugin}/ directory"
            )
    for name in sorted(local_marketplace):
        if name not in bundle_plugins:
            issues.append(
                f"marketplace plugin '{name}' has no enabled bundle in registry/bundles/"
            )
    for name in sorted(plugin_dirs):
        if name not in bundle_plugins:
            issues.append(
                f"plugins/{name}/ has no enabled bundle in registry/bundles/"
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
