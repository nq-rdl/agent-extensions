#!/usr/bin/env python3
"""Produce reproducible submission archives and an honest directory-readiness report.

Packaging readiness is not approval to publish. Publisher verification, legal URLs,
MCP domain ownership and authenticated behavioral evidence remain external gates.
"""

from __future__ import annotations
import argparse
import hashlib
import json
import re
import stat
import tempfile
import zipfile
from ipaddress import ip_address
from pathlib import Path
from urllib.parse import urlsplit
import yaml

try:
    from .codex_package import ROOT, bundles, validate, sync, frontmatter
except ImportError:
    from codex_package import ROOT, bundles, validate, sync, frontmatter


def absolute_https_url(value):
    if not isinstance(value, str) or any(c.isspace() or ord(c) < 32 or ord(c) == 127 for c in value):
        return False
    try:
        url = urlsplit(value)
        host = url.hostname or ""
        if ":" in host or re.fullmatch(r"[0-9.]+", host):
            ip_address(host)
        elif not all(
            re.fullmatch(r"[A-Za-z0-9](?:[A-Za-z0-9-]{0,61}[A-Za-z0-9])?", label)
            for label in host.encode("idna").decode("ascii").rstrip(".").split(".")
        ):
            return False
        # Accessing port also validates its syntax and range.
        return (
            url.scheme == "https" and bool(url.hostname)
            and url.username is None and url.password is None
            and (url.port is None or 0 < url.port <= 65535)
            and "\\" not in value
        )
    except (ValueError, UnicodeError):
        return False


def report(repo):
    enabled = bundles(repo)
    publisher_path = repo / "registry/codex-directory.yaml"
    publisher = (
        yaml.safe_load(publisher_path.read_text()) if publisher_path.exists() else {}
    )
    publisher = publisher or {}
    results = []
    for name, bundle in enabled.items():
        root = repo / ROOT / name
        manifest = json.loads((root / ".codex-plugin/plugin.json").read_text())
        interface = manifest["interface"]
        blockers = []
        for key in ("logo", "privacyPolicyURL", "termsOfServiceURL"):
            if not interface.get(key):
                blockers.append(f"Publisher must supply {key}")
            elif key != "logo" and not absolute_https_url(interface[key]):
                blockers.append(f"Publisher must supply a valid absolute HTTPS {key}")
        if not publisher.get("supportURL"):
            blockers.append("Publisher must supply supportURL")
        elif not absolute_https_url(publisher["supportURL"]):
            blockers.append("Publisher must supply a valid absolute HTTPS supportURL")
        if publisher.get("identityVerified") is not True:
            blockers.append(
                "Publisher identity and organization submission access are not recorded as verified"
            )
        explicit = []
        for path in sorted((root / "skills").glob("*/SKILL.md")):
            fm, _ = frontmatter(path.read_text())
            if fm.get("disable-model-invocation"):
                explicit.append(path.parent.name)
        if explicit:
            blockers.append(
                "Explicit-only invocation policy needs a directory-compatible decision; preserved for: "
                + ", ".join(explicit)
            )
        transport = "skills-only"
        if bundle["components"].get("mcp"):
            servers = json.loads((root / ".mcp.json").read_text())["mcpServers"]
            if any("command" in cfg for cfg in servers.values()):
                transport = "local-mcp"
                blockers.append(
                    "Local MCP requires an approved local-runtime submission path or a publisher-owned public HTTPS deployment"
                )
            else:
                transport = "remote-mcp"
                blockers.append(
                    "Remote MCP submission requires server-owner authorization, domain verification and authenticated connection evidence"
                )
        evidence = (publisher.get("behavioralEvidence") or {}).get(name)
        if evidence is not True:
            blockers.append(
                "Record authenticated execution evidence for five positive and three negative task cases"
            )
        regions = publisher.get("availabilityRegions")
        if not isinstance(regions, list) or not regions or any(
            not isinstance(region, str) or not region.strip() for region in regions
        ):
            blockers.append("Publisher must select supported availability regions")
        results.append(
            {
                "plugin": name,
                "version": manifest["version"],
                "route": transport,
                "package": str(ROOT / name),
                "skills": len(bundle["skills"]),
                "hooks": bool(bundle["components"].get("hooks")),
                "packageReady": True,
                "submissionReady": not blockers,
                "blockers": blockers,
            }
        )
    return {"publisher": publisher, "plugins": results}


def markdown(data):
    lines = [
        "# Codex directory readiness",
        "",
        "<!-- GENERATED by scripts/codex_directory.py --write-report. -->",
        "",
        "Every bundle has a strict, self-contained Codex package. Public submission is a separate gate.",
        "This report records missing evidence; it does not attest to publisher identity, legal review, or model task quality.",
        "",
        "| Plugin | Skills | Submission route | Submission ready |",
        "|---|---:|---|:---:|",
    ]
    for entry in data["plugins"]:
        lines.append(
            f"| {entry['plugin']} | {entry['skills']} | {entry['route']} | {'Yes' if entry['submissionReady'] else 'No'} |"
        )
    for entry in data["plugins"]:
        lines += ["", "## " + entry["plugin"], ""] + [
            "- " + x for x in entry["blockers"]
        ]
    lines += [
        "",
        "## Build archives",
        "",
        "```bash",
        "pixi run python3 scripts/codex_directory.py . --archives dist/codex/archives",
        "```",
        "",
        "Archives include full package contents and executable modes. `SHA256SUMS` identifies each archive.",
        "Use `--require-ready` to fail a submission gate when any blocker remains.",
        "",
        "Requirements: [OpenAI submission guide](https://developers.openai.com/plugins/deploy/submission),",
        "[Claude migration guide](https://developers.openai.com/plugins/guides/submit-claude-plugin).",
        "",
    ]
    return "\n".join(lines)


def archive(root, destination):
    with zipfile.ZipFile(
        destination, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=9
    ) as out:
        for path in sorted(root.rglob("*")):
            if path.is_symlink():
                raise ValueError(f"refusing archive symlink: {path}")
            if not path.is_file():
                continue
            info = zipfile.ZipInfo(
                path.relative_to(root).as_posix(), date_time=(1980, 1, 1, 0, 0, 0)
            )
            info.create_system = 3
            info.external_attr = (
                stat.S_IFREG | (0o755 if path.stat().st_mode & 0o111 else 0o644)
            ) << 16
            info.compress_type = zipfile.ZIP_DEFLATED
            out.writestr(info, path.read_bytes(), compresslevel=9)
    return hashlib.sha256(destination.read_bytes()).hexdigest()


def write_archives(repo, destination, data):
    destination.mkdir(parents=True, exist_ok=True)
    previous = set()
    checksum_path = destination / "SHA256SUMS"
    if checksum_path.exists():
        for line in checksum_path.read_text().splitlines():
            match = re.fullmatch(r"[0-9a-f]{64}  ([a-z0-9][a-z0-9.-]*\.zip)", line)
            if not match:
                raise ValueError(f"invalid generated archive checksum entry: {line!r}")
            previous.add(match[1])
    # Finish the entire build before replacing the previous submission set.
    # Only files tracked by our prior checksum manifest may be removed.
    with tempfile.TemporaryDirectory(prefix=".codex-archives-", dir=destination) as tmp:
        staging = Path(tmp)
        sums = []
        current = set()
        for entry in data["plugins"]:
            dest = staging / f"{entry['plugin']}-{entry['version']}.zip"
            sums.append(f"{archive(repo / entry['package'], dest)}  {dest.name}")
            current.add(dest.name)
        (staging / "SHA256SUMS").write_text("\n".join(sums) + ("\n" if sums else ""))
        (staging / "readiness.json").write_text(json.dumps(data, indent=2) + "\n")
        for name in sorted(current):
            (staging / name).replace(destination / name)
        for name in previous - current:
            (destination / name).unlink(missing_ok=True)
        for name in ("SHA256SUMS", "readiness.json"):
            (staging / name).replace(destination / name)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("repo", nargs="?", default=".")
    parser.add_argument("--archives", type=Path)
    parser.add_argument("--write-report", action="store_true")
    parser.add_argument("--check", action="store_true")
    parser.add_argument("--require-ready", action="store_true")
    args = parser.parse_args()
    repo = Path(args.repo).resolve()
    errors = validate(repo) + sync(repo, check=True)
    if errors:
        for error in errors:
            print("::error::" + error)
        return 1
    data = report(repo)
    text = markdown(data)
    path = repo / "docs/codex-directory.md"
    if args.write_report:
        path.write_text(text)
    if args.check and (not path.exists() or path.read_text() != text):
        print(
            "::error::docs/codex-directory.md is stale; run codex_directory.py --write-report"
        )
        return 1
    if args.archives:
        write_archives(repo, args.archives, data)
    if not (args.write_report or args.check or args.archives):
        print(json.dumps(data, indent=2))
    return int(
        args.require_ready and any(not p["submissionReady"] for p in data["plugins"])
    )


if __name__ == "__main__":
    raise SystemExit(main())
