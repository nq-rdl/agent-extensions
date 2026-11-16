"""Draft, fix and house-conventions rules: build conventions, decision ownership, check-first list."""
from pathlib import Path
import re
import unittest


ROOT = Path(__file__).resolve().parents[1]
TREES = (
    ("skills", "data-request-"),
    ("plugins/data-request/skills", ""),
    ("dist/codex/plugins/data-request/skills", ""),
)


def read(tree, prefix, rel):
    return " ".join((ROOT / tree / f"{prefix}{rel}").read_text().split())


class DraftConventions(unittest.TestCase):
    def test_draft_gives_the_amend_commands_and_request_suffix(self):
        for tree, prefix in TREES:
            with self.subTest(tree=tree):
                text = read(tree, prefix, "draft/SKILL.md")
                for phrase in ("pixi run amend record sql/v<N>/<name>_request.sql --builder MODULE:FUNCTION "
                               "--server ALIAS --input FILE", "the scaffold default alias",
                               "Repeat `--input` once for each repo-local input",
                               "run `pixi run amend regenerate` with no argument",
                               "every generated SQL file at its newest version",
                               "Copy confirmed scope wording verbatim"):
                    self.assertIn(phrase, text)
                self.assertLess(text.index("pixi run amend record"), text.index("pixi run amend regenerate"))

    def test_fix_asks_for_a_row_test_before_regenerating(self):
        for tree, prefix in TREES:
            with self.subTest(tree=tree):
                text = read(tree, prefix, "fix/SKILL.md")
                self.assertIn("one row test for each rule the fix changes", text)
                self.assertIn("After any builder edit, run `pixi run amend regenerate` with no argument", text)
                self.assertLess(text.index("one row test for each rule"), text.index("pixi run amend regenerate"))
                self.assertLess(text.index("one row test for each rule"), text.index("Make the smallest source change"))

    def test_draft_and_fix_point_to_house_conventions_without_restating_them(self):
        # The test and citation rules live once, in house-conventions.rst.
        for tree, prefix in TREES:
            for skill in ("draft", "fix"):
                with self.subTest(tree=tree, skill=skill):
                    text = read(tree, prefix, f"{skill}/SKILL.md")
                    self.assertIn("references/house-conventions.rst` for the test and citation", text)
                    for restated in ("structural asserts", "framework suite", "before every push",
                                     "quote its file and line"):
                        self.assertNotIn(restated, text)

    def test_draft_requires_evidence_for_constants_and_check_first(self):
        for tree, prefix in TREES:
            with self.subTest(tree=tree):
                text = read(tree, prefix, "draft/SKILL.md")
                for phrase in ("check-first list", "references/library.rst", "name the path you searched",
                               "cites a probe id or a library default",
                               "Do not override a library default without a probe"):
                    self.assertIn(phrase, text)


class HouseConventions(unittest.TestCase):
    def test_reference_states_ownership_isolation_naming_and_suites(self):
        for tree, prefix in TREES:
            with self.subTest(tree=tree):
                text = read(tree, prefix, "guardrails/references/house-conventions.rst")
                for phrase in ("The analyst owns cohort decisions", "wards, locations and facility sets",
                               "The engineer owns technical decisions", "engineer and DBA decision",
                               "engineer input", "quote the file and the line",
                               "<name>_request.sql", "tests_framework/", "Run both suites before every push",
                               "structural asserts", "probe location",
                               "Give each new module constant a name that no existing variable uses"):
                    self.assertIn(phrase, text)

    def test_reference_has_no_request_detail(self):
        text = (ROOT / "skills/data-request-guardrails/references/house-conventions.rst").read_text()
        self.assertIsNone(re.search(r"THHS|ENQ-?\d|\bF-?\d{2,3}\b", text))


class LibraryCheckFirst(unittest.TestCase):
    def test_library_reference_lists_routes_to_check(self):
        for tree, prefix in TREES:
            with self.subTest(tree=tree):
                text = read(tree, prefix, "guardrails/references/library.rst")
                for phrase in ("Check the library first", "``mssql`` module", "create_code_set_table",
                               "extract_mssql_schema.py", "Coded result rows", "string_agg",
                               "SuppliedCohort", "Name the path you searched"):
                    self.assertIn(phrase, text)


class StyleRules(unittest.TestCase):
    def test_new_prose_is_simplified_technical_english(self):
        for rel in ("skills/data-request-guardrails/references/house-conventions.rst",):
            text = (ROOT / rel).read_text()
            self.assertNotIn(";", text)
            self.assertIsNone(re.search(r"\b\w+n't\b|\b(?:e\.g\.|i\.e\.)", text))


if __name__ == "__main__":
    unittest.main()
