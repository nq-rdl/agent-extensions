"""Issue 585: `sqlreview.sh notes` takes a script's structure from query-builder's reader, not a second grammar.

The library function is `pypika_queries.script_format.describe_script` (nq-rdl/query-builder#501). Nothing here needs it
installed: the helper's call is replaced by tests/fixtures/script_format/standin_describe.py through
SQLREVIEW_DESCRIBE_CMD, which answers from the library's shipped conformance fixtures. LiveLibrary runs the real
function and both readers when it can be imported, and is skipped otherwise.
"""
import json
import os
import shlex
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

try:
    from test_sql_review_scripts import REPO, SQL_V1, Project, item, review_doc, run
except ModuleNotFoundError:
    from tests.test_sql_review_scripts import REPO, SQL_V1, Project, item, review_doc, run

FIX = REPO / "tests" / "fixtures" / "script_format"
STANDIN = f"{shlex.quote(sys.executable)} {shlex.quote(str(FIX / 'standin_describe.py'))}"
ACCEPTED = sorted(p.stem for p in FIX.glob("*.sql") if p.with_suffix(".manifest.json").exists())
REFUSED = sorted(p.stem for p in FIX.glob("*.sql") if p.with_suffix(".refusal.json").exists())
LIBRARY = {"SQLREVIEW_DESCRIBE_CMD": STANDIN, "SQLREVIEW_NOTES_READER": ""}
JQ = {"SQLREVIEW_NOTES_READER": "jq"}


def text_of(name):
    return (FIX / f"{name}.sql").read_bytes().decode("utf-8")


def comparable(parsed):
    """What the two readers must agree on: presence, each note's text, rationale and id, and its lines."""
    return {
        "present": parsed["present"],
        "lines": parsed["lines"],
        **{k: [{f: i[f] for f in ("text", "rationale", "lines", "note_id")} for i in parsed[k]]
           for k in ("assumptions", "limitations")},
    }


class Base(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.root = Path(self._tmp.name)

    def notes(self, text, env, *extra, name="q.sql"):
        p = self.root / name
        p.write_bytes(text.encode())
        return run(["notes", str(p), *extra], self.root, env=env)

    def parsed(self, text, env, *extra):
        r = self.notes(text, env, *extra)
        self.assertEqual(r.returncode, 0, r.stderr)
        return json.loads(r.stdout)


class ManifestReader(Base):
    def test_library_reader_is_named_and_gives_notes_batches_and_supplied(self):
        p = self.parsed(text_of("builder_full"), LIBRARY)
        self.assertEqual((p["reader"], p["library_version"], p["format_version"]), ("library", "0.0.0-standin", 1))
        self.assertEqual(p["disagreements"], [])
        self.assertEqual(p["assumptions"], [{"text": "Each person has one URN", "rationale": "example rule",
                                             "lines": [9, 10], "note_id": "assumption-1", "batch": None}])
        self.assertEqual(p["limitations"], [{"text": "Codes are matched exactly", "rationale": "example effect",
                                             "lines": [12, 13], "note_id": "limitation-1", "batch": None}])
        self.assertEqual([b["index"] for b in p["batches"]], list(range(1, 18)))
        self.assertEqual({b["index"]: b["kind"] for b in p["batches"]}[12], "output")
        self.assertEqual(p["supplied"][0]["name"], "example_cohort")

    def test_a_supplied_input_names_its_batch_and_nothing_else_does(self):
        p = self.parsed(text_of("builder_full"), LIBRARY)
        self.assertEqual(p["inputs"], [{"note_id": "input-1", "text": "supplied cohort example_cohort", "batch": 3}])
        self.assertEqual({i["batch"] for i in p["assumptions"] + p["limitations"]}, {None})

    def test_headerless_script_still_lists_its_batches(self):
        p = self.parsed(text_of("hand_written"), LIBRARY)
        self.assertEqual((p["reader"], p["present"], p["assumptions"], p["limitations"]), ("library", False, [], []))
        self.assertEqual(len(p["batches"]), 8)

    def test_jq_reader_says_so_and_has_no_manifest_fields(self):
        p = self.parsed(text_of("builder_full"), JQ)
        self.assertEqual(p["reader"], "jq")
        for key in ("batches", "supplied", "inputs", "library_version"):
            self.assertNotIn(key, p)

    def test_fallback_when_the_reader_is_unavailable(self):
        for cmd in ("exit 3", "exit 1", "echo not-json", "echo '{}'", "true"):
            with self.subTest(cmd=cmd):
                p = self.parsed(text_of("builder_full"), {"SQLREVIEW_DESCRIBE_CMD": cmd, "SQLREVIEW_NOTES_READER": ""})
                self.assertEqual(p["reader"], "jq")
                self.assertEqual(len(p["assumptions"]), 1)

    def test_default_call_falls_back_where_the_library_is_not_installed(self):
        env = {"SQLREVIEW_NOTES_READER": "", "PYTHONPATH": "", "PYTHONNOUSERSITE": "1"}
        r = self.notes(text_of("builder_full"), env)
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertIn(json.loads(r.stdout)["reader"], ("jq", "library"))  # a machine may have the library


class Refusals(Base):
    def test_a_refused_script_is_an_error_not_an_empty_result(self):
        for name in REFUSED:
            with self.subTest(name=name):
                r = self.notes(text_of(name), LIBRARY)
                self.assertEqual(r.returncode, 4, r.stderr)
                self.assertEqual(r.stdout, "")
                self.assertIn("refused", r.stderr)

    def test_the_jq_grammar_does_not_make_up_for_a_refusal(self):
        r = self.notes(text_of("refuse_unclosed_literal"), LIBRARY)
        self.assertEqual(r.returncode, 4)
        self.assertEqual(self.notes(text_of("refuse_unclosed_literal"), JQ).returncode, 0)  # the old gap

    def test_unknown_format_version_is_an_error(self):
        cmd = "echo '{\"format_version\": 2, \"library_version\": \"9\", \"batches\": [], \"notes\": [], \"supplied\": []}'"
        r = self.notes(SQL_V1, {"SQLREVIEW_DESCRIBE_CMD": cmd, "SQLREVIEW_NOTES_READER": ""})
        self.assertEqual(r.returncode, 4)
        self.assertIn("format version 2", r.stderr)
        self.assertEqual(r.stdout, "")

    def test_a_detail_the_helper_does_not_read_is_an_error(self):
        note = {"id": "assumption-1", "section": "assumption", "text": "t", "details": [["colour", "red"]], "batch": None}
        manifest = {"format_version": 1, "library_version": "9", "batches": [], "notes": [note], "supplied": []}
        r = self.notes(SQL_V1, {"SQLREVIEW_DESCRIBE_CMD": f"echo {shlex.quote(json.dumps(manifest))}", "SQLREVIEW_NOTES_READER": ""})
        self.assertEqual(r.returncode, 4)
        self.assertIn("assumption-1", r.stderr)

    def test_unknown_section_is_still_an_error_for_the_jq_grammar(self):
        r = self.notes("/*\nobservations:\n  - x\n*/\n" + SQL_V1, JQ)
        self.assertEqual(r.returncode, 4)
        self.assertIn("unknown section", r.stderr)

    def test_refusal_stops_the_scope_check_that_bootstrap_runs(self):
        scope = self.root / "scope.draft.json"
        scope.write_text(json.dumps({"kind": "scope", "assumptions": [], "limitations": []}))
        (self.root / "questions.draft.json").write_text(json.dumps({"questions": []}))
        r = self.notes(text_of("refuse_go_semicolon"), LIBRARY, "--against", str(scope),
                       "--questions", str(self.root / "questions.draft.json"))
        self.assertEqual(r.returncode, 4)
        self.assertNotIn("scope_check", r.stdout)


class Disagreement(Base):
    def standin_with(self, mutate):
        manifest = json.loads((FIX / "builder_full.manifest.json").read_text())
        manifest["library_version"] = "9"
        mutate(manifest)
        return {"SQLREVIEW_DESCRIBE_CMD": f"echo {shlex.quote(json.dumps(manifest))}", "SQLREVIEW_NOTES_READER": ""}

    def test_a_text_difference_drops_the_lines_and_is_reported(self):
        env = self.standin_with(lambda m: m["notes"][1].update(text="Each person has two URNs"))
        r = self.notes(text_of("builder_full"), env)
        self.assertEqual(r.returncode, 0, r.stderr)
        p = json.loads(r.stdout)
        self.assertEqual(p["assumptions"][0]["text"], "Each person has two URNs")  # the library is the authority
        self.assertIsNone(p["assumptions"][0]["lines"])
        self.assertIsNone(p["lines"])
        self.assertEqual(p["limitations"][0]["lines"], [12, 13])  # an unaffected section keeps its lines
        self.assertEqual(len(p["disagreements"]), 1)
        self.assertIn("differ", r.stderr)

    def test_a_header_only_the_library_reads_still_comes_back(self):
        # #567: a header the jq grammar rejects was once "present: false". The library's reading wins, with no lines.
        text = text_of("builder_full").replace("limitations:", "observations:", 1)
        self.assertEqual(self.notes(text, JQ).returncode, 4)
        env = self.standin_with(lambda m: None)
        r = self.notes(text, env)
        self.assertEqual(r.returncode, 0, r.stderr)
        p = json.loads(r.stdout)
        self.assertTrue(p["present"])
        self.assertIsNone(p["limitations"][0]["lines"])
        self.assertIn("rejected the header", p["disagreements"][1])


    def test_a_header_only_the_grammar_finds_is_an_error_not_no_header(self):
        env = self.standin_with(lambda m: m.update(notes=[]))
        r = self.notes(text_of("builder_full"), env)
        self.assertEqual(r.returncode, 4)
        self.assertEqual(r.stdout, "")
        self.assertIn("does not find notes", r.stderr)


class Agreement(Base):
    """The two readers over the same scripts: where both can read one, they return the same notes."""

    def test_over_the_library_conformance_fixtures(self):
        for name in ACCEPTED:
            with self.subTest(name=name):
                lib = self.parsed(text_of(name), LIBRARY)
                jq = self.parsed(text_of(name), JQ)
                self.assertEqual((lib["reader"], jq["reader"]), ("library", "jq"))
                self.assertEqual(comparable(lib), comparable(jq))
                self.assertEqual(lib["disagreements"], [])

    def test_the_fixture_with_a_header_has_one_note_of_each_kind(self):
        p = self.parsed(text_of("builder_full"), JQ)
        self.assertEqual((len(p["assumptions"]), len(p["limitations"]), p["present"]), (1, 1, True))

    def test_inputs_first_header_is_present_for_the_jq_grammar(self):  # #567 was fixed on this branch before this change
        self.assertTrue(self.parsed(text_of("builder_full"), JQ)["present"])


class BatchLocation(unittest.TestCase):
    def check(self, location):
        doc = review_doc()
        doc["assumptions"] = [item("A1", "x", 1, location=location)]
        with tempfile.TemporaryDirectory() as tmp:
            return run(["check", "--stdin"], Path(tmp), stdin=json.dumps(doc))

    def test_a_location_may_name_its_batch(self):
        for loc in ({"lines": [3, 5], "batch": 4}, {"lines": [3, 5], "batch": None}, {"lines": [3, 5]}):
            with self.subTest(loc=loc):
                self.assertEqual(self.check(loc).returncode, 0)

    def test_a_batch_must_be_a_positive_whole_number(self):
        for batch in (0, -1, 1.5, "3", True, [3]):
            with self.subTest(batch=batch):
                r = self.check({"lines": [3, 5], "batch": batch})
                self.assertEqual(r.returncode, 4)
                self.assertIn("optional batch number", r.stdout + r.stderr)

    def test_a_batch_without_lines_is_still_invalid(self):
        self.assertEqual(self.check({"batch": 2}).returncode, 4)


HEADER_VARIANTS = {
    "inputs only": "/*\ninputs:\n  - supplied cohort c\n    file: c.csv\n*/\n",
    "assumption without detail": "/*\nassumptions:\n  - Only text\n*/\n",
    "colon in text": "/*\nassumptions:\n  - Time zone: AEST\n    rationale: a: b\n*/\n",
    "two details": "/*\nassumptions:\n  - t\n    rationale: a\n    rationale: b\n*/\n",
    "wrong detail label": "/*\nassumptions:\n  - t\n    consequence: a\n*/\n",
    "unknown detail on limitation": "/*\nlimitations:\n  - t\n    colour: red\n*/\n",
    "empty item text": "/*\nassumptions:\n  - \n*/\n",
    "trailing space on section": "/*\nassumptions: \n  - t\n*/\n",
    "crlf": "/*\r\nassumptions:\r\n  - t\r\n    rationale: r\r\n*/\r\n",
    "limitations before assumptions": "/*\nlimitations:\n  - l\nassumptions:\n  - a\n*/\n",
    "repeated section": "/*\nassumptions:\n  - a\nassumptions:\n  - b\n*/\n",
    "empty section": "/*\nassumptions:\nlimitations:\n  - l\n*/\n",
    "banner then header": "/*\n  Licence text\n*/\n/*\nassumptions:\n  - a\n*/\n",
    "header after set": "SET NOCOUNT ON;\n/*\nassumptions:\n  - a\n*/\n",
}


def library_importable():
    r = subprocess.run([sys.executable, "-c", "import pypika_queries.script_format"], capture_output=True)
    return r.returncode == 0


@unittest.skipUnless(library_importable(), "query-builder with script_format is not installed")
class LiveLibrary(Base):
    """The real describe_script and the jq grammar over the same scripts (runs where the library is installed)."""

    ENV = {"SQLREVIEW_NOTES_READER": ""}

    def test_fixtures(self):
        for name in ACCEPTED:
            with self.subTest(name=name):
                lib = self.parsed(text_of(name), self.ENV)
                self.assertEqual(lib["reader"], "library")
                self.assertEqual(comparable(lib), comparable(self.parsed(text_of(name), JQ)))
        for name in REFUSED:
            with self.subTest(name=name):
                self.assertEqual(self.notes(text_of(name), self.ENV).returncode, 4)

    def test_header_variants_agree_or_are_a_recorded_difference(self):
        for label, header in HEADER_VARIANTS.items():
            with self.subTest(label=label):
                lib = self.notes(header + SQL_V1, self.ENV)
                jq = self.notes(header + SQL_V1, JQ)
                self.assertEqual((lib.returncode, jq.returncode), OUTCOME[label], msg=f"{lib.stderr!r} / {jq.stderr!r}")
                if lib.returncode == jq.returncode == 0:
                    a, b = json.loads(lib.stdout), json.loads(jq.stdout)
                    self.assertEqual(a["reader"], "library")
                    if a["disagreements"]:  # the library reads more than the grammar: no lines, text still compared
                        a, b = {**a, "lines": None}, {**b, "lines": None}
                    self.assertEqual(comparable(a)["present"], comparable(b)["present"])


# Exit status of (library reader, jq grammar) for each header variant. Where they differ these are findings (#585):
#   (0, 4)  the library reads a header the jq grammar rejects: an empty item text, limitations before assumptions, a
#           repeated or an empty section. The helper takes the library's reading and leaves the lines empty.
#   (4, 0)  the jq grammar reads a header the library does not find: it must be the first thing in the first batch,
#           with LF line ends and no trailing space. Reading it as "no header" would hide it, so notes stops (exit 4).
OUTCOME = {
    "inputs only": (0, 0),
    "assumption without detail": (0, 0),
    "colon in text": (0, 0),
    "two details": (4, 4),
    "wrong detail label": (4, 4),
    "unknown detail on limitation": (4, 4),
    "empty item text": (0, 4),
    "trailing space on section": (4, 0),
    "crlf": (4, 0),
    "limitations before assumptions": (0, 4),
    "repeated section": (0, 4),
    "empty section": (0, 4),
    "banner then header": (4, 0),
    "header after set": (4, 0),
}

if __name__ == "__main__":
    unittest.main()
