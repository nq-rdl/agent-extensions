#!/usr/bin/env python3
"""Generate Claude and Codex plugin manifests from the registry (D-3).

The registry is the single source of truth:

  * ``VERSION``                    — one version, stamped into every manifest.
  * ``registry/marketplace.yaml``  — marketplace metadata, plugin defaults,
                                      and display order.
  * ``registry/bundles/*.yaml``    — per-subject metadata and target settings.

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
    {
        "name",
        "displayName",
        "owner",
        "description",
        "pluginRoot",
        "pluginDefaults",
        "order",
    }
)

_CODEX_TARGET_KEYS = frozenset(
    {"enabled", "pluginName", "marketplaceName", "category", "components", "interface"}
)
_CODEX_COMPONENT_KEYS = frozenset({"skills", "mcp", "hooks", "apps"})
_CODEX_INTERFACE_KEYS = frozenset(
    {
        "displayName",
        "shortDescription",
        "longDescription",
        "developerName",
        "capabilities",
        "websiteURL",
        "privacyPolicyURL",
        "termsOfServiceURL",
        "defaultPrompt",
        "brandColor",
        "composerIcon",
        "logo",
        "logoDark",
        "screenshots",
    }
)
_CODEX_INTERFACE_LIST_KEYS = frozenset({"capabilities", "screenshots"})
_CODEX_INTERFACE_ASSET_KEYS = frozenset({"composerIcon", "logo", "logoDark", "screenshots"})


def _validate_codex_asset_path(bundle_file: Path, field: str, value: str) -> None:
    if (
        not value.startswith("./")
        or value == "./"
        or any(part == ".." for part in value[2:].replace("\\", "/").split("/"))
    ):
        raise ValueError(
            f"{bundle_file.name}: Codex interface.{field} must start with './' "
            "and stay within the plugin root"
        )


def _validate_codex_interface(bundle_file: Path, interface: dict) -> None:
    for field, value in interface.items():
        if field == "defaultPrompt":
            prompts = [value] if isinstance(value, str) else value
            if not isinstance(prompts, list) or not all(isinstance(item, str) for item in prompts):
                raise ValueError(
                    f"{bundle_file.name}: Codex interface.defaultPrompt must be a string "
                    "or list of strings"
                )
            if not prompts or len(prompts) > 3:
                raise ValueError(
                    f"{bundle_file.name}: Codex interface.defaultPrompt must contain 1-3 prompts"
                )
            if any(not prompt.strip() or len(" ".join(prompt.split())) > 128 for prompt in prompts):
                raise ValueError(
                    f"{bundle_file.name}: each Codex interface.defaultPrompt must be a "
                    "non-empty string of at most 128 characters"
                )
            continue

        if field in _CODEX_INTERFACE_LIST_KEYS:
            if not isinstance(value, list) or not all(isinstance(item, str) for item in value):
                raise ValueError(
                    f"{bundle_file.name}: Codex interface.{field} must be a list of strings"
                )
            if any(not item.strip() for item in value):
                raise ValueError(
                    f"{bundle_file.name}: Codex interface.{field} entries must not be empty"
                )
            values = value
        else:
            if not isinstance(value, str) or not value.strip():
                raise ValueError(
                    f"{bundle_file.name}: Codex interface.{field} must be a non-empty string"
                )
            values = [value]

        if field in _CODEX_INTERFACE_ASSET_KEYS:
            for asset in values:
                _validate_codex_asset_path(bundle_file, field, asset)


def _validate_codex_identifier(value: object, kind: str) -> None:
    allow_dots = kind == "plugin name"
    valid = isinstance(value, str) and bool(value)
    if valid:
        valid = all(
            char.isascii()
            and (char.isalnum() or char in "-_" or (allow_dots and char == "."))
            for char in value
        )
    if valid and allow_dots:
        valid = value not in {".", ".."} and not (
            value.startswith(".") or value.endswith(".") or ".." in value
        )
    if not valid:
        allowed = "ASCII letters, digits, '.', '_', and '-'" if allow_dots else (
            "ASCII letters, digits, '_', and '-'"
        )
        raise ValueError(f"invalid Codex {kind} {value!r}; use only {allowed}")


def _codex_marketplace_defaults(mkt: dict, defaults: dict) -> tuple[str, str, str | None]:
    display_name = mkt.get("displayName") or mkt["name"]
    if not isinstance(display_name, str) or not display_name.strip():
        raise ValueError("registry/marketplace.yaml: Codex displayName must be a non-empty string")

    author = defaults.get("author")
    if author is not None and not isinstance(author, dict):
        raise ValueError("registry/marketplace.yaml: pluginDefaults.author must be a mapping")
    developer_name = (author or {}).get("name", mkt["name"])
    if not isinstance(developer_name, str) or not developer_name.strip():
        raise ValueError(
            "registry/marketplace.yaml: pluginDefaults.author.name must be a non-empty string"
        )

    repository = defaults.get("repository")
    if repository is not None and (
        not isinstance(repository, str) or not repository.strip()
    ):
        raise ValueError(
            "registry/marketplace.yaml: pluginDefaults.repository must be a non-empty string"
        )
    return display_name, developer_name, repository


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
    """Return metadata for enabled Claude bundles."""
    out: dict[str, dict] = {}
    bundles_dir = repo / "registry" / "bundles"
    for bf in sorted(list(bundles_dir.glob("*.yaml")) + list(bundles_dir.glob("*.yml"))):
        data = _read_yaml(bf)
        claude = (data.get("targets") or {}).get("claude") or {}
        if not claude.get("enabled"):
            continue
        plugin = claude.get("pluginName") or data.get("id") or bf.stem
        out[plugin] = {
            "displayName": data.get("displayName") or plugin,
            "description": data.get("description") or "",
            "keywords": list(data.get("keywords") or []),
            # Optional per-bundle SPDX license override (e.g. Apache-2.0 for a
            # vendored fork). None means "fall back to pluginDefaults.license".
            "license": data.get("license"),
            "skills": list(data.get("skills") or []),
        }
    return out


def _codex_enabled_bundles(repo: Path, marketplace_name: str) -> dict[str, dict]:
    """Return validated phase-one Codex bundles keyed by target plugin name.

    Phase one deliberately publishes only skills from the existing shared plugin
    trees. MCP, hooks, apps, and Claude subagents remain disabled until they have
    target-specific runtime validation.
    """
    out: dict[str, dict] = {}
    bundles_dir = repo / "registry" / "bundles"
    for bf in sorted(list(bundles_dir.glob("*.yaml")) + list(bundles_dir.glob("*.yml"))):
        data = _read_yaml(bf)
        targets = data.get("targets")
        if targets is None:
            targets = {}
        elif not isinstance(targets, dict):
            raise ValueError(f"{bf.name}: targets must be a mapping")
        codex = targets.get("codex")
        if codex is None:
            codex = {}
        elif not isinstance(codex, dict):
            raise ValueError(f"{bf.name}: targets.codex must be a mapping")

        unknown = set(codex) - _CODEX_TARGET_KEYS
        if unknown:
            names = ", ".join(sorted(unknown))
            raise ValueError(f"{bf.name}: unknown targets.codex field(s): {names}")
        if "enabled" in codex and not isinstance(codex["enabled"], bool):
            raise ValueError(f"{bf.name}: targets.codex.enabled must be a boolean")
        if not codex.get("enabled"):
            continue

        plugin = codex.get("pluginName") or data.get("id") or bf.stem
        try:
            _validate_codex_identifier(plugin, "plugin name")
            _validate_codex_identifier(marketplace_name, "marketplace name")
        except ValueError as exc:
            raise ValueError(f"{bf.name}: {exc}") from exc
        if plugin in out:
            raise ValueError(
                f"Codex pluginName '{plugin}' is used by both '{out[plugin]['bundle']}' "
                f"and '{bf.stem}'"
            )

        configured_marketplace = codex.get("marketplaceName") or marketplace_name
        if configured_marketplace != marketplace_name:
            raise ValueError(
                f"{bf.name}: targets.codex.marketplaceName '{configured_marketplace}' "
                f"does not match registry marketplace '{marketplace_name}'"
            )

        # The phase-one Codex target reuses the Claude-generated plugin tree.
        claude = targets.get("claude")
        if not isinstance(claude, dict):
            raise ValueError(f"{bf.name}: targets.claude must be a mapping")
        claude_plugin = claude.get("pluginName") or data.get("id") or bf.stem
        if not claude.get("enabled") or claude_plugin != plugin:
            raise ValueError(
                f"{bf.name}: phase-one Codex pluginName must match an enabled Claude "
                "pluginName because both targets share plugins/<name>/"
            )

        components = codex.get("components")
        if components is None:
            components = {}
        elif not isinstance(components, dict):
            raise ValueError(f"{bf.name}: targets.codex.components must be a mapping")
        unknown_components = set(components) - _CODEX_COMPONENT_KEYS
        if unknown_components:
            names = ", ".join(sorted(unknown_components))
            raise ValueError(f"{bf.name}: unknown Codex component(s): {names}")
        for component, enabled in components.items():
            if not isinstance(enabled, bool):
                raise ValueError(
                    f"{bf.name}: targets.codex.components.{component} must be a boolean"
                )

        raw_skills = data.get("skills")
        if raw_skills is None:
            skills = []
        elif not isinstance(raw_skills, list):
            raise ValueError(f"{bf.name}: skills must be a list")
        else:
            skills = list(raw_skills)
        skills_enabled = components.get("skills", bool(skills))
        unsupported = [
            component
            for component in ("mcp", "hooks", "apps")
            if components.get(component, False)
        ]
        if unsupported:
            raise ValueError(
                f"{bf.name}: phase-one Codex generation does not support enabled "
                f"component(s): {', '.join(unsupported)}"
            )
        if not skills_enabled:
            raise ValueError(f"{bf.name}: enabled Codex bundle exposes no supported components")
        if not skills:
            raise ValueError(f"{bf.name}: Codex skills component is enabled but skills is empty")

        category = codex.get("category")
        if not isinstance(category, str) or not category:
            raise ValueError(f"{bf.name}: targets.codex.category must be a non-empty string")

        interface = codex.get("interface")
        if interface is None:
            interface = {}
        elif not isinstance(interface, dict):
            raise ValueError(f"{bf.name}: targets.codex.interface must be a mapping")
        unknown_interface = set(interface) - _CODEX_INTERFACE_KEYS
        if unknown_interface:
            names = ", ".join(sorted(unknown_interface))
            raise ValueError(f"{bf.name}: unknown Codex interface field(s): {names}")
        _validate_codex_interface(bf, interface)

        display_name = data.get("displayName") or plugin
        if not isinstance(display_name, str) or not display_name.strip():
            raise ValueError(f"{bf.name}: displayName must be a non-empty string")

        description = data.get("description") or ""
        if not isinstance(description, str) or not description.strip():
            raise ValueError(f"{bf.name}: description must be a non-empty string")

        keywords = data.get("keywords") or []
        if not isinstance(keywords, list) or not all(
            isinstance(keyword, str) for keyword in keywords
        ):
            raise ValueError(f"{bf.name}: keywords must be a list of strings")

        short_description = interface.get("shortDescription", description)
        if not isinstance(short_description, str) or not short_description:
            raise ValueError(
                f"{bf.name}: Codex interface.shortDescription must be a non-empty string"
            )
        if len(short_description) > 80:
            raise ValueError(
                f"{bf.name}: Codex interface.shortDescription exceeds 80 characters; "
                "add a shorter targets.codex.interface.shortDescription"
            )

        out[plugin] = {
            "bundle": bf.stem,
            "displayName": display_name,
            "description": description,
            "keywords": list(keywords),
            "license": data.get("license"),
            "skills": skills,
            "category": category,
            "interface": interface,
        }
    return out


def _ordered_local(order: list[str], enabled: dict[str, dict]) -> list[str]:
    """Local plugins in declared order; any enabled plugin missing from `order`
    is appended alphabetically with a ::warning:: (never silently dropped)."""
    ordered: list[str] = []
    seen: set[str] = set()
    for plugin in order:
        if plugin not in enabled:
            continue
        if plugin in seen:
            raise ValueError(
                f"duplicate plugin '{plugin}' in registry/marketplace.yaml 'order'"
            )
        ordered.append(plugin)
        seen.add(plugin)
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
    codex_enabled = _codex_enabled_bundles(repo, mkt["name"])
    codex_order = _ordered_local(list(mkt.get("order") or []), codex_enabled)
    if codex_enabled:
        codex_display_name, codex_developer_name, codex_repository = (
            _codex_marketplace_defaults(mkt, defaults)
        )

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

    # ── Native Codex marketplace + per-plugin manifests ────────────────────
    codex_marketplace_plugins: list[dict] = []
    codex_plugins: dict[str, dict] = {}
    for p in codex_order:
        bundle = codex_enabled[p]
        codex_marketplace_plugins.append(
            {
                "name": p,
                "source": {"source": "local", "path": f"./plugins/{p}"},
                "policy": {
                    "installation": "AVAILABLE",
                    "authentication": "ON_INSTALL",
                },
                "category": bundle["category"],
            }
        )

        interface = {
            "displayName": bundle["displayName"],
            "shortDescription": bundle["description"],
            "longDescription": bundle["description"],
            "developerName": codex_developer_name,
            "category": bundle["category"],
            "capabilities": ["Skills"],
            "websiteURL": codex_repository,
        }
        interface.update(bundle["interface"])

        codex_plugins[p] = {
            "name": p,
            "version": version,
            "description": bundle["description"],
            "author": defaults.get("author"),
            "repository": defaults.get("repository"),
            "license": bundle.get("license") or defaults.get("license"),
            "keywords": bundle["keywords"],
            "skills": "./skills/",
            "interface": interface,
        }

    codex_marketplace = {
        "name": mkt["name"],
        "interface": {
            "displayName": codex_display_name if codex_enabled else mkt.get("displayName")
        },
        "plugins": codex_marketplace_plugins,
    }

    return {
        "marketplace": marketplace,
        "plugins": out_plugins,
        "codex_marketplace": codex_marketplace,
        "codex_plugins": codex_plugins,
    }


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
    if gen["codex_plugins"]:
        out.append(
            (
                repo / ".agents" / "plugins" / "marketplace.json",
                _dumps(gen["codex_marketplace"]),
            )
        )
    for name, pj in gen["codex_plugins"].items():
        out.append((repo / "plugins" / name / ".codex-plugin" / "plugin.json", _dumps(pj)))
    return out


def _obsolete_codex_targets(repo: Path, gen: dict) -> list[Path]:
    """Return generated Codex files that no longer have an enabled target."""
    repo = Path(repo)
    obsolete: list[Path] = []
    if not gen["codex_plugins"]:
        marketplace = repo / ".agents" / "plugins" / "marketplace.json"
        if marketplace.is_file():
            obsolete.append(marketplace)

    enabled = set(gen["codex_plugins"])
    plugins_root = repo / "plugins"
    if plugins_root.is_dir():
        for manifest in sorted(plugins_root.glob("*/.codex-plugin/plugin.json")):
            if manifest.parent.parent.name not in enabled:
                obsolete.append(manifest)
    return obsolete


def write(repo) -> None:
    repo = Path(repo)
    gen = generate(repo)
    for path in _obsolete_codex_targets(repo, gen):
        path.unlink()
        for parent in (path.parent, path.parent.parent):
            try:
                parent.rmdir()
            except OSError:
                break
        print(f"  ✓ removed {path.relative_to(repo)}")
    for path, content in _targets(repo, gen):
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")
        print(f"  ✓ {path.relative_to(repo)}")


def check(repo) -> list[str]:
    repo = Path(repo)
    issues: list[str] = []
    gen = generate(repo)
    for path in _obsolete_codex_targets(repo, gen):
        issues.append(
            f"{path.relative_to(repo)} is obsolete — run "
            "`python3 scripts/generate_manifests.py .`"
        )
    for path, expected in _targets(repo, gen):
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
