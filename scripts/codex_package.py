#!/usr/bin/env python3
"""Build and validate self-contained Codex packages from canonical bundle sources.

Claude copies retain their existing naming contract. Codex copies carry explicit
leaf names. No target publishes standalone agents. Run through Pixi.
"""

from __future__ import annotations

import argparse
import json
import re
import shutil
import stat
import tempfile
from pathlib import Path

import yaml

try:
    from ._registry import normalize_member
    from .generate_manifests import (
        _codex_enabled_bundles,
        _read_yaml,
        generate,
        _targets,
    )
except ImportError:
    from _registry import normalize_member
    from generate_manifests import (
        _codex_enabled_bundles,
        _read_yaml,
        generate,
        _targets,
    )

ROOT = Path("dist/codex/plugins")
SKILL_KEYS = {
    "name",
    "description",
    "license",
    "compatibility",
    "metadata",
    "disable-model-invocation",
}
EVENTS = {
    "SessionStart",
    "SessionEnd",
    "UserPromptSubmit",
    "PreToolUse",
    "PostToolUse",
    "Stop",
    "SubagentStart",
    "SubagentStop",
    "PreCompact",
    "PostCompact",
    "PermissionRequest",
    "Interrupt",
}
SUBJECT_SKILLS = {
    "cc-setup",
    "cc-agent-teams",
    "cc-create-workflow",
    "cc-hook",
    "cc-pipeline",
    "opencode-delegate",
    "opencode-agent",
    "opencode-plugin",
    "opencode-tools",
}


def frontmatter(text):
    parts = text.split("---\n", 2)
    if len(parts) != 3 or parts[0].strip():
        raise ValueError("SKILL.md requires YAML frontmatter")
    data = yaml.safe_load(parts[1])
    if not isinstance(data, dict):
        raise ValueError("skill frontmatter must be a mapping")
    return data, parts[2]


def contained(root, relative):
    path = root / relative
    if not path.resolve().is_relative_to(root.resolve()):
        raise ValueError(f"path escapes package/source root: {relative}")
    return path


def copy_source(src, dst):
    if src.is_symlink():
        raise ValueError(f"symlinks are not package sources: {src}")
    if not src.exists():
        raise ValueError(f"missing package source: {src}")
    if src.is_dir():
        for path in src.rglob("*"):
            if path.is_symlink():
                raise ValueError(f"symlinks are not package sources: {path}")
        shutil.copytree(
            src,
            dst,
            dirs_exist_ok=True,
            ignore=shutil.ignore_patterns("__pycache__", "*.pyc", ".DS_Store"),
        )
    else:
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(src, dst)


def invocation_text(text, names):
    # Only known catalog ids, never URL paths, arbitrary code or upstream examples.
    return (
        re.sub(
            r"(?<![\w/])/(("
            + "|".join(re.escape(x) for x in sorted(names, key=len, reverse=True))
            + r"))(?![\w-])",
            lambda m: "$" + m[1],
            text,
        )
        if names
        else text
    )


def helper_invocations(text, src, source, leaf):
    """Resolve commands for helpers actually shipped by this skill, preserving cwd."""
    for helper in sorted((src / "scripts").rglob("*")):
        if not helper.is_file():
            continue
        relative = helper.relative_to(src).as_posix()
        pattern = (
            r"\b(bash|sh|python3?|node|source)([ \t]+)([\"']?)"
            + r"(?:\./)?(?:skills/" + re.escape(source) + r"/)?"
            + re.escape(relative) + r"\3(?=[\s`;|&)]|$)"
        )
        text = re.sub(
            pattern,
            lambda m: f'{m[1]}{m[2]}"${{PLUGIN_ROOT}}/skills/{leaf}/{relative}"',
            text,
        )
    return text


def skill_copy(repo, source, leaf, dest, config, names):
    if (
        not re.fullmatch(r"[a-z0-9]+(?:-[a-z0-9]+)*", source)
        or not re.fullmatch(r"[a-z0-9]+(?:-[a-z0-9]+)*", leaf)
        or len(leaf) > 64
    ):
        raise ValueError(f"invalid canonical skill or leaf: {source!r} -> {leaf!r}")
    src = contained(repo / "skills", source)
    copy_source(src, dest)
    data, body = frontmatter((src / "SKILL.md").read_text())
    native_override = source in config.get("skillOverrides", {})
    if native_override:
        body = contained(src, config["skillOverrides"][source]).read_text()
    data = {key: value for key, value in data.items() if key in SKILL_KEYS}
    data["name"] = leaf
    if source in config.get("skillDescriptions", {}):
        data["description"] = config["skillDescriptions"][source]
    # Runtime policy is preserved. Directory readiness reports explicit-only
    # entrypoints separately rather than silently enabling automatic invocation.
    if source not in SUBJECT_SKILLS:
        body = invocation_text(body, names)
        data["description"] = invocation_text(data.get("description", ""), names)
        # Native overrides may explicitly forbid Claude's tools. Replacing a
        # tool name there would invert the instruction's intended host scope.
        if not native_override:
            body = re.sub(
                r"\bAskUserQuestion(?: tools?)?\b", "the host user-question tool", body
            )
        body = body.replace("${CLAUDE_PLUGIN_ROOT}", "${PLUGIN_ROOT}")
    body = helper_invocations(body, src, source, leaf)
    reference_helpers = False
    for path in (dest / "references").rglob("*.rst"):
        original = path.read_text()
        adapted = helper_invocations(original, src, source, leaf)
        if adapted != original:
            path.write_text(adapted)
            reference_helpers = True
    prelude = []
    legacy_terms = (
        "AskUserQuestion",
        "${CLAUDE_PLUGIN_ROOT}",
        "BashOutput",
        "run_in_background",
    )
    if any(term in body for term in legacy_terms) or any(
        any(term in p.read_text() for term in legacy_terms)
        for p in (src / "references").rglob("*.rst")
    ):
        prelude.append(
            "Use the host’s available file, search, shell, and user-question tools for this workflow. "
            "Legacy tool names and slash-qualified skill references in supporting references "
            "describe capabilities; they do not install those tools. Keep code/configuration "
            "examples for another host unchanged when authoring that host’s artifacts."
        )
    if any(
        invocation_text(text, names) != text
        for text in (p.read_text() for p in (src / "references").rglob("*.rst"))
    ):
        prelude.append(
            "When supporting references invoke a catalog skill as /subject:facet, "
            "use $subject:facet in Codex. Preserve slash syntax inside examples "
            "that configure or document another host."
        )
    if source in SUBJECT_SKILLS:
        prelude.append(
            "This skill describes another host. Claude Code/OpenCode commands, configuration, "
            "and hook examples below are artifacts for that host, not tools available in Codex. "
            "Use Codex tools to inspect or author them; launch the target host only when the "
            "user requests execution and it is installed. Do not configure Codex as Claude Code."
        )
    if "${PLUGIN_ROOT}" in body or reference_helpers:
        prelude.append(
            "Before shell examples, set PLUGIN_ROOT to the absolute installed plugin directory: "
            "two parent directories above this SKILL.md’s containing skill directory. "
            "Derive it from the loaded file path, never the working directory. "
            "This variable is not automatically supplied to ordinary shell tools. Quote it in commands."
        )
    if "$ARGUMENTS" in body:
        prelude.append(
            "Here $ARGUMENTS means the user’s supplied skill arguments. Codex does not populate "
            "a shell variable for them. Pass arguments with shell quoting that preserves literal "
            "text; never evaluate user text as shell code."
        )
    if data.get("disable-model-invocation"):
        prelude.append(
            "Execute this workflow only on an explicit user request; preserve its review-only "
            "or mutation scope and existing authorization checks."
        )
    if (dest / "references/subagent.rst").is_file() and re.search(
        r"\]\(references/subagent\.rst(?:#[^)]*)?\)", body
    ):
        prelude.append(
            "Delegation is optional. Read references/subagent.rst only when delegation is useful "
            "or requested. It does not install a named agent or grant permissions."
        )
    if prelude:
        body = (
            "\n## Codex execution\n\n" + "\n\n".join(prelude) + "\n\n" + body.lstrip()
        )
    (dest / "SKILL.md").write_text(
        "---\n"
        + yaml.safe_dump(data, sort_keys=False, allow_unicode=True).rstrip()
        + "\n---\n"
        + body
    )


def mcp_config(path):
    data = json.loads(path.read_text())
    servers = data.get("mcpServers")
    if not isinstance(servers, dict) or not servers:
        raise ValueError(f"{path}: mcpServers must be a non-empty object")
    for name, server in servers.items():
        if not re.fullmatch(r"[A-Za-z0-9_-]+", name) or not isinstance(server, dict):
            raise ValueError(f"{path}: invalid MCP server {name}")
        if "url" in server:
            if not isinstance(server["url"], str) or not server["url"].startswith(
                "https://"
            ):
                raise ValueError(f"{path}: remote MCP {name} requires HTTPS")
            if (
                server.get("type") not in ("http", "streamable-http")
                or "command" in server
            ):
                raise ValueError(f"{path}: invalid remote transport for {name}")
        else:
            if not isinstance(server.get("command"), str) or not server["command"]:
                raise ValueError(f"{path}: MCP {name} needs command or url")
            if not isinstance(server.get("args", []), list) or any(
                not isinstance(x, str) for x in server.get("args", [])
            ):
                raise ValueError(f"{path}: invalid MCP args for {name}")
            if server["command"] == "npx" and not any(
                re.search(r"@[0-9]+\.[0-9]+\.[0-9]+$", x)
                for x in server.get("args", [])
            ):
                raise ValueError(f"{path}: npx MCP packages must be version-pinned")
        if "env" in server and (
            not isinstance(server["env"], dict)
            or any(not isinstance(v, str) for v in server["env"].values())
        ):
            raise ValueError(f"{path}: MCP env must map strings to strings")
    return data


def hook_config(path, root=None):
    data = json.loads(path.read_text())
    events = data.get("hooks")
    if not isinstance(events, dict) or not events:
        raise ValueError(f"{path}: hooks must be a non-empty object")
    for event, groups in events.items():
        if event not in EVENTS or not isinstance(groups, list) or not groups:
            raise ValueError(f"{path}: unsupported or empty Codex event {event}")
        for group in groups:
            if (
                not isinstance(group, dict)
                or not isinstance(group.get("hooks"), list)
                or not group["hooks"]
            ):
                raise ValueError(f"{path}: invalid hook group")
            if "matcher" in group:
                re.compile(group["matcher"])
            for hook in group["hooks"]:
                if hook.get("type") != "command":
                    raise ValueError(
                        f"{path}: Codex packaging supports command hooks only"
                    )
                command = hook.get("command", "")
                match = re.fullmatch(
                    r'bash "\$\{PLUGIN_ROOT\}/(hooks/[a-z0-9-]+\.sh)"(?: ([a-z0-9-]+))?',
                    command,
                )
                if not match:
                    raise ValueError(
                        f"{path}: hook command must use quoted PLUGIN_ROOT and a bundled shell hook"
                    )
                if (
                    not isinstance(hook.get("timeout", 10), (int, float))
                    or hook.get("timeout", 10) <= 0
                ):
                    raise ValueError(f"{path}: invalid hook timeout")
                if root is not None and not contained(root, match[1]).is_file():
                    raise ValueError(f"{path}: missing hook script {match[1]}")
    return data


def bundles(repo):
    marketplace = repo / "registry/marketplace.yaml"
    if not marketplace.exists():
        configs = [
            _read_yaml(p).get("targets") or {}
            for p in list((repo / "registry/bundles").glob("*.yaml"))
            + list((repo / "registry/bundles").glob("*.yml"))
        ]
        if not any(
            isinstance(c.get("codex"), dict) and c["codex"].get("enabled")
            for c in configs
        ):
            return {}
    return _codex_enabled_bundles(repo, _read_yaml(marketplace)["name"])


def build_package(repo, plugin, bundle, dest, names):
    config = bundle["config"]
    dest.mkdir(parents=True, exist_ok=True)
    for member in bundle["skills"]:
        source, leaf = normalize_member(member)
        skill_copy(repo, source, leaf, dest / "skills" / leaf, config, names)
    for resource in config.get("resources", []):
        copy_source(
            contained(repo, resource["source"]),
            contained(dest, resource["destination"]),
        )
    for filename in sorted({"NOTICE", *(p.name for p in repo.glob("LICENSE*"))}):
        if (repo / filename).is_file():
            copy_source(
                (repo / "plugins" / plugin / filename)
                if (repo / "plugins" / plugin / filename).is_file()
                else repo / filename,
                dest / filename,
            )
    if bundle["components"].get("mcp"):
        data = mcp_config(contained(repo, config["mcpConfig"]))
        if set(data["mcpServers"]) != set(bundle.get("mcp", [])):
            raise ValueError(f"{plugin}: MCP config must match registry server names")
        (dest / ".mcp.json").write_text(json.dumps(data, indent=2) + "\n")
        portable = json.loads(json.dumps(data))
        portable["$schema"] = "https://agent-plugins.org/schemas/1.0.0/mcp.schema.json"
        for server in portable["mcpServers"].values():
            if server.get("type") == "http":
                server["type"] = "streamable-http"
            elif "command" in server:
                server.setdefault("type", "stdio")
        (dest / "mcp.json").write_text(json.dumps(portable, indent=2) + "\n")
    if bundle["components"].get("hooks"):
        src = contained(repo, config["hookConfig"])
        hook_config(src)
        copy_source(src.parent, dest / "hooks")
        # Shared implementations stay canonical; native adapters handle event differences.
        adapter = repo / "hooks/codex/adapter.sh"
        copy_source(adapter, dest / "hooks/adapter.sh")
        for name in config.get("notes", {}).get("sharedHooks", []):
            if not re.fullmatch(r"[a-z0-9-]+", name):
                raise ValueError(f"invalid shared hook name: {name}")
            copy_source(repo / "hooks" / f"{name}.sh", dest / "hooks" / f"{name}.sh")
        hook_config(dest / "hooks/hooks.json", dest)


def tree_files(root):
    return {
        p.relative_to(root): (p.read_bytes(), stat.S_IMODE(p.stat().st_mode) & 0o111)
        for p in root.rglob("*")
        if p.is_file()
    }


def differences(expected, actual):
    exp, act = tree_files(expected), tree_files(actual)
    errors = []
    for rel in sorted(set(exp) | set(act)):
        if rel not in exp:
            errors.append(f"{rel}: stale file")
        elif rel not in act:
            errors.append(f"{rel}: missing file")
        elif exp[rel] != act[rel]:
            errors.append(f"{rel}: content or executable mode differs")
    for p in actual.rglob("*"):
        if p.is_symlink():
            errors.append(f"{p.relative_to(actual)}: symlink forbidden")
        if p.is_dir() and p.name == "agents":
            errors.append(f"{p.relative_to(actual)}: retired agents directory")
    return errors


def sync(repo, check=False, selected=()):
    enabled = bundles(repo)
    generated = generate(repo) if enabled else {}
    names = {
        f"{p}:{normalize_member(m)[1]}" for p, b in enabled.items() for m in b["skills"]
    }
    errors = []
    with tempfile.TemporaryDirectory() as tmp:
        temp = Path(tmp)
        for plugin, bundle in enabled.items():
            if selected and bundle["bundle"] not in selected:
                continue
            expected = temp / ROOT / plugin
            build_package(repo, plugin, bundle, expected, names)
            for path, content in _targets(temp, generated):
                if path.is_relative_to(expected):
                    path.parent.mkdir(parents=True, exist_ok=True)
                    path.write_text(content)
            dest = repo / ROOT / plugin
            if check:
                errors.extend(
                    f"{ROOT}/{plugin}/{e}" for e in differences(expected, dest)
                )
            else:
                if dest.is_symlink():
                    dest.unlink()
                elif dest.exists():
                    shutil.rmtree(dest)
                shutil.copytree(expected, dest)
        if not selected and (repo / ROOT).is_dir():
            for child in (repo / ROOT).iterdir():
                if child.name not in enabled:
                    if check:
                        errors.append(f"{ROOT}/{child.name}: stale package")
                    elif child.is_symlink() or child.is_file():
                        child.unlink()
                    else:
                        shutil.rmtree(child)
    return errors


def validate(repo):
    errors = []
    if (repo / "agents").exists():
        errors.append("canonical agents/ is retired; use skills/ references")
    for plugin, bundle in bundles(repo).items():
        root = repo / ROOT / plugin
        try:
            manifest = json.loads((root / ".codex-plugin/plugin.json").read_text())
            allowed = {
                "name",
                "version",
                "description",
                "author",
                "repository",
                "license",
                "keywords",
                "skills",
                "mcpServers",
                "interface",
            }
            if not isinstance(manifest, dict) or set(manifest) - allowed:
                raise ValueError("unknown native manifest field")
            if manifest.get("name") != plugin:
                raise ValueError("manifest identity does not match the registry")
            if not re.fullmatch(
                r"(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)",
                str(manifest.get("version", "")),
            ):
                raise ValueError("manifest version must be canonical X.Y.Z")
            if (
                not isinstance(manifest.get("description"), str)
                or not manifest["description"].strip()
            ):
                raise ValueError("manifest description must be a non-empty string")
            if bool(bundle["skills"]) != ("skills" in manifest) or (
                "skills" in manifest and manifest["skills"] != "./skills/"
            ):
                raise ValueError(
                    "manifest skills path does not match selected components"
                )
            if bool(bundle["components"].get("mcp")) != ("mcpServers" in manifest) or (
                "mcpServers" in manifest and manifest["mcpServers"] != "./.mcp.json"
            ):
                raise ValueError("manifest MCP path does not match selected components")
            if (root / "plugin.json").exists():
                raise ValueError(
                    "portable root manifest suppresses hooks in the pinned runtime; use the native manifest"
                )
            for p in root.rglob("*"):
                if p.is_symlink() or (p.is_dir() and p.name == "agents"):
                    raise ValueError(
                        f"{p}: symlinks and agents directories are forbidden"
                    )
            wanted = set()
            for member in bundle["skills"]:
                source, leaf = normalize_member(member)
                wanted.add(leaf)
                path = root / "skills" / leaf / "SKILL.md"
                fm, body = frontmatter(path.read_text())
                if (
                    fm.get("name") != leaf
                    or not re.fullmatch(r"[a-z0-9]+(?:-[a-z0-9]+)*", leaf)
                    or len(leaf) > 64
                ):
                    raise ValueError(
                        f"{path}: skill name must match valid leaf (at most 64 characters)"
                    )
                description = fm.get("description")
                if (
                    not isinstance(description, str)
                    or not description.strip()
                    or len(description) > 1024
                ):
                    raise ValueError(
                        f"{path}: description must be a nonempty string of at most 1024 characters"
                    )
                if set(fm) - SKILL_KEYS:
                    raise ValueError(f"{path}: unsupported frontmatter fields")
                if (
                    path.parent / "references/subagent.rst"
                ).exists() and "references/subagent.rst" not in body:
                    raise ValueError(f"{path}: delegation outline must remain linked")
                # Markdown relative links: scripts/templates may contain example links,
                # but SKILL.md links are part of the installed entrypoint contract.
                prose = re.sub(r"(?ms)^(```|~~~).*?^\1[^\n]*$", "", body)
                prose = re.sub(r"`[^`\n]+`", "", prose)
                for link in re.findall(r"\]\(([^\s)]+)\)", prose):
                    if "://" in link or link.startswith(("#", "mailto:")):
                        continue
                    link = link.split("#")[0]
                    if "<" in link or "$" in link:
                        continue
                    target = contained(
                        root, str((path.parent / link).relative_to(root))
                    )
                    if not target.exists():
                        raise ValueError(f"{path}: missing relative reference {link}")
            actual = (
                {p.name for p in (root / "skills").iterdir() if p.is_dir()}
                if (root / "skills").exists()
                else set()
            )
            if actual != wanted:
                raise ValueError(f"{root}: published skills differ from registry")
            if bundle["components"].get("mcp"):
                mcp_config(root / ".mcp.json")
                mcp_config(root / "mcp.json")
            elif (root / ".mcp.json").exists() or (root / "mcp.json").exists():
                raise ValueError(f"{root}: disabled MCP component is present")
            if bundle["components"].get("hooks"):
                hook_config(root / "hooks/hooks.json", root)
            elif (root / "hooks").exists():
                raise ValueError(f"{root}: disabled hooks component is present")
            for key in ("composerIcon", "logo", "logoDark", "screenshots"):
                values = manifest["interface"].get(key, [])
                for value in [values] if isinstance(values, str) else values:
                    if not contained(root, value).is_file():
                        raise ValueError(f"{root}: missing interface asset {value}")
        except (OSError, ValueError, KeyError, yaml.YAMLError) as exc:
            errors.append(f"{plugin}: {exc}")
    return errors


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("repo", nargs="?", default=".")
    parser.add_argument("--check", action="store_true")
    parser.add_argument("--validate", action="store_true")
    parser.add_argument("--bundles", nargs="*", default=[])
    args = parser.parse_args()
    repo = Path(args.repo).resolve()
    try:
        errors = (
            validate(repo) if args.validate else sync(repo, args.check, args.bundles)
        )
    except (ValueError, OSError, yaml.YAMLError) as exc:
        errors = [str(exc)]
    for error in errors:
        print(f"::error::{error}")
    return bool(errors)


if __name__ == "__main__":
    raise SystemExit(main())
