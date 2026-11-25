"""One definition of the store paths that never count as uncommitted source (review follow-up).

Status (`sr_load_uncommitted`) and fingerprint or a bound publish (`sr_source_clean`) must agree on which
paths under .sqlreview/ are records and which are source. The list lives once, in `sr_store_exempt`
(sqlreview-lib.sh). These tests pin that, for each exempt path, and that a path outside the list is still
source for both.
"""

import json
import re
import tempfile
import unittest

try:  # `unittest discover -s tests` puts tests/ on sys.path; `-m unittest tests.x` does not
    from test_sql_review_scripts import REPO, SQL_V1, Project, git, run, scope_doc
except ModuleNotFoundError:
    from tests.test_sql_review_scripts import REPO, SQL_V1, Project, git, run, scope_doc

SCRIPTS = REPO / "skills/data-request-setup/scripts"
SLUG, SQL = "reports__monthly", "reports/monthly.sql"
EXEMPT = (
    ".sqlreview/reviews/other/review.json",
    ".sqlreview/reviews/other/history/review/1.json",
    ".sqlreview/releases/v1.0.0/release.json",
    ".sqlreview/amendments/ZZTEST-90210.json",
    ".sqlreview/templates/note.json",
    ".sqlreview/ledger.json",
    ".sqlreview/.gitignore",
)
SOURCE = (".sqlreview/config.json.bak", ".sqlreview/other/x.json", ".sqlreview/reviewsx.json", "builder.conf")


class StoreExempt(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.p = Project(self.tmp.name)
        self.p.commit("init .sqlreview")
        self.p.sql(SQL, SQL_V1)
        self.p.commit("sql")
        r = run(["fingerprint", SQL], self.p.root)
        self.assertEqual(r.returncode, 0, r.stderr)
        fp = json.loads(r.stdout)
        fp.pop("sql_path")
        self.p.write_json(SLUG, "scope.json", scope_doc(SLUG, SQL, revision=3, **fp))
        self.p.commit("scope")
        self.baseline = self.next_hint()
        self.assertTrue(self.baseline.startswith("/data-request:analyse"), self.baseline)

    def next_hint(self):
        r = run(["status", "--json"], self.p.root)
        self.assertEqual(r.returncode, 0, r.stderr)
        return {row["slug"]: row for row in json.loads(r.stdout)["reviews"]}[SLUG]["next"]

    def write(self, rel):
        path = self.p.root / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("{}\n")

    def test_status_and_fingerprint_agree_for_each_exempt_path(self):
        for rel in EXEMPT:
            with self.subTest(rel):
                self.write(rel)
                self.assertEqual(self.next_hint(), self.baseline)
                r = run(["fingerprint", SQL], self.p.root)
                self.assertEqual(r.returncode, 0, r.stderr)
                (self.p.root / rel).unlink()

    def test_status_and_fingerprint_agree_for_each_source_path(self):
        for rel in SOURCE:
            with self.subTest(rel):
                self.write(rel)
                self.assertTrue(self.next_hint().startswith("commit the uncommitted source changes"))
                r = run(["fingerprint", SQL], self.p.root)
                self.assertEqual(r.returncode, 2, r.stdout)
                self.assertIn("uncommitted source changes", r.stderr)
                (self.p.root / rel).unlink()

    def test_a_renamed_exempt_record_is_exempt_at_both_ends(self):
        self.write(".sqlreview/reviews/other/review.json")
        self.p.commit("record")
        (self.p.root / ".sqlreview/amendments").mkdir(exist_ok=True)
        git(self.p.root, "mv", ".sqlreview/reviews/other/review.json", ".sqlreview/amendments/ZZTEST-90211.json")
        self.assertEqual(self.next_hint(), self.baseline)
        self.assertEqual(run(["fingerprint", SQL], self.p.root).returncode, 0)

    def test_the_exempt_list_is_written_once(self):
        # Three copies drifted before. The directory names appear in one case pattern, in sqlreview-lib.sh.
        hits = {}
        for script in sorted(SCRIPTS.glob("*.sh")):
            count = len(re.findall(r"/amendments/\*\|", script.read_text()))
            if count:
                hits[script.name] = count
        self.assertEqual(hits, {"sqlreview-lib.sh": 1})


if __name__ == "__main__":
    unittest.main()
