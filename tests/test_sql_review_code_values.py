"""Issue 439: lint prose strings without echoing numeric code values.

Runs the actual helper on scope/review/draft documents. Prose assertions are
instruction contracts, not evidence of live model behaviour.
"""
import copy
import json
import tempfile
import unittest
from pathlib import Path

from test_sql_review_scripts import REPO, item, review_doc, run, scope_doc

DIGITS = "87654321"  # synthetic, never a real code or patient identifier


class CodeValues(unittest.TestCase):
    def lint(self, doc, *flags, name="doc.json"):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / name
            path.write_text(json.dumps(doc))
            result = run(["lint", *flags, str(path)], tmp)
            self.assertNotRegex(result.stdout + result.stderr, r"[0-9]{8,10}")
            return result

    def code_rows(self, doc, *flags, **kwargs):
        result = self.lint(doc, *flags, **kwargs)
        self.assertEqual(result.returncode, 10, result.stdout + result.stderr)
        rows = [line.split("\t") for line in result.stdout.splitlines()]
        return [row for row in rows if any("code-value" in cell for cell in row)]

    def test_logic_description_reports_item_and_field_in_both_modes(self):
        doc = review_doc()
        doc["logic"][0]["description"] = "Filter by " + DIGITS
        for flags in ((), ("--ste",)):
            rows = self.code_rows(doc, *flags)
            self.assertEqual(len(rows), 1)
            self.assertEqual(rows[0][:2], ["logic[0]", "description"])
            self.assertEqual(len(rows[0]), 4 if flags else 3)

    def test_valid_binding_and_fingerprints_are_not_prose(self):
        for factory in (scope_doc, review_doc):
            doc = factory(sql_path="reports/extract_20260930.sql",
                          slug="reports__extract_20260930",
                          sql_sha256="a12345678a" + "a" * 54,
                          git_commit="b123456789b" + "b" * 29)
            for flags in ((), ("--ste",)):
                with self.subTest(kind=doc["kind"], flags=flags):
                    result = self.lint(doc, *flags)
                    self.assertEqual((result.returncode, result.stdout), (0, ""))
            with tempfile.TemporaryDirectory() as tmp:
                path = Path(tmp) / "doc.json"
                path.write_text(json.dumps(doc))
                before = path.read_bytes()
                self.assertEqual(run(["check", str(path)], tmp).returncode, 0)
                self.assertEqual(run(["lint", "--ste", str(path)], tmp).returncode, 0)
                self.assertEqual(path.read_bytes(), before)

    def test_metadata_exemptions_are_validated_and_location_specific(self):
        for over in ({"sql_sha256": "not a hash " + DIGITS},
                     {"git_commit": "not a commit " + DIGITS},
                     {"sql_path": "../extract_" + DIGITS + ".sql"},
                     {"slug": "unbound_" + DIGITS}):
            for flags in ((), ("--ste",)):
                with self.subTest(over=over, flags=flags):
                    self.assertEqual(len(self.code_rows(review_doc(**over), *flags)), 1)
        doc = review_doc()
        doc["extension"] = {"sql_sha256": "a12345678a" + "a" * 54,
                            "sql_path": "extract_20260930.sql"}
        self.assertEqual(len(self.code_rows(doc, "--ste")), 2)

    def test_fractional_machine_timestamps_are_not_prose(self):
        stamp = "2026-09-30T05:21:28.123456789Z"
        doc = review_doc(recorded_at=stamp)
        doc["assumptions"][0]["confirmed_at"] = stamp
        doc["assumptions"][0]["decided"] = {
            "by": "requester", "role": "Requester", "at": stamp,
            "source": "dated request document"}
        doc["changes"][0]["at"] = stamp
        for flags in ((), ("--ste",)):
            result = self.lint(doc, *flags)
            self.assertEqual((result.returncode, result.stdout), (0, ""))
        doc["changes"][0]["summary"] = "Use " + DIGITS
        self.assertEqual(len(self.code_rows(doc, "--ste")), 1)

    def test_every_non_metadata_string_field_in_scope_review_and_drafts(self):
        for factory in (scope_doc, review_doc):
            original = factory()
            # Capture all string leaf paths, not just fields currently known to lint.
            def paths(value, prefix=()):
                if isinstance(value, str):
                    yield prefix
                elif isinstance(value, dict):
                    for key, child in value.items():
                        yield from paths(child, (*prefix, key))
                elif isinstance(value, list):
                    for index, child in enumerate(value):
                        yield from paths(child, (*prefix, index))
            for path in paths(original):
                # Known binding/fingerprint fields have their own validation tests.
                if path in (("sql_path",), ("slug",), ("sql_sha256",), ("git_commit",)):
                    continue
                for name in ("scope.json", "review.json", "review.draft.json"):
                    with self.subTest(kind=original["kind"], path=path, name=name):
                        doc = copy.deepcopy(original)
                        parent = doc
                        for part in path[:-1]:
                            parent = parent[part]
                        parent[path[-1]] = "Use " + DIGITS
                        rows = self.code_rows(doc, "--ste", name=name)
                        self.assertEqual(len(rows), 1)

    def test_nested_provenance_unknown_fields_and_question_store(self):
        doc = scope_doc(assumptions=[item("A7", "Use the constant", status="candidate",
                                         decided={"source": "ticket " + DIGITS})])
        doc["extension"] = {"nested": [{"notes": ["Use " + DIGITS]}]}
        doc["questions"] = [{"id": "Q7", "text": "Does " + DIGITS + " apply?",
                             "closure": {"source": "ticket " + DIGITS}}]
        rows = self.code_rows(doc, "--ste")
        self.assertIn(["A7", "decided.source"], [row[:2] for row in rows])
        self.assertIn(["Q7", "text"], [row[:2] for row in rows])
        self.assertIn(["Q7", "closure.source"], [row[:2] for row in rows])
        self.assertEqual(len(rows), 4)

    def test_top_level_and_array_fields_are_locatable(self):
        doc = review_doc(purpose="Use " + DIGITS, open_questions=["Use " + DIGITS])
        doc["inputs"][0]["name"] = "code " + DIGITS
        doc["changes"][0]["summary"] = "Remove " + DIGITS
        rows = self.code_rows(doc, "--ste")
        self.assertEqual({tuple(row[:2]) for row in rows},
                         {("-", "purpose"), ("-", "open_questions[0]"),
                          ("inputs[0]", "name"), ("changes[0]", "summary")})

    def test_maximal_digit_runs_and_multiple_hits(self):
        for length in (8, 9, 10):
            for wrapper in ("{}", "'{}'", "`{}`", "code{}suffix", "[{}],"):
                with self.subTest(length=length, wrapper=wrapper):
                    doc = scope_doc(intent=wrapper.format(DIGITS + "0" * (length - 8)))
                    self.assertEqual(len(self.code_rows(doc)), 1)
        for text in ("1234567", "12345678901", "12345678901234567890", "12-34-56-78",
                     "EVENT_CD", "2026-09-24", "1234567a1234567"):
            result = self.lint(scope_doc(intent=text))
            self.assertEqual((result.returncode, result.stdout), (0, ""), text)
        rows = self.code_rows(scope_doc(intent=f"{DIGITS}, {DIGITS}0 and {DIGITS}00"), "--ste")
        self.assertEqual(len(rows), 3)
        self.assertTrue(all(row[:3] == ["-", "intent", "code-value"] for row in rows))

    def test_existing_diagnostics_do_not_leak_numeric_ids_or_paths(self):
        doc = scope_doc(assumptions=[item("A" + DIGITS, "Proposed; don't use it.",
                                         rationale="The requester decided the dates.")])
        doc["extra" + DIGITS] = {"nested" + DIGITS: DIGITS}
        for flags in ((), ("--ste",)):
            result = self.lint(doc, *flags)
            self.assertEqual(result.returncode, 10)
            self.assertIn("decision has no linked written source", result.stdout)
            self.assertIn("code-value", result.stdout)
            self.assertIn("contraction" if flags else "proposed", result.stdout)

    def test_invalid_draft_shapes_do_not_leak_through_jq_errors(self):
        for over in ({"assumptions": DIGITS},
                     {"assumptions": [item("A1", "Use the constant", decided=DIGITS)]}):
            for flags in ((), ("--ste",)):
                with self.subTest(over=over, flags=flags):
                    result = self.lint(scope_doc(**over), *flags)
                    self.assertEqual(result.returncode, 4)
                    self.assertIn("invalid JSON", result.stderr)

    def test_non_string_values_are_not_scanned_and_lint_does_not_mutate(self):
        doc = scope_doc()
        doc["extra"] = [87654321, None, True, {}, []]
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "scope.draft.json"
            path.write_text(json.dumps(doc))
            before = path.read_bytes()
            result = run(["lint", str(path)], tmp)
            self.assertEqual((result.returncode, result.stdout), (0, ""))
            self.assertEqual(path.read_bytes(), before)


class DraftingContract(unittest.TestCase):
    def test_bootstrap_checks_before_update_and_every_question_batch(self):
        text = (REPO / "skills/data-request-bootstrap/SKILL.md").read_text()
        before, update = text.split("## Existing scope", 1)
        update = update.split("## Fresh scope", 1)[0]
        self.assertIn('lint --ste ".sqlreview/reviews/$SLUG/scope.draft.json"', before)
        self.assertIn("Before every question batch", before)
        self.assertIn("stored prose", before)
        self.assertIn("Before re-putting intent", update)
        self.assertIn("before each `walk` batch", update)
        self.assertIn("inspect locally", update)

    def test_analyse_checks_before_delta_and_bulk_walk_questions(self):
        text = (REPO / "skills/data-request-analyse/SKILL.md").read_text()
        before, update = text.split("## Existing review", 1)
        changed = update.split("### Changed SQL", 1)[1].split("## Full review", 1)[0]
        self.assertIn('lint --ste ".sqlreview/reviews/$SLUG/review.draft.json"', before)
        self.assertIn("Before every question batch", before)
        self.assertIn("stored prose", before)
        self.assertIn("Before discussing the delta", changed)
        self.assertIn("before each `bulk`/`walk` question batch", changed)
        self.assertIn("do not paste raw", changed)

    def test_all_three_skills_name_constants_not_values(self):
        for stage in ("analyse", "bootstrap", "fix"):
            for root, source in (("skills", f"data-request-{stage}"),
                                 ("plugins/data-request/skills", stage),
                                 ("dist/codex/plugins/data-request/skills", stage)):
                with self.subTest(stage=stage, root=root):
                    text = (REPO / root / source / "SKILL.md").read_text()
                    self.assertIn("Name the constant, never its value", text)
                    self.assertIn("8 to 10 digits", text)
                    self.assertIn(".pii-code-values", text)
                    self.assertIn("code-value", text)
