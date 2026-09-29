"""Behaviour tests for skills/cc-agent-teams/scripts/check-config.sh (#305).

The script checks, enables, and disables CLAUDE_CODE_EXPERIMENTAL_AGENT_TEAMS.
Every run uses a temporary HOME and project directory; the real ~/.claude is
never read or written. Settings precedence follows
https://code.claude.com/docs/en/settings#settings-precedence (managed > project
local > shared project > user) and the agent-teams docs: a value in any
settings file beats a shell export, and "0" disables.

The Bash 3.2 class runs the script under docker.io/library/bash:3.2 (bash
3.2.57, BusyBox userland) with a static jq mounted in. It is skipped unless
podman, that image, and BASH32_STATIC_JQ (path to a static jq binary, e.g.
jq 1.7.1 jq-linux-amd64) are available.
"""

import json
import os
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

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


def podman_bash32():
    podman = shutil.which("podman")
    jq = os.environ.get("BASH32_STATIC_JQ")
    if not podman or not jq or not os.path.isfile(jq):
        return None
    probe = subprocess.run([podman, "image", "exists", "docker.io/library/bash:3.2"], capture_output=True)
    return (podman, jq) if probe.returncode == 0 else None


@unittest.skipUnless(podman_bash32(), "needs podman, docker.io/library/bash:3.2, and BASH32_STATIC_JQ")
class Bash32BusyBox(unittest.TestCase):
    """bash 3.2.57 (the macOS /bin/bash version) with BusyBox sed/grep and a static jq."""

    def test_enable_disable_check_under_bash32(self):
        podman, jq = podman_bash32()
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
                "bash /w/check-config.sh | grep -q 'Agent teams are ENABLED'; "
                "bash /w/check-config.sh --disable >/dev/null; "
                "jq -e '.env.%s == \"0\" and .model == \"m\"' /w/home/.claude/settings.json >/dev/null; "
                "bash /w/check-config.sh | grep -q 'Agent teams are NOT ENABLED'; "
                "bash --version | head -1" % VAR)
            r = subprocess.run([podman, "run", "--rm", "--network=none", "-v", f"{tmp}:/w:Z",
                                "docker.io/library/bash:3.2", "bash", "-c", script],
                               capture_output=True, text=True, timeout=180)
            self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
            self.assertIn("version 3.2", r.stdout)


if __name__ == "__main__":
    unittest.main()
