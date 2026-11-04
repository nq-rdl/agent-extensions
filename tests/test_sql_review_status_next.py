"""`sqlreview.sh status` names the next command for each state (#514).

The next command comes from existing records only: the state, scope.json and its
sql_sha256 binding, the root answers.intake.json and explain.json. When a bound scope's
SQL body or its imported analyst intake changed after the scope, the next command is
bootstrap, to publish the next scope revision, then analyse. Analyse fingerprints committed SQL
only, so uncommitted SQL is named for a commit first. Each fixture that expects a committed state
commits its SQL.
"""

import hashlib
import json
import os
import shutil
import tempfile
import unittest

try:  # `unittest discover -s tests` puts tests/ on sys.path; `-m unittest tests.x` does not
    from test_sql_review_scripts import SQL_V1, SQL_V2, Project, git, review_doc, run, scope_doc
    from test_sql_review_hooks import PREFLIGHT, decision, env_for, run_hook
    from test_data_request_lifts import ledger
except ModuleNotFoundError:
    from tests.test_sql_review_scripts import SQL_V1, SQL_V2, Project, git, review_doc, run, scope_doc
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
        # A real project commits its .sqlreview/config.json after setup. Fingerprint refuses any
        # other uncommitted source (#548), and status names it.
        self.p.commit("setup")

    def status(self):
        r = run(["status", "--json"], self.p.root)
        self.assertEqual(r.returncode, 0, r.stderr)
        return {row["slug"]: row for row in json.loads(r.stdout)["reviews"]}

    def sql(self, text, rel=SQL, commit=True):
        """Write the SQL and, unless commit is False, commit it, as analyse's fingerprint requires."""
        self.p.sql(rel, text)
        if commit:
            git(self.p.root, "add", "--", rel)
            git(self.p.root, "commit", "-q", "-m", f"sql {rel}")

    def row(self, slug=SLUG):
        return self.status()[slug]

    def fingerprint(self, rel=SQL):
        """Commit everything first, as a real project would, then fingerprint (#505)."""
        if git(self.p.root, "status", "--porcelain").stdout.strip():
            self.p.commit("record state before fingerprint")
        r = run(["fingerprint", rel], self.p.root)
        self.assertEqual(r.returncode, 0, r.stderr)
        fp = json.loads(r.stdout)
        fp.pop("sql_path")
        return fp

    def reviewed(self, slug, rel):
        """A review fingerprinted from committed SQL (#505)."""
        self.p.write_json(slug, "review.json", review_doc(slug, rel, **self.fingerprint(rel)))
        r = run(["snapshot", slug, rel], self.p.root)
        self.assertEqual(r.returncode, 0, r.stderr)

    def scope(self, sql_text=None, revision=3, **over):
        """A scope bound to sql_text by sql_sha256 and sql_body_sha256 (None: framed before the SQL existed)."""
        if sql_text is not None:
            fp = self.fingerprint()
            self.assertEqual(fp["sql_sha256"], sha(sql_text))
            over.setdefault("sql_sha256", fp["sql_sha256"])
            over.setdefault("sql_body_sha256", fp["sql_body_sha256"])
        self.p.write_json(SLUG, "scope.json", scope_doc(SLUG, SQL, revision=revision, **over))

    def review(self):
        self.reviewed(SLUG, SQL)

    def assert_rescope(self, row, why, then):
        self.assertEqual(row["next"], f"{why} changed after scope revision 3: run /data-request:bootstrap {SQL} "
                                      f"to publish scope revision 4, then {then}")

    # --- scope only -------------------------------------------------------------------------
    def test_scoped_without_sql_names_draft_then_analyse(self):
        self.scope()
        self.assertEqual(self.row()["state"], "scoped")
        self.assertEqual(self.row()["next"], f"/data-request:draft to write {SQL}, then /data-request:analyse {SQL}")

    def test_scoped_with_unchanged_sql_names_analyse(self):
        self.sql(SQL_V1)
        self.scope(SQL_V1)
        self.assertEqual(self.row()["next"], f"/data-request:analyse {SQL} to review the SQL")

    def test_stale_scope_names_bootstrap_to_rescope_then_analyse(self):
        self.sql(SQL_V1)
        self.scope(SQL_V1)
        self.sql(SQL_V2)
        row = self.row()
        self.assertEqual(row["state"], "stale")
        self.assert_rescope(row, "The SQL", f"/data-request:analyse {SQL}")

    def test_scoped_header_only_names_bootstrap_header_revision(self):
        self.sql(HEADER_V1)
        self.scope(HEADER_V1)
        self.sql(HEADER_V1.replace("original", "corrected"))
        row = self.row()
        self.assertEqual(row["state"], "scoped-header-only")
        self.assertEqual(row["next"], f"/data-request:bootstrap {SQL} to record the header revision of the scope")

    # --- review with a scope ----------------------------------------------------------------
    def test_current_review_over_a_stale_scope_names_bootstrap_first(self):
        # The issue's case: the SQL changed and analyse ran again, but scope.json stayed behind.
        self.sql(SQL_V1)
        self.scope(SQL_V1)
        self.sql(SQL_V2)
        self.review()
        row = self.row()
        self.assertEqual(row["state"], "current")
        self.assert_rescope(row, "The SQL", f"/data-request:analyse {SQL} --update")

    def test_stale_review_and_stale_scope_names_bootstrap_first(self):
        self.sql(SQL_V1)
        self.scope(SQL_V1)
        self.review()
        self.sql(SQL_V2)
        row = self.row()
        self.assertEqual(row["state"], "stale")
        self.assert_rescope(row, "The SQL", f"/data-request:analyse {SQL} --update")

    # --- a scope framed before the SQL existed (no SQL binding) ------------------------------
    def test_unbound_scope_with_sql_names_bootstrap_to_bind(self):
        self.scope()
        self.sql(SQL_V1)
        row = self.row()
        self.assertEqual(row["state"], "scoped")
        self.assertEqual(row["next"], f"/data-request:bootstrap {SQL} to bind the scope to the SQL, "
                                      f"then /data-request:analyse {SQL}")

    def test_current_review_over_an_unbound_scope_before_a_body_change_names_explain(self):
        self.scope()
        self.sql(SQL_V1)
        self.review()
        row = self.row()
        self.assertEqual(row["state"], "current")
        self.assertEqual(row["next"], f"/data-request:explain {SQL} to walk the analyst through the review")

    def test_stale_review_over_an_unbound_scope_names_the_rescope(self):
        self.scope()                    # framed before the SQL existed: no binding to compare
        self.sql(SQL_V1)
        self.review()
        self.sql(SQL_V2)
        row = self.row()
        self.assertEqual(row["state"], "stale")
        self.assertEqual(row["next"], f"The SQL changed after scope revision 3, which has no SQL binding: "
                                      f"run /data-request:bootstrap {SQL} to publish scope revision 4, "
                                      f"then /data-request:analyse {SQL} --update")

    # --- the SQL's working-tree state -------------------------------------------------------
    def test_uncommitted_sql_names_the_commit_before_analyse(self):
        self.sql(SQL_V1, commit=False)  # untracked
        self.scope(sql_sha256=sha(SQL_V1))  # bound by hash: fingerprint would commit the SQL first
        self.assertEqual(self.row()["next"], f"commit {SQL}, then /data-request:analyse {SQL} to review the SQL")
        git(self.p.root, "add", "--", SQL)  # staged is still not committed
        self.assertEqual(self.row()["next"], f"commit {SQL}, then /data-request:analyse {SQL} to review the SQL")

    def test_modified_sql_names_the_commit_before_analyse_update(self):
        self.sql(SQL_V1)
        self.review()
        self.sql(SQL_V2, commit=False)  # tracked, modified in the working tree
        row = self.row()
        self.assertEqual(row["state"], "stale")
        self.assertEqual(row["next"], f"commit {SQL}, then /data-request:analyse {SQL} --update")

    def test_committed_sql_names_analyse_alone(self):
        self.sql(SQL_V1)
        self.review()
        self.sql(SQL_V2)
        self.assertEqual(self.row()["next"], f"/data-request:analyse {SQL} --update")

    def test_uncommitted_sql_with_a_space_in_its_path(self):
        rel = "reports/monthly report.sql"
        self.sql(SQL_V1, rel=rel, commit=False)
        r = run(["slug", rel], self.p.root)
        self.assertEqual(r.returncode, 0, r.stderr)
        slug = r.stdout.strip()
        self.reviewed(slug, rel)  # fingerprint commits the SQL first (#505)
        self.sql(SQL_V2, rel=rel, commit=False)
        self.assertEqual(self.row(slug)["next"], f"commit {rel}, then /data-request:analyse {rel} --update")

    def test_uncommitted_unbound_and_rescope_lines_name_the_commit(self):
        self.scope()
        self.sql(SQL_V1, commit=False)
        # Bootstrap binds the scope to committed bytes, so the commit comes first (N1).
        self.assertEqual(self.row()["next"], f"commit {SQL}, then /data-request:bootstrap {SQL} to bind the scope "
                                             f"to the SQL, then /data-request:analyse {SQL}")

    def test_uncommitted_sql_after_a_rescope_names_the_commit_before_bootstrap(self):
        self.sql(SQL_V1)
        self.scope(SQL_V1)
        self.sql(SQL_V2, commit=False)
        self.assertEqual(self.row()["next"], f"The SQL changed after scope revision 3: commit {SQL}, then run "
                                             f"/data-request:bootstrap {SQL} to publish scope revision 4, "
                                             f"then /data-request:analyse {SQL}")

    def test_outside_a_git_repository_names_analyse_alone(self):
        with tempfile.TemporaryDirectory() as tmp:
            self.p = Project(tmp, git_repo=False)
            self.p.sql(SQL, SQL_V1)
            self.scope(sql_sha256=sha(SQL_V1))  # no git: bound by hash, not by fingerprint
            self.assertEqual(self.row()["next"], f"/data-request:analyse {SQL} to review the SQL")

    def test_one_git_call_per_status_run(self):
        for i in range(3):
            self.p.sql(f"r/q{i}.sql", SQL_V1)
            self.p.write_json(f"r__q{i}", "review.json", review_doc(f"r__q{i}", f"r/q{i}.sql"))
        log = self.p.root.parent / f"{self.p.root.name}-git.log"
        shims = self.p.root.parent / f"{self.p.root.name}-shims"
        shims.mkdir()
        real = shutil.which("git")
        (shims / "git").write_text(f'#!/bin/sh\nprintf "git\\n" >> "{log}"\nexec "{real}" "$@"\n')
        (shims / "git").chmod(0o755)
        self.addCleanup(shutil.rmtree, shims, True)
        self.addCleanup(lambda: log.unlink(missing_ok=True))
        r = run(["status", "--json"], self.p.root, env={"PATH": f"{shims}{os.pathsep}{os.environ['PATH']}"})
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertEqual(len(json.loads(r.stdout)["reviews"]), 3)
        self.assertEqual(log.read_text().split(), ["git"])

    # --- an empty project -------------------------------------------------------------------
    def test_empty_project_names_bootstrap_on_one_line(self):
        text = run(["status"], self.p.root).stdout
        self.assertEqual(text, "no reviews yet\tnext=/data-request:bootstrap <sql path> to scope the first SQL file\n")
        r = run(["status", "--json"], self.p.root)
        doc = json.loads(r.stdout)
        self.assertEqual((doc["reviews"], doc["next"]),
                         ([], "/data-request:bootstrap <sql path> to scope the first SQL file"))

    def test_a_project_with_reviews_has_no_project_next(self):
        self.scope()
        self.assertIsNone(json.loads(run(["status", "--json"], self.p.root).stdout)["next"])

    def test_header_only_change_keeps_the_scope_and_names_analyse(self):
        self.sql(HEADER_V1)
        self.scope(HEADER_V1)
        self.review()
        self.sql(HEADER_V1.replace("original", "corrected"))
        row = self.row()
        self.assertEqual(row["state"], "header-only")
        self.assertEqual(row["next"], f"/data-request:analyse {SQL} to record the header revision of the review")

    # --- review without a scope -------------------------------------------------------------
    def test_no_baseline_names_analyse_update(self):
        self.sql(SQL_V1)
        self.p.write_json(SLUG, "review.json", review_doc(SLUG, SQL))
        row = self.row()
        self.assertEqual(row["state"], "no-baseline")
        self.assertEqual(row["next"], f"/data-request:analyse {SQL} --update")

    def test_current_review_names_explain_resume_or_release(self):
        self.sql(SQL_V1)
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
    def commit_text(self, path, text):
        """The analyst commits the changed sidecar, so only the intake change is named."""
        path.write_text(text)
        self.p.commit("analyst intake")

    def import_intake(self):
        source = self.p.root / "answers.intake.json"
        source.write_text(json.dumps(sidecar()))
        r = run(["intake", str(source), "3"], self.p.root)
        self.assertEqual(r.returncode, 0, r.stderr)
        return source, json.loads(r.stdout)["assumptions"]

    def test_changed_intake_names_bootstrap_to_rescope(self):
        self.sql(SQL_V1)
        source, imported = self.import_intake()
        self.scope(SQL_V1, assumptions=scope_doc(revision=3)["assumptions"] + imported)
        self.assertEqual(self.row()["next"], f"/data-request:analyse {SQL} to review the SQL")
        self.commit_text(source, json.dumps(sidecar("Include adults aged 16 and over.")))
        self.assert_rescope(self.row(), "The analyst intake", f"/data-request:analyse {SQL}")

    def test_intake_and_sql_changes_are_named_together(self):
        self.sql(SQL_V1)
        source, imported = self.import_intake()
        self.scope(SQL_V1, assumptions=scope_doc(revision=3)["assumptions"] + imported)
        self.review()
        self.sql(SQL_V2)
        self.commit_text(source, json.dumps(sidecar("Include adults aged 16 and over.")))
        self.assert_rescope(self.row(), "The SQL and the analyst intake", f"/data-request:analyse {SQL} --update")

    def test_unreadable_intake_gives_no_signal(self):
        self.sql(SQL_V1)
        source, imported = self.import_intake()
        self.scope(SQL_V1, assumptions=scope_doc(revision=3)["assumptions"] + imported)
        self.commit_text(source, "{not json")
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
        self.sql(SQL_V1)
        self.scope(SQL_V1)
        self.sql(SQL_V2)
        self.review()
        self.p.sql("other.sql", SQL_V1)
        self.reviewed("other", "other.sql")
        ctx = decision(run_hook(PREFLIGHT, {"cwd": str(self.p.root)}, env_for()))["additionalContext"]
        lines = ctx.splitlines()
        # One summary line, then one line for the review that needs action. The plain current
        # review needs no engineer action, so it adds no line.
        self.assertEqual(len(lines), 2, ctx)
        self.assertIn(f"- next for {SLUG} (current): The SQL changed after scope revision 3: "
                      f"run /data-request:bootstrap {SQL} to publish scope revision 4", lines[1])
        self.assertNotIn("other", ctx)



class StatusSources(unittest.TestCase):
    """Status names the commit step for the same source set that fingerprint refuses (#548):
    every uncommitted path but the review records, with one git call per run."""

    setUp, status, sql, row, fingerprint, reviewed, scope, review = (
        StatusNext.setUp, StatusNext.status, StatusNext.sql, StatusNext.row, StatusNext.fingerprint,
        StatusNext.reviewed, StatusNext.scope, StatusNext.review)

    def fingerprint_refuses(self):
        r = run(["fingerprint", SQL], self.p.root)
        self.assertEqual(r.returncode, 2, r.stdout + r.stderr)
        self.assertIn("uncommitted source changes", r.stderr)

    def scoped_and_committed(self):
        self.sql(SQL_V1)
        self.scope(SQL_V1)
        self.p.commit("scope")

    def test_an_uncommitted_builder_names_the_commit_before_analyse(self):
        self.scoped_and_committed()
        self.p.sql("pipeline/build.py", "QUERY = 'x'\n")       # untracked builder
        self.assertEqual(self.row()["next"], "commit the uncommitted sources (builders, configuration, pins), "
                                             f"then /data-request:analyse {SQL} to review the SQL")
        self.fingerprint_refuses()

    def test_modified_pins_and_configuration_count(self):
        self.p.sql("pixi.toml", "[workspace]\n")
        self.scoped_and_committed()
        for rel in ("pixi.toml", ".sqlreview/config.json"):
            with self.subTest(rel=rel):
                path = self.p.root / rel
                before = path.read_text()
                path.write_text(before + "\n")
                self.assertTrue(self.row()["next"].startswith("commit the uncommitted sources"), self.row())
                self.fingerprint_refuses()
                path.write_text(before)

    def test_review_records_do_not_count(self):
        self.scoped_and_committed()
        self.p.write_json(SLUG, "scope.draft.json", scope_doc(SLUG, SQL, revision=4))
        (self.p.root / ".sqlreview" / "ledger.json").write_text("{}")
        self.assertEqual(self.row()["next"], f"/data-request:analyse {SQL} to review the SQL")

    def test_uncommitted_sql_and_other_sources_are_named_together(self):
        self.scoped_and_committed()
        self.sql(SQL_V2, commit=False)
        self.p.sql("pipeline/build.py", "QUERY = 'x'\n")
        # The commit comes before bootstrap, which binds the scope to committed bytes (N1).
        self.assertIn(f"commit {SQL} and the other uncommitted sources, then run /data-request:bootstrap {SQL} "
                      f"to publish scope revision 4, then /data-request:analyse {SQL}", self.row()["next"])


class StatusAmendment(unittest.TestCase):
    """An open amendment part (#534) gets one status line: its part ids and the next action."""

    setUp, status, sql, row, fingerprint, reviewed, scope, review = (
        StatusNext.setUp, StatusNext.status, StatusNext.sql, StatusNext.row, StatusNext.fingerprint,
        StatusNext.reviewed, StatusNext.scope, StatusNext.review)

    REC = "enq9177-falls"

    def record(self, parts, name=None):
        path = self.p.root / ".sqlreview" / "amendments" / f"{name or self.REC}.json"
        path.parent.mkdir(exist_ok=True)
        path.write_text(json.dumps({"schemaVersion": 1, "kind": "amendment", "parts": parts}))
        return path

    def part(self, pid, status, **fields):
        return {"id": pid, "status": status, "text": "LEAK-CANARY change", **fields}

    def text(self):
        r = run(["status"], self.p.root)
        self.assertEqual(r.returncode, 0, r.stderr)
        return r.stdout

    def test_a_handed_off_part_is_named_with_its_next_action(self):
        self.record([self.part("P1", "done", commit="a" * 40), self.part("P2", "handed off")])
        line = [ln for ln in self.text().splitlines() if ln.startswith("amendment ")]
        self.assertEqual(line, [f"amendment {self.REC}\thanded off: P2\tnext=the engineer comments done: P2 <commit> "
                                "or the analyst comments withdrawn: P2 <reason> on the deliverable PR, then "
                                f"/data-request:amend updates .sqlreview/amendments/{self.REC}.json before release"])
        j = json.loads(run(["status", "--json"], self.p.root).stdout)
        self.assertEqual(j["amendments"], [{"record": f".sqlreview/amendments/{self.REC}.json",
                                            "handed_off": ["P2"], "next": line[0].split("next=", 1)[1]}])

    def test_several_open_parts_use_the_generic_part_form(self):
        self.record([self.part("P2", "handed off"), self.part("P3", "handed off")])
        j = json.loads(run(["status", "--json"], self.p.root).stdout)
        self.assertEqual(j["amendments"][0]["handed_off"], ["P2", "P3"])
        self.assertIn("done: P<n> <commit>", j["amendments"][0]["next"])

    def test_closed_invalid_and_malformed_records_add_no_line(self):
        self.record([self.part("P1", "done", commit="a" * 40), self.part("P2", "withdrawn", reason="r")])
        self.record([self.part("LEAK-CANARY", "handed off")], name="enq9178-falls")
        (self.p.root / ".sqlreview" / "amendments" / "enq9179-falls.json").write_text("{LEAK-CANARY")
        text = self.text()
        self.assertNotIn("amendment ", text)
        self.assertNotIn("LEAK-C", text)
        self.assertEqual(json.loads(run(["status", "--json"], self.p.root).stdout)["amendments"], [])

    def test_the_preflight_hook_names_the_open_part(self):
        self.record([self.part("P2", "handed off")])
        for with_review in (False, True):
            with self.subTest(with_review=with_review):
                if with_review:
                    self.sql(SQL_V1)
                    self.review()
                ctx = decision(run_hook(PREFLIGHT, {"cwd": str(self.p.root)}, env_for()))["additionalContext"]
                self.assertIn(f"- next for .sqlreview/amendments/{self.REC}.json (handed off: P2): the engineer "
                              "comments done: P2 <commit>", ctx)
                self.assertNotIn("LEAK-C", ctx)

    def ledger(self, artifacts, stages_done=("intake", "amend")):
        """The triage ledger shows an amendment (the amend stage), with or without its record path."""
        entry = {"ticket": "rdl-service-desk/service-desk#9177", "enquiry": "ENQ9177", "stage": "release",
                 "stages_done": list(stages_done), "evidence_revision": {"ticket": "2026-11-01", "pr": "abc1234"},
                 "stage_evidence": {"intake": {"sources": ["ticket"], "artifacts": []}},
                 "decisions": [], "blockers": [], "depends_on": [], "next_action": "analyst-handle: release",
                 "verification": {"status": "unverified", "commands": [], "at": "2026-11-01"}}
        if "amend" in stages_done:
            entry["stage_evidence"]["amend"] = {"sources": ["pr"], "artifacts": artifacts}
        (self.p.root / ".sqlreview" / "ledger.json").write_text(json.dumps({"schemaVersion": 1, "entries": [entry]}))
        r = run(["ledger", "check", ".sqlreview/ledger.json"], self.p.root)
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)

    MISSING_NEXT = ("write it from the amendment hand-off comment on the deliverable PR "
                    "(/data-request:amend step 5)")

    def test_a_ledger_amendment_with_no_record_file_is_named(self):
        # N3: release holds on it, so status and preflight say so before release is tried.
        for name, artifacts, rec in (("record named", [{"path": f".sqlreview/amendments/{self.REC}.json",
                                                       "sha256": "0" * 64}], self.REC),
                                     ("no record named", [], "<request>")):
            with self.subTest(name):
                self.ledger(artifacts)
                lines = [ln for ln in self.text().splitlines() if ln.startswith("amendment ")]
                self.assertEqual(lines, [f"amendment {rec}\trecord missing\tnext={self.MISSING_NEXT}"])
                j = json.loads(run(["status", "--json"], self.p.root).stdout)
                self.assertEqual(j["amendments"], [{"record": f".sqlreview/amendments/{rec}.json", "handed_off": [],
                                                    "next": self.MISSING_NEXT, "missing": True}])
                ctx = decision(run_hook(PREFLIGHT, {"cwd": str(self.p.root)}, env_for()))["additionalContext"]
                self.assertIn(f"- next for .sqlreview/amendments/{rec}.json (record missing): {self.MISSING_NEXT}", ctx)

    def test_a_ledger_amendment_with_its_record_or_without_an_amendment_adds_no_line(self):
        self.ledger([{"path": f".sqlreview/amendments/{self.REC}.json", "sha256": "0" * 64}])
        self.record([self.part("P1", "done", commit="a" * 40)])
        self.assertNotIn("amendment ", self.text())
        self.ledger([], stages_done=("intake",))
        self.assertNotIn("amendment ", self.text())
        (self.p.root / ".sqlreview" / "ledger.json").write_text("{LEAK-CANARY")
        text = self.text()
        self.assertNotIn("amendment ", text)
        self.assertNotIn("LEAK-C", text)


if __name__ == "__main__":
    unittest.main()
