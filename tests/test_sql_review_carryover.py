"""Issue 346: analyse offers one bulk carry-over for scope items bootstrap already confirmed."""
import hashlib
import json
import tempfile
import unittest

from test_sql_review_scripts import Project, SQL_V1, item, review_doc, run, scope_doc

SCOPE_ITEMS = dict(
    assumptions=[item("A1", "Only completed stays", rationale="Open stays have no discharge date."),
                 item("A2", "Months are calendar months", rationale="Dashboard convention.",
                      location={"lines": [5, 7]})],
    limitations=[item("L1", "Excludes transfers", rationale="Transfers are counted by the sending ward.")],
)


def draft_item(id_, text, rationale, lines=None):
    return {"id": id_, "text": text, "rationale": rationale,
            "location": {"lines": lines} if lines else None, "status": "candidate"}


class CarryOver(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.p = Project(self.tmp.name)
        self.sql = self.p.sql("q.sql", SQL_V1)
        self.d = self.p.review_dir("q")
        self.draft = self.d / "review.draft.json"
        self.draft.write_text(json.dumps(review_doc("q", "q.sql", assumptions=[
            draft_item("A1", "Only completed stays", "Open stays have no discharge date."),
            draft_item("A2", "Months are calendar months", "Dashboard convention.", [5, 7]),
            draft_item("A3", "Counts are per ward", "New in the SQL."),
        ], limitations=[
            draft_item("L1", "Excludes transfers", "Reworded rationale."),
        ])))

    def scope(self, baseline=SQL_V1, **over):
        self.p.write_json("q", "scope.json", scope_doc("q", "q.sql", **SCOPE_ITEMS, **over))
        if baseline is not None:
            (self.d / "scope.source.sql").write_text(baseline)

    def carryover(self, expected=0):
        r = run(["carryover", "q", str(self.draft)], self.p.root)
        self.assertEqual(r.returncode, expected, r.stdout + r.stderr)
        return json.loads(r.stdout) if expected == 0 else r

    def test_unchanged_sql_carries_over_every_matching_item(self):
        self.scope()
        out = self.carryover()
        self.assertTrue(out["sql_unchanged"])
        self.assertEqual(out["scope_revision"], 1)
        self.assertEqual([(c["id"], c["scope_id"], c["basis"]) for c in out["carry_over"]],
                         [("A1", "A1", "sql-unchanged"), ("A2", "A2", "sql-unchanged")])
        self.assertEqual(out["carry_over"][0]["rationale"], "Open stays have no discharge date.")
        self.assertEqual([(w["kind"], w["id"]) for w in out["walk"]], [("assumptions", "A3"), ("limitations", "L1")])

    def test_changed_sql_carries_over_only_items_whose_lines_are_unchanged(self):
        self.scope()
        self.sql.write_text(SQL_V1.replace("adm.stays", "adm.stays_v2"))  # line 2 only
        out = self.carryover()
        self.assertFalse(out["sql_unchanged"])
        self.assertEqual([(c["id"], c["basis"]) for c in out["carry_over"]], [("A2", "lines-unchanged")])
        why = {w["id"]: w["why"] for w in out["walk"]}
        self.assertIn("SQL changed", why["A1"])
        self.assertIn("differs", why["L1"])

    def test_changed_location_lines_are_walked(self):
        self.scope()
        self.sql.write_text(SQL_V1.replace("GROUP BY month", "GROUP BY month, ward"))  # line 7
        self.assertEqual(self.carryover()["carry_over"], [])

    def test_recorded_scope_sha_is_honoured_and_a_disagreeing_baseline_is_ignored(self):
        self.scope(baseline=None, sql_sha256=hashlib.sha256(SQL_V1.encode()).hexdigest())
        self.assertEqual(len(self.carryover()["carry_over"]), 2)
        self.scope(baseline="something else\n", sql_sha256="0" * 64)
        out = self.carryover()
        self.assertFalse(out["sql_unchanged"])
        self.assertEqual(out["carry_over"], [])

    def test_without_baseline_nothing_carries_over(self):
        self.scope(baseline=None)
        self.assertEqual(self.carryover()["carry_over"], [])

    def test_without_scope_every_item_is_walked(self):
        out = self.carryover()
        self.assertIsNone(out["scope_revision"])
        self.assertEqual(out["carry_over"], [])
        self.assertEqual(len(out["walk"]), 4)

    def test_errors(self):
        self.assertEqual(run(["carryover", "q"], self.p.root).returncode, 1)
        self.assertEqual(run(["carryover", "q", str(self.d / "nope.json")], self.p.root).returncode, 2)
        self.assertEqual(run(["carryover", "../x", str(self.draft)], self.p.root).returncode, 2)
        (self.d / "scope.json").write_text("{}")
        self.assertEqual(run(["carryover", "q", str(self.draft)], self.p.root).returncode, 4)


if __name__ == "__main__":
    unittest.main()
