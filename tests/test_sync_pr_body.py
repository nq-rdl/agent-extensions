"""Tests for scripts/sync_pr_body.py — the sync PR-body summariser.

The old workflow embedded `git diff --stat HEAD~1` directly in the PR body,
producing a ~60k-line dump that can exceed GitHub's 65,536-char body limit
(audit #6). This module turns the raw name-status diff into a concise summary of
which skills were added / removed / modified, and surfaces registry drift
(audit #4).
"""

import contextlib
import io
import os
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))

import sync_pr_body  # noqa: E402


class TestClassify(unittest.TestCase):
    def test_buckets_added_removed_modified_by_skill(self):
        lines = [
            "A\tskills/rust-explain/SKILL.md",
            "A\tskills/rust-explain/references/x.rst",
            "D\tskills/csv/SKILL.md",
            "D\tskills/csv/scripts/validate.py",
            "M\tskills/changie/SKILL.md",
            "M\tplugins/swe/skills/changie/SKILL.md",  # plugin mirror, ignored for skill buckets
        ]
        changes = sync_pr_body.classify_skill_changes(lines)
        self.assertEqual(changes["added"], ["rust-explain"])
        self.assertEqual(changes["removed"], ["csv"])
        self.assertEqual(changes["modified"], ["changie"])

    def test_rename_counts_old_as_removed_and_new_as_added(self):
        # `git diff --name-status` emits a rename as: R100\told\tnew
        lines = ["R100\tskills/csv/SKILL.md\tskills/csv-v2/SKILL.md"]
        changes = sync_pr_body.classify_skill_changes(lines)
        self.assertEqual(changes["removed"], ["csv"])
        self.assertEqual(changes["added"], ["csv-v2"])
        self.assertEqual(changes["modified"], [])


class TestRender(unittest.TestCase):
    def _changes(self):
        return {"added": ["rust-explain"], "removed": ["csv", "docx"], "modified": ["changie"]}

    def test_body_summarises_names_not_raw_paths(self):
        body = sync_pr_body.render_pr_body("v0.9.0", self._changes())
        self.assertIn("v0.9.0", body)
        self.assertIn("rust-explain", body)
        self.assertIn("releases/tag/v0.9.0", body)
        # must NOT contain raw file-diff noise
        self.assertNotIn("SKILL.md", body)
        self.assertNotIn("Bin ", body)

    def test_drift_section_present_when_drift_given(self):
        body = sync_pr_body.render_pr_body(
            "v0.9.0",
            self._changes(),
            drift_messages=["dataops references removed skill 'csv'"],
        )
        self.assertIn("dataops", body)
        # a clearly-flagged reconciliation/drift heading
        self.assertRegex(body.lower(), r"reconcil|drift|action required")

    def test_no_drift_section_when_clean(self):
        body = sync_pr_body.render_pr_body("v0.9.0", self._changes(), drift_messages=[])
        self.assertNotRegex(body.lower(), r"reconcil|drift|action required")

    def test_body_stays_under_github_limit(self):
        huge = {
            "added": [f"skill-{i}" for i in range(5000)],
            "removed": [],
            "modified": [],
        }
        body = sync_pr_body.render_pr_body("v0.9.0", huge, max_chars=60000)
        self.assertLessEqual(len(body), 60000)


class TestMain(unittest.TestCase):
    def test_main_reads_name_status_from_stdin_and_drift_from_env(self):
        out = io.StringIO()
        old_stdin, old_env = sys.stdin, os.environ.get("SYNC_DRIFT")
        sys.stdin = io.StringIO("A\tskills/new-skill/SKILL.md\n")
        os.environ["SYNC_DRIFT"] = "dataops references removed skill 'csv'"
        try:
            with contextlib.redirect_stdout(out):
                rc = sync_pr_body.main(["v0.9.0"])
        finally:
            sys.stdin = old_stdin
            if old_env is None:
                os.environ.pop("SYNC_DRIFT", None)
            else:
                os.environ["SYNC_DRIFT"] = old_env
        self.assertEqual(rc, 0)
        self.assertIn("new-skill", out.getvalue())
        self.assertIn("dataops", out.getvalue())


if __name__ == "__main__":
    unittest.main()
