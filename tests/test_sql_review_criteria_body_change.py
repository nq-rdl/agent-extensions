"""A criteria_status row carries across a SQL body change only when the change does not touch it.

A row states what the SQL does with a research criterion. The decided re-walk rule: after a change, walk
only the rows the diff touches, then put every other row in one carry question. A row with a recorded
location carries when the diff maps its lines unchanged (criteria-lines-unchanged). A row the change
touches is walked. A row with no location goes into the one carry question, and its answer is a fresh
confirmation, never a carried one. Publish refuses a row that claims a carry it cannot prove, and names
only the criterion id. A header-only change keeps the carry. The release table then shows the state the
engineer confirmed.

The rehearsal case: the age filter moves from 18 to 16, and the table must not say Applied for
"Aged 18 and over" without a new confirmation.
"""
import hashlib
import json
import shutil
import tempfile
import unittest
from pathlib import Path

try:  # `unittest discover -s tests` puts tests/ on sys.path; `-m unittest tests.x` does not
    from test_data_request_release import (FINGERPRINTS, RELEASE, SQLREVIEW, criterion, git, record,
                                           render_record, run, status_row, violations)
except ModuleNotFoundError:
    from tests.test_data_request_release import (FINGERPRINTS, RELEASE, SQLREVIEW, criterion, git, record,
                                                 render_record, run, status_row, violations)

LEAK_CANARY = "LEAK-CANARY"
SLUG = "sql__v1__adults"
SQL_PATH = "sql/v1/adults.sql"
BASIS = "criteria-unchanged"

HEADER = "/* assumptions:\n  - draft header\n*/\n"
BODY_18 = "SELECT p.patient_id, p.age_years\nFROM ed.patients p\nWHERE p.age_years >= 18;\n"
SQL_18 = HEADER + BODY_18
SQL_18_HEADER = HEADER.replace("draft header", "reworded header") + BODY_18     # header-only change
SQL_17 = SQL_18.replace(">= 18", ">= 17")
SQL_16 = SQL_18.replace(">= 18", ">= 16")

CRITERIA = [
    criterion("N1", "entry_event", "First emergency presentation"),
    criterion("I1", "inclusion", "Aged 18 and over " + LEAK_CANARY, applied_by="rdl"),
    criterion("D1", "data_element", "Age at presentation"),
]
STATUS_V1 = [
    status_row("N1", "applied"),
    status_row("I1", "applied"),
    status_row("D1", "delivered", reason="Recorded age " + LEAK_CANARY),
]


def sha(text):
    return hashlib.sha256(text.encode()).hexdigest()


class Base(unittest.TestCase):
    """A git project with the analyst's sidecar and revision 1 of the owning scope, at SQL_18."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.out = tempfile.TemporaryDirectory()
        self.addCleanup(self.out.cleanup)
        self.root = Path(self.tmp.name)
        git(self.root, "init", "-q", "-b", "main")
        git(self.root, "config", "user.email", "t@example")
        git(self.root, "config", "user.name", "t")
        self.assertEqual(run(SQLREVIEW, ["init"], self.root).returncode, 0)
        self.d = self.root / ".sqlreview/reviews" / SLUG
        self.d.mkdir(parents=True, exist_ok=True)
        self.draft = self.d / "scope.draft.json"
        self.fp = Path(self.out.name) / "fingerprints.json"
        self.fp.write_text(json.dumps(FINGERPRINTS))
        sidecar = {"schemaVersion": 2, "approval_number": "THHSAQUIRE-9042", "decisions": [], "open_questions": [],
                   "criteria": CRITERIA, "fingerprints": FINGERPRINTS}
        (self.root / "answers.intake.json").write_text(json.dumps(sidecar, indent=2))
        self.write_sql(SQL_18)
        self.publish(1, SQL_18, STATUS_V1)

    # --- helpers ----------------------------------------------------------------------------
    def write_sql(self, sql):
        p = self.root / SQL_PATH
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(sql)

    def scope(self, revision, sql, status):
        return {"schemaVersion": 1, "kind": "scope", "slug": SLUG, "sql_path": SQL_PATH, "title": "Adults",
                "revision": revision, "recorded_at": "2026-10-20T00:00:00Z", "recorded_by": "eng-login",
                "git_commit": None, "intent": "Adult emergency presentations.",
                "inputs": [{"name": "ed.patients", "description": "one row per patient"}],
                "outputs": [{"name": "patient_id", "description": "patient"}],
                "assumptions": [], "limitations": [], "open_questions": [],
                "sql_sha256": sha(sql), "criteria_status": status}

    def commit(self):
        """Hash-only reviews (#548): commit the sources and return HEAD for the draft's git_commit."""
        git(self.root, "add", "-A")
        if git(self.root, "status", "--porcelain"):
            git(self.root, "commit", "-q", "-m", "fixture sources")
        return git(self.root, "rev-parse", "HEAD")

    def draft_doc(self, revision, sql, status):
        return dict(self.scope(revision, sql, status), git_commit=self.commit())

    def publish(self, revision, sql, status, expected=0):
        self.draft.write_text(json.dumps(self.draft_doc(revision, sql, status)))
        r = run(SQLREVIEW, ["publish", SLUG, "scope", str(self.draft)], self.root)
        self.assertEqual(r.returncode, expected, r.stdout + r.stderr)
        return r

    def published(self):
        return json.loads((self.d / "scope.json").read_text())

    def carryforward(self, revision, sql, status):
        self.draft.write_text(json.dumps(self.draft_doc(revision, sql, status)))
        r = run(SQLREVIEW, ["carryforward", SLUG, "scope", str(self.draft)], self.root)
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        return json.loads(r.stdout)

    def carried(self, revision):
        """Every row of the published scope as carried into `revision`."""
        return [dict(r, carried_from_revision=revision - 1, carried_basis=BASIS)
                for r in self.published()["criteria_status"]]

    def reconfirmed(self, revision, **states):
        """Every row confirmed afresh at `revision`; `states` maps criterion -> replacement fields."""
        out = []
        for r in self.published()["criteria_status"]:
            r = {k: v for k, v in r.items() if k not in ("carried_from_revision", "carried_basis")}
            r.update(confirmed_revision=revision, confirmed_at="2026-10-21T00:00:00Z")
            r.update(states.get(r["criterion"], {}))
            out.append({k: v for k, v in r.items() if v is not None})
        return out

    def assert_refused(self, revision, sql, status):
        before = (self.d / "scope.json").read_bytes()
        r = self.publish(revision, sql, status, expected=4)
        text = r.stdout + r.stderr
        for cid in ("N1", "I1", "D1"):
            self.assertIn(f"{cid}: cannot carry the confirmation forward: the SQL body changed", text)
        self.assertIn("re-confirm for this revision", text)
        self.assertNotIn(LEAK_CANARY, text)
        self.assertNotIn("Aged 18", text)
        self.assertEqual((self.d / "scope.json").read_bytes(), before)
        return r

    def release_table(self, tag, sql):
        """Commit with a review current for `sql`, tag, and build the complete criteria table."""
        r = self.release_run(tag, sql)
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        table = json.loads(r.stdout)
        self.assertEqual(table["status"], "complete", table)
        return {row["id"]: row for row in table["rows"]}

    def release_run(self, tag, sql):
        """Commit with a review current for `sql`, tag, and run `release.sh criteria`."""
        self.draft.unlink(missing_ok=True)
        reviewed = self.commit()
        review = {"schemaVersion": 2, "kind": "review", "slug": SLUG, "sql_path": SQL_PATH, "title": "Adults",
                  "revision": 1, "recorded_at": "2026-10-21T00:00:00Z", "recorded_by": "eng-login",
                  "sql_sha256": sha(sql), "git_commit": reviewed, "git_dirty": False,
                  "purpose": "Adults.", "grain": "one row per patient",
                  "inputs": [{"name": "ed.patients", "description": "one row per patient"}],
                  "outputs": [{"name": "patient_id", "description": "patient"}],
                  "logic": [{"step": 1, "title": "Filter", "lines": [4, 6], "description": "age"}],
                  "assumptions": [], "limitations": [], "open_questions": [],
                  "changes": [{"revision": 1, "at": "2026-10-21T00:00:00Z", "by": "eng-login", "summary": "first"}]}
        (self.d / "review.json").write_text(json.dumps(review, indent=2))
        self.draft.unlink(missing_ok=True)
        git(self.root, "add", "-A")
        git(self.root, "commit", "-q", "-m", f"release {tag}")
        git(self.root, "tag", tag)
        return run(RELEASE, ["criteria", tag, "--fingerprints", str(self.fp)], self.root)


@unittest.skipUnless(shutil.which("jq") and shutil.which("git"), "sqlreview.sh needs jq and git")
class CriteriaBodyChange(Base):
    def test_body_change_puts_rows_without_a_location_in_the_one_carry_question(self):
        self.write_sql(SQL_16)
        draft = [{k: v for k, v in r.items() if not k.startswith("confirmed")} for r in STATUS_V1]
        out = self.carryforward(2, SQL_16, draft)
        self.assertFalse(out["sql_body_unchanged"])
        self.assertEqual([c for c in out["carry"] if c["kind"] == "criteria_status"], [])
        self.assertEqual(out["walk"], [])
        bulk = {b["id"]: b for b in out["bulk"]}
        self.assertEqual(set(bulk), {"N1", "I1", "D1"})
        for b in bulk.values():
            self.assertEqual(b["kind"], "criteria_status")
            self.assertEqual(b["why"], "the SQL body changed since revision 1")
        self.assertEqual({q["id"] for q in out["carry_question"]}, {"N1", "I1", "D1"})
        self.assertNotIn(LEAK_CANARY, json.dumps(out))
        self.assert_refused(2, SQL_16, self.carried(2))
        # The carry question's answer is a fresh confirmation for each row: publish passes.
        self.publish(2, SQL_16, self.reconfirmed(2))
        self.assertEqual({r["confirmed_revision"] for r in self.published()["criteria_status"]}, {2})

    def test_a_change_that_touches_one_located_row_walks_only_that_row(self):
        # SQL_18 lines: 4 SELECT (D1), 5 FROM (N1), 6 WHERE age filter (I1).
        where = {"N1": [5, 5], "I1": [6, 6], "D1": [4, 4]}
        located = [dict(r, location={"lines": where[r["criterion"]]}) for r in STATUS_V1]
        self.publish(2, SQL_18, [dict(r, confirmed_revision=2) for r in located])
        self.write_sql(SQL_16)
        out = self.carryforward(3, SQL_16, located)
        self.assertEqual([w["id"] for w in out["walk"]], ["I1"])
        self.assertEqual(out["bulk"], [])
        self.assertEqual({(c["id"], c["basis"]) for c in out["carry"]},
                         {("N1", "criteria-lines-unchanged"), ("D1", "criteria-lines-unchanged")})
        self.assertEqual({q["id"] for q in out["carry_question"]}, {"N1", "D1"})
        self.assertNotIn(LEAK_CANARY, json.dumps(out))
        sets = {c["id"]: c["set"] for c in out["carry"]}
        claim_all = [dict(r, **sets.get(r["criterion"], {"carried_from_revision": 2,
                                                        "carried_basis": "criteria-lines-unchanged"})) for r in located]
        r = self.publish(3, SQL_16, claim_all, expected=4)
        self.assertIn("I1: cannot carry", r.stdout + r.stderr)
        rows = [dict(r, **sets[r["criterion"]]) if r["criterion"] in sets
                else dict(r, confirmed_revision=3, confirmed_at="2026-10-21T00:00:00Z") for r in located]
        self.publish(3, SQL_16, rows)
        published = {r["criterion"]: r for r in self.published()["criteria_status"]}
        self.assertEqual(published["N1"]["carried_basis"], "criteria-lines-unchanged")
        self.assertEqual(published["I1"]["confirmed_revision"], 3)
        self.assertNotIn("carried_basis", published["I1"])

    def test_header_only_change_carries_as_before(self):
        self.write_sql(SQL_18_HEADER)
        out = self.carryforward(2, SQL_18_HEADER, STATUS_V1)
        self.assertTrue(out["sql_body_unchanged"])
        self.assertEqual(out["walk"], [])
        self.assertEqual({(c["id"], c["basis"]) for c in out["carry"]}, {("N1", BASIS), ("I1", BASIS), ("D1", BASIS)})
        self.publish(2, SQL_18_HEADER, self.carried(2))
        published = self.published()["criteria_status"]
        self.assertEqual({r["confirmed_revision"] for r in published}, {1})
        self.assertEqual({r["carried_basis"] for r in published}, {BASIS})

    def test_a_location_change_with_an_unchanged_body_needs_a_line_map_proof(self):
        # SQL_18 lines: 4 SELECT (D1), 5 FROM (N1), 6 WHERE age filter (I1).
        where = {"N1": [5, 5], "I1": [6, 6], "D1": [4, 4]}
        located = [dict(r, location={"lines": where[r["criterion"]]}) for r in STATUS_V1]
        self.publish(2, SQL_18, [dict(r, confirmed_revision=2) for r in located])
        # Same SQL. D1 moves to unrelated lines, I1 loses its location and N1 keeps it.
        moved = {"D1": {"location": {"lines": [5, 5]}}, "I1": {"location": None}}
        draft = [dict(r, **moved.get(r["criterion"], {})) for r in located]
        draft = [{k: v for k, v in r.items() if v is not None} for r in draft]
        cases = {"sql-unchanged": SQL_18, "header-only": SQL_18_HEADER}
        for name, sql in cases.items():
            with self.subTest(name):
                self.write_sql(sql)
                out = self.carryforward(3, sql, draft)
                self.assertTrue(out["sql_body_unchanged"])
                self.assertEqual({(c["id"], c["basis"]) for c in out["carry"]}, {("N1", BASIS)})
                self.assertEqual({w["id"] for w in out["walk"]}, {"D1", "I1"})
                claim = [dict(r, carried_from_revision=2, carried_basis=BASIS) for r in draft]
                r = self.publish(3, sql, claim, expected=4)
                text = r.stdout + r.stderr
                self.assertIn("D1: cannot carry", text)
                self.assertIn("I1: cannot carry", text)
                self.assertNotIn("N1: cannot carry", text)
                self.assertNotIn(LEAK_CANARY, text)
        # A header that shifts every line: the line map re-locates an unchanged range, so it still carries.
        shifted = "-- extra header line\n" + SQL_18
        self.write_sql(shifted)
        draft = [dict(r, location={"lines": [where[r["criterion"]][0] + 1] * 2}) for r in located]
        out = self.carryforward(3, shifted, draft)
        self.assertTrue(out["sql_body_unchanged"])
        self.assertEqual({c["id"] for c in out["carry"]}, {"N1", "I1", "D1"})

    def test_reconfirmed_state_after_a_body_change_reaches_the_release_table(self):
        self.write_sql(SQL_16)
        self.assert_refused(2, SQL_16, self.carried(2))
        reason = "Filter is 16 and over " + LEAK_CANARY
        self.publish(2, SQL_16, self.reconfirmed(2, I1={"state": "partially-applied", "reason": reason}))
        rows = self.release_table("0.1.0", SQL_16)
        self.assertEqual((rows["I1"]["state"], rows["I1"]["proposed_note"]),
                         ("partially-applied", "Partially applied: " + reason))
        self.assertEqual((rows["N1"]["state"], rows["N1"]["proposed_note"]), ("applied", "Applied"))
        self.assertEqual(self.published()["criteria_status"][1]["confirmed_revision"], 2)

    def test_rehearsal_age_filter_18_to_16_cannot_stay_applied_without_a_new_confirmation(self):
        # Three rescopes, each a body change: 18 to 17, 17 to 16, then one more clause on the 16 SQL.
        # No revision may carry I1 "applied" forward.
        steps = [SQL_17, SQL_16, SQL_16.replace(";\n", "\n  AND p.patient_id IS NOT NULL;\n")]
        for revision, sql in enumerate(steps, start=2):
            with self.subTest(revision=revision):
                self.write_sql(sql)
                out = self.carryforward(revision, sql, STATUS_V1)
                self.assertNotIn("I1", {c["id"] for c in out["carry"]})
                self.assertIn("I1", {w["id"] for w in out["walk"] + out["bulk"]})
                self.assert_refused(revision, sql, self.carried(revision))
                state = {"state": "not-applied", "reason": "Filter is below 18"} if revision == 4 else {}
                self.publish(revision, sql, self.reconfirmed(revision, I1=state))
        i1 = self.published()["criteria_status"][1]
        self.assertEqual((i1["state"], i1["confirmed_revision"]), ("not-applied", 4))
        self.assertNotIn("carried_from_revision", i1)
        rows = self.release_table("0.1.0", steps[-1])
        self.assertEqual((rows["I1"]["state"], rows["I1"]["proposed_note"]),
                         ("not-applied", "Not applied: Filter is below 18"))
        self.assertNotEqual(rows["I1"]["proposed_note"], "Applied")


@unittest.skipUnless(shutil.which("jq") and shutil.which("git"), "release.sh needs jq and git")
class ScopeStaleRelease(Base):
    """`release.sh criteria` holds as scope-stale when the SQL body at the tag differs from the body the owning
    scope recorded. The scope is never published again here, so only the release check can catch it."""

    def held(self, r):
        self.assertEqual(r.returncode, 10, r.stdout + r.stderr)
        table = json.loads(r.stdout)
        self.assertEqual((table["status"], table["held_reasons"]), ("held", ["scope-stale"]), table)
        self.assertEqual(table["scope"], {"slug": SLUG, "revision": 1})
        self.assertIn(f"criteria held: scope {SLUG} is stale (scope-stale)", r.stderr)
        self.assertIn("rescope with /data-request:bootstrap, then publish", r.stderr)
        return table

    def test_body_change_after_the_last_scope_publish_holds(self):
        self.write_sql(SQL_16)
        table = self.held(self.release_run("0.1.0", SQL_16))
        i1 = next(row for row in table["rows"] if row["id"] == "I1")
        self.assertEqual(i1["state"], "applied", "the stale state is shown, and the hold stops its release")

    def test_header_only_change_after_publish_does_not_hold(self):
        self.write_sql(SQL_18_HEADER)
        r = self.release_run("0.1.0", SQL_18_HEADER)
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertEqual(json.loads(r.stdout)["held_reasons"], [])
        self.assertNotIn("scope-stale", r.stderr)

    def test_rescope_and_publish_clears_the_hold_and_shows_the_reconfirmed_states(self):
        self.write_sql(SQL_16)
        self.held(self.release_run("0.1.0", SQL_16))
        self.publish(2, SQL_16, self.reconfirmed(2, I1={"state": "not-applied", "reason": "Filter is below 18"}))
        rows = self.release_table("0.1.1", SQL_16)
        self.assertEqual((rows["I1"]["state"], rows["I1"]["proposed_note"]),
                         ("not-applied", "Not applied: Filter is below 18"))
        self.assertEqual((rows["N1"]["proposed_note"], rows["D1"]["proposed_note"]), ("Applied", "Delivered"))

    def test_no_sql_or_criterion_value_is_printed(self):
        sql = SQL_18.replace(";\n", f"\n  AND p.site_code <> '{LEAK_CANARY}-SQL';\n")
        self.write_sql(sql)
        r = self.release_run("0.1.0", sql)
        table = self.held(r)
        self.assertNotIn(LEAK_CANARY, r.stderr)
        # The table copies each criterion's text into its row by design. Nothing else carries a value.
        self.assertNotIn(LEAK_CANARY + "-SQL", r.stdout)
        rest = dict(table, rows=[{k: v for k, v in row.items() if k not in ("text", "proposed_note")}
                                 for row in table["rows"]])
        self.assertNotIn(LEAK_CANARY, json.dumps(rest))

    def test_a_held_scope_stale_table_checks_on_a_draft_and_blocks_approval(self):
        self.write_sql(SQL_16)
        table = self.held(self.release_run("0.1.0", SQL_16))
        code, out = violations(record(tag="0.1.0", status="draft", criteria=table))
        self.assertEqual(code, 0, out)
        code, out = violations(record(tag="0.1.0", criteria=table))
        self.assertEqual(code, 4, out)
        self.assertIn("approved: criteria table held: scope-stale", out)
        body = render_record(record(tag="0.1.0", status="draft", criteria=table))
        self.assertEqual(body.returncode, 0, body.stderr)
        self.assertIn("Criteria table held: scope-stale", body.stdout)
        self.assertNotIn(LEAK_CANARY, body.stdout + body.stderr)


if __name__ == "__main__":
    unittest.main()
