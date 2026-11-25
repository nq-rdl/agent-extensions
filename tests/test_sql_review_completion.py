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
        project.commit()
        fp = json.loads(self.helper("fingerprint", "q.sql").stdout)
        self.directory = self.workspace / ".sqlreview/reviews/q"
        self.directory.mkdir(parents=True)
        self.draft = self.directory / "review.draft.json"
        self.draft.write_text(json.dumps(review_doc("q", **fp)))
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

    def test_header_only_completion_records_revision_without_reconfirming(self):
        sql = self.workspace / "q.sql"
        sql.write_text("-- corrected header\nselect 1;\n")
        Project(self.workspace, git_repo=False, init=False).commit("header update")
        self.assertEqual(self.helper("delta", "q").returncode, 0)
        result = self.recover()
        self.assertEqual(result.returncode, 0, result.stderr)
        published = json.loads((self.directory / "review.json").read_text())
        self.assertEqual(published["revision"], 1)
        self.assertEqual(published["header_revisions"][-1]["sql_sha256"], hashlib.sha256(sql.read_bytes()).hexdigest())
        self.assertEqual(published["sql_sha256"], hashlib.sha256(b"select 1;\n").hexdigest())
        self.assertEqual(list(self.directory.rglob("*.sql")), [])
        self.assertIn("Header revision", (self.directory / "review.md").read_text())
        self.assertFalse(self.draft.exists(), "helper-owned history is not unpublished work")

    def test_header_recovery_preserves_semantically_changed_draft(self):
        sql = self.workspace / "q.sql"
        sql.write_text("-- corrected header\nselect 1;\n")
        Project(self.workspace, git_repo=False, init=False).commit("header update")
        draft = json.loads(self.draft.read_text())
        draft["assumptions"][0]["rationale"] = "Unpublished rationale"
        self.draft.write_text(json.dumps(draft))
        original = self.draft.read_bytes()
        result = self.recover()
        self.assertEqual(result.returncode, 4, "unpublished work must stop the hand-off")
        self.assertIn("unpublished", result.stderr)
        self.assertEqual(self.draft.read_bytes(), original)

    def test_recovery_removes_semantically_equal_reserialized_draft(self):
        draft = json.loads(self.draft.read_text())
        self.draft.write_text(json.dumps(draft, indent=4, sort_keys=True))
        self.assertNotEqual(self.draft.read_bytes(), self.final_bytes)
        result = self.recover()
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertFalse(self.draft.exists())

    def test_recovery_preserves_malformed_draft(self):
        self.draft.write_text("not JSON")
        result = self.recover()
        self.assertEqual(result.returncode, 4, "unreadable work must stop the hand-off")
        self.assertIn("unpublished", result.stderr)
        self.assertEqual(self.draft.read_text(), "not JSON")

    def test_render_failure_then_resume_completes_without_new_revision(self):
        template = self.workspace / ".sqlreview/templates/review.md"
        original = template.read_text()
        template.unlink()
        template.mkdir()  # a missing template is reinstalled (#349); a directory still fails
        self.assertNotEqual(self.helper("render", "q", "review").returncode, 0)
        self.assertEqual(self.helper("delta", "q").returncode, 0)
        self.assertNotEqual(self.recover().returncode, 0)
        self.assertTrue(self.draft.exists())
        template.rmdir()
        template.write_text(original)
        result = self.recover()
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertTrue((self.directory / "review.md").is_file())
        self.assertEqual((self.directory / "review.json").read_bytes(), self.final_bytes)
        self.assertFalse((self.directory / "history").exists())
        self.assertFalse(self.draft.exists())

    def test_no_draft_allows_unchanged_review_to_continue(self):
        self.draft.unlink()
        result = self.recover()
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertTrue((self.directory / "review.md").is_file())
        self.assertEqual((self.directory / "review.json").read_bytes(), self.final_bytes)

    def referenced_review_with_pending_questions(self):
        review = json.loads((self.directory / "review.json").read_text())
        review.pop("open_questions")
        review["question_store"] = "questions.json"
        (self.directory / "review.json").write_text(json.dumps(review))
        self.draft.write_text(json.dumps(review))
        questions = {"schemaVersion": 1, "kind": "questions", "slug": "q", "sql_path": "q.sql",
                     "questions": [{"id": "Q1", "text": "Which wards?", "applies": "review",
                                    "owner": None, "status": "open"}]}
        pending = self.directory / "questions.draft.json"
        pending.write_text(json.dumps(questions))
        return pending, questions

    def test_recovery_publishes_pending_first_store_before_render_without_new_revision(self):
        pending, questions = self.referenced_review_with_pending_questions()
        before = {p.name: p.read_bytes() for p in self.directory.glob("history/**/*.json")}
        final = (self.directory / "review.json").read_bytes()
        self.assertEqual(self.helper("render", "q", "review").returncode, 4)
        result = self.recover()
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertEqual(json.loads((self.directory / "questions.json").read_text()), questions)
        self.assertIn("Q1", (self.directory / "review.md").read_text())
        self.assertEqual((self.directory / "review.json").read_bytes(), final)
        self.assertEqual({p.name: p.read_bytes() for p in self.directory.glob("history/**/*.json")}, before)
        self.assertEqual(json.loads(pending.read_text()), questions)

    def test_recovery_keeps_bad_pending_questions_and_reports_incomplete(self):
        pending, questions = self.referenced_review_with_pending_questions()
        pending.write_text("{")
        result = self.recover()
        self.assertEqual(result.returncode, 4, result.stdout + result.stderr)
        self.assertEqual(pending.read_text(), "{")
        self.assertTrue(self.draft.exists())
        self.assertFalse((self.directory / "questions.json").exists())
        self.assertFalse((self.directory / "review.md").exists())
        pending.unlink()
        self.assertEqual(self.recover().returncode, 4)
        self.assertFalse((self.directory / "questions.json").exists())
        pending.write_text(json.dumps(questions))
        (self.directory / "questions.json").write_text("{")
        self.assertEqual(self.recover().returncode, 4)
        self.assertEqual((self.directory / "questions.json").read_text(), "{")

    def test_recovery_does_not_publish_differing_question_draft_over_valid_store(self):
        pending, questions = self.referenced_review_with_pending_questions()
        self.assertEqual(self.helper("publish-questions", "q", str(pending)).returncode, 0)
        pending.write_text('{"unpublished": true}')
        self.assertEqual(self.recover().returncode, 0)
        self.assertEqual(json.loads((self.directory / "questions.json").read_text()), questions)
        self.assertEqual(pending.read_text(), '{"unpublished": true}')

    def test_recovery_replaces_old_report_and_preserves_unpublished_draft(self):
        (self.directory / "review.md").write_text("old report")
        self.draft.write_text('{"unpublished": true}')
        result = self.recover()
        self.assertNotEqual(result.returncode, 0, "unpublished work must stop the hand-off")
        self.assertIn("unpublished", result.stderr)
        self.assertNotEqual((self.directory / "review.md").read_text(), "old report")
        self.assertEqual(self.draft.read_text(), '{"unpublished": true}')
        self.assertEqual((self.directory / "review.json").read_bytes(), self.final_bytes)
