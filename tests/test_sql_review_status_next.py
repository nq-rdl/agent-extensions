"""`sqlreview.sh status` names the next command for each state (#514).

The next command comes from existing records only: the state, scope.json and its
scope.source.sql binding, the root answers.intake.json and explain.json. When a bound scope's
SQL body or its imported analyst intake changed after the scope, the next command is
bootstrap, to publish the next scope revision, then analyse.
"""

import hashlib
import json
import tempfile
import unittest

try:  # `unittest discover -s tests` puts tests/ on sys.path; `-m unittest tests.x` does not
    from test_sql_review_scripts import SQL_V1, SQL_V2, Project, review_doc, run, scope_doc
    from test_sql_review_hooks import PREFLIGHT, decision, env_for, run_hook
    from test_data_request_lifts import ledger
except ModuleNotFoundError:
    from tests.test_sql_review_scripts import SQL_V1, SQL_V2, Project, review_doc, run, scope_doc
    from tests.test_sql_review_hooks import PREFLIGHT, decision, env_for, run_hook
    from tests.test_data_request_lifts import ledger

SLUG, SQL = "reports__monthly", "reports/monthly.sql"
HEADER_V1 = "-- original header\n" + SQL_V1


def sha(text):
    return hashlib.sha256(text.encode()).hexdigest()


def sidecar(text="Include adults aged 18 and over."):
    return {"schemaVersion": 1, "approval_number": "THHSAQUIRE-042", "open_questions": [], "decisions": [
        {"id": "age", "topic": "cohort", "text": text, "rationale": "The requester studies adults.",
         "confirmed_by": "analyst-login", "confirmed_role": "analyst", "confirmed_at": "2026-09-29T10:00:00Z"}]}


class StatusNext(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.p = Project(self.tmp.name)

    def status(self):
        r = run(["status", "--json"], self.p.root)
        self.assertEqual(r.returncode, 0, r.stderr)
        return {row["slug"]: row for row in json.loads(r.stdout)["reviews"]}

    def row(self, slug=SLUG):
        return self.status()[slug]

    def scope(self, sql_text=None, revision=3, **over):
        """A scope bound to sql_text (None: framed before the SQL existed)."""
        if sql_text is not None:
            over.setdefault("sql_sha256", sha(sql_text))
            self.p.review_dir(SLUG).joinpath("scope.source.sql").write_text(sql_text)
        self.p.write_json(SLUG, "scope.json", scope_doc(SLUG, SQL, revision=revision, **over))

    def review(self):
        self.p.write_json(SLUG, "review.json", review_doc(SLUG, SQL))
        r = run(["snapshot", SLUG, SQL], self.p.root)
        self.assertEqual(r.returncode, 0, r.stderr)

    def assert_rescope(self, row, why, then):
        self.assertEqual(row["next"], f"{why} changed after scope revision 3: run /data-request:bootstrap {SQL} "
                                      f"to publish scope revision 4, then {then}")

    # --- scope only -------------------------------------------------------------------------
    def test_scoped_without_sql_names_draft_then_analyse(self):
        self.scope()
        self.assertEqual(self.row()["state"], "scoped")
        self.assertEqual(self.row()["next"], f"/data-request:draft to write {SQL}, then /data-request:analyse {SQL}")

    def test_scoped_with_unchanged_sql_names_analyse(self):
        self.p.sql(SQL, SQL_V1)
        self.scope(SQL_V1)
        self.assertEqual(self.row()["next"], f"/data-request:analyse {SQL} to review the SQL")

    def test_stale_scope_names_bootstrap_to_rescope_then_analyse(self):
        self.p.sql(SQL, SQL_V1)
        self.scope(SQL_V1)
        self.p.sql(SQL, SQL_V2)
        row = self.row()
        self.assertEqual(row["state"], "stale")
        self.assert_rescope(row, "The SQL", f"/data-request:analyse {SQL}")

    def test_scoped_header_only_names_bootstrap_header_revision(self):
        self.p.sql(SQL, HEADER_V1)
        self.scope(HEADER_V1)
        self.p.sql(SQL, HEADER_V1.replace("original", "corrected"))
        row = self.row()
        self.assertEqual(row["state"], "scoped-header-only")
        self.assertEqual(row["next"], f"/data-request:bootstrap {SQL} to record the header revision of the scope")

    # --- review with a scope ----------------------------------------------------------------
    def test_current_review_over_a_stale_scope_names_bootstrap_first(self):
        # The issue's case: the SQL changed and analyse ran again, but scope.json stayed behind.
        self.p.sql(SQL, SQL_V1)
        self.scope(SQL_V1)
        self.p.sql(SQL, SQL_V2)
        self.review()
        row = self.row()
        self.assertEqual(row["state"], "current")
        self.assert_rescope(row, "The SQL", f"/data-request:analyse {SQL} --update")

    def test_stale_review_and_stale_scope_names_bootstrap_first(self):
        self.p.sql(SQL, SQL_V1)
        self.scope(SQL_V1)
        self.review()
        self.p.sql(SQL, SQL_V2)
        row = self.row()
        self.assertEqual(row["state"], "stale")
        self.assert_rescope(row, "The SQL", f"/data-request:analyse {SQL} --update")

    def test_stale_review_over_an_unbound_scope_names_analyse_update(self):
        self.scope()                    # framed before the SQL existed: no binding to compare
        self.p.sql(SQL, SQL_V1)
        self.review()
        self.p.sql(SQL, SQL_V2)
        self.assertEqual(self.row()["next"], f"/data-request:analyse {SQL} --update")

    def test_header_only_change_keeps_the_scope_and_names_analyse(self):
        self.p.sql(SQL, HEADER_V1)
        self.scope(HEADER_V1)
        self.review()
        self.p.sql(SQL, HEADER_V1.replace("original", "corrected"))
        row = self.row()
        self.assertEqual(row["state"], "header-only")
        self.assertEqual(row["next"], f"/data-request:analyse {SQL} to record the header revision of the review")

    # --- review without a scope -------------------------------------------------------------
    def test_no_baseline_names_analyse_update(self):
        self.p.sql(SQL, SQL_V1)
        self.p.write_json(SLUG, "review.json", review_doc(SLUG, SQL))
        row = self.row()
        self.assertEqual(row["state"], "no-baseline")
        self.assertEqual(row["next"], f"/data-request:analyse {SQL} --update")

    def test_current_review_names_explain_resume_or_release(self):
        self.p.sql(SQL, SQL_V1)
        self.review()
        self.assertEqual(self.row()["next"], f"/data-request:explain {SQL} to walk the analyst through the review")
        marker = self.p.review_dir(SLUG) / "explain.json"
        base = {"sql_sha256": sha(SQL_V1), "review_revision": 1, "at": "2026-09-30T00:00:00Z", "by": "analyst-login"}
        marker.write_text(json.dumps(dict(base, completed=False, last_step="logic")))
        self.assertEqual(self.row()["next"], f"/data-request:explain {SQL} to resume the walkthrough")
        marker.write_text(json.dumps(dict(base, completed=True, last_step="outputs")))
        self.assertEqual(self.row()["next"],
                         "/data-request:release <candidate ref> after the analyst accepts the explained SQL")
        # A marker for an older snapshot does not count.
        marker.write_text(json.dumps(dict(base, sql_sha256=sha(SQL_V2), completed=True)))
        self.assertEqual(self.row()["next"], f"/data-request:explain {SQL} to walk the analyst through the review")

    # --- analyst intake ---------------------------------------------------------------------
    def import_intake(self):
        source = self.p.root / "answers.intake.json"
        source.write_text(json.dumps(sidecar()))
        r = run(["intake", str(source), "3"], self.p.root)
        self.assertEqual(r.returncode, 0, r.stderr)
        return source, json.loads(r.stdout)["assumptions"]

    def test_changed_intake_names_bootstrap_to_rescope(self):
        self.p.sql(SQL, SQL_V1)
        source, imported = self.import_intake()
        self.scope(SQL_V1, assumptions=scope_doc(revision=3)["assumptions"] + imported)
        self.assertEqual(self.row()["next"], f"/data-request:analyse {SQL} to review the SQL")
        source.write_text(json.dumps(sidecar("Include adults aged 16 and over.")))
        self.assert_rescope(self.row(), "The analyst intake", f"/data-request:analyse {SQL}")

    def test_intake_and_sql_changes_are_named_together(self):
        self.p.sql(SQL, SQL_V1)
        source, imported = self.import_intake()
        self.scope(SQL_V1, assumptions=scope_doc(revision=3)["assumptions"] + imported)
        self.review()
        self.p.sql(SQL, SQL_V2)
        source.write_text(json.dumps(sidecar("Include adults aged 16 and over.")))
        self.assert_rescope(self.row(), "The SQL and the analyst intake", f"/data-request:analyse {SQL} --update")

    def test_unreadable_intake_gives_no_signal(self):
        self.p.sql(SQL, SQL_V1)
        source, imported = self.import_intake()
        self.scope(SQL_V1, assumptions=scope_doc(revision=3)["assumptions"] + imported)
        source.write_text("{not json")
        self.assertEqual(self.row()["next"], f"/data-request:analyse {SQL} to review the SQL")

    # --- states without a workflow position -------------------------------------------------
    def test_missing_invalid_draft_and_lifts(self):
        self.p.sql("gone.sql", SQL_V1)
        self.p.write_json("gone", "review.json", review_doc("gone", "gone.sql"))
        run(["snapshot", "gone", "gone.sql"], self.p.root)
        (self.p.root / "gone.sql").unlink()
        self.p.review_dir("broken").joinpath("review.json").write_text("{}")
        self.p.write_json("planned", "scope.draft.json", scope_doc("planned", "planned.sql"))
        self.p.write_json("reviewing", "review.draft.json", review_doc("reviewing", "reviewing.sql"))
        self.p.sql("pipeline.py", 'db.query("SELECT 1")\n')
        doc = ledger()
        draft = self.p.write_json(doc["slug"], "lifts.draft.json", doc)
        self.assertEqual(run(["publish", doc["slug"], "lifts", str(draft)], self.p.root).returncode, 0)
        rows = self.status()
        self.assertEqual({s: (r["state"], r["next"]) for s, r in rows.items()}, {
            "gone": ("missing", "sqlreview.sh move 'gone.sql' <new path> if the SQL moved"),
            "broken": ("invalid", "run sqlreview.sh status --verbose to see why, then repair the documents"),
            "planned": ("draft", "resume /data-request:bootstrap to finish the scope draft"),
            "reviewing": ("draft", "resume /data-request:analyse to finish the review draft"),
            "pipeline.py": ("lifts", "/data-request:lift to close out the lift ledger"),
        })

    # --- output forms -----------------------------------------------------------------------
    def test_text_output_adds_a_next_column_after_lifts(self):
        self.scope()
        text = run(["status"], self.p.root).stdout
        self.assertRegex(text, rf"(?m)^{SLUG}\tscoped\t{SQL}\t3\tlifts=\{{\}}\tnext=/data-request:draft to write {SQL}, "
                               rf"then /data-request:analyse {SQL}$")
        self.assertEqual(len(text.splitlines()), 1)

    def test_preflight_hook_names_the_rescope_step(self):
        self.p.sql(SQL, SQL_V1)
        self.scope(SQL_V1)
        self.p.sql(SQL, SQL_V2)
        self.review()
        self.p.sql("other.sql", SQL_V1)
        self.p.write_json("other", "review.json", review_doc("other", "other.sql"))
        run(["snapshot", "other", "other.sql"], self.p.root)
        ctx = decision(run_hook(PREFLIGHT, {"cwd": str(self.p.root)}, env_for()))["additionalContext"]
        lines = ctx.splitlines()
        # One summary line, then one line for the review that needs action. The plain current
        # review needs no engineer action, so it adds no line.
        self.assertEqual(len(lines), 2, ctx)
        self.assertIn(f"- next for {SLUG} (current): The SQL changed after scope revision 3: "
                      f"run /data-request:bootstrap {SQL} to publish scope revision 4", lines[1])
        self.assertNotIn("other", ctx)


if __name__ == "__main__":
    unittest.main()
