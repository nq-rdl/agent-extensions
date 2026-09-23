"""Issue 355: the SQL review reads query-builder's rendered analysis-notes header as evidence.

query-builder >= 0.6.0 renders what pipeline/resolver code recorded with ``record_assumption()`` /
``record_limitation()`` as a leading ``/* ... */`` header (contract: docs/ANALYSIS_NOTES.md in
nq-rdl/query-builder). ``sqlreview.sh notes SQL [--against JSON]`` parses that header, read-only and
deterministically, so /data-request:analyse can seed candidate review items from it. The skills
must still put every item to the human; these tests also pin that wording.
"""
import json
import tempfile
import unittest
from pathlib import Path

try:  # `unittest discover -s tests` puts tests/ on sys.path; `-m unittest tests.x` does not
    from test_sql_review_scripts import REPO, SCRIPT, SQL_V1, Project, item, review_doc, run
except ModuleNotFoundError:
    from tests.test_sql_review_scripts import REPO, SCRIPT, SQL_V1, Project, item, review_doc, run

HEADER = (
    "/*\n"                                                          # 1
    "assumptions:\n"                                                # 2
    "  - Medication template orders are encounter-local\n"          # 3
    "    rationale: Validated against ORDERS encounter linkage\n"   # 4
    "  - Admissions are one per encounter\n"                        # 5
    "limitations:\n"                                                # 6
    "  - Source reads may use NOLOCK\n"                             # 7
    "    consequence: Post-extract reconciliation is required\n"    # 8
    "*/\n"                                                          # 9
    "\n"                                                            # 10
)
BODY = "-- @extract: medications\n" + SQL_V1                         # 11 marker, 12.. SQL

EXPECTED = {
    "present": True,
    "lines": [1, 9],
    "assumptions": [
        {"text": "Medication template orders are encounter-local",
         "rationale": "Validated against ORDERS encounter linkage", "lines": [3, 4]},
        {"text": "Admissions are one per encounter", "rationale": None, "lines": [5, 5]},
    ],
    "limitations": [
        {"text": "Source reads may use NOLOCK",
         "rationale": "Post-extract reconciliation is required", "lines": [7, 8]},
    ],
}
ABSENT = {"present": False, "lines": None, "assumptions": [], "limitations": []}


def shift(expected, by):
    """EXPECTED with every line number moved down by ``by``."""
    out = json.loads(json.dumps(expected))
    out["lines"] = [n + by for n in out["lines"]]
    for k in ("assumptions", "limitations"):
        for i in out[k]:
            i["lines"] = [n + by for n in i["lines"]]
    return out


class Notes(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.root = Path(self._tmp.name)

    def notes(self, text, *extra, name="q.sql"):
        p = self.root / name
        p.write_bytes(text.encode())
        return run(["notes", str(p), *extra], self.root)

    def parsed(self, text, *extra):
        r = self.notes(text, *extra)
        self.assertEqual(r.returncode, 0, r.stderr)
        return json.loads(r.stdout)

    # --- present / absent -------------------------------------------------------------------
    def test_full_header_items_and_lines(self):
        self.assertEqual(self.parsed(HEADER + BODY), EXPECTED)

    def test_no_header_is_absent_not_an_error(self):
        r = self.notes(SQL_V1)
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertEqual(json.loads(r.stdout), ABSENT)
        self.assertEqual(r.stderr, "")

    def test_empty_file_is_absent(self):
        self.assertEqual(self.parsed(""), ABSENT)

    def test_only_assumptions(self):
        sql = "/*\nassumptions:\n  - Grain is one row per stay\n    rationale: Request says stays\n*/\n" + SQL_V1
        self.assertEqual(self.parsed(sql), {
            "present": True, "lines": [1, 5], "limitations": [],
            "assumptions": [{"text": "Grain is one row per stay", "rationale": "Request says stays", "lines": [3, 4]}]})

    def test_only_limitations(self):
        sql = "/*\nlimitations:\n  - Refunds are not netted off\n*/\n" + SQL_V1
        self.assertEqual(self.parsed(sql), {
            "present": True, "lines": [1, 4], "assumptions": [],
            "limitations": [{"text": "Refunds are not netted off", "rationale": None, "lines": [3, 3]}]})

    def test_item_text_is_verbatim_including_colons_and_dashes(self):
        sql = "/*\nassumptions:\n  - Time zone: AEST - fixed +10\n    rationale: DDL comment: UTC+10\n*/\n"
        a = self.parsed(sql)["assumptions"][0]
        self.assertEqual((a["text"], a["rationale"]), ("Time zone: AEST - fixed +10", "DDL comment: UTC+10"))

    # --- position (contract: first GO batch, before the -- @extract: marker) ------------------
    def test_header_after_leading_set_and_use(self):
        pre = "SET NOCOUNT ON;\nuse rdl_warehouse;\n\n"
        self.assertEqual(self.parsed(pre + HEADER + BODY), shift(EXPECTED, 3))

    def test_header_after_line_comments(self):
        self.assertEqual(self.parsed("-- generated by pipeline.py\n" + HEADER + BODY), shift(EXPECTED, 1))

    def test_header_inside_first_batch_before_later_batches(self):
        sql = HEADER + "-- @extract: cohort\nSELECT 1 AS x\nGO\n-- @extract: meds\nSELECT 2 AS y\n"
        self.assertEqual(self.parsed(sql), EXPECTED)

    def test_block_after_the_extract_marker_is_not_the_header(self):
        self.assertEqual(self.parsed(BODY + HEADER), ABSENT)

    def test_block_after_executable_sql_is_not_the_header(self):
        self.assertEqual(self.parsed("SELECT 1 AS x;\n" + HEADER), ABSENT)

    def test_block_in_a_later_go_batch_is_not_the_header(self):
        self.assertEqual(self.parsed("SET NOCOUNT ON;\nGO\n" + HEADER + BODY), ABSENT)

    # --- other block comments ------------------------------------------------------------------
    def test_licence_banner_alone_is_not_misparsed(self):
        banner = "/*\n  Copyright 2026 RDL\n  assumptions: none documented here\n  - not an item\n*/\n"
        self.assertEqual(self.parsed(banner + SQL_V1), ABSENT)

    def test_header_after_a_licence_banner(self):
        banner = "/*\n  Licensed under CC-BY-4.0\n*/\n"
        self.assertEqual(self.parsed(banner + HEADER + BODY), shift(EXPECTED, 3))

    def test_single_line_block_comment_before_the_header(self):
        self.assertEqual(self.parsed("/* generated */\n" + HEADER + BODY), shift(EXPECTED, 1))

    def test_crlf_line_endings(self):
        self.assertEqual(self.parsed((HEADER + BODY).replace("\n", "\r\n")), EXPECTED)

    # --- malformed header: exit 4, one diagnostic naming the line, nothing on stdout -----------
    def assert_malformed(self, sql, line, fragment):
        r = self.notes(sql)
        self.assertEqual(r.returncode, 4, r.stdout + r.stderr)
        self.assertEqual(r.stdout, "")
        self.assertIn(f"line {line}", r.stderr)
        self.assertIn(fragment, r.stderr)

    def test_unterminated_header(self):
        self.assert_malformed("/*\nassumptions:\n  - Grain is one row per stay\n", 1, "unterminated")
        self.assert_malformed("/*\nassumptions:\n  - Grain is one row per stay\n" + SQL_V1, 4, "unexpected")

    def test_detail_key_must_match_the_section(self):
        self.assert_malformed("/*\nassumptions:\n  - A\n    consequence: B\n*/\n", 4, "consequence")
        self.assert_malformed("/*\nlimitations:\n  - A\n    rationale: B\n*/\n", 4, "rationale")

    def test_detail_without_an_item(self):
        self.assert_malformed("/*\nassumptions:\n    rationale: B\n*/\n", 3, "rationale")

    def test_second_detail_on_one_item(self):
        self.assert_malformed("/*\nassumptions:\n  - A\n    rationale: B\n    rationale: C\n*/\n", 5, "rationale")

    def test_empty_section(self):
        self.assert_malformed("/*\nassumptions:\nlimitations:\n  - A\n*/\n", 2, "empty")

    def test_repeated_or_out_of_order_sections(self):
        self.assert_malformed("/*\nlimitations:\n  - A\nassumptions:\n  - B\n*/\n", 4, "assumptions")
        self.assert_malformed("/*\nassumptions:\n  - A\nassumptions:\n  - B\n*/\n", 4, "assumptions")

    def test_unexpected_line(self):
        self.assert_malformed("/*\nassumptions:\n  - A\n  something else\n*/\n", 4, "unexpected")

    def test_empty_item_text(self):
        self.assert_malformed("/*\nassumptions:\n  - \n*/\n", 3, "empty")

    # --- usage, errors, read-only --------------------------------------------------------------
    def test_usage_and_missing_file(self):
        self.assertEqual(run(["notes"], self.root).returncode, 1)
        self.assertEqual(run(["notes", "a.sql", "b.sql"], self.root).returncode, 1)
        self.assertEqual(run(["notes", "a.sql", "--bogus", "x"], self.root).returncode, 1)
        r = run(["notes", str(self.root / "missing.sql")], self.root)
        self.assertEqual(r.returncode, 2)
        self.assertIn("missing.sql", r.stderr)

    def test_needs_no_sqlreview_and_writes_nothing(self):
        p = self.root / "q.sql"
        p.write_text(HEADER + BODY)
        before = sorted(self.root.rglob("*"))
        r = run(["notes", "q.sql"], self.root)
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertEqual(sorted(self.root.rglob("*")), before)
        self.assertEqual(p.read_text(), HEADER + BODY)
        self.assertFalse((self.root / ".sqlreview").exists())

    # --- --against: header vs an existing review/scope/draft ------------------------------------
    def test_against_matches_by_list_and_text(self):
        doc = review_doc(
            assumptions=[item("A3", "Medication template orders are encounter-local",
                              rationale="Validated against ORDERS encounter linkage")],
            limitations=[item("L2", "Source reads may use NOLOCK", rationale="Reconcile after extract"),
                         item("L3", "Admissions are one per encounter")])
        against = self.root / "review.json"
        against.write_text(json.dumps(doc))
        out = self.parsed(HEADER + BODY, "--against", str(against))
        a1, a2 = out["assumptions"]
        (l1,) = out["limitations"]
        self.assertEqual(a1["match"], {"id": "A3", "rationale_same": True})
        self.assertIsNone(a2["match"], "same text in the other list is not a match")
        self.assertEqual(l1["match"], {"id": "L2", "rationale_same": False})

    def test_against_with_no_header_and_errors(self):
        against = self.root / "review.json"
        against.write_text(json.dumps(review_doc()))
        self.assertEqual(self.parsed(SQL_V1, "--against", str(against)), ABSENT)
        self.assertEqual(self.notes(HEADER, "--against", str(self.root / "none.json")).returncode, 2)
        (self.root / "bad.json").write_text("{not json")
        self.assertEqual(self.notes(HEADER, "--against", str(self.root / "bad.json")).returncode, 4)

    def test_against_works_inside_an_initialised_project(self):
        p = Project(self._tmp.name)
        p.sql("reports/monthly.sql", HEADER + BODY)
        p.write_json("reports__monthly", "review.json", review_doc())
        r = run(["notes", "reports/monthly.sql", "--against",
                 ".sqlreview/reviews/reports__monthly/review.json"], p.root)
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertTrue(all(i["match"] is None for i in json.loads(r.stdout)["assumptions"]))


class NotesContract(unittest.TestCase):
    """Doc contract: the skills prescribe recording at the point of logic and read the header."""

    @staticmethod
    def skill(leaf):
        return (REPO / "skills" / f"data-request-{leaf}" / "SKILL.md").read_text()

    def test_engineer_skills_prescribe_recording_at_the_point_of_logic(self):
        for leaf in ("draft", "fix", "lift", "guardrails"):
            with self.subTest(leaf=leaf):
                body = self.skill(leaf)
                self.assertIn("record_limitation", body)
                if leaf != "lift":  # close-out records delivered hand-SQL limitations only
                    self.assertIn("record_assumption", body)

    def test_query_builder_floor_is_pinned(self):
        for leaf in ("draft", "fix", "lift", "guardrails", "analyse"):
            with self.subTest(leaf=leaf):
                front = self.skill(leaf).split("\n---\n", 1)[0]
                self.assertIn("query-builder 0.6.0", front)

    def test_guardrails_links_the_canonical_contract(self):
        self.assertIn("https://github.com/nq-rdl/query-builder/blob/main/docs/ANALYSIS_NOTES.md",
                      self.skill("guardrails"))

    def test_analyse_seeds_candidates_and_still_requires_confirmation(self):
        body = self.skill("analyse")
        self.assertIn('sqlreview.sh" notes', body)
        self.assertIn('"status": "candidate"', body)
        self.assertIn("mismatch", body)
        self.assertRegex(body, r"(?i)header items are candidates")

    def test_explain_reads_the_header(self):
        self.assertIn('sqlreview.sh" notes', self.skill("explain"))

    def test_helper_usage_and_design_spec_list_the_command(self):
        usage = SCRIPT.read_text().split("\nset -u", 1)[0]
        self.assertIn("notes SQL", usage)
        spec = (REPO / "docs/specs/2026-09-15-sql-review-plugin-design.md").read_text()
        self.assertIn("| `notes SQL [--against JSON]` |", spec)


if __name__ == "__main__":
    unittest.main()
