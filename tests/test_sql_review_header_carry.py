"""#431: dated named header decisions are candidates; a human answer confirms them.

Real shell/git tests cover history proofs. Instruction contracts are not a live pilot.
"""
import copy
import hashlib
import json
import os
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

from test_sql_review_scripts import Project, REPO, SQL_V1, item, review_doc, run

R = "Engineer decision (engineer-login, 2026-09-24), flagged for the data analyst"
HEADER = "/*\nassumptions:\n  - Use discharged stays\n    rationale: " + R + "\n*/\n"
SQL = HEADER + SQL_V1


class HeaderCarry(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.p = Project(self.tmp.name)
        self.sql = self.p.sql("q.sql", SQL)
        self.draft = self.p.review_dir("q") / "review.draft.json"
        self.doc = review_doc("q", "q.sql", assumptions=[item("A1", "Use discharged stays", rationale=R,
            location={"lines": [8, 8]}, status="candidate", confirmed_by=None, confirmed_at=None,
            confirmed_revision=None)], limitations=[])
        self.commit("2026-09-24T12:00:00Z")

    def commit(self, at):
        env = dict(os.environ, GIT_AUTHOR_DATE=at, GIT_COMMITTER_DATE=at)
        subprocess.run(["git", "add", "q.sql"], cwd=self.p.root, check=True, capture_output=True)
        subprocess.run(["git", "commit", "-qm", "SQL decision"], cwd=self.p.root, env=env, check=True, capture_output=True)
        return subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=self.p.root, text=True).strip()

    def notes(self, actor="engineer-login", refresh=True):
        if refresh:
            self.doc["sql_sha256"] = hashlib.sha256(self.sql.read_bytes()).hexdigest()
        self.draft.write_text(json.dumps(self.doc))
        args = ["notes", str(self.sql), "--against", str(self.draft)]
        if actor is not None:
            args += ["--confirmed-by", actor]
        r = run(args, self.p.root)
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        return json.loads(r.stdout)

    def eligible(self):
        out = self.notes()
        self.assertEqual([i["id"] for i in out["header_carry_over"]], ["A1"], out)
        row = out["header_carry_over"][0]
        self.assertEqual(row["basis"], "header-decision")
        self.assertEqual(row["location"], self.doc["assumptions"][0]["location"])
        self.assertEqual(row["decided"]["by"], "engineer-login")
        self.assertIn("git:", row["decided"]["source"])
        self.assertEqual(row["evidence"]["precision"], "date")
        self.assertEqual(self.doc["assumptions"][0]["status"], "candidate")
        return row

    def walked(self, actor="engineer-login", refresh=True):
        out = self.notes(actor, refresh)
        self.assertEqual(out["header_carry_over"], [])
        self.assertEqual([i["id"] for i in out["header_walk"]], ["A1"])

    def test_same_day_named_decision_is_candidate_without_confirmation(self):
        self.eligible()
        self.assertNotIn("confirmed_at", self.notes()["header_carry_over"][0])

    def test_actual_confirmer_required_and_recorder_is_not_used(self):
        self.walked("different-engineer")
        self.walked(None)
        self.doc["recorded_by"] = "technical-recorder"
        self.eligible()

    def test_other_body_lines_can_change_and_location_can_remap(self):
        self.sql.write_text(SQL.replace("SELECT month,", "SELECT calendar_month,"))
        self.commit("2026-09-25T10:00:00Z")
        self.eligible()
        self.sql.write_text(SQL.replace("WITH stays AS", "-- comment\nWITH stays AS"))
        self.doc["assumptions"][0]["location"] = {"lines": [9, 9]}
        self.eligible()

    def test_changed_governed_line_in_worktree_or_commit_walks(self):
        self.sql.write_text(SQL.replace("IS NOT NULL", "IS NULL"))
        self.walked()
        self.commit("2026-09-25T10:00:00Z")
        self.walked()

    def test_changed_then_reverted_governed_line_still_walks(self):
        self.sql.write_text(SQL.replace("IS NOT NULL", "IS NULL"))
        self.commit("2026-09-25T10:00:00Z")
        self.sql.write_text(SQL)
        self.commit("2026-09-26T10:00:00Z")
        self.walked()

    def test_changed_then_reverted_header_rationale_walks(self):
        self.sql.write_text(SQL.replace("flagged for", "to discuss with"))
        self.commit("2026-09-25T10:00:00Z")
        self.sql.write_text(SQL)
        self.commit("2026-09-26T10:00:00Z")
        self.walked()

    def test_draft_wording_and_provenance_edits_walk(self):
        original = copy.deepcopy(self.doc)
        for key, value in (("text", "Different assumption"), ("rationale", R + "."),
                           ("decided", {"by": "engineer-login", "role": "engineer", "at": "2026-09-24", "source": "tampered"})):
            self.doc = copy.deepcopy(original)
            self.doc["assumptions"][0][key] = value
            self.walked()

    def test_unnamed_generic_and_invalid_future_decisions_walk(self):
        for rationale in ("Engineer decision of 2026-09-24", "Engineer decision (someone-else, 2026-09-24)",
                          "Engineer decision (engineer-login, 2026-02-30)",
                          "Engineer decision (engineer-login, 2099-09-24)"):
            self.sql.write_text(SQL.replace(R, rationale))
            self.doc["assumptions"][0]["rationale"] = rationale
            self.walked()

    def test_legacy_named_date_format_is_supported(self):
        rationale = "Engineer decision by engineer-login on 2026-09-24"
        self.sql.write_text(SQL.replace(R, rationale))
        self.doc["assumptions"][0]["rationale"] = rationale
        self.commit("2026-09-24T13:00:00Z")
        self.eligible()

    def test_decision_precedes_first_record_or_has_ambiguous_location_walks(self):
        self.sql.write_text(SQL.replace("2026-09-24", "2026-09-23"))
        self.doc["assumptions"][0]["rationale"] = R.replace("2026-09-24", "2026-09-23")
        self.walked()
        self.sql.write_text(SQL)
        self.doc["assumptions"][0]["rationale"] = R
        self.doc["assumptions"][0]["location"] = None
        self.walked()

    def test_precise_time_before_record_walks(self):
        rationale = R.replace("2026-09-24", "2026-09-24T11:00:00Z")
        self.sql.write_text(SQL.replace(R, rationale))
        self.doc["assumptions"][0]["rationale"] = rationale
        self.commit("2026-09-24T13:00:00Z")
        self.walked()

    def test_wrong_sql_path_hash_or_missing_git_history_walks(self):
        self.doc["sql_path"] = "other.sql"
        self.walked()
        self.doc["sql_path"] = "q.sql"
        self.doc["sql_sha256"] = "0" * 64
        self.walked(refresh=False)
        subprocess.run(["git", "update-ref", "-d", "HEAD"], cwd=self.p.root, check=True, capture_output=True)
        self.walked()

    def test_shallow_history_walks(self):
        head = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=self.p.root, text=True).strip()
        (self.p.root / ".git/shallow").write_text(head + "\n")
        self.walked()

    def test_publish_reproves_basis_and_render_shows_it(self):
        row = self.eligible()
        self.doc["assumptions"][0].update(decided=row["decided"], carried_basis="header-decision",
            status="confirmed", confirmed_by="engineer-login", confirmed_at="2026-09-29T12:00:00Z", confirmed_revision=1)
        self.draft.write_text(json.dumps(self.doc))
        r = run(["publish", "q", "review", str(self.draft)], self.p.root)
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        r = run(["render", "q", "review"], self.p.root)
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertIn("header-decision", (self.draft.parent / "review.md").read_text())

    def test_observed_same_day_source_time_preserves_date_precision(self):
        row = self.eligible()
        self.assertEqual(row["decided"]["at"], "2026-09-24")
        self.assertEqual(row["evidence"]["committed_at"], "2026-09-24T12:00:00Z")

    def test_precise_cutoff_accepts_prior_source_and_rejects_later_source(self):
        rationale = R.replace("2026-09-24", "2026-09-24T14:00:00Z")
        self.sql.write_text(SQL.replace(R, rationale))
        self.doc["assumptions"][0]["rationale"] = rationale
        self.commit("2026-09-24T13:00:00Z")
        row = self.notes()["header_carry_over"]
        self.assertEqual(len(row), 1)
        self.assertEqual(row[0]["decided"]["at"], "2026-09-24T14:00:00Z")
        self.assertEqual(row[0]["evidence"]["precision"], "instant")

    def test_duplicate_elsewhere_cannot_prove_original_changed_range(self):
        self.sql.write_text(SQL.replace("GROUP BY month;", "GROUP BY month;\n  WHERE discharge_date IS NOT NULL"))
        self.commit("2026-09-25T10:00:00Z")
        self.sql.write_text(self.sql.read_text().replace("IS NOT NULL", "IS NULL", 1))
        self.walked()

    def test_relocated_unique_snippet_is_unproven(self):
        text = SQL.replace("  WHERE discharge_date IS NOT NULL\n", "")
        self.sql.write_text(text + "  WHERE discharge_date IS NOT NULL\n")
        self.doc["assumptions"][0]["location"] = {"lines": [12, 12]}
        self.walked()

    def test_repeated_governed_snippet_is_ambiguous_even_unchanged(self):
        self.sql.write_text(SQL + "  WHERE discharge_date IS NOT NULL\n")
        self.commit("2026-09-24T13:00:00Z")
        self.walked()

    def merge_branch(self, relevant=False, rename=False, revert=False):
        branch = subprocess.check_output(["git", "branch", "--show-current"], cwd=self.p.root, text=True).strip()
        subprocess.run(["git", "checkout", "-qb", "side"], cwd=self.p.root, check=True, capture_output=True)
        if rename:
            subprocess.run(["git", "mv", "q.sql", "renamed.sql"], cwd=self.p.root, check=True, capture_output=True)
        elif relevant:
            self.sql.write_text(SQL.replace("IS NOT NULL", "IS NULL"))
        else:
            (self.p.root / "unrelated.txt").write_text("side")
        env = dict(os.environ, GIT_AUTHOR_DATE="2026-09-25T10:00:00Z", GIT_COMMITTER_DATE="2026-09-25T10:00:00Z")
        subprocess.run(["git", "add", "-A"], cwd=self.p.root, check=True, capture_output=True)
        subprocess.run(["git", "commit", "-qm", "side"], cwd=self.p.root, env=env, check=True, capture_output=True)
        if revert:
            self.sql.write_text(SQL)
            subprocess.run(["git", "add", "q.sql"], cwd=self.p.root, check=True, capture_output=True)
            subprocess.run(["git", "commit", "-qm", "revert side SQL"], cwd=self.p.root, env=env, check=True, capture_output=True)
        subprocess.run(["git", "checkout", "-q", branch], cwd=self.p.root, check=True, capture_output=True)
        subprocess.run(["git", "merge", "--no-ff", "-m", "merge", "side"], cwd=self.p.root, env=env, check=True, capture_output=True)

    def test_unrelated_pr_merge_is_not_a_history_failure(self):
        self.merge_branch()
        self.eligible()

    def test_relevant_merge_walks_even_when_content_is_reverted(self):
        self.merge_branch(relevant=True)
        self.sql.write_text(SQL)
        self.commit("2026-09-26T10:00:00Z")
        self.walked()

    def test_alternate_parent_reverted_edit_is_not_hidden_by_merge_simplification(self):
        self.merge_branch(relevant=True, revert=True)
        self.walked()

    def test_display_role_label_is_not_a_handle(self):
        config = self.p.root / ".sqlreview/config.json"
        data = json.loads(config.read_text())
        data["roles"]["engineer"] = "engineer-login"
        config.write_text(json.dumps(data))
        self.walked(None)
        self.walked("Data Engineer")
        self.eligible()

    def test_missing_committed_object_cannot_be_skipped(self):
        blob = subprocess.check_output(["git", "rev-parse", "HEAD:q.sql"], cwd=self.p.root, text=True).strip()
        (self.p.root / ".git/objects" / blob[:2] / blob[2:]).unlink()
        self.walked()

    def test_rename_has_no_old_path_proof(self):
        self.merge_branch(rename=True)
        self.sql = self.p.root / "renamed.sql"
        self.doc["sql_path"] = "renamed.sql"
        self.walked()

    def test_limitations_and_mixed_deciders_are_partitioned(self):
        limitation = "Engineer decision (other-engineer, 2026-09-24)"
        new = HEADER.replace("*/", "limitations:\n  - Missing transfers\n    consequence: " + limitation + "\n*/") + SQL_V1
        self.sql.write_text(new)
        self.doc["assumptions"][0]["location"] = {"lines": [11, 11]}
        self.doc["limitations"] = [item("L1", "Missing transfers", rationale=limitation,
            location={"lines": [11, 11]}, status="candidate", confirmed_by=None,
            confirmed_at=None, confirmed_revision=None)]
        self.commit("2026-09-24T13:00:00Z")
        out = self.notes()
        self.assertEqual([r["id"] for r in out["header_carry_over"]], ["A1"])
        self.assertEqual([r["id"] for r in out["header_walk"]], ["L1"])
        out = self.notes("other-engineer")
        self.assertEqual([r["id"] for r in out["header_carry_over"]], ["L1"])

    def test_unanswered_bulk_candidate_cannot_publish(self):
        row = self.eligible()
        self.doc["assumptions"][0].update(decided=row["decided"], carried_basis="header-decision")
        self.draft.write_text(json.dumps(self.doc))
        r = run(["publish", "q", "review", str(self.draft)], self.p.root)
        self.assertEqual(r.returncode, 4, r.stdout + r.stderr)
        self.assertFalse((self.draft.parent / "review.json").exists())

    def answered(self):
        row = self.eligible()
        self.doc["assumptions"][0].update(decided=row["decided"], carried_basis="header-decision",
            status="confirmed", confirmed_by="engineer-login", confirmed_at="2026-09-29T12:00:00Z", confirmed_revision=1)
        self.draft.write_text(json.dumps(self.doc))
        return row

    def test_publish_rechecks_after_candidate_discovery(self):
        self.answered()
        self.sql.write_text(SQL.replace("IS NOT NULL", "IS NULL"))
        self.doc["sql_sha256"] = hashlib.sha256(self.sql.read_bytes()).hexdigest()
        self.draft.write_text(json.dumps(self.doc))
        r = run(["publish", "q", "review", str(self.draft)], self.p.root)
        self.assertEqual(r.returncode, 4, r.stdout + r.stderr)
        self.assertFalse((self.draft.parent / "review.json").exists())

    def publish_answered(self):
        self.answered()
        self.doc["schemaVersion"] = 2
        self.p.commit("commit review setup")
        fp = json.loads(run(["fingerprint", "q.sql"], self.p.root).stdout)
        self.doc["sql_body_sha256"] = fp["sql_body_sha256"]
        self.draft.write_text(json.dumps(self.doc))
        r = run(["publish", "q", "review", str(self.draft)], self.p.root)
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        r = run(["snapshot", "q", "q.sql"], self.p.root)
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        return self.draft.parent / "review.json"

    def test_header_only_republish_rejects_missing_changed_or_malformed_decision(self):
        dest = self.publish_answered()
        original = dest.read_bytes()
        snapshot = (dest.parent / "source.sql").read_bytes()
        for text in (SQL_V1, SQL.replace(R, R + " changed"), SQL.replace("rationale:", "unexpected:")):
            with self.subTest(text=text):
                self.sql.write_text(text)
                r = run(["publish", "q", "review", str(dest)], self.p.root)
                self.assertEqual(r.returncode, 4, r.stdout + r.stderr)
                self.assertEqual(dest.read_bytes(), original)
                self.assertEqual((dest.parent / "source.sql").read_bytes(), snapshot)

    def test_header_only_republish_allows_unchanged_decision_and_is_idempotent(self):
        dest = self.publish_answered()
        snapshot = (dest.parent / "source.sql").read_bytes()
        self.sql.write_text(SQL.replace("assumptions:", "assumptions: "))
        r = run(["publish", "q", "review", str(dest)], self.p.root)
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertIn("published header revision", r.stdout)
        published = json.loads(dest.read_text())
        self.assertEqual(published["revision"], 1)
        self.assertEqual(published["assumptions"], self.doc["assumptions"])
        self.assertEqual(len(published["header_revisions"]), 1)
        self.assertEqual((dest.parent / "source.sql").read_bytes(), snapshot)
        r = run(["publish", "q", "review", str(dest)], self.p.root)
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertIn("already published", r.stdout)
        self.sql.write_text(SQL_V1)
        r = run(["publish", "q", "review", str(dest)], self.p.root)
        self.assertEqual(r.returncode, 4, r.stdout + r.stderr)
        self.assertEqual(json.loads(dest.read_text()), published)

    def test_large_sql_body_does_not_travel_in_argv(self):
        self.sql.write_text(SQL + "SELECT '" + "x" * 160000 + "';\n")
        self.commit("2026-09-24T13:00:00Z")
        self.eligible()
        self.sql.write_text(self.sql.read_text().replace("IS NOT NULL", "IS NULL"))
        self.walked()

    def test_accumulated_history_does_not_travel_in_argv(self):
        for n in range(12):
            self.sql.write_text(SQL + "-- " + "x" * 16000 + str(n) + "\n")
            self.commit("2026-09-24T13:00:00Z")
        self.eligible()

    def new_decision(self, at="2026-09-26T10:00:00Z"):
        rationale = R.replace("2026-09-24", "2026-09-26")
        self.sql.write_text(SQL.replace(R, rationale))
        self.doc["assumptions"][0]["rationale"] = rationale
        return self.commit(at)

    def test_malformed_header_before_source_does_not_poison_new_decision(self):
        self.sql.write_text(SQL.replace("rationale:", "unexpected:"))
        self.commit("2026-09-25T10:00:00Z")
        source = self.new_decision()
        self.assertEqual(self.eligible()["evidence"]["commit"], source)
        self.sql.write_text(self.sql.read_text().replace("rationale:", "unexpected:"))
        self.commit("2026-09-27T10:00:00Z")
        self.new_decision("2026-09-28T10:00:00Z")
        self.walked()

    def test_relevant_merge_before_source_does_not_poison_new_decision(self):
        self.merge_branch(relevant=True)
        source = self.new_decision()
        self.assertEqual(self.eligible()["evidence"]["commit"], source)

    def test_nonmonotonic_time_before_source_does_not_poison_new_decision(self):
        self.sql.write_text(SQL.replace("SELECT month,", "SELECT calendar_month,"))
        self.commit("2026-09-23T10:00:00Z")
        source = self.new_decision()
        self.assertEqual(self.eligible()["evidence"]["commit"], source)
        self.sql.write_text(self.sql.read_text().replace("SELECT month,", "SELECT calendar_month,"))
        self.commit("2026-09-25T10:00:00Z")
        self.walked()

    def test_missing_pre_source_blob_cannot_hide_an_earlier_decision_source(self):
        blob = subprocess.check_output(["git", "rev-parse", "HEAD:q.sql"], cwd=self.p.root, text=True).strip()
        self.new_decision()
        (self.p.root / ".git/objects" / blob[:2] / blob[2:]).unlink()
        self.walked()

    def test_source_time_need_not_follow_irrelevant_pre_source_timestamp(self):
        self.sql.write_text(SQL.replace("SELECT month,", "SELECT calendar_month,"))
        self.commit("2026-09-28T10:00:00Z")
        source = self.new_decision()
        self.assertEqual(self.eligible()["evidence"]["commit"], source)

    def test_publish_rechecks_tampered_source(self):
        self.answered()
        self.doc["assumptions"][0]["decided"]["source"] = "git:" + "0" * 40 + ":q.sql#L3"
        self.draft.write_text(json.dumps(self.doc))
        r = run(["publish", "q", "review", str(self.draft)], self.p.root)
        self.assertEqual(r.returncode, 4, r.stdout + r.stderr)

    def test_independent_origin_is_not_replaced_to_gain_eligibility(self):
        origin = {"by": "analyst-login", "role": "analyst", "at": "2026-09-23", "source": "unlinked (verbal)"}
        self.doc["assumptions"][0]["decided"] = origin.copy()
        self.walked()
        self.assertEqual(self.doc["assumptions"][0]["decided"], origin)

    def test_missing_header_reports_walk_not_confirmation(self):
        self.sql.write_text(SQL_V1)
        self.walked()

    def test_missing_header_without_actor_retains_legacy_notes_shape(self):
        self.sql.write_text(SQL_V1)
        self.assertEqual(self.notes(None), {"present": False, "lines": None, "assumptions": [], "limitations": []})

    def test_later_carryforward_preserves_header_origin(self):
        origin = self.answered()["decided"]
        r = run(["publish", "q", "review", str(self.draft)], self.p.root)
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        r = run(["snapshot", "q", "q.sql"], self.p.root)
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.sql.write_text(SQL.replace("SELECT month,", "SELECT calendar_month,"))
        self.doc["revision"] = 2
        self.doc["sql_sha256"] = hashlib.sha256(self.sql.read_bytes()).hexdigest()
        self.draft.write_text(json.dumps(self.doc))
        r = run(["carryforward", "q", "review", str(self.draft)], self.p.root)
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.doc["assumptions"][0].update(json.loads(r.stdout)["carry"][0]["set"])
        self.assertEqual(self.doc["assumptions"][0]["decided"], origin)
        self.draft.write_text(json.dumps(self.doc))
        r = run(["publish", "q", "review", str(self.draft)], self.p.root)
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        r = run(["render", "q", "review"], self.p.root)
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertIn("recorded SQL header", (self.draft.parent / "review.md").read_text())

    def test_installed_copies_execute_discovery_publish_and_render_from_spaces(self):
        original = copy.deepcopy(self.doc)
        for tree in ("plugins/data-request/skills/setup", "dist/codex/plugins/data-request/skills/setup"):
            with self.subTest(tree=tree), tempfile.TemporaryDirectory(prefix="header carry installed ") as installed:
                self.doc = copy.deepcopy(original)
                target = Path(installed) / "setup"
                shutil.copytree(REPO / tree, target)
                script = target / "scripts/sqlreview.sh"
                self.notes()
                r = subprocess.run(["bash", str(script), "notes", "q.sql", "--against", str(self.draft),
                    "--confirmed-by", "engineer-login"], cwd=self.p.root, capture_output=True, text=True, timeout=60)
                self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
                self.assertEqual(json.loads(r.stdout)["header_carry_over"][0]["id"], "A1")
                self.answered()
                for args in (["publish", "q", "review", str(self.draft)], ["render", "q", "review"]):
                    r = subprocess.run(["bash", str(script), *args], cwd=self.p.root, capture_output=True, text=True, timeout=60)
                    self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
                self.assertIn("header-decision", (self.draft.parent / "review.md").read_text())

    def test_publish_refuses_forged_header_basis(self):
        self.doc["assumptions"][0].update(carried_basis="header-decision", status="confirmed",
            confirmed_by="different-engineer", confirmed_at="2026-09-29T12:00:00Z", confirmed_revision=1)
        self.notes()
        r = run(["publish", "q", "review", str(self.draft)], self.p.root)
        self.assertEqual(r.returncode, 4, r.stdout + r.stderr)
        self.assertFalse((self.draft.parent / "review.json").exists())


class Contracts(unittest.TestCase):
    def test_installed_analyse_batches_header_candidates_with_actual_answer(self):
        for tree, leaf in (("skills", "data-request-analyse"), ("plugins/data-request/skills", "analyse"),
                           ("dist/codex/plugins/data-request/skills", "analyse")):
            text = (REPO / tree / leaf / "SKILL.md").read_text()
            for phrase in ("header_carry_over", "--confirmed-by", "Carry over all", "header-decision", "answered"):
                self.assertIn(phrase, text)

    def test_future_authoring_names_actor_and_date(self):
        for leaf in ("draft", "fix", "guardrails"):
            text = (REPO / f"skills/data-request-{leaf}/SKILL.md").read_text()
            self.assertIn("Engineer decision (<login>, <date>), flagged for the data analyst", text)
