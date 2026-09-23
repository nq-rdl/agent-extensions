"""Issue 347: legacy reviews explain why they are invalid and can be rebound by slug."""
import json
import tempfile
import unittest

from test_sql_review_scripts import Project, SQL_V1, review_doc, run

LEGACY_SLUG = "aaa_screening_log"
NEW_PATH = "sql/cohort_pipeline/aaa_screening_log.sql"
NEW_SLUG = "sql__cohort%5Fpipeline__aaa%5Fscreening%5Flog"


class LegacyReviews(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.p = Project(self.tmp.name)
        self.p.sql(NEW_PATH, SQL_V1)
        # Schema 1, hand-chosen slug, sql_path pointing at a file that no longer exists.
        self.p.write_json(LEGACY_SLUG, "review.json", review_doc(LEGACY_SLUG, "old/aaa_screening_log.sql"))

    def status(self, *args):
        r = run(["status", *args], self.p.root)
        self.assertEqual(r.returncode, 0, r.stderr)
        return r

    def test_plain_status_is_unchanged(self):
        j = json.loads(self.status("--json").stdout)
        self.assertEqual(j["reviews"][0]["state"], "invalid")
        self.assertNotIn("reason", j["reviews"][0])
        self.assertNotIn("reason=", self.status().stdout)

    def test_verbose_status_names_the_invalid_reason(self):
        text = self.status("--verbose").stdout
        self.assertIn("reason=review.json: slug/sql_path binding mismatch", text)
        self.assertIn("schemaVersion 1", text)
        self.assertIn("sql_path target missing: old/aaa_screening_log.sql", text)
        self.assertIn(f"move --slug {LEGACY_SLUG}", text)
        row = json.loads(self.status("--json", "--verbose").stdout)["reviews"][0]
        self.assertIn("binding mismatch", row["reason"])

    def test_verbose_status_explains_empty_directories(self):
        self.p.review_dir("empty")
        rows = json.loads(self.status("--verbose", "--json").stdout)["reviews"]
        self.assertEqual({r["slug"]: r["reason"] for r in rows}["empty"], "no review.json, scope.json or lifts.json")

    def test_unknown_status_flag_is_a_usage_error(self):
        self.assertEqual(run(["status", "--bogus"], self.p.root).returncode, 1)

    def test_slug_points_at_a_legacy_review_bound_to_the_path(self):
        self.p.write_json("legacy2", "review.json", review_doc("legacy2", NEW_PATH))
        r = run(["slug", NEW_PATH], self.p.root)
        self.assertEqual((r.returncode, r.stdout.strip()), (0, NEW_SLUG))
        self.assertIn("move --slug legacy2", r.stderr)

    def test_move_by_slug_rebinds_the_legacy_review(self):
        r = run(["move", "--slug", LEGACY_SLUG, NEW_PATH], self.p.root)
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertEqual(r.stdout.strip().split("\t"), ["moved", LEGACY_SLUG, NEW_SLUG, NEW_PATH])
        d = self.p.root / ".sqlreview" / "reviews" / NEW_SLUG
        self.assertFalse((self.p.root / ".sqlreview" / "reviews" / LEGACY_SLUG).exists())
        self.assertTrue((d / "rebind-required").is_file())
        j = json.loads((d / "review.json").read_text())
        self.assertEqual((j["slug"], j["sql_path"]), (NEW_SLUG, NEW_PATH))
        row = json.loads(self.status("--json").stdout)["reviews"][0]
        self.assertEqual((row["slug"], row["state"]), (NEW_SLUG, "no-baseline"))

    def test_move_by_slug_refuses_bad_input(self):
        for args, rc in ((["--slug", "nope", NEW_PATH], 2), (["--slug", "../x", NEW_PATH], 2),
                         (["--slug", LEGACY_SLUG], 1)):
            with self.subTest(args=args):
                self.assertEqual(run(["move", *args], self.p.root).returncode, rc)
        self.p.review_dir(NEW_SLUG)
        r = run(["move", "--slug", LEGACY_SLUG, NEW_PATH], self.p.root)
        self.assertEqual(r.returncode, 2)
        self.assertIn("already exists", r.stderr)


if __name__ == "__main__":
    unittest.main()
