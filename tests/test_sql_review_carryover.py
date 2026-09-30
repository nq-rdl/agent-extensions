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

    def test_changed_sql_carries_over_located_items_on_lines_and_intent_items_on_intent(self):
        self.scope()
        self.sql.write_text(SQL_V1.replace("adm.stays", "adm.stays_v2"))  # line 2 only
        out = self.carryover()
        self.assertFalse(out["sql_unchanged"])
        self.assertFalse(out["sql_body_unchanged"])
        # Before #366 A1 (no location in the scope) was walked on any SQL change.
        self.assertEqual([(c["id"], c["basis"]) for c in out["carry_over"]], [("A2", "lines-unchanged")])
        self.assertEqual([(c["id"], c["basis"]) for c in out["carry_over_intent"]], [("A1", "intent-unchanged")])
        why = {w["id"]: w["why"] for w in out["walk"]}
        self.assertEqual(set(why), {"A3", "L1"})
        self.assertIn("differs", why["L1"])

    def test_changed_location_lines_are_walked(self):
        self.scope()
        self.sql.write_text(SQL_V1.replace("GROUP BY month", "GROUP BY month, ward"))  # line 7
        out = self.carryover()
        self.assertEqual(out["carry_over"], [])
        self.assertEqual([(c["id"], c["basis"]) for c in out["carry_over_intent"]], [("A1", "intent-unchanged")])
        self.assertIn("A2", {w["id"] for w in out["walk"]})

    def test_recorded_scope_sha_is_honoured_and_a_disagreeing_baseline_is_ignored(self):
        self.scope(baseline=None, sql_sha256=hashlib.sha256(SQL_V1.encode()).hexdigest())
        self.assertEqual(len(self.carryover()["carry_over"]), 2)
        self.scope(baseline="something else\n", sql_sha256="0" * 64)
        out = self.carryover()
        self.assertFalse(out["sql_unchanged"])
        self.assertFalse(out["sql_body_unchanged"])
        # no evidence for located A2; A1 states intent (#366)
        self.assertEqual(out["carry_over"], [])
        self.assertEqual([(c["id"], c["basis"]) for c in out["carry_over_intent"]], [("A1", "intent-unchanged")])

    def test_scope_first_without_baseline_carries_over(self):
        # sql_sha256 null and no scope.source.sql: the scope was confirmed before the SQL existed.
        # Before #366 this pinned "nothing carries over", which is the scope-first bug.
        self.scope(baseline=None)
        out = self.carryover()
        self.assertTrue(out["scope_before_sql"])
        self.assertEqual(out["carry_over"], [])
        self.assertEqual([(c["id"], c["basis"]) for c in out["carry_over_intent"]],
                         [("A1", "scope-before-sql"), ("A2", "scope-before-sql")])

    def test_recorded_sha_without_baseline_walks_located_items_after_an_edit(self):
        self.scope(baseline=None, sql_sha256="0" * 64)
        out = self.carryover()
        self.assertFalse(out["scope_before_sql"])
        self.assertEqual(out["carry_over"], [])
        self.assertEqual([(c["id"], c["basis"]) for c in out["carry_over_intent"]], [("A1", "intent-unchanged")])

    def test_without_scope_every_item_is_walked(self):
        out = self.carryover()
        self.assertIsNone(out["scope_revision"])
        self.assertEqual(out["carry_over"], [])
        self.assertEqual(len(out["walk"]), 4)

    def test_decision_origin_survives_scope_to_review_confirmation(self):
        origin = {"by": "original-engineer", "role": "Data Engineer",
                  "at": "2026-09-14", "source": "https://example.com/decision/12"}
        for before_sql in (False, True):
            with self.subTest(before_sql=before_sql):
                scoped = dict(assumptions=[item("S1", "Keep the source grain", decided=origin)],
                              limitations=[item("S2", "Source omits transfers", decided=origin)])
                self.p.write_json("q", "scope.json", scope_doc(
                    "q", "q.sql", schemaVersion=2, **scoped))
                baseline = self.d / "scope.source.sql"
                if before_sql:
                    baseline.unlink(missing_ok=True)
                else:
                    baseline.write_text(SQL_V1)
                draft = review_doc("q", "q.sql", schemaVersion=2,
                    sql_sha256=hashlib.sha256(SQL_V1.encode()).hexdigest(),
                    assumptions=[draft_item("A1", "Keep the source grain", "because")],
                    limitations=[draft_item("L1", "Source omits transfers", "because")])
                # Full-review drafting preserves the scope origin before asking for carryover.
                # Main's #446 contract walks missing or changed provenance, even with equal prose.
                for kind in ("assumptions", "limitations"):
                    draft[kind][0]["decided"] = dict(origin)
                self.draft.write_text(json.dumps(draft))
                out = self.carryover()
                rows = out["carry_over_intent" if before_sql else "carry_over"]
                self.assertEqual(len(rows), 2)
                for row in rows:
                    self.assertEqual(row.get("decided"), origin)
                    # Carryover is a suggestion, not an answered confirmation.
                    self.assertNotIn("confirmed_by", row)
                    target = next(i for i in draft[row["kind"]] if i["id"] == row["id"])
                    target.update(decided=row["decided"], status="confirmed",
                                  confirmed_by="review-confirmer", confirmed_at="2026-09-30T04:00:00Z",
                                  confirmed_revision=1)
                self.draft.write_text(json.dumps(draft))
                result = run(["publish", "q", "review", str(self.draft)], self.p.root)
                self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
                published = json.loads((self.d / "review.json").read_text())
                for kind in ("assumptions", "limitations"):
                    self.assertEqual(published[kind][0]["decided"], origin)
                    self.assertEqual(published[kind][0]["confirmed_by"], "review-confirmer")
                (self.d / "review.json").unlink()

    def test_walk_keeps_matched_scope_origin_when_governed_sql_changed(self):
        origin = {"by": "original-engineer", "role": "Data Engineer",
                  "at": "2026-09-14T12:30:00Z", "source": "https://example.com/decision/13"}
        self.scope()
        scope = json.loads((self.d / "scope.json").read_text())
        scope["assumptions"][1]["decided"] = origin
        (self.d / "scope.json").write_text(json.dumps(scope))
        draft = json.loads(self.draft.read_text())
        draft["assumptions"][1]["decided"] = dict(origin)
        self.draft.write_text(json.dumps(draft))
        self.sql.write_text(SQL_V1.replace("GROUP BY month", "GROUP BY month, ward"))
        row = next(r for r in self.carryover()["walk"] if r["id"] == "A2")
        self.assertEqual(row.get("decided"), origin)
        self.assertNotIn("confirmed_by", row)

    def test_missing_or_changed_origin_is_walked_without_overwriting_draft_provenance(self):
        origin = {"by": "original-engineer", "role": "Data Engineer",
                  "at": "2026-09-14", "source": "https://example.com/decision/14"}
        self.scope()
        scope = json.loads((self.d / "scope.json").read_text())
        scope["assumptions"][0]["decided"] = origin
        (self.d / "scope.json").write_text(json.dumps(scope))
        for draft_origin in (None, dict(origin, by="other-engineer")):
            with self.subTest(draft_origin=draft_origin):
                draft = json.loads(self.draft.read_text())
                if draft_origin is not None:
                    draft["assumptions"][0]["decided"] = draft_origin
                self.draft.write_text(json.dumps(draft))
                out = self.carryover()
                self.assertNotIn("A1", {r["id"] for r in out["carry_over"]})
                row = next(r for r in out["walk"] if r["id"] == "A1")
                self.assertIn("provenance differs", row["why"])
                self.assertEqual(row.get("decided"), draft_origin)
                self.assertNotIn("confirmed_by", row)

    def test_carryover_does_not_invent_optional_decision_origin(self):
        self.scope()
        for row in self.carryover()["carry_over"]:
            self.assertNotIn("decided", row)

    def test_errors(self):
        self.assertEqual(run(["carryover", "q"], self.p.root).returncode, 1)
        self.assertEqual(run(["carryover", "q", str(self.d / "nope.json")], self.p.root).returncode, 2)
        self.assertEqual(run(["carryover", "../x", str(self.draft)], self.p.root).returncode, 2)
        (self.d / "scope.json").write_text("{}")
        self.assertEqual(run(["carryover", "q", str(self.draft)], self.p.root).returncode, 4)


if __name__ == "__main__":
    unittest.main()
