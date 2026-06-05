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


class TestUnmappedSection(unittest.TestCase):
    """A synced skill is copied but not installable until a bundle maps it; the
    PR body must flag exactly which added skills are still unmapped."""

    def _changes(self):
        return {"added": ["zod", "go-gh"], "removed": [], "modified": []}

    def test_flags_added_skills_that_no_bundle_maps(self):
        body = sync_pr_body.render_pr_body(
            "v0.9.0", self._changes(), mapped_sources={"go-gh"}
        )
        # go-gh is mapped → not flagged; zod is unmapped → flagged.
        self.assertIn("map these to publish", body.lower())
        self.assertIn("`zod`", body)
        action_block = body.split("Action required")[1]
        self.assertNotIn("`go-gh`", action_block)

    def test_no_section_when_all_added_skills_mapped(self):
        body = sync_pr_body.render_pr_body(
            "v0.9.0", self._changes(), mapped_sources={"go-gh", "zod"}
        )
        self.assertNotIn("map these to publish", body.lower())

    def test_no_section_when_mapped_sources_unknown(self):
        # mapped_sources=None (no repo passed) → degrade gracefully, no section.
        body = sync_pr_body.render_pr_body("v0.9.0", self._changes())
        self.assertNotIn("map these to publish", body.lower())

    def test_mapped_skill_sources_reads_flat_and_mapping_members(self):
        import tempfile

        with tempfile.TemporaryDirectory() as tmp:
            bundles = Path(tmp) / "registry" / "bundles"
            bundles.mkdir(parents=True)
            (bundles / "go.yaml").write_text(
                "id: go\nskills:\n  - {source: go-gh, leaf: gh}\n"
            )
            (bundles / "git.yaml").write_text("id: git\nskills:\n  - changie\n")
            sources = sync_pr_body.mapped_skill_sources(tmp)
            self.assertEqual(sources, {"go-gh", "changie"})

    def test_mapped_skill_sources_returns_none_when_registry_absent(self):
        # "unknown" must be None, not set() — an empty set would falsely flag
        # every added skill as unmapped.
        import tempfile

        with tempfile.TemporaryDirectory() as tmp:
            self.assertIsNone(sync_pr_body.mapped_skill_sources(tmp))


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

    def test_main_with_repo_arg_flags_unmapped_added_skills(self):
        # The production invocation is `sync_pr_body.py <tag> <repo>`; the repo
        # arg enables the "map these to publish" section for synced-but-unmapped
        # skills. Exercise that end-to-end wiring (argv → mapped_skill_sources →
        # render_pr_body), which the single-arg test above does not cover.
        import tempfile

        out = io.StringIO()
        old_stdin = sys.stdin
        with tempfile.TemporaryDirectory() as tmp:
            bundles = Path(tmp) / "registry" / "bundles"
            bundles.mkdir(parents=True)
            (bundles / "go.yaml").write_text("id: go\nskills:\n  - mapped-skill\n")
            sys.stdin = io.StringIO(
                "A\tskills/mapped-skill/SKILL.md\nA\tskills/orphan-skill/SKILL.md\n"
            )
            try:
                with contextlib.redirect_stdout(out):
                    rc = sync_pr_body.main(["v0.9.0", tmp])
            finally:
                sys.stdin = old_stdin
        body = out.getvalue()
        self.assertEqual(rc, 0)
        self.assertIn("map these to publish", body)
        unmapped_section = body.split("map these to publish", 1)[1]
        self.assertIn("orphan-skill", unmapped_section)       # unmapped → flagged
        self.assertNotIn("mapped-skill", unmapped_section)    # mapped → not flagged


if __name__ == "__main__":
    unittest.main()
