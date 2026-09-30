"""#445 approval posture: offline skill contracts, not model/classifier evidence.

Pin the build/review boundary that generic spec checks cannot see, including the
unchecked vs explicitly restricted cases and unchanged runtime authorisation.
Existing executable release/guard tests cover actual review-record enforcement.
"""

import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
TREES = {
    "canonical": REPO / "skills",
    "claude": REPO / "plugins/data-request/skills",
    "codex": REPO / "dist/codex/plugins/data-request/skills",
}


def text(tree, leaf, relative="SKILL.md"):
    source = f"data-request-{leaf}" if tree == "canonical" else leaf
    return " ".join((TREES[tree] / source / relative).read_text().split())


class ApprovalPosture(unittest.TestCase):
    def test_enquiry_approval_authorises_request_code_not_a_separate_permission_step(self):
        for tree in TREES:
            with self.subTest(tree=tree):
                rule = text(tree, "guardrails", "references/release.rst")
                self.assertIn("permission to build, commit and push its request code", rule)
                self.assertIn("does not need a separate permission step", rule)
                self.assertIn("analyst checks the delivered elements against the approval", rule)

    def test_unchecked_identifiers_and_free_text_are_built_for_delivery(self):
        for tree in TREES:
            with self.subTest(tree=tree):
                rule = text(tree, "guardrails", "references/release.rst")
                self.assertIn("Build every requested element as usual, including identifiers and free text", rule)
                self.assertIn("Do not withhold a requested output or mark it ``internal`` just because the approval is unchecked", rule)
                self.assertIn("clinic_notes", rule)
                self.assertIn("outwards correspondence", rule)
                self.assertIn("URN/MRN", rule)

    def test_unchecked_approval_generates_at_most_one_review_limitation_not_questions(self):
        for tree in TREES:
            with self.subTest(tree=tree):
                rule = text(tree, "guardrails", "references/release.rst")
                self.assertIn("not a blocker, open question or Ben note item", rule)
                self.assertIn("At most one limitation", rule)
                self.assertIn("Reuse it in the analyst hand-off; do not repeat the question at each stage", rule)

    def test_triage_governance_class_requires_a_known_restriction_or_custodian_decision(self):
        for tree in TREES:
            with self.subTest(tree=tree):
                checks = text(tree, "triage", "references/checks.rst")
                governance = checks.split("Blocker taxonomy", 1)[1].split(" governance ", 1)[1].split(" scaffold ", 1)[0]
                self.assertIn("known approval restriction", governance)
                self.assertIn("custodian decision", governance)
                self.assertIn("Unchecked approval alone is not a governance blocker", governance)
                self.assertIn("never widen the output meanwhile", governance)

    def test_screening_only_approval_still_excludes_identity_contact_pathology(self):
        for tree in TREES:
            with self.subTest(tree=tree):
                checks = text(tree, "triage", "references/checks.rst")
                self.assertIn("screening-log approval limits the output to screening fields", checks)
                self.assertIn("Contact, identity and pathology fields from the intake stay out", checks)
                self.assertIn("If the approval is unchecked, build the requested fields", checks)
                self.assertNotIn("Reconcile fields added during review", checks)

    def test_raw_dates_and_both_outputs_do_not_require_unchecked_coverage_proof(self):
        for tree in TREES:
            with self.subTest(tree=tree):
                rule = text(tree, "guardrails", "references/release.rst")
                self.assertIn("a known approval restriction excludes the raw date", rule)
                self.assertIn("Deliver both only when both are requested and no known restriction excludes them", rule)
                self.assertNotIn("Do not deliver both unless the approval covers both", rule)

    def test_validation_listings_and_link_tables_stay_undelivered(self):
        for tree in TREES:
            with self.subTest(tree=tree):
                rule = text(tree, "guardrails", "references/release.rst")
                self.assertIn("keep them out of the delivery run", rule)
                self.assertIn("never goes in any extract of the delivery run", rule)
                self.assertIn("only when the pinned runner supports the flag", rule)
                self.assertIn("Never hand-edit a generated marker", rule)

    def test_build_posture_is_discoverable_in_both_entrypoints(self):
        for tree in TREES:
            for leaf in ("triage", "guardrails"):
                with self.subTest(tree=tree, leaf=leaf):
                    entry = text(tree, leaf)
                    self.assertIn("approval is unchecked", entry)
                    self.assertIn("analyst", entry)
                    self.assertIn("references/", entry)

    def test_triage_only_and_runtime_permission_boundaries_remain_explicit(self):
        for tree in TREES:
            with self.subTest(tree=tree):
                entry = text(tree, "triage")
                self.assertIn("read-only in every repository", entry)
                for boundary in ("writing to service-desk", "running an extract or any query",
                                 "merging a PR", "pushing to a child's `main`", "hooks and checks",
                                 "copier update"):
                    self.assertIn(boundary, entry)
                self.assertIn("Enquiry approval does not override runtime tool permissions", entry)
                self.assertIn("report it and stop; never retry in another form", entry)

    def test_handoff_keeps_known_restrictions_as_release_gates_not_unchecked_approval(self):
        for tree in TREES:
            with self.subTest(tree=tree):
                handoff = text(tree, "triage", "references/handoff.rst")
                self.assertIn("An unchecked approval does not by itself prevent review", handoff)
                self.assertIn("known restriction remains a release gate", handoff)
                self.assertIn("analyst checks the delivered elements against the approval", handoff)
                self.assertIn("engineer hands over", handoff)

    def test_permission_configuration_is_engineer_owned_not_a_denial_workaround(self):
        doc = " ".join((REPO / "docs/data-request-permissions.md").read_text().split())
        self.assertIn("Only the engineer may add permission rules", doc)
        self.assertIn("Do not retry a denied action in another form", doc)
        self.assertIn("not a blanket allowlist", doc)
        self.assertIn("hooks", doc)
        self.assertIn("warehouse", doc)


if __name__ == "__main__":
    unittest.main()
