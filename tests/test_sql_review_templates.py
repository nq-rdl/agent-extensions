"""Issue 349: render installs a missing bundled template; status reports missing templates."""
import json
import tempfile
import unittest

from test_data_request_lifts import ledger
from test_sql_review_criteria_status import row
from test_sql_review_scripts import ASSETS, Project, run, scope_doc

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
        self.assertEqual(self.tpl.stat().st_mode & 0o777, 0o644)  # not mktemp's 0600
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


class RenderScopeCriteria(unittest.TestCase):
    """Spec 017 (T031): the bundled scope.md renders `criteria_status` as an ID/State/Note table."""

    SLUG = "reports__monthly"
    HEADER = "| ID | State | Note |\n|---|---|---|\n"

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.p = Project(self.tmp.name)
        self.tpl = self.p.root / ".sqlreview" / "templates" / "scope.md"

    def render(self, **over):
        self.p.write_json(self.SLUG, "scope.json", scope_doc(**over))
        r = run(["render", self.SLUG, "scope"], self.p.root)
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        return r, (self.p.review_dir(self.SLUG) / "scope.md").read_text()

    def test_bundled_template_has_a_criteria_section_after_outputs(self):
        text = (ASSETS / "templates" / "scope.md").read_text()
        self.assertIn("## Criteria\n\n{{criteria}}\n", text)
        self.assertLess(text.index("{{outputs_list}}"), text.index("## Criteria"))
        self.assertLess(text.index("{{criteria}}"), text.index("## Assumptions"))

    def test_renders_a_table_ordered_by_kind_then_numeric_id(self):
        status = [
            row("D2", "not-delivered", reason="Not held in the source"),
            row("E10", "applied"),
            row("E4", "flagged", flag={"output": "patients", "column": "excl_prior_repair"}),
            row("I1", "applied"),
            row("E2", "not-applied", reason="First pass: cohort kept broad"),
            row("N1", "applied"),
            row("D1", "delivered"),
        ]
        r, md = self.render(criteria_status=status)
        self.assertEqual(r.stderr, "")
        expected = self.HEADER + "\n".join([
            "| N1 | applied |  |",
            "| I1 | applied |  |",
            "| E2 | not-applied | First pass: cohort kept broad |",
            "| E4 | flagged | `patients.excl_prior_repair` |",
            "| E10 | applied |  |",
            "| D1 | delivered |  |",
            "| D2 | not-delivered | Not held in the source |",
        ])
        self.assertIn("## Outputs\n\n- **month**", md)
        self.assertIn("## Criteria\n\n" + expected + "\n\n## Assumptions", md)
        self.assertNotIn("{{", md)

    def test_cell_content_is_escaped(self):
        status = [
            row("I1", "not-applied", reason="a | b\nsecond line"),
            row("E1", "flagged", flag={"output": "pat|ients", "column": "col\nx"}),
        ]
        _, md = self.render(criteria_status=status)
        self.assertIn("| I1 | not-applied | a &#124; b<br>second line |", md)
        self.assertIn("| E1 | flagged | `pat&#124;ients.col<br>x` |", md)

    def test_scope_without_criteria_status_renders_an_empty_section(self):
        for over in ({}, {"criteria_status": []}):
            r, md = self.render(**over)
            self.assertEqual(r.stderr, "")
            self.assertIn("## Criteria\n\n\n\n## Assumptions", md)
            self.assertNotIn("{{", md)
            self.assertNotIn("| ID | State |", md)

    def test_older_installed_template_still_renders(self):
        bundled = (ASSETS / "templates" / "scope.md").read_text()
        older = bundled.replace("## Criteria\n\n{{criteria}}\n\n", "")
        self.assertNotEqual(older, bundled)
        self.tpl.write_text(older)
        r, md = self.render(criteria_status=[row("N1", "applied")])
        self.assertEqual(r.stderr, "")
        self.assertNotIn("Criteria", md)
        self.assertNotIn("| N1 |", md)
        self.assertIn("Only completed stays are in scope", md)

    def test_older_template_only_gets_the_existing_unknown_placeholder_warning(self):
        older = (ASSETS / "templates" / "scope.md").read_text().replace("## Criteria\n\n{{criteria}}\n\n", "")
        self.tpl.write_text(older + "\n{{not_a_thing}}\n")
        r, md = self.render(criteria_status=[row("N1", "applied")])
        self.assertEqual(r.stderr.strip(), "sqlreview: unknown placeholder(s) left in place: {{not_a_thing}}")
        self.assertIn("{{not_a_thing}}", md)
