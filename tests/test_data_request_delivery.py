"""Offline authored delivery contracts; not an extract/writer integration test."""
from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]
TREES = (
    ("skills", "data-request-"),
    ("plugins/data-request/skills", ""),
    ("dist/codex/plugins/data-request/skills", ""),
)


class DeliveryGuidanceTests(unittest.TestCase):
    def test_limits_and_canonical_behaviour(self):
        for tree, prefix in TREES:
            with self.subTest(tree=tree):
                text = (ROOT / tree / f"{prefix}guardrails/references/delivery.rst").read_text()
                for phrase in (
                    "1,048,575 data rows", "16,384 columns", "32,767 characters",
                    "31 characters", "unique without regard to case",
                    "template/src/services/file_manager.py", "template/scripts/run_extract.py",
                    "both row and column dimensions", "Parquet retains every captured",
                    "cell truncation", "older child runners may differ",
                ):
                    self.assertIn(phrase, text)

    def test_uncertainty_and_engineer_handoff(self):
        for tree, prefix in TREES:
            with self.subTest(tree=tree):
                text = (ROOT / tree / f"{prefix}guardrails/references/delivery.rst").read_text()
                for phrase in (
                    "within 10%", "undecided", "rows_vs_limit", "under half",
                    "between half and the limit", "over the limit",
                    "longer than 32,767 characters", "rounded count of long notes",
                    "Accept the sheet split", "Deliver Parquet first",
                    "Reduce or change the grain", "Cut text columns",
                    "not automatic", "Do not silently aggregate",
                    "record_limitation", "decision-authority.rst",
                ):
                    self.assertIn(phrase, text)

    def test_stage_hooks_and_local_reference(self):
        for tree, prefix in TREES:
            with self.subTest(tree=tree):
                guardrails = (ROOT / tree / f"{prefix}guardrails/SKILL.md").read_text()
                self.assertIn("[references/delivery.rst](references/delivery.rst)", guardrails)
                for stage in ("map", "draft"):
                    text = " ".join((ROOT / tree / f"{prefix}{stage}/SKILL.md").read_text().split())
                    for phrase in ("references/delivery.rst", "probe counts", "length bands", "10%",
                                   "engineer, flagged for the analyst"):
                        self.assertIn(phrase, text)


if __name__ == "__main__":
    unittest.main()
