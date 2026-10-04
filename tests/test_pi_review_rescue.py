"""Offline contracts for pi:review and pi:rescue under host Bash and Bash 3.2.

``tests/fixtures/pi-review-rescue/scenario.sh`` drives the helpers against a
fake ``pi`` that records its arguments; no model is called. Review cases that
need a real git repository run on the host only; the pinned Bash 3.2 image has
no git, so it runs the render, rescue (with a rev-parse shim) cases.
"""
import os
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
HOST_CASES = ("render", "review-args", "review-branch", "review-worktree", "rescue")
BASH32_CASES = ("render", "rescue")
RUBRIC_COMMIT = "81de4f251cfdaf32ecb85e2160ebfc11a562d44b"


def fixture(directory):
    target = Path(directory)
    shutil.copytree(ROOT / "tests/fixtures/pi-review-rescue", target, dirs_exist_ok=True)
    for name in ("review", "rescue"):
        shutil.copytree(ROOT / f"skills/pi-{name}", target / name)
    for shim in [*(target / "bin").iterdir(), *(target / "gitshim").iterdir()]:
        shim.chmod(0o755)


class HostBash(unittest.TestCase):
    def check_case(self, case):
        if case != "render" and not shutil.which("git"):
            self.skipTest("requires git")
        with tempfile.TemporaryDirectory(prefix="pi-rr-") as tmp:
            fixture(tmp)
            env = {k: v for k, v in os.environ.items() if not k.startswith(("GIT_", "PI_"))}
            r = subprocess.run(["bash", "scenario.sh", case], cwd=tmp, env=env,
                               capture_output=True, text=True, timeout=60)
            self.assertEqual(r.returncode, 0, r.stdout + r.stderr)


for case in HOST_CASES:
    setattr(HostBash, f"test_{case.replace('-', '_')}",
            lambda self, case=case: self.check_case(case))


class Bash32(unittest.TestCase):
    def test_offline_contracts(self):
        from bash32_fixture import container_runtime, run_container, static_jq
        if not container_runtime() or not static_jq():
            self.skipTest("requires pinned Bash 3.2 container and verified static jq")
        for case in BASH32_CASES:
            with self.subTest(case=case), tempfile.TemporaryDirectory(prefix="pi-rr-bash32-") as tmp:
                fixture(tmp)
                jq = Path(tmp) / "bin/jq"
                shutil.copyfile(static_jq(), jq)
                jq.chmod(0o755)
                command = (f"cd /fixture; trap 'chown -R {os.getuid()}:{os.getgid()} /fixture' EXIT; "
                           f"bash scenario.sh {case}")
                r = run_container(tmp, "/fixture", command)
                self.assertEqual(r.returncode, 0, r.stdout + r.stderr)


class Contracts(unittest.TestCase):
    def test_rubric_attribution_and_pin(self):
        rubric = (ROOT / "skills/pi-review/assets/review-rubric.md").read_text()
        self.assertTrue(rubric.startswith("<!--\nSPDX-License-Identifier: Apache-2.0\n"))
        self.assertIn(RUBRIC_COMMIT, rubric)
        self.assertIn('"overall_correctness": "patch is correct" | "patch is incorrect"', rubric)

    def test_skills_keep_forwarder_and_question_contracts(self):
        review = " ".join((ROOT / "skills/pi-review/SKILL.md").read_text().split())
        rescue = " ".join((ROOT / "skills/pi-rescue/SKILL.md").read_text().split())
        for text in (review, rescue):
            self.assertIn("Create Unsafe Agents", text)
            self.assertIn("If the user dismisses or cancels the question, stop", text)
        self.assertIn("`Wait for results` and `Run in background`", review)
        self.assertIn("`Continue current pi session` or `Start a new pi session`", rescue)
        self.assertIn("Fast mode is not used", review)
        self.assertIn("forward the text unchanged", rescue)

    def test_prompting_copy_is_openai_only(self):
        guide = (ROOT / "skills/pi-rescue/references/gpt-prompting.rst").read_text()
        self.assertIn("``openai`` or ``openai-codex``", guide)
        for name in ("prompt-blocks.rst", "prompt-recipes.rst", "prompt-antipatterns.rst"):
            text = (ROOT / "skills/pi-rescue/references" / name).read_text()
            self.assertNotIn("codex:rescue", text)
            self.assertNotIn("companion", text)


if __name__ == "__main__":
    unittest.main()
