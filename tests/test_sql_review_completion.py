"""Run the analyse skill's recovery commands after interrupted publication."""

import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import tempfile
import unittest

from tests.test_sql_review_scripts import REPO, Project, review_doc


class CompletePublication(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        root = Path(temp.name)
        self.workspace = root / "unrelated workspace"
        self.workspace.mkdir()
        project = Project(self.workspace)
        self.scripts = root / "installed cache" / "skills" / "setup" / "scripts"
        shutil.copytree(REPO / "skills/data-request-setup", self.scripts.parent)
        self.env = {k: v for k, v in os.environ.items() if not k.startswith("SQLREVIEW_")}
        self.env.update(S=str(self.scripts), SLUG="q")
        project.sql("q.sql", "select 1;\n")
        sha = hashlib.sha256((self.workspace / "q.sql").read_bytes()).hexdigest()
        self.directory = self.workspace / ".sqlreview/reviews/q"
        self.directory.mkdir(parents=True)
        self.draft = self.directory / "review.draft.json"
        self.draft.write_text(json.dumps(review_doc("q", "q.sql", sql_sha256=sha)))
        self.assertEqual(self.helper("publish", "q", "review", str(self.draft)).returncode, 0)
        self.assertEqual(self.helper("snapshot", "q", "q.sql").returncode, 0)
        self.final_bytes = (self.directory / "review.json").read_bytes()
        skill = (REPO / "skills/data-request-analyse/SKILL.md").read_text()
        section = skill.split("### Unchanged SQL: complete publication before stopping", 1)[1]
        self.recovery = re.search(r"```bash\n(.*?)\n```", section, re.S).group(1)

    def helper(self, *args):
        return subprocess.run(["bash", str(self.scripts / "sqlreview.sh"), *args],
                              cwd=self.workspace, env=self.env, capture_output=True, text=True)

    def recover(self):
        return subprocess.run(["bash", "-c", self.recovery], cwd=self.workspace,
                              env=self.env, capture_output=True, text=True)

    def test_render_failure_then_resume_completes_without_new_revision(self):
        template = self.workspace / ".sqlreview/templates/review.md"
        original = template.read_text()
        template.unlink()
        self.assertNotEqual(self.helper("render", "q", "review").returncode, 0)
        self.assertEqual(self.helper("delta", "q").returncode, 0)
        self.assertNotEqual(self.recover().returncode, 0)
        self.assertTrue(self.draft.exists())
        template.write_text(original)
        result = self.recover()
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertTrue((self.directory / "review.md").is_file())
        self.assertEqual((self.directory / "review.json").read_bytes(), self.final_bytes)
        self.assertEqual(sorted(p.name for p in (self.directory / "history").iterdir()), ["1.sql"])
        self.assertFalse(self.draft.exists())

    def test_recovery_replaces_old_report_and_preserves_unpublished_draft(self):
        (self.directory / "review.md").write_text("old report")
        self.draft.write_text('{"unpublished": true}')
        self.assertEqual(self.recover().returncode, 0)
        self.assertNotEqual((self.directory / "review.md").read_text(), "old report")
        self.assertEqual(self.draft.read_text(), '{"unpublished": true}')
        self.assertEqual((self.directory / "review.json").read_bytes(), self.final_bytes)
