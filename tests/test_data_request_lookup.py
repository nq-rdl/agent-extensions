"""Offline authored lookup contracts, not a command or warehouse integration test.

The catalog is workflow-only: privacy checks must not themselves publish private
schema names. Guard identifier shapes and SQL syntax without a source denylist.
"""
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

    def assert_workflow_only(self, text):
        identifiers = set(re.findall(r"\b[A-Z][A-Z0-9]*(?:_[A-Z0-9]+)+\b", text))
        # Claude/Codex host substitutions, not source identifiers. Keep this narrow.
        self.assertFalse(identifiers - {"CLAUDE_PLUGIN_ROOT", "PLUGIN_ROOT"})
        self.assertNotRegex(
            text, r"\b(?:SELECT|JOIN|COLLATE|GETUTCDATE|GETDATE|BIGINT|WHERE|INSERT|UPDATE|DELETE)\b"
        )
        self.assertNotIn("```sql", text)
        self.assertNotRegex(text, r"https://github\.com/nq-rdl/agent-extensions/blob/(?:main|master)/")

    def test_public_skill_contains_no_schema_or_sql_rules(self):
        for tree, text in self.texts():
            with self.subTest(tree=tree):
                self.assert_workflow_only(text.split("---", 2)[2])
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
                lookup_mapping = mapping.split("## Lookup evidence for codes\n", 1)[1].split("\n## ", 1)[0]
                self.assert_workflow_only(lookup_mapping)
                self.assertIn("lookup record's path, revision and labelled grid", mapping)
                self.assertIn("a hit does not confirm clinical inclusion", mapping)
                guard = (root / f"{prefix}guardrails/SKILL.md").read_text()
                lookup_guard = guard.split("**Code-discovery probes:**", 1)[1].split("\n\n", 1)[0]
                self.assert_workflow_only(lookup_guard)
                # Pre-lookup main's longest line is 372 columns; do not evade the
                # lean body limit by joining prose into longer lines.
                self.assertLessEqual(max(map(len, guard.splitlines())), 372)
                for phrase in ("exempt under those operator-probe",
                               "skills/setup/references/lifts.rst` gives both rules in full.",
                               "bounded to a single scan", "feeds no delivered extract"):
                    self.assertIn(phrase, guard)
                lifts = (root / f"{prefix}setup/references/lifts.rst").read_text()
                lookup_rules = lifts.split("**Code-discovery probes:**", 1)[1].split("\n\n", 1)[0]
                self.assert_workflow_only(lookup_rules)
                self.assertLessEqual(max(map(len, lookup_rules.splitlines())), 100)
                rules = " ".join(lookup_rules.replace("``", "`").split())
                for phrase in ("only codes, labels and counts", "`<7`", "no totals",
                               "complementary suppression", "operator-probe conditions",
                               "waives only lift capture", "authorised human"):
                    self.assertIn(phrase, rules)


if __name__ == "__main__":
    unittest.main()
