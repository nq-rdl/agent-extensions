"""Hook-env guard for the test jobs in lefthook.yml.

Git exports GIT_DIR (and, depending on the hook, GIT_WORK_TREE / GIT_INDEX_FILE) into
hooks. A pre-push test job that inherits them runs its throwaway-repo git commands
against the real repository. Commit 7f8cbfb fixed the Python job; the codex Node job
leaked the same way. Both jobs must clear the variables. The Node helpers also scrub
them on import (tests/codex/git-env-isolation.test.mjs).
"""

import unittest
from pathlib import Path

import yaml

REPO = Path(__file__).resolve().parent.parent
REQUIRED_UNSETS = ("GIT_DIR", "GIT_WORK_TREE", "GIT_INDEX_FILE")


class LefthookTestJobsClearGitEnv(unittest.TestCase):
    def test_test_jobs_unset_hook_git_env(self):
        config = yaml.safe_load((REPO / "lefthook.yml").read_text())
        jobs = {job["name"]: job for job in config["pre-push"]["jobs"]}
        for name in ("python-unit-tests", "codex-js-tests"):
            with self.subTest(job=name):
                run = jobs[name]["run"]
                self.assertTrue(run.startswith("env -u "), run)
                for var in REQUIRED_UNSETS:
                    self.assertIn(f"-u {var} ", run)

    def test_codex_helpers_scrub_on_import(self):
        helpers = (REPO / "tests" / "codex" / "helpers.mjs").read_text()
        self.assertIn("\nscrubGitEnv(process.env);\n", helpers)
        for var in REQUIRED_UNSETS + ("GIT_PREFIX", "GIT_COMMON_DIR"):
            self.assertIn(f'"{var}"', helpers)


if __name__ == "__main__":
    unittest.main()
