#!/usr/bin/env python3
"""Generate plugin.json + marketplace.json from the registry (D-3).

The registry is the single source of truth:

  * ``VERSION``                    — one version, stamped into every manifest.
  * ``registry/marketplace.yaml``  — marketplace metadata, plugin defaults,
                                      and display order.
  * ``registry/bundles/*.yaml``    — per-subject name/description/keywords.

This is the structural fix for #100's metadata rot: hand-edited manifests can no
longer drift, because CI runs ``generate_manifests.py --check`` and fails if any
generated file differs from what the registry would produce.

CLI:
    python3 scripts/generate_manifests.py [REPO_ROOT]            # write manifests
    python3 scripts/generate_manifests.py [REPO_ROOT] --check    # fail on drift
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import yaml


def _read_yaml(path: Path) -> dict:
    with path.open() as fh:
        return yaml.safe_load(fh) or {}


# Top-level keys generate() actually consumes from registry/marketplace.yaml.
# Anything else is ignored — but an ignored key is almost always a mistake (a
# typo, or a stale block like the removed `external:` passthrough), so we warn
# rather than drop it silently. Same never-silently-drop policy as _ordered_local.
_KNOWN_MARKETPLACE_KEYS = frozenset(
    {"name", "owner", "description", "pluginRoot", "pluginDefaults", "order"}
)


def _warn_unknown_marketplace_keys(mkt: dict) -> None:
    """::warning:: for any top-level marketplace.yaml key generate() ignores, so a
    stale `external:` block or a typo'd key surfaces instead of failing silently."""
    unknown = set(mkt) - _KNOWN_MARKETPLACE_KEYS
    if "external" in unknown:
        unknown.discard("external")
        print(
            "::warning::registry/marketplace.yaml still defines 'external:' — "
            "external plugins are installed by users from their own upstream "
            "marketplaces via user-level Claude Code config (see "
            "docs/external-marketplaces.md); this key is ignored.",
            file=sys.stderr,
        )
    for key in sorted(unknown):
        print(
            f"::warning::registry/marketplace.yaml: unrecognized top-level key "
            f"'{key}' — ignored",
            file=sys.stderr,
        )


def _enabled_bundles(repo: Path) -> dict[str, dict]:
    """Return {pluginName: {'description', 'keywords'}} for enabled Claude bundles."""
    out: dict[str, dict] = {}
    bundles_dir = repo / "registry" / "bundles"
    for bf in sorted(list(bundles_dir.glob("*.yaml")) + list(bundles_dir.glob("*.yml"))):
        data = _read_yaml(bf)
        claude = (data.get("targets") or {}).get("claude") or {}
        if not claude.get("enabled"):
            continue
        plugin = claude.get("pluginName") or data.get("id") or bf.stem
        out[plugin] = {
            "description": data.get("description") or "",
            "keywords": list(data.get("keywords") or []),
            # Optional per-bundle SPDX license override (e.g. Apache-2.0 for a
            # vendored fork). None means "fall back to pluginDefaults.license".
            "license": data.get("license"),
        }
    return out


def _ordered_local(order: list[str], enabled: dict[str, dict]) -> list[str]:
    """Local plugins in declared order; any enabled plugin missing from `order`
    is appended alphabetically with a ::warning:: (never silently dropped)."""
    ordered = [p for p in order if p in enabled]
    leftover = sorted(set(enabled) - set(ordered))
    for p in leftover:
        print(
            f"::warning::plugin '{p}' is enabled but absent from registry/"
            "marketplace.yaml 'order' — appended alphabetically",
            file=sys.stderr,
        )
    return ordered + leftover


def generate(repo) -> dict:
    repo = Path(repo)
    version = (repo / "VERSION").read_text().strip()
    mkt = _read_yaml(repo / "registry" / "marketplace.yaml")
    _warn_unknown_marketplace_keys(mkt)
    defaults = mkt.get("pluginDefaults") or {}
    enabled = _enabled_bundles(repo)
    local_order = _ordered_local(list(mkt.get("order") or []), enabled)

    # ── marketplace.json ────────────────────────────────────────────────────
    plugins: list[dict] = []
    for p in local_order:
        plugins.append(
            {
                "name": p,
                "source": f"./plugins/{p}",
                "description": enabled[p]["description"],
                "version": version,
                "keywords": enabled[p]["keywords"],
            }
        )

    marketplace = {
        "name": mkt["name"],
        "owner": mkt["owner"],
        "metadata": {
            "description": mkt.get("description", ""),
            "version": version,
            "pluginRoot": mkt.get("pluginRoot", "./plugins"),
        },
        "plugins": plugins,
    }

    # ── per-plugin plugin.json ──────────────────────────────────────────────
    out_plugins: dict[str, dict] = {}
    for p in local_order:
        out_plugins[p] = {
            "name": p,
            "version": version,
            "description": enabled[p]["description"],
            "author": defaults.get("author"),
            "repository": defaults.get("repository"),
            # A bundle's own `license:` wins; otherwise the marketplace default.
            "license": enabled[p].get("license") or defaults.get("license"),
        }

    return {"marketplace": marketplace, "plugins": out_plugins}


def _dumps(obj: dict) -> str:
    # ensure_ascii=False keeps em dashes literal (matches the hand-written files);
    # trailing newline matches the existing manifests.
    return json.dumps(obj, indent=2, ensure_ascii=False) + "\n"


def _targets(repo: Path, gen: dict) -> list[tuple[Path, str]]:
    """(path, expected-content) for every generated file."""
    repo = Path(repo)
    out = [(repo / ".claude-plugin" / "marketplace.json", _dumps(gen["marketplace"]))]
    for name, pj in gen["plugins"].items():
        out.append((repo / "plugins" / name / ".claude-plugin" / "plugin.json", _dumps(pj)))
    return out


def write(repo) -> None:
    repo = Path(repo)
    for path, content in _targets(repo, generate(repo)):
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")
        print(f"  ✓ {path.relative_to(repo)}")


def check(repo) -> list[str]:
    repo = Path(repo)
    issues: list[str] = []
    for path, expected in _targets(repo, generate(repo)):
        actual = path.read_text(encoding="utf-8") if path.is_file() else None
        if actual != expected:
            rel = path.relative_to(repo)
            reason = "missing" if actual is None else "stale"
            issues.append(
                f"{rel} is {reason} — run `python3 scripts/generate_manifests.py .`"
            )
    return issues


def main(argv=None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    do_check = "--check" in argv
    positional = [a for a in argv if not a.startswith("--")]
    repo = Path(positional[0]) if positional else Path(".")
    if do_check:
        issues = check(repo)
        for msg in issues:
            print(f"::error::{msg}", file=sys.stderr)
        if issues:
            print(f"{len(issues)} stale generated manifest(s)", file=sys.stderr)
            return 1
        print("Generated manifests are in sync.")
        return 0
    write(repo)
    print("Done.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
