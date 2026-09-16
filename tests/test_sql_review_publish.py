"""Exercise the sanctioned final-write path from an installed native package."""

import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest

from tests.test_sql_review_scripts import REPO, Project, review_doc, scope_doc


class Publish(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        root = Path(self.temp.name)
        self.workspace = root / "unrelated workspace"
        self.workspace.mkdir()
        self.project = Project(self.workspace)
        self.cache = root / "plugin cache"
        shutil.copytree(REPO / "dist/codex/plugins/sql-code", self.cache)
        self.script = self.cache / "skills/setup/scripts/sqlreview.sh"
        self.draft = root / "confirmed draft.json"
        self.final = self.workspace / ".sqlreview/reviews/q"

    def run_helper(self, *args):
        env = {k: v for k, v in os.environ.items() if not k.startswith("SQLREVIEW_")}
        return subprocess.run(["bash", str(self.script), *args], cwd=self.workspace,
                              env=env, capture_output=True, text=True)

    def publish(self, doc, slug="q", kind=None):
        self.draft.write_text(json.dumps(doc))
        return self.run_helper("publish", slug, kind or doc["kind"], str(self.draft))

    def test_scope_then_review_publish_snapshot_and_render(self):
        scope = scope_doc("q", "q.sql")
        result = self.publish(scope)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertEqual(json.loads((self.final / "scope.json").read_text()), scope)
        self.assertEqual(self.run_helper("render", "q", "scope").returncode, 0)
        self.project.sql("q.sql", "select 1;\n")
        sha = hashlib.sha256((self.workspace / "q.sql").read_bytes()).hexdigest()
        review = review_doc("q", "q.sql", sql_sha256=sha)
        self.assertEqual(self.publish(review).returncode, 0)
        self.assertEqual(self.publish(review).returncode, 0)  # interrupted workflow retry
        self.assertEqual(self.run_helper("snapshot", "q", "q.sql").returncode, 0)
        self.assertEqual(self.run_helper("render", "q", "review").returncode, 0)
        self.assertEqual((self.final / "source.sql").read_bytes(), (self.workspace / "q.sql").read_bytes())
        self.assertTrue((self.final / "review.md").is_file())
        review = review_doc("q", "q.sql", revision=2, sql_sha256=sha)
        self.assertEqual(self.publish(review).returncode, 0)
        self.assertEqual(self.run_helper("snapshot", "q", "q.sql").returncode, 0)
        self.assertTrue((self.final / "history/2.sql").is_file())

    def test_invalid_publish_preserves_final_and_draft(self):
        original = scope_doc("q", "q.sql")
        self.assertEqual(self.publish(original).returncode, 0)
        final_bytes = (self.final / "scope.json").read_bytes()
        pending = scope_doc("q", "q.sql", revision=2)
        pending["assumptions"][0]["status"] = "pending"
        stale_confirmation = scope_doc("q", "q.sql", revision=2)
        stale_confirmation["assumptions"][0]["confirmed_revision"] = 1
        for doc, slug, kind in [
            (pending, "q", "scope"), (stale_confirmation, "q", "scope"),
            (scope_doc("q", "q.sql", revision=3), "q", "scope"),
            (scope_doc("q", "q.sql", intent="Changed without revision"), "q", "scope"),
            (scope_doc("other", "other.sql"), "q", "scope"),
            (original, "q", "review"), (original, "../escape", "scope"),
        ]:
            with self.subTest(doc=doc, slug=slug, kind=kind):
                self.assertNotEqual(self.publish(doc, slug, kind).returncode, 0)
                self.assertEqual((self.final / "scope.json").read_bytes(), final_bytes)
                self.assertTrue(self.draft.is_file())
                self.assertEqual(list(self.final.glob(".publish.*")), [])

    def test_changed_sql_and_symlink_destinations_are_refused(self):
        self.project.sql("q.sql", "select 1;")
        result = self.publish(review_doc("q", "q.sql"))
        self.assertNotEqual(result.returncode, 0)
        self.assertFalse((self.final / "review.json").exists())
        outside = Path(self.temp.name) / "outside.json"
        outside.write_text("keep")
        (self.final / "scope.json").symlink_to(outside)
        self.assertNotEqual(self.publish(scope_doc("q", "q.sql")).returncode, 0)
        self.assertEqual(outside.read_text(), "keep")
