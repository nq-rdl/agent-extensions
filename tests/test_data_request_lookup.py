"""Offline authored lookup contracts, not a command or warehouse integration test."""
import re
import unittest
from pathlib import Path

import yaml

REPO = Path(__file__).resolve().parents[1]
TREES = (
    REPO / "skills/data-request-lookup",
    REPO / "plugins/data-request/skills/lookup",
    REPO / "dist/codex/plugins/data-request/skills/lookup",
)


class LookupContract(unittest.TestCase):
    def texts(self):
        for tree in TREES:
            yield tree, (tree / "SKILL.md").read_text()

    def test_exposed_on_both_targets(self):
        bundle = yaml.safe_load((REPO / "registry/bundles/data-request.yaml").read_text())
        self.assertIn({"source": "data-request-lookup", "leaf": "lookup"}, bundle["skills"])
        for tree, text in self.texts():
            with self.subTest(tree=tree):
                frontmatter = yaml.safe_load(text.split("---", 2)[1])
                expected = "data-request-lookup" if tree == TREES[0] else "lookup"
                if tree == TREES[1]:
                    self.assertNotIn("name", frontmatter)
                else:
                    self.assertEqual(expected, frontmatter["name"])
                self.assertLessEqual(len(text.split("---", 2)[2].splitlines()), 500)

    def test_workflow_families_direction_and_private_sources(self):
        for tree, text in self.texts():
            with self.subTest(tree=tree):
                for phrase in ("order field", "clinical event code or event set", "medication",
                               "ICD-10-AM, ACHI, SNOMED CT", "pathology task",
                               "Forward", "Reverse", "short date window",
                               "rdl-ide-settings/snippets/SQL/", "R12/R13", "dataops",
                               "analyst-intake.rst", "no separate intake skill"):
                    self.assertIn(phrase, text)
                self.assertIn("https://github.com/nq-rdl/query-builder/issues/231", text)
                self.assertIn("temp table of keys", text)
                self.assertIn("State no local rule", text)

    def test_public_skill_contains_no_schema_or_sql_rules(self):
        forbidden = re.compile(
            r"\b(?:ORDER_DETAIL|ORDERS|ORDER_CATALOG\w*|OE_\w+|ORDER_ENTRY_\w+|"
            r"V500_\w+|MLTM_\w+|CODE_VALUE|DISCRETE_TASK_ASSAY|ACTION_SEQUENCE|"
            r"UPDT_DT_TM|MNEMONIC_KEY_CAP|ACTIVE_IND|END_EFFECTIVE_DT_TM|"
            r"GETUTCDATE|GETDATE|BIGINT|COLLATE|ORDER_ID|matched_terms)\b"
        )
        for tree, text in self.texts():
            with self.subTest(tree=tree):
                self.assertIsNone(forbidden.search(text))
                self.assertNotIn("```sql", text)
                self.assertNotRegex(text, r"--(?:order|term|reverse|from|to|format)\b")
                self.assertIn("never copy them into this catalog", text)

    def test_unmerged_dependency_and_unsupported_families_fail_closed(self):
        for tree, text in self.texts():
            with self.subTest(tree=tree):
                for phrase in ("open and unmerged", "installed dependency pin",
                               "no diagnosis/procedure builder", "no\n   task-assay command syntax",
                               "do not write hand SQL", "engineer-reviewed probe",
                               "not guessed flags", "do not select a winner",
                               "The agent runs no query"):
                    self.assertIn(phrase, text)

    def test_disclosure_and_record_evidence(self):
        for tree, text in self.texts():
            with self.subTest(tree=tree):
                for phrase in ("only codes, labels and counts", "`<7`", "complementary suppression",
                               "no totals", "bounded single-scan", "no delivered-extract use"):
                    self.assertIn(phrase, text)
                for field in ("Question and context", "Search", "Provenance", "Run",
                              "Candidates", "Disposition", "who ran it", "source table/resolver",
                              "labelled-grid citation", "selected, rejected or unresolved",
                              "never label it\nOBSERVED", "no paste-back means no"):
                    self.assertIn(field, text)
                self.assertIn("new `.sqlreview` document type", text)

    def test_map_and_guardrails_integrate_without_weakening_exemption(self):
        roots = (REPO / "skills", REPO / "plugins/data-request/skills",
                 REPO / "dist/codex/plugins/data-request/skills")
        for root in roots:
            prefix = "data-request-" if root == roots[0] else ""
            with self.subTest(root=root):
                mapping = (root / f"{prefix}map/SKILL.md").read_text()
                self.assertIn("lookup record's path, revision and labelled grid", mapping)
                self.assertIn("a hit does not confirm clinical inclusion", mapping)
                guard = (root / f"{prefix}guardrails/SKILL.md").read_text()
                for phrase in ("only codes, labels and counts", "`<7`", "no totals", "complementary suppression",
                               "bounded to a single scan", "feeds no delivered extract",
                               "waives only lift capture", "authorised human"):
                    self.assertIn(phrase, guard)


if __name__ == "__main__":
    unittest.main()
