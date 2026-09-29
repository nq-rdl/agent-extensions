"""Behaviour tests for skills/cc-agent-teams/scripts/check-config.sh (#305).

The script checks, enables, and disables CLAUDE_CODE_EXPERIMENTAL_AGENT_TEAMS.
Every run uses a temporary HOME and project directory; the real ~/.claude is
never read or written. Settings precedence follows
https://code.claude.com/docs/en/settings#settings-precedence (managed > project
local > shared project > user) and the agent-teams docs: a value in any
settings file beats a shell export, and "0" disables.

The Bash 3.2 class uses the pinned Docker/Podman BusyBox fixture and verified
static jq. Discovery may skip it locally; the dedicated CI runner rejects skips.
This Linux stand-in does not prove native macOS/BSD portability.
"""

import json
import os
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

from bash32_fixture import container_runtime, run_container, static_jq

REPO = Path(__file__).resolve().parent.parent
SCRIPT = REPO / "skills" / "cc-agent-teams" / "scripts" / "check-config.sh"
VAR = "CLAUDE_CODE_EXPERIMENTAL_AGENT_TEAMS"


class Fixture:
    def __init__(self):
        self.tmp = tempfile.TemporaryDirectory()
        root = Path(self.tmp.name)
        self.home = root / "home"
        self.project = root / "project"
        self.managed = root / "managed-settings.json"
        (self.home / ".claude").mkdir(parents=True)
        (self.project / ".claude").mkdir(parents=True)
        self.bin = root / "bin"
        self.bin.mkdir()
        # Only jq and a POSIX userland: no claude or tmux on PATH.
        os.symlink(shutil.which("jq"), self.bin / "jq")

    def path(self, scope):
        return {
            "user": self.home / ".claude" / "settings.json",
            "user-local": self.home / ".claude" / "settings.local.json",
            "project": self.project / ".claude" / "settings.json",
            "local": self.project / ".claude" / "settings.local.json",
            "managed": self.managed,
        }[scope]

    def write(self, scope, data):
        p = self.path(scope)
        p.write_text(data if isinstance(data, str) else json.dumps(data, indent=2))
        return p

    def run(self, *args, shell_env=None):
        env = {"HOME": str(self.home), "PATH": f"{self.bin}:/usr/bin:/bin",
               "CHECK_CONFIG_MANAGED_FILE": str(self.managed)}
        if shell_env is not None:
            env[VAR] = shell_env
        return subprocess.run(["bash", str(SCRIPT), *args], cwd=self.project, env=env,
                              capture_output=True, text=True, timeout=60)

    def close(self):
        self.tmp.cleanup()


class Base(unittest.TestCase):
    def setUp(self):
        self.fx = Fixture()
        self.addCleanup(self.fx.close)

    def assertEnabled(self, r, enabled):
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertIn("Agent teams are NOT ENABLED" if not enabled else "Agent teams are ENABLED", r.stdout)


class ScopesAndPrecedence(Base):
    def test_user_local_file_is_not_a_settings_scope(self):
        self.fx.write("user-local", {"env": {VAR: "1"}})
        r = self.fx.run()
        self.assertEnabled(r, False)
        self.assertNotIn("User local", r.stdout)

    def test_project_local_zero_overrides_user_one(self):
        self.fx.write("user", {"env": {VAR: "1"}})
        self.fx.write("local", {"env": {VAR: "0"}})
        self.assertEnabled(self.fx.run(), False)

    def test_project_one_overrides_user_zero(self):
        self.fx.write("user", {"env": {VAR: "0"}})
        self.fx.write("project", {"env": {VAR: "1"}})
        self.assertEnabled(self.fx.run(), True)

    def test_user_zero_overrides_shell_export(self):
        self.fx.write("user", {"env": {VAR: "0"}})
        self.assertEnabled(self.fx.run(shell_env="1"), False)

    def test_shell_export_applies_without_settings(self):
        self.assertEnabled(self.fx.run(shell_env="1"), True)

    def test_managed_settings_win(self):
        self.fx.write("local", {"env": {VAR: "1"}})
        self.fx.write("managed", {"env": {VAR: "0"}})
        self.assertEnabled(self.fx.run(), False)

    def test_nothing_configured(self):
        self.assertEnabled(self.fx.run(), False)

    def test_true_is_reported_as_not_one(self):
        self.fx.write("user", {"env": {VAR: "true"}})
        r = self.fx.run()
        self.assertEnabled(r, False)
        self.assertIn('should be "1"', r.stdout)


class EnableDisable(Base):
    def read(self, scope):
        return json.loads(self.fx.path(scope).read_text())

    def test_disable_keeps_valid_json_and_other_keys(self):
        self.fx.write("user", '{\n  "env": {\n    "OTHER": "x",\n    "%s": "1"\n  },\n  "model": "m"\n}\n' % VAR)
        r = self.fx.run("--disable")
        self.assertEqual(r.returncode, 0, r.stderr)
        data = self.read("user")
        self.assertEqual(data["env"], {"OTHER": "x", VAR: "0"})
        self.assertEqual(data["model"], "m")
        self.assertEnabled(self.fx.run(shell_env="1"), False)

    def test_enable_into_empty_env_block(self):
        self.fx.write("user", '{"env": {}, "model": "m"}')
        r = self.fx.run("--enable")
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertEqual(self.read("user"), {"env": {VAR: "1"}, "model": "m"})

    def test_enable_minified_file_without_env(self):
        self.fx.write("user", '{"model":"m"}')
        self.assertEqual(self.fx.run("--enable").returncode, 0)
        self.assertEqual(self.read("user"), {"model": "m", "env": {VAR: "1"}})

    def test_enable_creates_project_file(self):
        self.fx.path("project").unlink(missing_ok=True)
        r = self.fx.run("--enable", "--project")
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertEqual(self.read("project"), {"env": {VAR: "1"}})
        self.assertFalse(self.fx.path("user").exists())

    def test_enable_replaces_existing_value(self):
        self.fx.write("user", {"env": {VAR: "true", "OTHER": "x"}})
        self.fx.run("--enable")
        self.assertEqual(self.read("user")["env"], {VAR: "1", "OTHER": "x"})

    def test_invalid_json_is_left_untouched(self):
        original = '{"env": {"A": "x",}}'
        p = self.fx.write("user", original)
        for action in ("--enable", "--disable"):
            with self.subTest(action=action):
                r = self.fx.run(action)
                self.assertNotEqual(r.returncode, 0)
                self.assertEqual(p.read_text(), original)

    def test_disable_without_file_is_a_no_op(self):
        r = self.fx.run("--disable")
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertFalse(self.fx.path("user").exists())


class Portability(unittest.TestCase):
    def test_no_in_place_sed(self):
        text = SCRIPT.read_text()
        self.assertNotRegex(text, r"\bsed\s+(-[a-zA-Z]*\s+)*-i")


@unittest.skipUnless(container_runtime() and static_jq(), "needs pinned Bash 3.2 image and verified BASH32_STATIC_JQ")
class Bash32BusyBox(unittest.TestCase):
    """Bash 3.2.57 with BusyBox sed/grep and a verified static jq."""

    def test_enable_disable_check_under_bash32(self):
        jq = static_jq()
        with tempfile.TemporaryDirectory() as tmp:
            t = Path(tmp)
            shutil.copy2(SCRIPT, t / "check-config.sh")
            shutil.copy2(jq, t / "jq")
            (t / "home" / ".claude").mkdir(parents=True)
            (t / "proj" / ".claude").mkdir(parents=True)
            (t / "home" / ".claude" / "settings.json").write_text('{"env": {}, "model": "m"}')
            script = (
                "set -e; export HOME=/w/home PATH=/w:$PATH CHECK_CONFIG_MANAGED_FILE=/w/none; cd /w/proj; "
                "bash /w/check-config.sh --enable >/dev/null; "
                "bash /w/check-config.sh | grep 'Agent teams are ENABLED' >/dev/null; "
                "bash /w/check-config.sh --disable >/dev/null; "
                "jq -e '.env.%s == \"0\" and .model == \"m\"' /w/home/.claude/settings.json >/dev/null; "
                "bash /w/check-config.sh | grep 'Agent teams are NOT ENABLED' >/dev/null; "
                "bash --version | sed -n '1p'" % VAR)
            r = run_container(tmp, "/w", script)
            self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
            self.assertIn("version 3.2", r.stdout)


if __name__ == "__main__":
    unittest.main()
