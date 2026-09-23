"""Issue 340: a scope framed against existing SQL, and provisional wording in confirmed items."""
import hashlib
import json
import tempfile
import unittest

from test_sql_review_scripts import Project, SQL_V1, SQL_V2, item, run, scope_doc


class ScopeFraming(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.p = Project(self.tmp.name)
        self.sql = self.p.sql("q.sql", SQL_V1)
        self.draft = self.p.review_dir("q") / "scope.draft.json"

    def publish(self, doc):
        self.draft.write_text(json.dumps(doc))
        return run(["publish", "q", "scope", str(self.draft)], self.p.root)

    def sha(self):
        return hashlib.sha256(self.sql.read_bytes()).hexdigest()

    def test_scope_without_sql_sha_still_publishes(self):
        self.assertEqual(self.publish(scope_doc("q", "q.sql")).returncode, 0)
        self.assertEqual(self.publish(scope_doc("q", "q.sql", revision=2, sql_sha256=None)).returncode, 0)

    def test_scope_sql_sha_must_be_a_digest(self):
        r = run(["check", "--stdin"], self.p.root, stdin=json.dumps(scope_doc("q", "q.sql", sql_sha256="abc")))
        self.assertEqual(r.returncode, 4)
        self.assertIn("scope sql_sha256 must be null or a SHA256", r.stdout)

    def test_publish_refuses_a_scope_framed_against_older_sql(self):
        framed = self.sha()
        self.sql.write_text(SQL_V2)  # edited mid-interview
        r = self.publish(scope_doc("q", "q.sql", sql_sha256=framed))
        self.assertEqual(r.returncode, 2)
        self.assertIn("re-put intent, inputs, outputs", r.stderr)
        self.assertFalse((self.p.root / ".sqlreview/reviews/q/scope.json").exists())
        self.assertEqual(self.publish(scope_doc("q", "q.sql", sql_sha256=self.sha())).returncode, 0)

    def test_publish_refuses_a_scope_sha_when_sql_is_gone(self):
        framed = self.sha()
        self.sql.unlink()
        r = self.publish(scope_doc("q", "q.sql", sql_sha256=framed))
        self.assertEqual(r.returncode, 2)
        self.assertIn("SQL is missing", r.stderr)


class Lint(unittest.TestCase):
    def lint(self, doc):
        with tempfile.TemporaryDirectory() as tmp:
            path = f"{tmp}/doc.json"
            with open(path, "w") as f:
                json.dump(doc, f)
            return run(["lint", path], tmp)

    def test_clean_document_exits_0(self):
        r = self.lint(scope_doc(assumptions=[item("A1", "Qualified lab values are included in min/max",
                                                  rationale="The engineer confirmed qualified values count.")]))
        self.assertEqual((r.returncode, r.stdout), (0, ""))

    def test_provisional_wording_in_confirmed_items_is_flagged(self):
        doc = scope_doc(
            assumptions=[item("A1", "Qualified lab values are included",
                              rationale="Proposed: exclude them; should be confirmed with the requester."),
                         item("A2", "Timezone is converted to local", rationale="Needs confirming (TBC).")],
            limitations=[item("L1", "Proposed cap of 90 days", rationale="Source retention.")],
        )
        r = self.lint(doc)
        self.assertEqual(r.returncode, 10)
        rows = [line.split("\t") for line in r.stdout.splitlines()]
        self.assertIn(["A1", "rationale", "proposed, should be confirmed"], rows)
        self.assertIn(["A2", "rationale", "needs confirming, tbc"], rows)
        self.assertIn(["L1", "text", "proposed"], rows)
        self.assertEqual(len(rows), 3)

    def test_unconfirmed_candidates_are_not_flagged(self):
        doc = scope_doc(assumptions=[item("A1", "x", rationale="proposed", status="candidate")])
        self.assertEqual(self.lint(doc).returncode, 0)

    def test_errors(self):
        with tempfile.TemporaryDirectory() as tmp:
            self.assertEqual(run(["lint", f"{tmp}/nope.json"], tmp).returncode, 2)
            with open(f"{tmp}/bad.json", "w") as f:
                f.write("{not json")
            self.assertEqual(run(["lint", f"{tmp}/bad.json"], tmp).returncode, 4)
            self.assertEqual(run(["lint"], tmp).returncode, 1)


if __name__ == "__main__":
    unittest.main()
