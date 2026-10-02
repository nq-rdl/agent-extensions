"""Offline CLI contracts under host Bash and pinned Bash 3.2 + BusyBox + jq."""
import json
import os
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
CASES = ("parse", "waves", "render", "launch", "fast", "cap", "status", "lock", "setup")


def fixture(directory):
    target = Path(directory)
    shutil.copytree(ROOT / "tests/fixtures/pi-dispatch", target, dirs_exist_ok=True)
    for name in ("dispatch", "setup"):
        shutil.copytree(ROOT / f"skills/pi-{name}", target / name)
    for shim in (target / "bin").iterdir():
        shim.chmod(0o755)


class HostBash(unittest.TestCase):
    def check_case(self, case):
        with tempfile.TemporaryDirectory(prefix="pi-shim-") as tmp:
            fixture(tmp)
            # No real pi/wt/gh calls: all external CLIs are local shims.
            env = os.environ.copy()
            for key in ("PI_DISPATCH_CAP", "PI_DISPATCH_STATE_DIR", "PI_DELAY", "PI_EXIT",
                        "AUTH_FAIL", "GH_FAIL", "FILTER_FULL", "NO_PR", "CI_BUCKET", "CHECK_EXIT",
                        "PI_DISPATCH_SERVICE_TIER", "CODEX_HOME"):
                env.pop(key, None)
            r = subprocess.run(["bash", "scenario.sh", case], cwd=tmp, env=env,
                               capture_output=True, text=True, timeout=30)
            self.assertEqual(r.returncode, 0, r.stdout + r.stderr)


for case in CASES:
    setattr(HostBash, f"test_{case}", lambda self, case=case: self.check_case(case))


class Bash32(unittest.TestCase):
    def test_offline_contracts(self):
        from bash32_fixture import container_runtime, run_container, static_jq
        if not container_runtime() or not static_jq():
            self.skipTest("requires pinned Bash 3.2 container and verified static jq")
        for case in CASES:
            with self.subTest(case=case), tempfile.TemporaryDirectory(prefix="pi-bash32-") as tmp:
                fixture(tmp)
                jq = Path(tmp) / "bin/jq"
                shutil.copyfile(static_jq(), jq)
                jq.chmod(0o755)
                # Container-created state is private/root-owned. Return only the
                # disposable copy to our UID, even when an assertion fails.
                command = (f"cd /fixture; trap 'chown -R {os.getuid()}:{os.getgid()} /fixture' EXIT; "
                           f"bash scenario.sh {case}")
                r = run_container(tmp, "/fixture", command)
                self.assertEqual(r.returncode, 0, r.stdout + r.stderr)


class ServiceTierExtension(unittest.TestCase):
    def test_fake_provider_events_and_invalid_tiers(self):
        r = subprocess.run(["node", str(ROOT / "tests/fixtures/pi-dispatch/extension-test.mjs"),
                            str(ROOT / "skills/pi-dispatch/assets/service-tier.mjs")],
                           capture_output=True, text=True, timeout=15)
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertEqual(json.loads(r.stdout)["cases"], 26)
        self.assertEqual(r.stderr.count("only priority is allowed"), 6)
        self.assertNotIn("PRIVATE-PAYLOAD-MARKER", r.stdout + r.stderr)


class SafetyText(unittest.TestCase):
    def test_codex_suite_is_scoped_to_branch_changes(self):
        hooks = yaml.safe_load((ROOT / "lefthook.yml").read_text())
        job = next(j for j in hooks["pre-push"]["jobs"] if j["name"] == "codex-js-tests")
        self.assertEqual(job["files"], "git diff --name-only origin/main...HEAD")
        self.assertEqual(job["glob"], "{plugins/codex/**,tests/codex/**,hooks/codex-*.sh}")

    def test_authorisation_and_scope_contracts(self):
        dispatch = (ROOT / "skills/pi-dispatch/SKILL.md").read_text()
        setup = (ROOT / "skills/pi-setup/SKILL.md").read_text()
        template = " ".join((ROOT / "skills/pi-dispatch/references/worker-prompt.rst").read_text().split())
        for value in ("human-only", "umbrella", "blocked", "quick repository grep",
                      "Ask the user to confirm", "user authorisation", "memory-heavy",
                      "Create Unsafe Agents", "RPC", "rolling slots", "dependsOn",
                      "parallel-then-rebase", "stacked", "wait-for-merge",
                      "generated/derived outputs", "shared generators/configuration"):
            self.assertIn(value, " ".join(dispatch.split()))
        for value in ("Summary", "Changes", "Validation", "Decisions for review",
                      "Never merge", "AGENTS.md", "CONTRIBUTING.md", "isolated environment",
                      "credential cleanup", "Do not bypass git hooks",
                      "standard commit/push hooks and CI is expected",
                      "credentialed or billed calls", "do not enable it implicitly"):
            self.assertIn(value, template)
        helpers = " ".join((ROOT / "skills/pi-dispatch/references/helpers.rst").read_text().split())
        for value in ("worktree BRANCH [BASE]", "prBase", "SAME worktree",
                      "stable session ID", "Fast must be re-selected explicitly",
                      "git rebase --onto origin/main", "lease-protected push",
                      "stop on unexpected design conflicts"):
            self.assertIn(value, helpers)
        for value in ("never `--yes`", "without the user's approval", "--no-refresh",
                      "exact provider/id", "`!`", "config.json"):
            self.assertIn(value, setup)
        for text in (dispatch, setup):
            self.assertIn("pi 0.99.1", text)
            self.assertIn("wt 0.77.0", text)
            self.assertLess(len(text.split("---", 2)[2].splitlines()), 500)

    def test_fast_consent_cost_and_provenance(self):
        dispatch = (ROOT / "skills/pi-dispatch/SKILL.md").read_text()
        setup = (ROOT / "skills/pi-setup/SKILL.md").read_text()
        reference = (ROOT / "skills/pi-dispatch/references/fast.rst").read_text()
        for text in (dispatch, setup, reference):
            for value in ("0.159.1", "2026-10-01", "requested"):
                self.assertIn(value, text)
        for value in ("OFF by default", "--fast", "--no-fast", "fast-check", "increased plan usage"):
            self.assertIn(value, dispatch)
        for value in ("fast", "default", "service_tiers", "additional_speed_tiers",
                      "default_service_tier", "--fast-unverified", "language-policy exception"):
            self.assertIn(value, reference)
        self.assertIn("fast` (boolean, default", setup)

    def test_all_scripts_have_bash32_syntax(self):
        for name in ("dispatch", "setup"):
            for script in (ROOT / f"skills/pi-{name}/scripts").glob("*.sh"):
                r = subprocess.run(["bash", "-n", str(script)], capture_output=True, text=True)
                self.assertEqual(r.returncode, 0, r.stderr)
                for forbidden in ("declare -A", "mapfile", "readarray", "${var,,}"):
                    self.assertNotIn(forbidden, script.read_text())
