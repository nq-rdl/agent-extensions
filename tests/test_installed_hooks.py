"""Installed-copy runtime tests for the Claude hook plugins (#311).

Each test copies ONLY ``plugins/<plugin>/`` into a temporary cache path that
contains spaces, runs from an unrelated working directory with a throwaway
HOME, and executes the command strings from the installed ``hooks/hooks.json``
the way Claude Code's shell form does (see
https://code.claude.com/docs/en/hooks, "shell form" and "Reference scripts by
path"): once left for the shell to expand from the exported
``CLAUDE_PLUGIN_ROOT``, and once with the placeholder substituted textually.
Nothing reads this checkout at hook run time; no test makes a network call or
touches real credentials (RH_*/BW_* variables are stripped, credential sources
are pinned to env/file). The Codex wrappers have the same coverage in
``tests/codex/hook-wrappers.test.mjs``.

Advisory hooks are also exercised for fire / no-fire / malformed input and the
event-specific output contract: UserPromptSubmit and PostToolUse context is
``hookSpecificOutput.additionalContext`` with a matching ``hookEventName``;
a jq-less fallback may print plain text, which only UserPromptSubmit and
SessionStart add to context. No-fire means exit 0 with empty stdout.
"""

from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

import yaml

REPO = Path(__file__).resolve().parent.parent
HOOK_PLUGINS = ("claude-code", "opencode-dev", "redhat", "speckit-dev", "data-request", "tech-writing")


def base_env(home: Path, root: Path, **extra) -> dict:
    env = {k: v for k, v in os.environ.items()
           if not k.startswith(("RH_", "BW_", "CLAUDE_", "GIT_"))}
    env.update(HOME=str(home), XDG_CONFIG_HOME=str(home / ".config"),
               XDG_RUNTIME_DIR=str(home / "run"), TMPDIR=str(home),
               CLAUDE_PLUGIN_ROOT=str(root), RH_CRED_SOURCES="env,file")
    env.update(extra)
    return env


def tool_dir(home: Path, tools) -> Path:
    """A PATH directory holding only ``tools`` (symlinks to the host binaries)."""
    bindir = home / "restricted bin"
    bindir.mkdir()
    for tool in tools:
        found = shutil.which(tool)
        if found:
            (bindir / tool).symlink_to(found)
    return bindir


class Installed:
    def __init__(self, plugin: str):
        self._tmp = tempfile.TemporaryDirectory(prefix="hook install ")
        base = Path(self._tmp.name)
        self.root = base / "plugin cache" / plugin
        shutil.copytree(REPO / "plugins" / plugin, self.root, symlinks=False)
        self.cwd = base / "unrelated cwd"
        self.cwd.mkdir()
        self.home = base / "home dir"
        self.home.mkdir()

    def close(self):
        self._tmp.cleanup()

    def commands(self, event: str):
        config = json.loads((self.root / "hooks/hooks.json").read_text())
        return [h["command"] for g in config["hooks"].get(event, []) for h in g["hooks"]
                if h.get("type") == "command"]

    def run_command(self, command: str, payload, substitute=False, env=None):
        if substitute:
            command = command.replace("${CLAUDE_PLUGIN_ROOT}", str(self.root))
        stdin = payload if isinstance(payload, str) else json.dumps(payload)
        return subprocess.run(["/bin/sh", "-c", command], input=stdin, cwd=self.cwd,
                              env=env or base_env(self.home, self.root),
                              capture_output=True, text=True, timeout=60)

    def run_script(self, rel: str, payload, env=None):
        stdin = payload if isinstance(payload, str) else json.dumps(payload)
        return subprocess.run(["bash", str(self.root / rel)], input=stdin, cwd=self.cwd,
                              env=env or base_env(self.home, self.root),
                              capture_output=True, text=True, timeout=60)


def benign_event(event: str, cwd: Path) -> dict:
    return {"hook_event_name": event, "cwd": str(cwd), "session_id": "test",
            "prompt": "hello", "tool_name": "Bash", "tool_input": {"command": "true"}}


class InstalledCommandsRun(unittest.TestCase):
    def test_every_command_runs_from_a_spaced_install(self):
        for plugin in HOOK_PLUGINS:
            install = Installed(plugin)
            try:
                config = json.loads((install.root / "hooks/hooks.json").read_text())
                for event in config["hooks"]:
                    for command in install.commands(event):
                        for substitute in (False, True):
                            with self.subTest(plugin=plugin, event=event, substitute=substitute):
                                r = install.run_command(command, benign_event(event, install.cwd), substitute)
                                self.assertEqual(r.returncode, 0, r.stderr)
                                self.assertNotRegex(r.stderr, r"No such file|not found|Permission denied")
            finally:
                install.close()

    def test_unquoted_plugin_root_breaks_under_spaces(self):
        # Why the canonical configs quote the plugin root: the previous form fails here.
        install = Installed("redhat")
        try:
            r = install.run_command("${CLAUDE_PLUGIN_ROOT}/scripts/redhat-docs-preflight.sh", {}, False)
            self.assertNotEqual(r.returncode, 0)
        finally:
            install.close()


GATED = {"tool_name": "Bash", "tool_input": {
    "command": "curl -sS 'https://api.access.redhat.com/support/search/kcs?q=*&fq=id:7137578'"}}


class RedHatGuardFallback(unittest.TestCase):
    def setUp(self):
        self.install = Installed("redhat")
        self.guard = self.install.commands("PreToolUse")[0]
        self.preflight = self.install.root / "skills/fetch-docs/scripts/rh-preflight.sh"
        self.lib = self.install.root / "skills/fetch-docs/scripts/rh-lib.sh"

    def tearDown(self):
        self.install.close()

    def decision(self, env=None):
        r = self.install.run_command(self.guard, GATED, env=env)
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertEqual(r.stderr, "")
        return json.loads(r.stdout)["hookSpecificOutput"] if r.stdout.strip() else None

    def token_file(self):
        path = self.install.home / ".config/redhat/offline-token"
        path.parent.mkdir(parents=True)
        path.write_text("file-token-value\n")
        path.chmod(0o600)

    def test_companion_preflight_present_denies_without_credential(self):
        self.assertTrue(self.preflight.is_file())
        d = self.decision()
        self.assertEqual(d["permissionDecision"], "deny")
        self.assertIn("/redhat:setup", d["permissionDecisionReason"])

    def test_without_preflight_denies_when_no_credential(self):
        self.preflight.unlink()
        d = self.decision()
        self.assertEqual(d["permissionDecision"], "deny")
        self.assertIn("/redhat:setup", d["permissionDecisionReason"])

    def test_without_preflight_env_credential_passes(self):
        self.preflight.unlink()
        env = base_env(self.install.home, self.install.root, RH_OFFLINE_TOKEN="presence-only")
        self.assertIsNone(self.decision(env))

    def test_without_preflight_file_credential_passes(self):
        self.preflight.unlink()
        self.token_file()
        self.assertIsNone(self.decision())

    def test_missing_sourced_library_fails_closed(self):
        # rh-preflight.sh sources rh-lib.sh; a broken companion must not bypass the gate.
        self.lib.unlink()
        d = self.decision()
        self.assertEqual(d["permissionDecision"], "deny")

    def test_without_plugin_root_resolves_relative_to_the_installed_copy(self):
        self.token_file()
        env = base_env(self.install.home, self.install.root)
        del env["CLAUDE_PLUGIN_ROOT"]
        r = self.install.run_script("scripts/redhat-docs-guard.sh", GATED, env=env)
        self.assertEqual((r.returncode, r.stdout.strip()), (0, ""))

    def test_session_preflight_without_companion_is_a_silent_noop(self):
        self.preflight.unlink()
        command = self.install.commands("SessionStart")[0]
        r = self.install.run_command(command, {"hook_event_name": "SessionStart"})
        self.assertEqual((r.returncode, r.stdout, r.stderr), (0, "", ""))

    def test_fallback_token_path_matches_the_companion_library(self):
        default = "${RH_OFFLINE_TOKEN_FILE:-${XDG_CONFIG_HOME:-$HOME/.config}/redhat/offline-token}"
        self.assertIn(default, (REPO / "hooks/redhat-docs-guard.sh").read_text())
        self.assertIn(default, (REPO / "skills/redhat-docs-fetch/scripts/rh-lib.sh").read_text())

    def test_sso_ask_makes_no_fixed_token_lifetime_claim(self):
        r = self.install.run_command(self.guard, {"tool_name": "Bash", "tool_input": {
            "command": "curl -X POST https://sso.redhat.com/auth/realms/redhat-external/protocol/openid-connect/token"}})
        reason = json.loads(r.stdout)["hookSpecificOutput"]["permissionDecisionReason"]
        self.assertIn("rh-token.sh", reason)
        self.assertNotRegex(reason, r"\d+-minute")


def context(result, event):
    output = json.loads(result.stdout)
    self_check = output["hookSpecificOutput"]
    assert self_check["hookEventName"] == event, output
    return self_check["additionalContext"]


class PromptAdvisoryHooks(unittest.TestCase):
    """UserPromptSubmit advisories: opencode-doc-review and speckit-publish-target."""

    CASES = {
        "opencode-dev": ("Develop an OpenCode plugin with @opencode-ai/sdk", "<opencode-dev-guidance>",
                         ["Help me with OpenAI Codex", "open code review please", "hello"]),
        "speckit-dev": ("Publish my spec-kit extension to the catalog", "<speckit-publish-guidance>",
                        ["Scaffold a spec-kit extension", "publish the npm package", "hello"]),
    }

    def run_prompt(self, plugin, payload, env=None):
        install = Installed(plugin)
        try:
            command = install.commands("UserPromptSubmit")[0]
            return install.run_command(command, payload, env=env(install) if env else None)
        finally:
            install.close()

    def test_fires_with_user_prompt_submit_context(self):
        for plugin, (prompt, marker, _) in self.CASES.items():
            with self.subTest(plugin=plugin):
                r = self.run_prompt(plugin, {"hook_event_name": "UserPromptSubmit", "prompt": prompt})
                self.assertEqual(r.returncode, 0, r.stderr)
                self.assertIn(marker, context(r, "UserPromptSubmit"))
                self.assertNotIn("decision", json.loads(r.stdout))

    def test_unrelated_prompts_are_silent(self):
        for plugin, (_, _, quiet) in self.CASES.items():
            for prompt in quiet:
                with self.subTest(plugin=plugin, prompt=prompt):
                    r = self.run_prompt(plugin, {"hook_event_name": "UserPromptSubmit", "prompt": prompt})
                    self.assertEqual((r.returncode, r.stdout), (0, ""), r.stderr)

    def test_malformed_input_is_a_silent_noop(self):
        for plugin in self.CASES:
            for payload in ("", "not json", "null", "[]", "{}", '{"prompt": 7}'):
                with self.subTest(plugin=plugin, payload=payload):
                    r = self.run_prompt(plugin, payload)
                    self.assertEqual((r.returncode, r.stdout), (0, ""), r.stderr)

    def test_without_jq_the_fallbacks_still_gate(self):
        # Degraded hosts: python3 without jq, then neither (sed scrape only).
        base = ("bash", "sh", "cat", "grep", "sed", "tr", "head", "printf")
        for tools in (base + ("python3",), base):
            for plugin, (prompt, marker, quiet) in self.CASES.items():
                cases = [(prompt, True), (f'Say \\"hi\\" then:\\n{prompt}', True)]
                cases += [(q, False) for q in quiet]
                for text, fires in cases:
                    with self.subTest(python="python3" in tools, plugin=plugin, prompt=text):
                        payload = '{"session_id":"s","hook_event_name":"UserPromptSubmit","prompt":"%s"}' % text
                        r = self.run_prompt(plugin, payload, env=lambda i: base_env(
                            i.home, i.root, PATH=str(tool_dir(i.home, tools))))
                        self.assertEqual(r.returncode, 0, r.stderr)
                        self.assertEqual(marker in r.stdout, fires, r.stdout + r.stderr)
                for payload in ("not json", "[]", '{"prompt": 7}'):
                    with self.subTest(python="python3" in tools, plugin=plugin, payload=payload):
                        r = self.run_prompt(plugin, payload, env=lambda i: base_env(
                            i.home, i.root, PATH=str(tool_dir(i.home, tools))))
                        self.assertEqual((r.returncode, r.stdout), (0, ""), r.stderr)


class OpenCodeRoutes(unittest.TestCase):
    def test_route_list_matches_bundle_leaves(self):
        bundle = yaml.safe_load((REPO / "registry/bundles/opencode-dev.yaml").read_text())
        leaves = {m["leaf"] if isinstance(m, dict) else m for m in bundle["skills"]}
        text = (REPO / "hooks/opencode-doc-review.sh").read_text()
        routes = set(re.findall(r"/opencode-dev:([a-z0-9-]+)", text))
        self.assertEqual(routes, leaves)

    def test_no_copied_version_pin(self):
        text = (REPO / "hooks/opencode-doc-review.sh").read_text()
        self.assertNotRegex(text, r"v\d+\.\d+\.\d+|Go \d+\.\d+")
        self.assertNotIn("forced-eval-hook.sh", text, "stale source-path comment")


class SkillAuditNudge(unittest.TestCase):
    def setUp(self):
        self.install = Installed("claude-code")
        self.command = self.install.commands("PostToolUse")[0]

    def tearDown(self):
        self.install.close()

    def test_skill_entrypoint_edit_fires_post_tool_use_context(self):
        for path in ("/work/repo/skills/demo/SKILL.md", "skills/demo/SKILL.md"):
            with self.subTest(path=path):
                r = self.install.run_command(self.command, {
                    "hook_event_name": "PostToolUse", "tool_name": "Edit",
                    "tool_input": {"file_path": path}, "tool_response": {}})
                self.assertEqual(r.returncode, 0, r.stderr)
                self.assertIn("/claude-code:skill-audit", context(r, "PostToolUse"))

    def test_other_files_and_malformed_input_are_silent(self):
        payloads = ["", "not json", "{}", json.dumps({
            "hook_event_name": "PostToolUse", "tool_name": "Write",
            "tool_input": {"file_path": "/work/repo/skills/demo/references/x.md"}}), json.dumps({
            "hook_event_name": "PostToolUse", "tool_name": "Write",
            "tool_input": {"file_path": "/work/repo/SKILL.md"}})]
        for payload in payloads:
            with self.subTest(payload=payload):
                r = self.install.run_command(self.command, payload)
                self.assertEqual((r.returncode, r.stdout), (0, ""), r.stderr)

    def test_without_jq_is_silent(self):
        env = base_env(self.install.home, self.install.root,
                       PATH=str(tool_dir(self.install.home, ("bash", "sh", "cat"))))
        r = self.install.run_command(self.command, {"tool_input": {"file_path": "skills/a/SKILL.md"}}, env=env)
        self.assertEqual((r.returncode, r.stdout), (0, ""), r.stderr)


def podman_bash32():
    podman = shutil.which("podman")
    if not podman:
        return None
    probe = subprocess.run([podman, "image", "exists", "docker.io/library/bash:3.2"], capture_output=True)
    return podman if probe.returncode == 0 else None


@unittest.skipUnless(podman_bash32(), "needs podman and a local docker.io/library/bash:3.2 image")
class Bash32BusyBoxFallback(unittest.TestCase):
    """bash 3.2.57 (the macOS /bin/bash version) with BusyBox grep/sed, no jq/python3."""

    def run_in_container(self, plugin, hook, prompt):
        # Mount a throwaway copy of the installed script (never relabel the checkout).
        payload = '{"hook_event_name":"UserPromptSubmit","prompt":"%s"}' % prompt
        with tempfile.TemporaryDirectory() as tmp:
            shutil.copy2(REPO / "plugins" / plugin / "scripts" / f"{hook}.sh", tmp)
            return subprocess.run(
                [podman_bash32(), "run", "--rm", "-i", "--network=none",
                 "-v", f"{tmp}:/p:ro,Z", "docker.io/library/bash:3.2",
                 "bash", f"/p/{hook}.sh"],
                input=payload, capture_output=True, text=True, timeout=120)

    def test_prompt_fallbacks_gate_without_jq_or_python(self):
        for plugin, hook, prompt, marker in (
            ("opencode-dev", "opencode-doc-review", 'Build an \\"OpenCode\\" plugin', "<opencode-dev-guidance>"),
            ("speckit-dev", "speckit-publish-target", "Publish my spec-kit extension", "<speckit-publish-guidance>"),
        ):
            with self.subTest(hook=hook):
                fired = self.run_in_container(plugin, hook, prompt)
                self.assertEqual(fired.returncode, 0, fired.stderr)
                self.assertIn(marker, fired.stdout)
                quiet = self.run_in_container(plugin, hook, "hello there")
                self.assertEqual((quiet.returncode, quiet.stdout), (0, ""), quiet.stderr)


if __name__ == "__main__":
    unittest.main()
