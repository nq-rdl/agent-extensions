"""Issue 434: decision provenance is independent of engineer confirmation.

Runs the real helper. Contract tests describe instructions, not live agent evidence.
Existing confirmation/carry tests did not cover a decider, missing sources, or source edits.
"""
import copy
import json
import tempfile
import unittest

from test_sql_review_scripts import Project, REPO, SQL_V1, item, review_doc, run, scope_doc

DECIDED = {"by": "requester-login", "role": "requester", "at": "2026-09-24",
           "source": "request.md#dated-decision"}


class Decisions(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.p = Project(self.tmp.name)
        self.p.sql("q.sql", SQL_V1)
        self.d = self.p.review_dir("q")
        self.draft = self.d / "draft.json"

    def call(self, command, doc, *args):
        self.draft.write_text(json.dumps(doc))
        return run([command, *args, str(self.draft)], self.p.root)

    def doc(self, kind="scope", **over):
        factory = scope_doc if kind == "scope" else review_doc
        return factory("q", "q.sql", assumptions=[item("A1", "Use supplied dates", decided=copy.deepcopy(DECIDED))], **over)

    def test_linked_decider_and_engineer_confirmation_are_independent(self):
        for kind in ("scope", "review"):
            with self.subTest(kind=kind):
                doc = self.doc(kind)
                doc["assumptions"][0]["confirmed_by"] = "engineer-login"
                r = self.call("check", doc)
                self.assertEqual(r.returncode, 0, r.stderr)

    def test_legacy_omitted_decision_remains_valid(self):
        self.assertEqual(self.call("check", scope_doc("q", "q.sql")).returncode, 0)

    def test_present_decision_requires_nonempty_strings(self):
        for value in (None, [], "verbal", {}, *[{**DECIDED, k: v} for k in DECIDED for v in (None, "", "  ", 42)]):
            with self.subTest(value=value):
                doc = self.doc()
                doc["assumptions"][0]["decided"] = value
                r = self.call("check", doc)
                self.assertEqual(r.returncode, 4, r.stdout + r.stderr)
                self.assertIn("decided", r.stdout + r.stderr)

    def test_decider_email_is_refused_without_echoing_it(self):
        doc = self.doc()
        doc["assumptions"][0]["decided"]["by"] = "private@example.com"
        r = self.call("check", doc)
        self.assertEqual(r.returncode, 4)
        self.assertNotIn("private@example.com", r.stderr)

    def test_unlinked_verbal_decision_is_valid_and_visible_in_both_reports(self):
        for kind in ("scope", "review"):
            with self.subTest(kind=kind):
                doc = self.doc(kind)
                doc["assumptions"][0]["decided"]["source"] = "unlinked (verbal)"
                self.assertEqual(self.call("check", doc).returncode, 0)
                self.p.write_json("q", kind + ".json", doc)
                r = run(["render", "q", kind], self.p.root)
                self.assertEqual(r.returncode, 0, r.stderr)
                text = (self.d / (kind + ".md")).read_text()
                for token in ("requester-login", "requester", "2026-09-24", "unlinked (verbal)", "UNLINKED"):
                    self.assertIn(token, text)
                self.assertIn("analyst-login", text)

    def test_render_escapes_decision_cells(self):
        doc = self.doc()
        doc["assumptions"][0]["decided"]["source"] = "doc | revision\nsection"
        self.p.write_json("q", "scope.json", doc)
        self.assertEqual(run(["render", "q", "scope"], self.p.root).returncode, 0)
        self.assertIn("doc &#124; revision<br>section", (self.d / "scope.md").read_text())

    def test_lint_flags_unlinked_decisions_even_on_candidates(self):
        for status in ("confirmed", "candidate"):
            doc = self.doc()
            doc["assumptions"][0].update(status=status, decided={**DECIDED, "source": "unlinked (verbal)"})
            r = self.call("lint", doc)
            self.assertEqual(r.returncode, 10, r.stdout + r.stderr)
            self.assertIn("A1\tdecided.source\t", r.stdout)

    def test_lint_flags_attributed_rationale_without_a_source(self):
        for rationale in ("The requester decided on 2026-09-24.", "Morgan gave this window.",
                          "The requester provided the dates.", "Decided by requester in a call."):
            doc = self.doc()
            del doc["assumptions"][0]["decided"]
            doc["assumptions"][0]["rationale"] = rationale
            r = self.call("lint", doc)
            self.assertEqual(r.returncode, 10, rationale + r.stdout + r.stderr)
            self.assertIn("decided.source", r.stdout)

    def test_lint_linked_or_unattributed_legacy_items_are_clean(self):
        doc = self.doc()
        doc["assumptions"][0]["rationale"] = "The requester decided the window."
        self.assertEqual(self.call("lint", doc).returncode, 0)
        self.assertEqual(self.call("lint", scope_doc("q", "q.sql")).returncode, 0)

    def test_ste_lint_keeps_four_column_provenance_warning(self):
        doc = self.doc()
        doc["assumptions"][0]["decided"]["source"] = "unlinked (verbal)"
        r = self.call("lint", doc, "--ste")
        self.assertEqual(r.returncode, 10, r.stdout + r.stderr)
        self.assertEqual(r.stdout.strip().split("\t")[:3], ["A1", "decided.source", "decision-source"])
        self.assertEqual(len(r.stdout.strip().split("\t")), 4)

    def test_limitation_provenance_is_validated(self):
        doc = self.doc("review")
        doc["limitations"][0]["decided"] = {**DECIDED, "by": ""}
        r = self.call("check", doc)
        self.assertEqual(r.returncode, 4)
        self.assertIn("L1: decided.by", r.stdout)

    def test_render_linked_decision_keeps_confirmation_visible(self):
        self.p.write_json("q", "scope.json", self.doc())
        self.assertEqual(run(["render", "q", "scope"], self.p.root).returncode, 0)
        text = (self.d / "scope.md").read_text()
        for token in ("Decision and source", "requester-login", "request.md#dated-decision", "analyst-login"):
            self.assertIn(token, text)
        self.assertNotIn("UNLINKED", text)

    def test_carryforward_walks_all_provenance_edits_in_scope_and_review(self):
        for kind in ("scope", "review"):
            for key in DECIDED:
                with self.subTest(kind=kind, field=key):
                    prior = self.doc(kind)
                    self.p.write_json("q", kind + ".json", prior)
                    draft = self.doc(kind, revision=2)
                    draft["assumptions"][0]["decided"][key] = "changed"
                    r = self.call("carryforward", draft, "q", kind)
                    self.assertEqual(r.returncode, 0, r.stderr)
                    out = json.loads(r.stdout)
                    self.assertIn("A1", [i["id"] for i in out["walk"]])
                    self.assertNotIn("A1", [i["id"] for i in out["carry"]])

    def test_carryforward_walks_added_and_removed_decision(self):
        for removing in (True, False):
            prior = self.doc()
            draft = self.doc(revision=2)
            del (draft if removing else prior)["assumptions"][0]["decided"]
            self.p.write_json("q", "scope.json", prior)
            out = json.loads(self.call("carryforward", draft, "q", "scope").stdout)
            self.assertEqual([i["id"] for i in out["walk"]], ["A1"])

    def test_carryover_preserves_decision_and_walks_changed_provenance(self):
        prior = self.doc()
        self.p.write_json("q", "scope.json", prior)
        draft = self.doc("review")
        r = self.call("carryover", draft, "q")
        self.assertEqual(r.returncode, 0, r.stderr)
        rows = json.loads(r.stdout)["carry_over_intent"]
        self.assertEqual(rows[0]["decided"], DECIDED)
        draft["assumptions"][0]["decided"]["source"] = "different.md"
        r = self.call("carryover", draft, "q")
        self.assertEqual([x["id"] for x in json.loads(r.stdout)["walk"]], ["A1", "L1"])

    def test_carryforward_preserves_provenance_and_publish_refuses_a_source_edit(self):
        self.p.write_json("q", "scope.json", self.doc())
        draft = self.doc(revision=2)
        r = self.call("carryforward", draft, "q", "scope")
        self.assertEqual(r.returncode, 0, r.stderr)
        output = json.loads(r.stdout)
        draft["assumptions"][0].update(output["carry"][0]["set"])
        self.assertEqual(draft["assumptions"][0]["decided"], DECIDED)
        draft["assumptions"][0]["decided"]["source"] = "different.md"
        r = run(["publish", "q", "scope", str(self.write(draft))], self.p.root)
        self.assertEqual(r.returncode, 4, r.stdout + r.stderr)
        self.assertIn("decided", r.stdout + r.stderr)

    def write(self, doc):
        self.draft.write_text(json.dumps(doc))
        return self.draft


class InstructionContract(unittest.TestCase):
    def test_authors_collect_decision_evidence_and_preserve_it(self):
        for stage in ("bootstrap", "analyse"):
            text = (REPO / f"skills/data-request-{stage}/SKILL.md").read_text()
            for phrase in ("decided", "unlinked (verbal)", "separate", "source"):
                self.assertIn(phrase, text)

    def test_triage_treats_unlinked_record_decisions_as_clarification_blockers(self):
        text = (REPO / "skills/data-request-triage/references/checks.rst").read_text()
        for phrase in ("scope.json", "review.json", "decided.source", "clarification blocker", "engineer confirmation"):
            self.assertIn(phrase, text)
