"""Contract tests for the `data-request:amend` entry point (issue #356).

The skill classifies an analyst amendment against query-builder's boundary document
and links to it rather than restating it. These checks keep it registered, packaged
for Claude Code and Codex, discoverable beside the other leaves, and free of any
instruction to hand-edit generated SQL. No model call is made.
"""

import re
import unittest
from pathlib import Path

import yaml

REPO = Path(__file__).resolve().parent.parent
CANONICAL = REPO / "skills/data-request-amend/SKILL.md"
CLAUDE_COPY = REPO / "plugins/data-request/skills/amend/SKILL.md"
CODEX_COPY = REPO / "dist/codex/plugins/data-request/skills/amend/SKILL.md"

BOUNDARY_DOC = "https://github.com/nq-rdl/query-builder/blob/main/docs/ANALYST_AMENDMENTS.md"
GOVERNANCE_SOP = "zensical/governance/docs/governance/data-amendments.md"
EXTENSION_POINTS = ("rename=", "SelectFields", "projection", "cohort.yaml", "SelectStep",
                    "AnalysisPipeline.select", "output_name", "register_result(")
# Distinctive rows of the boundary document's example table. The skill classifies
# against the document; copying its rule set here would let the two drift apart.
BOUNDARY_TABLE_ROWS = (
    "`DedupeByKeyStep`", "dedupe_or", "`FacilitySpec`", "ADR 0003",
    "a combined address", "inclusive or half-open",
)


def frontmatter(path: Path) -> tuple[dict, str]:
    text = path.read_text()
    _, meta, body = text.split("---\n", 2)
    return yaml.safe_load(meta), body


class Registration(unittest.TestCase):
    def test_bundle_maps_the_canonical_skill_to_the_amend_leaf(self):
        bundle = yaml.safe_load((REPO / "registry/bundles/data-request.yaml").read_text())
        self.assertIn({"source": "data-request-amend", "leaf": "amend"}, bundle["skills"])

    def test_canonical_frontmatter_names_the_source(self):
        meta, _ = frontmatter(CANONICAL)
        self.assertEqual(meta["name"], "data-request-amend")
        self.assertTrue(meta["user-invocable"])
        self.assertIn("amend", meta["description"].lower())

    def test_claude_copy_is_namespaced_by_its_leaf(self):
        meta, body = frontmatter(CLAUDE_COPY)
        self.assertNotIn("name", meta, "sync strips name: so /data-request:amend is namespaced")
        self.assertEqual(body, frontmatter(CANONICAL)[1])

    def test_codex_copy_names_the_leaf(self):
        meta, _ = frontmatter(CODEX_COPY)
        self.assertEqual(meta["name"], "amend")

    def test_bundle_doc_lists_amend_for_both_targets(self):
        doc = (REPO / "docs/bundles.md").read_text()
        for entry in ("- `/data-request:amend`", "- `$data-request:amend`"):
            self.assertTrue(entry in doc, f"docs/bundles.md lacks {entry}")


class Content(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.meta, cls.body = frontmatter(CANONICAL)

    def test_links_the_boundary_document_at_its_permanent_location(self):
        self.assertIn(BOUNDARY_DOC, self.body)

    def test_does_not_restate_the_boundary_rule_set(self):
        for row in BOUNDARY_TABLE_ROWS:
            with self.subTest(row=row):
                self.assertNotIn(row, self.body)
        self.assertNotRegex(self.body, r"\|\s*Analyst-safe\s*\|\s*Engineer-required\s*\|")

    def test_classifies_before_editing_and_defaults_to_engineer_required(self):
        classify = self.body.index("classification: analyst-safe")
        self.assertLess(classify, self.body.index("rename="))
        self.assertIn("classification: engineer-required", self.body)
        self.assertRegex(self.body, r"(?i)in doubt[^.]*engineer-required")

    def test_engineer_required_hand_off_names_rule_change_and_files(self):
        for field in ("requested change:", "boundary rule:", "affected files:"):
            with self.subTest(field=field):
                self.assertIn(field, self.body)
        self.assertRegex(self.body, r"(?i)make no edit")

    def test_governance_is_a_separate_check_pointing_to_the_sop(self):
        self.assertIn(GOVERNANCE_SOP, self.body)
        self.assertIn("Data Amendments SOP", self.body)
        self.assertRegex(self.body, r"(?i)original request ID")
        self.assertRegex(self.body, r"(?i)reason for the amendment")

    def test_safe_changes_use_only_the_supported_extension_points(self):
        for point in EXTENSION_POINTS:
            with self.subTest(point=point):
                self.assertIn(point, self.body)

    def test_records_the_amendment_with_its_classification(self):
        self.assertIn("specs/amendments.md", self.body)
        self.assertIn("data-analysis-scaffold/issues/234", self.body)

    def test_validation_gates(self):
        for gate in ("sql_gate", "spec-validate", "final projection", "row count", "key set",
                     "blocker"):
            with self.subTest(gate=gate):
                self.assertIn(gate, self.body)

    def test_reuses_sibling_actions_by_reference(self):
        self.assertIn("${CLAUDE_PLUGIN_ROOT}/skills/guardrails/SKILL.md", self.body)
        for leaf in ("validate", "fix", "analyse"):
            with self.subTest(leaf=leaf):
                self.assertIn(f"/data-request:{leaf}", self.body)

    def test_never_instructs_a_hand_edit_of_generated_sql(self):
        self.assertNotRegex(self.body, r"```\s*sql", "the skill ships no SQL to paste")
        sentences = re.split(r"(?<=[.!?])\s+", " ".join(self.body.split()))
        edits = [s for s in sentences
                 if re.search(r"(?i)generated SQL", s) and re.search(r"(?i)\b(hand-?)?edit", s)]
        self.assertTrue(edits, "the skill must address hand edits of generated SQL")
        for sentence in edits:
            with self.subTest(sentence=sentence):
                self.assertRegex(sentence, r"(?i)\b(never|not|refus\w*|no)\b")


class Routing(unittest.TestCase):
    def test_fix_points_change_requests_to_amend(self):
        body = frontmatter(REPO / "skills/data-request-fix/SKILL.md")[1]
        line = next((l for l in body.splitlines() if "/data-request:amend" in l), "")
        self.assertRegex(line, r"(?i)change request")

    def test_validate_routes_amendments_to_amend(self):
        body = frontmatter(REPO / "skills/data-request-validate/SKILL.md")[1]
        self.assertIn("/data-request:amend", body)


if __name__ == "__main__":
    unittest.main()
