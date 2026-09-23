"""Issue 349: render installs a missing bundled template; status reports missing templates."""
import json
import tempfile
import unittest

from test_data_request_lifts import ledger
from test_sql_review_scripts import ASSETS, Project, run

FIX = "sqlreview.sh init --apply templates/lifts.md"


class MissingTemplate(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.p = Project(self.tmp.name)
        self.p.sql("pipeline.py", 'db.query("SELECT 1")\n')
        self.sr = self.p.root / ".sqlreview"
        self.tpl = self.sr / "templates" / "lifts.md"
        self.tpl.unlink()  # a project initialised before lifts shipped
        self.doc = ledger()
        draft = self.p.write_json(self.doc["slug"], "lifts.draft.json", self.doc)
        r = run(["publish", self.doc["slug"], "lifts", str(draft)], self.p.root)
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)

    def render(self, expected=0):
        r = run(["render", self.doc["slug"], "lifts"], self.p.root)
        self.assertEqual(r.returncode, expected, r.stdout + r.stderr)
        return r

    def rendered(self):
        return (self.p.review_dir(self.doc["slug"]) / "lifts.md").read_text()

    def test_render_installs_the_missing_template_and_renders(self):
        r = self.render()
        self.assertEqual(self.tpl.read_bytes(), (ASSETS / "templates" / "lifts.md").read_bytes())
        self.assertIn("installed missing template .sqlreview/templates/lifts.md from the bundled default", r.stderr)
        self.assertNotIn("installed", r.stdout)
        self.assertIn("Current labelled status", self.rendered())
        self.assertEqual(list((self.sr / "templates").glob(".*")), [])  # no staging leftovers
        self.assertNotIn("installed", self.render().stderr)  # second render: nothing to install

    def test_render_recreates_a_missing_templates_directory(self):
        for f in (self.sr / "templates").iterdir():
            f.unlink()
        (self.sr / "templates").rmdir()
        self.render()
        self.assertEqual(sorted(f.name for f in (self.sr / "templates").iterdir()), ["lifts.md"])

    def test_existing_customised_template_is_never_overwritten(self):
        self.tpl.write_text("CUSTOM LEDGER {{title}}\n")
        r = self.render()
        self.assertEqual(self.tpl.read_text(), "CUSTOM LEDGER {{title}}\n")
        self.assertNotIn("installed", r.stderr)
        self.assertIn("CUSTOM LEDGER", self.rendered())

    def test_symlinked_templates_directory_is_refused(self):
        outside = self.p.root / "outside"
        outside.mkdir()
        for f in (self.sr / "templates").iterdir():
            f.rename(outside / f.name)
        (self.sr / "templates").rmdir()
        (self.sr / "templates").symlink_to(outside)
        r = self.render(expected=2)
        self.assertIn("symlink path refused", r.stderr)
        self.assertFalse((outside / "lifts.md").exists())

    def test_dangling_template_symlink_is_refused(self):
        target = self.p.root / "elsewhere.md"
        self.tpl.symlink_to(target)
        r = self.render(expected=2)
        self.assertIn("symlink path refused", r.stderr)
        self.assertFalse(target.exists())

    def test_template_path_that_is_a_directory_is_refused(self):
        self.tpl.mkdir()
        r = self.render(expected=2)
        self.assertIn("not a regular file", r.stderr)
        self.assertEqual(list(self.tpl.iterdir()), [])

    def test_missing_config_still_fails_without_installing(self):
        (self.sr / "config.json").unlink()
        r = self.render(expected=2)
        self.assertIn("config missing", r.stderr)
        self.assertFalse(self.tpl.exists())


class StatusReportsMissingTemplates(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.p = Project(self.tmp.name)
        self.tpl = self.p.root / ".sqlreview" / "templates" / "lifts.md"

    def status(self, *args):
        r = run(["status", *args], self.p.root)
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        return r

    def test_status_lists_the_missing_template_and_the_fix(self):
        self.tpl.unlink()
        j = json.loads(self.status("--json").stdout)
        self.assertEqual(j["missing_templates"], ["templates/lifts.md"])
        self.assertEqual(j["missing_templates_fix"], FIX)
        text = self.status()
        self.assertEqual(text.stdout, "")  # stdout stays one tab-separated row per review
        self.assertIn("templates/lifts.md", text.stderr)
        self.assertIn(FIX, text.stderr)

    def test_status_is_clean_when_every_template_exists(self):
        j = json.loads(self.status("--json").stdout)
        self.assertEqual(j["missing_templates"], [])
        self.assertIsNone(j["missing_templates_fix"])
        self.assertEqual(self.status().stderr, "")

    def test_customised_template_is_not_reported(self):
        self.tpl.write_text("mine\n")
        self.assertEqual(json.loads(self.status("--json").stdout)["missing_templates"], [])


if __name__ == "__main__":
    unittest.main()
