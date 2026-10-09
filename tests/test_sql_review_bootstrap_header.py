"""#433: factual pre-publish evidence, not a semantic matcher or live agent pilot."""
import copy
import json
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

try:
    from test_sql_review_scripts import REPO, SCRIPT, SQL_V1, Project, item, run, scope_doc
except ModuleNotFoundError:
    from tests.test_sql_review_scripts import REPO, SCRIPT, SQL_V1, Project, item, run, scope_doc

HEADER = """/*
assumptions:
  - Actim Partus results use code 123
    rationale: Engineer selected the code
limitations:
  - A PAMG note cannot establish the PartoSure brand
    consequence: Brand attribution remains unknown
*/
"""


class BootstrapHeader(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.p = Project(self.tmp.name)
        self.sql = self.p.sql("q.sql", HEADER + SQL_V1)
        self.scope = scope_doc(slug="q", sql_path="q.sql", assumptions=[], limitations=[],
                               question_store="questions.json")
        self.scope.pop("open_questions")
        self.draft = self.p.write_json("q", "scope.draft.json", self.scope)
        self.qdoc = {"schemaVersion": 1, "kind": "questions", "slug": "q", "sql_path": "q.sql",
                     "questions": [
                         {"id": "Q7", "text": "Which ieMR codes hold an Actim Partus result?",
                          "applies": "scope", "owner": "analyst-login", "status": "open"},
                         {"id": "Q9", "text": "Can a PAMG note hit name PartoSure?",
                          "applies": "scope", "owner": None, "status": "open"}]}
        self.questions = self.p.write_json("q", "questions.draft.json", self.qdoc)

    def notes(self, *extra, script=SCRIPT):
        return subprocess.run(["bash", str(script), "notes", "q.sql", "--against", str(self.draft), *extra],
                              cwd=self.p.root, text=True, capture_output=True, timeout=60)

    def compared(self, *extra):
        r = self.notes("--questions", str(self.questions), *extra)
        self.assertEqual(r.returncode, 0, r.stderr)
        return json.loads(r.stdout)["scope_check"]

    def test_unmatched_items_have_header_id_lines_and_wording(self):
        out = self.compared()
        self.assertEqual([r["header_id"] for r in out["unmatched_header"]], ["HA1", "HL1"])
        self.assertEqual(out["unmatched_header"][0]["lines"], [3, 4])
        self.assertEqual(out["unmatched_header"][1]["kind"], "limitations")
        self.assertEqual(out["unmatched_header"][1]["text"], "A PAMG note cannot establish the PartoSure brand")

    def test_enq1219_style_pairs_keep_both_identities_without_inferred_settlement(self):
        out = self.compared()
        pairs = {(r["question"]["id"], r["header"]["header_id"]): r for r in out["question_checks"]}
        self.assertEqual(set(pairs), {("Q7", "HA1"), ("Q7", "HL1"), ("Q9", "HA1"), ("Q9", "HL1")})
        self.assertEqual(pairs["Q7", "HA1"]["question"]["text"], self.qdoc["questions"][0]["text"])
        self.assertEqual(pairs["Q9", "HL1"]["header"]["lines"], [6, 7])
        self.assertEqual(out["question_check_basis"], "semantic-review-required")
        self.assertNotIn("conflicts", out, "The helper cannot establish semantic settlement")

    def match_all(self):
        self.scope["assumptions"] = [item("A14", "Actim Partus results use code 123", rationale="Engineer selected the code")]
        self.scope["limitations"] = [item("L4", "A PAMG note cannot establish the PartoSure brand", rationale="Brand attribution remains unknown")]
        self.draft.write_text(json.dumps(self.scope))

    def test_clean_match_has_no_warning(self):
        self.match_all()
        self.qdoc["questions"] = []
        self.questions.write_text(json.dumps(self.qdoc))
        r = self.notes("--questions", str(self.questions))
        self.assertEqual(r.returncode, 0, r.stderr)
        out = json.loads(r.stdout)["scope_check"]
        self.assertEqual(out["unmatched_header"], [])
        self.assertEqual(out["rationale_differences"], [])
        self.assertEqual(out["question_checks"], [])
        self.assertEqual(r.stderr, "")

    def test_adding_a_scope_item_does_not_answer_the_question(self):
        self.match_all()
        out = self.compared()
        self.assertEqual(out["unmatched_header"], [])
        self.assertEqual(out["question_checks"][0]["header"]["match"]["id"], "A14")
        self.assertEqual(len(out["question_checks"]), 4)

    def test_same_text_different_rationale_is_reported(self):
        self.match_all()
        self.scope["limitations"][0]["rationale"] = "Await analyst answer to Q9; this is an implementation constraint, not an answer"
        self.draft.write_text(json.dumps(self.scope))
        out = self.compared()
        self.assertEqual([r["match"]["id"] for r in out["rationale_differences"]], ["L4"])

    def test_provisional_question_is_retained_and_read_only(self):
        self.match_all()
        self.scope["assumptions"][0]["rationale"] += "; implementation default only pending Q7"
        self.draft.write_text(json.dumps(self.scope))
        before = {p: p.read_bytes() for p in self.p.root.rglob("*") if p.is_file()}
        out = self.compared()
        self.assertEqual(out["question_checks"][0]["question"]["status"], "open")
        after = {p: p.read_bytes() for p in self.p.root.rglob("*") if p.is_file()}
        self.assertEqual(before, after)

    def test_explicit_provisional_boundary_publishes_without_answering_questions(self):
        self.match_all()
        self.scope["assumptions"][0]["text"] = "Implementation uses code 123 pending analyst answer Q7"
        self.scope["assumptions"][0]["rationale"] = "Engineer confirms this implementation default only; ieMR code mapping Q7 remains unanswered"
        self.scope["limitations"][0]["text"] = "Implementation does not assign a PartoSure brand pending analyst answer Q9"
        self.scope["limitations"][0]["rationale"] = "Engineer confirms this boundary only; PAMG brand attribution Q9 remains unanswered"
        self.sql.write_text("/*\nassumptions:\n  - " + self.scope["assumptions"][0]["text"] +
                            "\n    rationale: " + self.scope["assumptions"][0]["rationale"] +
                            "\nlimitations:\n  - " + self.scope["limitations"][0]["text"] +
                            "\n    consequence: " + self.scope["limitations"][0]["rationale"] + "\n*/\n" + SQL_V1)
        self.p.commit()
        fp = run(["fingerprint", "q.sql"], self.p.root)
        self.assertEqual(fp.returncode, 0, fp.stderr)
        self.scope.update(json.loads(fp.stdout))
        self.draft.write_text(json.dumps(self.scope))
        out = self.compared()
        self.assertEqual(out["unmatched_header"], [])
        self.assertEqual(out["rationale_differences"], [])
        for args in (["lint", str(self.draft)], ["publish", "q", "scope", str(self.draft)],
                     ["publish-questions", "q", str(self.questions)], ["render", "q", "scope"]):
            r = run(args, self.p.root)
            self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        saved = json.loads((self.draft.parent / "questions.json").read_text())
        self.assertEqual(saved, self.qdoc)
        self.assertTrue(all(q["status"] == "open" and "closed" not in q for q in saved["questions"]))
        rendered = (self.draft.parent / "scope.md").read_text()
        self.assertIn("Q7", rendered)
        self.assertIn("Q9", rendered)

    def test_closed_and_review_only_questions_are_not_scope_checks(self):
        self.qdoc["questions"][0].update(status="closed", closed={"answer": "Code 123", "by": "analyst-login", "at": "2026-09-29", "source": "request.md"})
        self.qdoc["questions"][1]["applies"] = "review"
        self.questions.write_text(json.dumps(self.qdoc))
        self.assertEqual(self.compared()["question_checks"], [])

    def test_shared_store_is_loaded_on_resume(self):
        self.p.write_json("q", "questions.json", self.qdoc)
        r = self.notes()
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertEqual(len(json.loads(r.stdout)["scope_check"]["question_checks"]), 4)

    def test_staged_questions_reject_lost_or_changed_published_history_before_output(self):
        published = copy.deepcopy(self.qdoc)
        published["questions"][1].update(status="closed", closed={
            "answer": "Brand is unknown", "by": "analyst-login", "at": "2026-09-29", "source": "request.md"})
        published["questions"][1]["decided"] = {
            "by": "requester-login", "role": "requester", "at": "2026-09-28", "source": "request.md"}
        published["questions"].append({"id": "Q11", "text": "Count transfers?", "applies": "review",
                                       "owner": None, "status": "open"})
        self.p.write_json("q", "questions.json", published)
        self.p.write_json("q", "scope.json", self.scope)
        bads = []
        for index in (0, 1, 2):
            bad = copy.deepcopy(published)
            del bad["questions"][index]
            bads.append(bad)
        for index, updates in ((0, {"id": "Q8"}), (0, {"text": "Different codes?"}),
                               (0, {"applies": "review"}), (1, {"owner": "other-login"}),
                               (1, {"closed": {**published["questions"][1]["closed"], "answer": "Changed"}}),
                               (1, {"decided": {**published["questions"][1]["decided"], "at": "2026-09-27"}})):
            bad = copy.deepcopy(published)
            bad["questions"][index].update(updates)
            bads.append(bad)
        bad = copy.deepcopy(published)
        bad["questions"][1].update(status="open")
        del bad["questions"][1]["closed"]
        bads.append(bad)
        bad = copy.deepcopy(published)
        bad["questions"].append({**published["questions"][1], "id": "Q10"})
        bads.append(bad)
        for bad in bads:
            with self.subTest(questions=bad["questions"]):
                self.questions.write_text(json.dumps(bad))
                before = {p: p.read_bytes() for p in self.p.root.rglob("*") if p.is_file()}
                r = self.notes("--questions", str(self.questions))
                self.assertEqual(r.returncode, 4, r.stdout + r.stderr)
                self.assertEqual(r.stdout, "")
                self.assertIn("history", r.stderr)
                self.assertEqual(before, {p: p.read_bytes() for p in self.p.root.rglob("*") if p.is_file()})

    def test_valid_staged_question_transition_matches_publisher(self):
        self.p.write_json("q", "questions.json", self.qdoc)
        self.p.write_json("q", "scope.json", self.scope)
        self.qdoc["questions"][0].update(status="closed", closed={
            "answer": "Code 123", "by": "analyst-login", "at": "2026-09-29", "source": "request.md"})
        self.qdoc["questions"][1]["owner"] = "analyst-login"
        self.qdoc["questions"].append({"id": "Q10", "text": "Which wards?", "applies": "scope",
                                       "owner": None, "status": "open"})
        self.questions.write_text(json.dumps(self.qdoc))
        out = self.compared()
        self.assertEqual({row["question"]["id"] for row in out["question_checks"]}, {"Q9", "Q10"})
        r = run(["publish-questions", "q", str(self.questions)], self.p.root)
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)

    def test_explicit_draft_cannot_bypass_invalid_published_store(self):
        for raw in ("{bad", json.dumps(dict(self.qdoc, slug="other", sql_path="other.sql"))):
            with self.subTest(raw=raw):
                self.p.write_json("q", "questions.json", {}).write_text(raw)
                r = self.notes("--questions", str(self.questions))
                self.assertEqual(r.returncode, 4, r.stdout + r.stderr)
                self.assertEqual(r.stdout, "")

    def test_explicit_draft_cannot_bypass_symlinked_published_store(self):
        store = self.draft.parent / "questions.json"
        store.symlink_to(self.questions)
        r = self.notes("--questions", str(self.questions))
        self.assertEqual(r.returncode, 2, r.stdout + r.stderr)
        self.assertEqual(r.stdout, "")

    def test_staged_history_is_checked_even_without_an_sql_header(self):
        self.sql.write_text(SQL_V1)
        self.p.write_json("q", "questions.json", self.qdoc)
        self.qdoc["questions"] = []
        self.questions.write_text(json.dumps(self.qdoc))
        r = self.notes("--questions", str(self.questions))
        self.assertEqual(r.returncode, 4, r.stdout + r.stderr)
        self.assertEqual(r.stdout, "")

    def test_installed_helpers_reject_truncated_question_drafts(self):
        self.p.write_json("q", "questions.json", self.qdoc)
        self.qdoc["questions"] = []
        self.questions.write_text(json.dumps(self.qdoc))
        for tree in (REPO / "plugins/data-request", REPO / "dist/codex/plugins/data-request"):
            with self.subTest(tree=tree), tempfile.TemporaryDirectory(prefix="installed question history ") as tmp:
                installed = Path(tmp) / "plugin with spaces"
                shutil.copytree(tree, installed)
                r = self.notes("--questions", str(self.questions), script=installed / "skills/setup/scripts/sqlreview.sh")
                self.assertEqual(r.returncode, 4, r.stdout + r.stderr)
                self.assertEqual(r.stdout, "")

    def test_declared_missing_store_is_not_silently_clean(self):
        r = self.notes()
        self.assertEqual(r.returncode, 4, r.stdout + r.stderr)
        self.assertIn("questions", r.stderr)
        self.assertEqual(r.stdout, "")

    def test_bad_or_wrongly_bound_question_draft_fails_without_output(self):
        for doc in ("{bad", json.dumps(dict(self.qdoc, slug="other", sql_path="other.sql"))):
            self.questions.write_text(doc)
            r = self.notes("--questions", str(self.questions))
            self.assertEqual(r.returncode, 4, r.stdout + r.stderr)
            self.assertEqual(r.stdout, "")

    def test_legacy_questions_are_projected_with_ids_but_shared_closure_wins(self):
        self.scope.pop("question_store")
        self.scope["open_questions"] = [self.qdoc["questions"][0]["text"]]
        self.draft.write_text(json.dumps(self.scope))
        r = self.notes()
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertEqual(json.loads(r.stdout)["scope_check"]["question_checks"][0]["question"]["id"], "Q1")
        self.qdoc["questions"][0].update(status="closed", closed={"answer": "Code 123", "by": "analyst-login", "at": "2026-09-29", "source": "request.md"})
        self.qdoc["questions"] = self.qdoc["questions"][:1]
        self.p.write_json("q", "questions.json", self.qdoc)
        self.assertEqual(json.loads(self.notes().stdout)["scope_check"]["question_checks"], [])

    def test_absent_header_produces_no_mismatch_and_malformed_fails(self):
        self.sql.write_text(SQL_V1)
        self.assertEqual(self.compared()["unmatched_header"], [])
        self.assertEqual(self.compared()["question_checks"], [])
        self.sql.write_text("/*\nassumptions:\n  - broken\n")
        r = self.notes("--questions", str(self.questions))
        self.assertEqual(r.returncode, 4, r.stdout + r.stderr)
        self.assertIn("unterminated", r.stderr)

    def test_no_initialised_project_is_required_and_installed_helpers_work(self):
        for tree in (REPO / "plugins/data-request", REPO / "dist/codex/plugins/data-request"):
            with self.subTest(tree=tree), tempfile.TemporaryDirectory(prefix="installed scope header ") as tmp:
                installed = Path(tmp) / "plugin with spaces"
                shutil.copytree(tree, installed)
                r = self.notes("--questions", str(self.questions), script=installed / "skills/setup/scripts/sqlreview.sh")
                self.assertEqual(r.returncode, 0, r.stderr)
                self.assertEqual(len(json.loads(r.stdout)["scope_check"]["question_checks"]), 4)
        shutil.rmtree(self.p.root / ".sqlreview")
        self.draft = self.p.root / "scope.draft.json"
        self.draft.write_text(json.dumps(self.scope))
        self.questions = self.p.root / "questions.draft.json"
        self.questions.write_text(json.dumps(self.qdoc))
        self.assertEqual(len(self.compared()["question_checks"]), 4)
        self.assertFalse((self.p.root / ".sqlreview").exists())

    def test_unrelated_pairs_are_not_classified_as_conflicts(self):
        self.qdoc["questions"][0]["text"] = "Which wards?"
        self.questions.write_text(json.dumps(self.qdoc))
        out = self.compared()
        self.assertEqual(out["question_checks"][0]["question"]["text"], "Which wards?")
        self.assertNotIn("warning", out["question_checks"][0])
        self.assertNotIn("conflict", out["question_checks"][0])

    def test_question_symlink_is_rejected(self):
        link = self.questions.with_name("linked.json")
        link.symlink_to(self.questions)
        r = self.notes("--questions", str(link))
        self.assertEqual(r.returncode, 2, r.stdout + r.stderr)


class BootstrapContract(unittest.TestCase):
    def test_prepublication_comparison_and_resolution_in_all_targets(self):
        for path in (REPO / "skills/data-request-bootstrap/SKILL.md",
                     REPO / "plugins/data-request/skills/bootstrap/SKILL.md",
                     REPO / "dist/codex/plugins/data-request/skills/bootstrap/SKILL.md"):
            with self.subTest(path=path):
                body = path.read_text()
                check = body.index('sqlreview.sh" notes')
                publish = body.index('sqlreview.sh" publish "$SLUG" scope')
                self.assertLess(check, publish)
                for phrase in ("--against", "--questions", "question_checks", "unmatched_header",
                               "both identities", "provisional", "Do not close", "semantic"):
                    self.assertIn(phrase, body)
                self.assertRegex(body, r"[/\$]data-request:fix")
                self.assertNotIn('if [ -f "<sql path>" ]', body)
                self.assertIn('sr_source_render HEAD "$SQL_PATH" "$T/current.sql"', body)
                self.assertIn("SQL-bound draft", body)
                self.assertIn("malformed", body)
                self.assertIn("no warning", body)

    def test_no_sql_still_allows_scope_publication(self):
        with tempfile.TemporaryDirectory() as tmp:
            p = Project(tmp)
            draft = p.write_json("q", "scope.draft.json", scope_doc(slug="q", sql_path="q.sql", sql_sha256=None))
            r = run(["publish", "q", "scope", str(draft)], p.root)
            self.assertEqual(r.returncode, 0, r.stderr)


if __name__ == "__main__":
    unittest.main()
