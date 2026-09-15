#!/usr/bin/env python3
"""Inspect native Codex hook/MCP registration without making model requests.

Uses an isolated CODEX_HOME and real installed plugin caches. --live-mcp also
initializes the pinned stdio server and probes the remote authentication boundary.
It does not use personal credentials or alter the current session's plugins.
"""

import argparse
import json
import os
from pathlib import Path
import queue
import subprocess
import tempfile
import threading
import time
import urllib.error
import urllib.request


class RPC:
    def __init__(self, command, env=None, cwd=None):
        self.proc = subprocess.Popen(
            command,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            text=True,
            env=env,
            cwd=cwd,
        )
        self.messages = queue.Queue()
        self.number = 0

        def read():
            for line in self.proc.stdout:
                try:
                    self.messages.put(json.loads(line))
                except json.JSONDecodeError:
                    pass

        self.reader = threading.Thread(target=read, daemon=True)
        self.reader.start()

    def send(self, method, params=None, notification=False, timeout=45):
        self.number += 1
        payload = {"jsonrpc": "2.0", "method": method, "params": params or {}}
        if not notification:
            payload["id"] = self.number
        self.proc.stdin.write(json.dumps(payload) + "\n")
        self.proc.stdin.flush()
        if notification:
            return None
        deadline = time.monotonic() + timeout
        while True:
            result = self.messages.get(timeout=max(0, deadline - time.monotonic()))
            if result.get("id") == self.number:
                if "error" in result:
                    raise RuntimeError(f"{method}: {result['error']}")
                return result["result"]

    def close(self):
        self.proc.terminate()
        try:
            self.proc.wait(timeout=5)
        except subprocess.TimeoutExpired:
            self.proc.kill()
            self.proc.wait(timeout=5)
        self.proc.stdin.close()
        self.proc.stdout.close()


def check(repo, live=False):
    cli = os.environ.get("CODEX_BIN", "codex")
    entries = json.loads((repo / ".agents/plugins/marketplace.json").read_text())[
        "plugins"
    ]
    expected_hooks = 0
    cache = Path(os.environ.get("XDG_CACHE_HOME", str(Path.home() / ".cache")))
    cache.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="rdl-native-codex-", dir=cache) as tmp:
        env = {**os.environ, "CODEX_HOME": tmp}
        # Offline checks never inherit API credentials.
        for key in (
            "OPENAI_API_KEY",
            "CODEX_API_KEY",
            "CODEX_CI",
            "CODEX_SESSION_ID",
            "CODEX_THREAD_ID",
        ):
            env.pop(key, None)
        workspace = Path(tmp) / "workspace"
        workspace.mkdir()
        subprocess.run(
            [cli, "plugin", "marketplace", "add", str(repo), "--json"],
            env=env,
            check=True,
            stdout=subprocess.DEVNULL,
        )
        for entry in entries:
            root = repo / entry["source"]["path"]
            hook = root / "hooks/hooks.json"
            if hook.exists():
                expected_hooks += sum(
                    len(g["hooks"])
                    for groups in json.loads(hook.read_text())["hooks"].values()
                    for g in groups
                )
            subprocess.run(
                [
                    cli,
                    "plugin",
                    "add",
                    entry["name"] + "@rdl-agent-extensions",
                    "--json",
                ],
                env=env,
                check=True,
                stdout=subprocess.DEVNULL,
            )
        with (Path(tmp) / "config.toml").open("a") as config:
            config.write("\n[features]\nhooks = true\nplugins = true\n")
        rpc = RPC([cli, "app-server"], env=env, cwd=workspace)
        try:
            rpc.send(
                "initialize",
                {
                    "clientInfo": {
                        "name": "rdl-package-validation",
                        "version": "1.0.0",
                    },
                    "capabilities": {"experimentalApi": True},
                },
            )
            rpc.send("initialized", notification=True)
            result = rpc.send("hooks/list", {"cwds": [str(workspace)]})
            hooks = [hook for entry in result["data"] for hook in entry["hooks"]]
            errors = [error for entry in result["data"] for error in entry["errors"]]
            if errors:
                raise RuntimeError(f"Codex rejected hook configuration: {errors}")
            if len(hooks) != expected_hooks:
                raise RuntimeError(
                    f"expected {expected_hooks} hooks, Codex loaded {len(hooks)}; response={result}"
                )
            print(
                f"Codex app-server loaded {len(hooks)} native command hooks without schema errors; hook trust was not bypassed."
            )
            if live:
                status = rpc.send("mcpServerStatus/list", {"limit": 100})
                # Print only server identity/status, never tools, inputs or credentials.
                names = {x["name"] for x in status["data"]}
                if not {"lucid", "playwright"} <= names:
                    raise RuntimeError(
                        "Codex did not register both packaged MCP servers"
                    )
                print("Codex MCP inventory: " + ", ".join(sorted(names)))
        finally:
            rpc.close()
    if live:
        root = repo / "dist/codex/plugins"
        server = json.loads((root / "playwright/.mcp.json").read_text())["mcpServers"][
            "playwright"
        ]
        rpc = RPC([server["command"], *server.get("args", [])])
        try:
            rpc.send(
                "initialize",
                {
                    "protocolVersion": "2024-11-05",
                    "capabilities": {},
                    "clientInfo": {"name": "rdl-package-smoke", "version": "1.0.0"},
                },
                timeout=60,
            )
            rpc.send("notifications/initialized", notification=True)
            result = rpc.send("tools/list")
            if not result.get("tools"):
                raise RuntimeError("Playwright returned no tools")
            print(
                f"Pinned Playwright MCP initialized and exposed {len(result['tools'])} tools."
            )
        finally:
            rpc.close()
        url = json.loads((root / "lucid/.mcp.json").read_text())["mcpServers"]["lucid"][
            "url"
        ]
        request = urllib.request.Request(
            url,
            data=json.dumps(
                {
                    "jsonrpc": "2.0",
                    "id": 1,
                    "method": "initialize",
                    "params": {
                        "protocolVersion": "2024-11-05",
                        "capabilities": {},
                        "clientInfo": {"name": "rdl-package-smoke", "version": "1.0.0"},
                    },
                }
            ).encode(),
            headers={
                "Content-Type": "application/json",
                "Accept": "application/json, text/event-stream",
            },
        )
        try:
            with urllib.request.urlopen(request, timeout=30) as response:
                print(
                    f"Lucid endpoint responded HTTP {response.status}; authenticated tool execution is a separate acceptance test."
                )
        except urllib.error.HTTPError as exc:
            if exc.code != 401:
                raise
            print(
                "Lucid endpoint returned HTTP 401 as expected without credentials; authenticated connection remains unverified."
            )


def upgrade_check():
    """Prove a changed package version replaces discovery and cached content."""
    cli = os.environ.get("CODEX_BIN", "codex")
    cache = Path(os.environ.get("XDG_CACHE_HOME", str(Path.home() / ".cache")))
    cache.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="rdl-codex-upgrade-", dir=cache) as tmp:
        base = Path(tmp)
        home = base / "home"
        home.mkdir()
        source = base / "source"
        package = source / "plugins/update-probe"
        (source / ".agents/plugins").mkdir(parents=True)
        (package / ".codex-plugin").mkdir(parents=True)
        (package / "skills/verify").mkdir(parents=True)
        (source / ".agents/plugins/marketplace.json").write_text(
            json.dumps(
                {
                    "name": "rdl-upgrade-test",
                    "plugins": [
                        {
                            "name": "update-probe",
                            "source": {
                                "source": "local",
                                "path": "./plugins/update-probe",
                            },
                            "policy": {
                                "installation": "AVAILABLE",
                                "authentication": "ON_INSTALL",
                            },
                            "category": "Developer Tools",
                        }
                    ],
                }
            )
        )
        env = {**os.environ, "CODEX_HOME": str(home)}
        for key in (
            "OPENAI_API_KEY",
            "CODEX_API_KEY",
            "CODEX_CI",
            "CODEX_SESSION_ID",
            "CODEX_THREAD_ID",
        ):
            env.pop(key, None)

        def run(*args):
            return subprocess.check_output(
                [cli, *args], env=env, cwd=base, text=True, stderr=subprocess.DEVNULL
            )

        for version, description in [
            ("1.0.0", "first revision marker"),
            ("2.0.0", "second revision marker"),
        ]:
            (package / ".codex-plugin/plugin.json").write_text(
                json.dumps(
                    {
                        "name": "update-probe",
                        "version": version,
                        "description": "Upgrade test",
                    }
                )
            )
            (package / "skills/verify/SKILL.md").write_text(
                "---\nname: verify\ndescription: "
                + description
                + "\n---\nReport the installed revision.\n"
            )
            if version == "1.0.0":
                run("plugin", "marketplace", "add", str(source), "--json")
            run("plugin", "add", "update-probe@rdl-upgrade-test", "--json")
            prompt = run("debug", "prompt-input", "List skills")
            if description not in prompt:
                raise RuntimeError(f"upgraded skill was not discovered: {version}")
        if "first revision marker" in prompt:
            raise RuntimeError("old skill still discovered after upgrade")
        run("plugin", "remove", "update-probe@rdl-upgrade-test", "--json")
        print(
            "Codex package upgrade verified: version 1.0.0 -> 2.0.0 updates fresh-session discovery."
        )


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("repo", nargs="?", default=".")
    parser.add_argument("--live-mcp", action="store_true")
    args = parser.parse_args()
    check(Path(args.repo).resolve(), args.live_mcp)
    upgrade_check()


if __name__ == "__main__":
    main()
