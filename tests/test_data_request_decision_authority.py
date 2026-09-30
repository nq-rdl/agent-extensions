"""#443 offline decision-authority contracts; not live agent/warehouse evidence.

Exercise all shipped trees: generic validation cannot detect technical choices
parked as analyst questions, scope creep or fabricated engineer provenance.
Executable scope/identity/carryforward enforcement remains in existing suites.
"""

import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
TREES = {"canonical": REPO / "skills",
         "claude": REPO / "plugins/data-request/skills",
         "codex": REPO / "dist/codex/plugins/data-request/skills"}


def text(tree, leaf, relative="SKILL.md"):
    source = f"data-request-{leaf}" if tree == "canonical" else leaf
    return " ".join((TREES[tree] / source / relative).read_text().split())


class DecisionAuthority(unittest.TestCase):
    def rule(self, tree):
        return text(tree, "guardrails", "references/decision-authority.rst")

    def test_shared_rule_is_discoverable_from_required_stages(self):
        for tree in TREES:
            for leaf in ("guardrails", "triage", "bootstrap", "draft"):
                with self.subTest(tree=tree, leaf=leaf):
                    entry = text(tree, leaf)
                    self.assertIn("Engineer decisions: proceed and flag", entry)
                    self.assertIn("decision-authority.rst", entry)

    def test_evidenced_technical_choices_do_not_wait_for_analyst_approval(self):
        choices = ("source and table choice", "join keys", "tie-breaks", "time zones",
                   "00200", "holding and placeholder codes", "null handling",
                   "column naming and order", "presentation", "one authorised probe")
        for tree in TREES:
            with self.subTest(tree=tree):
                rule = self.rule(tree)
                self.assertIn("proceed without waiting for the analyst", rule)
                for choice in choices:
                    self.assertIn(choice, rule)
                self.assertIn("not a new cohort filter", rule)
                self.assertIn("not a clinical definition", rule)

    def test_decision_origin_is_real_and_independent_of_formal_confirmation(self):
        for tree in TREES:
            with self.subTest(tree=tree):
                rule = self.rule(tree)
                for token in ("Engineer decision (<login>, <date>), flagged for the data analyst",
                              "actual engineer login", "decision date", "SQL header",
                              "record_assumption", "analyst hand-off", "decided", "source",
                              "Date-only", "never invent midnight", "display labels"):
                    self.assertIn(token, rule)
                self.assertIn("Never attribute an autonomous agent choice to a human", rule)
                self.assertIn("does not fill confirmation fields", rule)
                self.assertIn("answered human question", rule)

    def test_known_governance_blocks_but_unchecked_coverage_does_not(self):
        for tree in TREES:
            with self.subTest(tree=tree):
                rule = self.rule(tree)
                self.assertIn("known approval restriction or custodian decision", rule)
                self.assertIn("Unchecked approval alone is not a blocker", rule)
                self.assertIn("build requested identifiers and free text", rule)
                self.assertIn("at most one review limitation", rule)

    def test_cohort_expansion_is_not_an_engineer_default(self):
        for tree in TREES:
            with self.subTest(tree=tree):
                rule = self.rule(tree)
                self.assertIn("cohort change beyond the request", rule)
                self.assertIn("keep the requested cohort", rule)
                self.assertIn("do not add I71.8", rule)

    def test_released_output_row_count_changes_require_an_answer(self):
        for tree in TREES:
            with self.subTest(tree=tree):
                rule = self.rule(tree)
                self.assertIn("grain change that alters the row count of a released output", rule)
                self.assertIn("preserve the released grain", rule)
                self.assertIn("not a released-output grain change", rule)

    def test_unsupported_clinical_definition_stops_only_dependent_work(self):
        for tree in TREES:
            with self.subTest(tree=tree):
                rule = self.rule(tree)
                self.assertIn("unsupported clinical, research or business definition", rule)
                self.assertIn("do not invent a 30-day outcome", rule)
                self.assertIn("Stop only the dependent portion", rule)
                self.assertIn("continue independent work", rule)

    def test_requested_columns_do_not_expand_into_unrequested_ward_stay_list(self):
        for tree in TREES:
            with self.subTest(tree=tree):
                rule = self.rule(tree)
                for token in ("narrowest reading", "Deliver what was asked", "Offer extras",
                              "do not build them", "Admitting Ward and Facility Code",
                              "ward-stay list", "TWAA", "00200", "probe's population"):
                    self.assertIn(token, rule)

    def test_remaining_questions_are_batched_without_using_silence_as_approval(self):
        for tree in TREES:
            with self.subTest(tree=tree):
                rule = self.rule(tree)
                for token in ("one analyst message", "default and its evidence", "safe defaults",
                              "Silence is not approval", "Never implement a prohibited output"):
                    self.assertIn(token, rule)
                checks = text(tree, "triage", "references/checks.rst")
                self.assertNotIn("never as a decision", checks)
                self.assertNotIn("The request has more than one reasonable reading", checks)
                self.assertIn("engineer-owned technical choice is not a clarification blocker", checks)

    def test_status_and_handoff_distinguish_real_blockers_from_flagged_choices(self):
        for tree in TREES:
            with self.subTest(tree=tree):
                comments = text(tree, "triage", "references/comments.rst")
                for token in ("Blocked (cannot proceed)", "Proceeding on an engineer decision, flagged",
                              "class", "dependent portion", "login", "date", "evidence"):
                    self.assertIn(token, comments)
                handoff = text(tree, "triage", "references/handoff.rst")
                for token in ("Engineer decision (<login>, <date>), flagged for the data analyst",
                              "rationale", "SQL location", "evidence", "offered extras (not built)"):
                    self.assertIn(token, handoff)

    def test_review_drafting_preserves_optional_origin_not_confirmation(self):
        for tree in TREES:
            with self.subTest(tree=tree):
                analyse = text(tree, "analyse")
                for token in ("copy its optional `decided` object verbatim", "original actor",
                              "source", "date-only precision", "does not supply confirmation"):
                    self.assertIn(token, analyse)
                carry = text(tree, "analyse", "references/carry.rst")
                self.assertIn("optional ``decided``", carry)
                self.assertIn("separate from the new confirmer", carry)

    def test_triage_status_is_assessment_only_unless_execution_is_evidenced(self):
        for tree in TREES:
            with self.subTest(tree=tree):
                comments = text(tree, "triage", "references/comments.rst")
                for token in ("Status: Assessment only; no work executed in this run",
                              "Only use ``Proceeding on an engineer decision, flagged``",
                              "Omit ``Engineer decisions`` when no human decision is evidenced",
                              "Only include ``Independent work continuing`` for work actually executed",
                              "triage-only", "planned, not implemented",
                              "For an execution run, report the actual actions"):
                    self.assertIn(token, comments)
                self.assertNotIn("Status: Proceeding on an engineer decision, flagged", comments)

    def test_business_and_research_definitions_are_not_technical_defaults(self):
        for tree in TREES:
            with self.subTest(tree=tree):
                rule = self.rule(tree)
                for token in ("clinical, research or business definition", "length of stay",
                              "rate denominator", "qualifying business states",
                              "no executable invented default", "continue independent work"):
                    self.assertIn(token, rule)
                for leaf, relative in (("draft", "SKILL.md"), ("bootstrap", "SKILL.md"),
                                       ("triage", "references/checks.rst"),
                                       ("triage", "references/comments.rst")):
                    with self.subTest(leaf=leaf, relative=relative):
                        self.assertIn("requester-defined measure", text(tree, leaf, relative))

    def test_formal_scope_and_runtime_controls_are_not_bypassed(self):
        for tree in TREES:
            with self.subTest(tree=tree):
                bootstrap = text(tree, "bootstrap")
                self.assertIn("Never fill `confirmed_by`", bootstrap)
                self.assertIn("does not park the build for analyst approval", bootstrap)
                rule = self.rule(tree)
                for token in ("triage-only stays read-only", "warehouse", "runtime denial",
                              "report and stop", "no alternative-action retry", "dependency"):
                    self.assertIn(token, rule)


if __name__ == "__main__":
    unittest.main()
