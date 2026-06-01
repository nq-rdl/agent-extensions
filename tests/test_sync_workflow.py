"""Regression guards for .github/workflows/sync-skills.yml hardening.

These encode the fixes from the pipeline audit so the workflow cannot silently
regress to the old behaviour:
  - #1 CI-trigger gap: the sync PR must be created via a GitHub App token (so
    validate.yml actually runs on it), not the default GITHUB_TOKEN.
  - #5 change detection must use `git status --porcelain` (catches untracked
    new skills), not `git diff --quiet` (which ignores untracked files).
  - #6 the PR body must be built by the summariser, not a raw `git diff --stat`.
  - drift must be surfaced via check_bundle_refs.py before a human merges.
"""

import unittest
from pathlib import Path

WORKFLOW = (
    Path(__file__).resolve().parent.parent / ".github" / "workflows" / "sync-skills.yml"
)


class TestSyncWorkflowHardening(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.raw = WORKFLOW.read_text()

    def test_generates_github_app_token(self):
        self.assertIn("create-github-app-token", self.raw)
        self.assertIn("steps.app-token.outputs.token", self.raw)

    def test_does_not_dump_raw_diff_stat_into_body(self):
        self.assertNotIn("git diff --stat HEAD", self.raw)

    def test_uses_summariser_for_pr_body(self):
        self.assertIn("sync_pr_body.py", self.raw)

    def test_change_detection_uses_porcelain_not_diff_quiet(self):
        self.assertIn("git status --porcelain", self.raw)
        self.assertNotIn("git diff --quiet", self.raw)

    def test_flags_drift_with_checker(self):
        self.assertIn("check_bundle_refs.py", self.raw)


if __name__ == "__main__":
    unittest.main()
