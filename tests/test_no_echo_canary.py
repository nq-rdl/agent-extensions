"""No-echo canary: a LEAK-CANARY value fed through each input must not reach stdout, stderr or argv.

Each case writes a canary value into a request document, a SQL file or a release record, runs one
script command and checks every output channel. A jq and git wrapper on PATH logs the argv of each
call. Messages name the field and the rule, never the value. Fixed paths fail here on any leak.

Known cases skip and name their deferred fix, so they do not fail CI:
  F-4  values passed to jq on argv (--arg, --argjson, --rawfile names)
  F-6  `lint --ste` names the matched word
Intentional outputs stay allowed on stdout only: delta and impact SQL text, intake output,
carryforward and evidence output, and the release table text. stderr stays clean for them too.
Fake request numbers only (9xxx).
"""

import json
import os
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
S = REPO / "skills/data-request-setup/scripts"
SR, RL, RD = S / "sqlreview.sh", S / "release.sh", S / "recurring-decisions.sh"
GUARD = REPO / "hooks/data-request-guard.sh"
CANARY = "LEAK-CANARY"
FRAGS = ("LEAK-C", "CANARY")   # jq truncates long values in its errors, so a prefix counts too
APPROVAL = "THHSAQUIRE-9187"
F4 = "F-4 deferred: values passed to jq on argv (--arg, --argjson) are a later fix"
F6 = "F-6 deferred: lint --ste names the matched word, a later fix"


def seen(text):
    return any(f in (text or "") for f in FRAGS)


def git(cwd, *a):
    return subprocess.run(["git", *a], cwd=cwd, capture_output=True, text=True, check=True)


def item(i, text="Plain text", **o):
    d = {"id": i, "text": text, "rationale": "because", "location": None, "status": "confirmed",
         "confirmed_by": "eng-login", "confirmed_at": "2026-11-01T00:00:00Z", "confirmed_revision": 1}
    d.update(o)
    return d


def review(**o):
    d = {"schemaVersion": 1, "kind": "review", "slug": "q", "sql_path": "q.sql", "title": "T", "revision": 1,
         "recorded_at": "2026-11-01T00:00:00Z", "recorded_by": "eng-login", "sql_sha256": "0" * 64,
         "git_commit": None, "git_dirty": False, "purpose": "p", "inputs": [{"name": "a", "description": "b"}],
         "outputs": [{"name": "c", "description": "d"}], "grain": "g",
         "logic": [{"step": 1, "title": "t", "lines": [1, 1], "description": "d"}],
         "assumptions": [item("A1")], "limitations": [item("L1")], "open_questions": [],
         "changes": [{"revision": 1, "at": "2026-11-01T00:00:00Z", "by": "eng-login", "summary": "s"}]}
    d.update(o)
    return d


def scope(**o):
    d = {"schemaVersion": 1, "kind": "scope", "slug": "q", "sql_path": "q.sql", "title": "T", "revision": 1,
         "recorded_at": "2026-11-01T00:00:00Z", "recorded_by": "eng-login", "git_commit": None, "sql_sha256": None,
         "intent": "i", "inputs": [{"name": "a", "description": "b"}], "outputs": [{"name": "c", "description": "d"}],
         "assumptions": [item("A1")], "limitations": [], "open_questions": []}
    d.update(o)
    return d


STAMP = {"confirmed_by": "analyst-login", "confirmed_role": "analyst", "confirmed_at": "2026-11-01T00:00:00Z"}


def sidecar(text="Adults", approval=APPROVAL, reason="Narrowed"):
    return {"schemaVersion": 2, "approval_number": approval, "open_questions": [],
            "decisions": [{"id": "age", "topic": "cohort", "text": text, "rationale": "r", **STAMP}],
            "criteria": [{"id": "I1", "kind": "inclusion", "text": "Aged 18 " + text, **STAMP},
                         {"id": "E1", "kind": "exclusion", "text": "Old", **STAMP,
                          "withdrawn": {"reason": reason, "at": "2026-11-01"}}],
            "fingerprints": {k: "sha256:" + "a" * 64 for k in
                             ("cohort_entry_event", "inclusion_criteria", "exclusion_criteria", "requested_data_elements")}}


def release_record(**o):
    d = {"schemaVersion": 1, "kind": "release", "tag": "v1.0.0", "commit": "a" * 40, "status": "draft",
         "recorded_at": "2026-11-01T00:00:00Z", "recorded_by": "analyst-login", "evidence": [],
         "questions": [], "claims": [{"id": "C1", "section": "summary", "proposed": "p", "decision": "pending",
                                      "final": None, "sources": [{"kind": "file", "path": "q.sql", "ref": "v1.0.0"}]}]}
    d.update(o)
    return d


@unittest.skipUnless(shutil.which("jq") and shutil.which("git"), "the scripts need jq and git")
class Canary(unittest.TestCase):
    """One throwaway project per test, with an argv-logging jq and git first on PATH."""

    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="canary-"))
        self.addCleanup(shutil.rmtree, self.tmp, True)
        self.root = self.tmp / "proj"
        self.root.mkdir()
        self.bin = self.tmp / "bin"
        self.bin.mkdir()
        self.argv = self.tmp / "argv.log"
        for name in ("jq", "git"):
            w = self.bin / name
            w.write_text(f'#!/bin/sh\nprintf "%s\\n" "{name} $*" >> "{self.argv}"\nexec "{shutil.which(name)}" "$@"\n')
            w.chmod(0o755)
        git(self.root, "init", "-q")
        git(self.root, "config", "user.email", "t@example.org")
        git(self.root, "config", "user.name", "t")
        self.assertEqual(self.run_script(SR, "init").returncode, 0)
        self.argv.unlink(missing_ok=True)

    # --- helpers --------------------------------------------------------------------------------
    def run_script(self, script, *args, stdin=None):
        env = {k: v for k, v in os.environ.items() if not k.startswith("SQLREVIEW_")}
        env["PATH"] = f"{self.bin}{os.pathsep}{env['PATH']}"
        return subprocess.run(["bash", str(script), *map(str, args)], cwd=self.root, env=env,
                              input=stdin, capture_output=True, text=True, timeout=120)

    def write(self, rel, data):
        p = self.root / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(data if isinstance(data, str) else json.dumps(data, indent=2))
        return p

    def commit(self):
        git(self.root, "add", "-A")
        git(self.root, "commit", "-q", "-m", "x", "--allow-empty")

    def guard_write(self, rel, doc):
        ev = {"tool_name": "Write", "cwd": str(self.root),
              "tool_input": {"file_path": str(self.root / ".sqlreview" / rel), "content": json.dumps(doc)}}
        return self.run_script(GUARD, stdin=json.dumps(ev))

    def argv_text(self):
        return self.argv.read_text() if self.argv.exists() else ""

    def assertClean(self, r, exit_code=None, stdout=True, argv=True):
        """No canary on stderr, and on stdout and argv unless the case allows it there."""
        if exit_code is not None:
            self.assertEqual(r.returncode, exit_code, r.stdout + r.stderr)
        self.assertFalse(seen(r.stderr), "stderr leaks the canary: " + r.stderr)
        if stdout:
            self.assertFalse(seen(r.stdout), "stdout leaks the canary: " + r.stdout)
        if argv:
            self.assertFalse(seen(self.argv_text()), "argv leaks the canary")

    def assertDenied(self, r):
        self.assertEqual(r.returncode, 0, r.stderr)
        decision = json.loads(r.stdout)["hookSpecificOutput"]
        self.assertEqual(decision["permissionDecision"], "deny", decision)
        self.assertClean(r)
        return decision["permissionDecisionReason"]

    # --- F-2: a jq failure prints a fixed line ---------------------------------------------------
    def test_check_jq_failure_prints_a_fixed_line(self):
        r = self.run_script(SR, "check", self.write("d.json", review(sql_sha256=[CANARY])))
        self.assertClean(r, 4)
        self.assertEqual(r.stdout.strip(), "check failed to run")

    def test_guard_denies_a_failing_check_without_the_value(self):
        self.assertIn("check failed to run", self.assertDenied(
            self.guard_write("reviews/q/review.json", review(sql_sha256=[CANARY]))))

    def test_carryover_jq_failure(self):
        self.write(".sqlreview/reviews/q/scope.json", scope())
        self.assertClean(self.run_script(SR, "carryover", "q", self.write("d.json", review(assumptions=CANARY + " text"))), 4)

    def test_render_with_a_non_string_upstream_file(self):
        self.write(".sqlreview/reviews/q/review.json", review(assumptions=[item(
            "A1", upstream={"source": "analyst-intake", "file": [CANARY]})]))
        r = self.run_script(SR, "render", "q", "review")
        self.assertNotEqual(r.returncode, 0)
        self.assertClean(r, argv=False)  # argv: F-4

    def test_recurring_decisions_match_failure(self):
        self.assertClean(self.run_script(RD, "match", self.write("d.json", scope(assumptions=[item("A1", [CANARY])]))))

    # --- F-3: check names the field and the rule, never the value --------------------------------
    def test_check_status_value(self):
        r = self.run_script(SR, "check", self.write("d.json", review(assumptions=[item("A1", status=CANARY)])))
        self.assertClean(r, 4)
        self.assertIn("A1: status must be confirmed", r.stdout)

    def test_check_kind_value(self):
        r = self.run_script(SR, "check", self.write("d.json", review(kind=CANARY)))
        self.assertClean(r, 4)
        self.assertIn('kind must be "review" or "scope" or "lifts"', r.stdout)

    def test_check_schema_version_value(self):
        r = self.run_script(SR, "check", self.write("d.json", review(schemaVersion=CANARY)))
        self.assertClean(r, 4)
        self.assertIn("schemaVersion must be 1 or 2", r.stdout)

    def test_check_free_text_item_ids(self):
        dup = CANARY + " duplicate"
        doc = review(assumptions=[item(dup, status="pending"), item(dup)])
        r = self.run_script(SR, "check", self.write("d.json", doc))
        self.assertClean(r, 4)
        self.assertIn("duplicate id in assumptions: (invalid id)", r.stdout)

    def test_check_revision_fields(self):
        doc = review(revision=2, assumptions=[item("A1", confirmed_revision=CANARY)],
                     limitations=[item("L1", carried_from_revision=CANARY, carried_basis=CANARY)])
        self.assertClean(self.run_script(SR, "check", self.write("d.json", doc)), 4)

    def test_status_reason_schema_version_and_sql_path(self):
        self.write(".sqlreview/reviews/q/review.json", review(schemaVersion=CANARY, sql_path="/" + CANARY))
        for args in (("status", "--verbose"), ("status", "--json", "--verbose")):
            with self.subTest(args=args):
                r = self.run_script(SR, *args)
                self.assertClean(r, 0, argv=False)  # argv: status reads --arg values (F-4)
                self.assertIn("schemaVersion invalid", r.stdout)

    def test_guard_denies_a_bad_status_without_the_value(self):
        reason = self.assertDenied(self.guard_write("reviews/q/review.json",
                                                    review(assumptions=[item("A1", status=CANARY)])))
        self.assertIn("A1: status must be confirmed", reason)

    def test_guard_denies_an_explain_identity_without_the_key(self):
        reason = self.assertDenied(self.guard_write("reviews/q/explain.json", {CANARY: {"by": "a@b.org"}}))
        self.assertIn("(key).by: by must be a handle", reason)

    def test_release_check_claim_and_question_ids(self):
        doc = release_record(claims=[dict(release_record()["claims"][0], id=CANARY)] * 2,
                             questions=[{"id": CANARY, "text": "t", "sources": []}])
        r = self.run_script(RL, "check", "--stdin", stdin=json.dumps(doc))
        self.assertClean(r, 4)
        self.assertIn("claim id must be C<n>", r.stdout)
        self.assertIn("question id must be Q<n>", r.stdout)

    def test_release_check_raw_values(self):
        doc = release_record(schemaVersion=CANARY, kind=CANARY, status=CANARY)
        r = self.run_script(RL, "check", "--stdin", stdin=json.dumps(doc))
        self.assertClean(r, 4)
        for rule in ("schemaVersion must be 1", "kind must be release", "status must be draft or approved"):
            self.assertIn(rule, r.stdout)

    def test_guard_denies_a_release_record_without_the_value(self):
        doc = release_record(claims=[dict(release_record()["claims"][0], id=CANARY)])
        self.assertIn("claim id must be C<n>", self.assertDenied(self.guard_write("releases/v1.0.0/release.json", doc)))

    # --- F-1: a missing intake sidecar with a DRAFT prints nothing --------------------------------
    def test_intake_missing_file_never_prints_the_draft(self):
        r = self.run_script(SR, "intake", self.root / "absent.json", "1", self.write("draft.json", CANARY + "\n"))
        self.assertClean(r, 0)
        self.assertEqual(r.stdout, "")

    # --- F-5: unsafe paths and malformed header lines name no text --------------------------------
    def test_notes_malformed_header_names_the_line_only(self):
        sql = self.write("q.sql", "/*\nassumptions:\n  - Grain is one row\n" + CANARY + " stray\n*/\nSELECT 1;\n")
        r = self.run_script(SR, "notes", sql)
        self.assertClean(r, 4)
        self.assertIn("line 4: unexpected line in notes header", r.stderr)

    def test_carryforward_unsafe_sql_path(self):
        r = self.run_script(SR, "carryforward", "q", "review", self.write("d.json", review(sql_path="/" + CANARY)))
        self.assertClean(r, 2)
        self.assertIn("unsafe sql_path", r.stderr)

    # --- #548 late paths: move archive, materialize, discard-draft, publish from the archive -------
    def reviewed_project(self, **over):
        """A committed q.sql and a published review whose free-text fields all carry the canary."""
        self.write("q.sql", "SELECT 1;\n")
        self.commit()
        fp = json.loads(self.run_script(SR, "fingerprint", "q.sql").stdout)
        fp.pop("sql_path")
        doc = review(purpose=CANARY + " purpose", title=CANARY + " title", grain=CANARY + " grain",
                     assumptions=[item("A1", CANARY + " text", rationale=CANARY + " why")],
                     limitations=[item("L1", CANARY + " limit")], open_questions=[CANARY + " question?"], **fp)
        doc.update(over)
        self.write(".sqlreview/reviews/q/review.json", doc)
        return fp

    def test_materialize_refusals_name_no_value(self):
        self.reviewed_project()
        out = self.tmp / "out.sql"
        cases = (("q", "review", "9", out),                       # revision unavailable
                 ("q", "review", "1", self.root / "inside.sql"),   # output inside the git tree
                 ("q", "review", "1", "relative.sql"),             # output not absolute
                 ("q", "lifts", "1", out))                         # kind refused
        for args in cases:
            with self.subTest(args=args[1:3]):
                r = self.run_script(SR, "materialize", *args)
                self.assertNotEqual(r.returncode, 0)
                self.assertClean(r)
        # A history entry the check refuses, with canary values in every field.
        hist = self.root / ".sqlreview/reviews/q/history/review"
        hist.mkdir(parents=True)
        (hist / "1.json").write_text(json.dumps(review(slug=CANARY, kind=CANARY, sql_path="/" + CANARY,
                                                       git_commit=CANARY, sql_sha256=CANARY)))
        self.assertClean(self.run_script(SR, "materialize", "q", "review", "1", out))

    def test_materialize_and_delta_from_an_archive_with_free_text(self):
        fp = self.reviewed_project()
        hist = self.root / ".sqlreview/reviews/q/history/review"
        hist.mkdir(parents=True)
        shutil.copy(self.root / ".sqlreview/reviews/q/review.json", hist / "1.json")
        self.write("q.sql", "SELECT 2;\n")
        self.commit()
        out = self.tmp / "out.sql"
        r = self.run_script(SR, "materialize", "q", "review", "1", out)
        self.assertClean(r, 0, argv=False)  # argv: jq --arg values (F-4)
        self.assertEqual(out.read_text(), "SELECT 1;\n")
        self.assertClean(self.run_script(SR, "status", "--verbose"), 0, argv=False)
        self.assertClean(self.run_script(SR, "delta", "q"), stdout=False, argv=False)

    def test_discard_draft_never_reads_or_prints_the_draft(self):
        self.write(".sqlreview/reviews/q/review.draft.json", review(purpose=CANARY))
        r = self.run_script(SR, "discard-draft", "q", "review")
        self.assertClean(r, 0)
        self.assertFalse((self.root / ".sqlreview/reviews/q/review.draft.json").exists())
        self.write(".sqlreview/reviews/q/scope.draft.json", CANARY)
        (self.root / ".sqlreview/reviews/q/review.draft.json").mkdir()
        for kind in ("review", "scope"):
            with self.subTest(kind=kind):
                r = self.run_script(SR, "discard-draft", "q", kind)
                self.assertClean(r)
        self.assertClean(self.run_script(SR, "discard-draft", "q", "lifts"), 0)

    def test_move_archives_the_binding_without_echoing_values(self):
        self.reviewed_project()
        git(self.root, "mv", "q.sql", "r.sql")
        self.commit()
        r = self.run_script(SR, "move", "q.sql", "r.sql")
        self.assertClean(r, 0, argv=False)  # argv: jq --arg values (F-4)
        self.assertTrue((self.root / ".sqlreview/reviews/r/history/review/1.json").is_file())
        out = self.tmp / "out.sql"
        self.assertClean(self.run_script(SR, "materialize", "r", "review", "1", out), 0, argv=False)
        self.assertEqual(out.read_text(), "SELECT 1;\n")
        self.assertClean(self.run_script(SR, "move", "q.sql", "r.sql"))
        self.assertClean(self.run_script(SR, "status", "--json", "--verbose"), 0, argv=False)

    def test_publish_refusals_name_no_value(self):
        self.reviewed_project()
        draft = self.write(".sqlreview/reviews/q/review.draft.json",
                           review(revision=2, purpose=CANARY, title=CANARY, assumptions=[item("A1", CANARY)]))
        r = self.run_script(SR, "publish", "q", "review", draft)
        self.assertNotEqual(r.returncode, 0)
        self.assertClean(r, argv=False)  # argv: jq --arg values (F-4)

    # --- intentional outputs: allowed on stdout, never on stderr ---------------------------------
    def test_delta_and_impact_print_the_sql_text_by_design(self):
        self.write("q.sql", f"SELECT '{CANARY}';\n")
        self.commit()
        fp = json.loads(self.run_script(SR, "fingerprint", "q.sql").stdout)
        fp.pop("sql_path")
        self.write(".sqlreview/reviews/q/review.json", review(**fp))
        self.write("q.sql", f"SELECT '{CANARY}2';\n")
        self.commit()
        for cmd in ("delta", "impact"):
            with self.subTest(cmd=cmd):
                self.assertClean(self.run_script(SR, cmd, "q"), stdout=False, argv=False)

    def test_intake_output_by_design(self):
        r = self.run_script(SR, "intake", self.write("answers.intake.json", sidecar(CANARY)), "1")
        self.assertClean(r, 0, stdout=False, argv=False)
        self.assertTrue(seen(r.stdout), "intake copies the analyst's text by design")

    def test_carryforward_output_by_design(self):
        self.write("q.sql", "SELECT 1;\n")
        self.commit()
        r = self.run_script(SR, "carryforward", "q", "review", self.write("d.json", review(assumptions=[item("A1", CANARY)])))
        self.assertClean(r, stdout=False, argv=False)

    def test_release_evidence_output_by_design(self):
        self.write(".sqlreview/reviews/q/review.json", review(kind=CANARY))
        self.commit()
        git(self.root, "tag", "v1.0.0")
        self.assertClean(self.run_script(RL, "evidence", "v1.0.0"), stdout=False, argv=False)

    def test_release_table_text_by_design(self):
        self.write("answers.intake.json", sidecar(CANARY))
        self.write(".sqlreview/reviews/q/scope.json", scope(criteria_status=[
            {"criterion": "I1", "state": "applied", "confirmed_by": "e", "confirmed_at": "2026-11-01T00:00:00Z",
             "confirmed_revision": 1}]))
        self.commit()
        git(self.root, "tag", "v1.0.0")
        self.assertClean(self.run_script(RL, "criteria", "v1.0.0"), stdout=False, argv=False)

    # --- known and deferred ------------------------------------------------------------------------
    def criteria_draft(self, **kw):
        self.write("answers.intake.json", sidecar(**kw))
        self.write("q.sql", "SELECT 1;\n")
        self.commit()
        return self.run_script(SR, "criteria", self.write(".sqlreview/reviews/q/scope.draft.json", scope(criteria_status=[
            {"criterion": "I1", "state": "bogus", "confirmed_by": "e", "confirmed_at": "2026-11-01T00:00:00Z",
             "confirmed_revision": 1}])))

    def test_f4_criteria_values_on_argv(self):
        for kw in ({"text": CANARY}, {"approval": "THHSAQUIRE-" + CANARY}, {"reason": CANARY}):
            with self.subTest(**kw):
                self.assertClean(self.criteria_draft(**kw), 10, argv=False)
        self.skipTest(F4)

    def test_f4_render_values_on_argv(self):
        self.write(".sqlreview/reviews/q/review.json", review(assumptions=[item("A1", CANARY)]))
        self.assertClean(self.run_script(SR, "render", "q", "review"), 0, stdout=False, argv=False)
        self.skipTest(F4)

    def test_f6_lint_ste_matched_word(self):
        r = self.run_script(SR, "lint", "--ste", self.write("d.json", review(assumptions=[item("A1", f"It {CANARY}n't work")])))
        self.assertClean(r, 10, stdout=False, argv=False)
        self.skipTest(F6)

if __name__ == "__main__":
    unittest.main()
