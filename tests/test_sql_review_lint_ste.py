"""Issue 394: `sqlreview.sh lint --ste` checks STE wording before the human confirms it.

Plain `lint` (provisional wording in confirmed items, #340) passed scope drafts whose sentences
were too long, so a scope needed a second revision only for STE splits. `lint --ste` checks
`intent` and every assumption/limitation `text` and `rationale`, whatever the status, and prints
one `<id>\t<field>\t<rule>\t<detail>` line per hit (exit 10). It is opt-in so the plain `lint`
contract (3 columns, confirmed items only) stays as bootstrap and the existing tests use it.
"""
import json
import tempfile
import unittest

try:  # `unittest discover -s tests` puts tests/ on sys.path; `-m unittest tests.x` does not
    from test_sql_review_scripts import item, run, scope_doc
except ModuleNotFoundError:
    from tests.test_sql_review_scripts import item, run, scope_doc

LONG = ("The cohort includes every admitted patient whose first recorded stay in the reporting "
        "period ends with a discharge to home, to another ward, or to a hospice")  # 27 words
SHORT = "Only completed stays are in scope."


def words(text):
    return len(text.split())


class LintSte(unittest.TestCase):
    def lint(self, doc, *flags):
        with tempfile.TemporaryDirectory() as tmp:
            path = f"{tmp}/doc.json"
            with open(path, "w") as f:
                json.dump(doc, f)
            return run(["lint", *flags, path], tmp)

    def rows(self, doc):
        r = self.lint(doc, "--ste")
        self.assertIn(r.returncode, (0, 10), r.stdout + r.stderr)
        return r.returncode, [line.split("\t") for line in r.stdout.splitlines()]

    def test_long_sentence_is_flagged_with_its_word_count(self):
        self.assertEqual(words(LONG), 27)
        doc = scope_doc(intent=SHORT, assumptions=[item("A1", SHORT, rationale=LONG + ". " + SHORT,
                                                        status="candidate")])
        rc, rows = self.rows(doc)
        self.assertEqual(rc, 10)
        self.assertEqual(rows, [["A1", "rationale", "sentence-length", "27"]])

    def test_twenty_five_words_pass(self):
        text = " ".join(["word"] * 24) + " end."
        self.assertEqual(self.rows(scope_doc(intent=text, assumptions=[item("A1", text, rationale=text)])), (0, []))

    def test_intent_and_limitations_are_checked(self):
        doc = scope_doc(intent=LONG + ".", assumptions=[],
                        limitations=[item("L1", LONG, rationale=SHORT)])
        rc, rows = self.rows(doc)
        self.assertEqual(rc, 10)
        self.assertIn(["-", "intent", "sentence-length", "27"], rows)
        self.assertIn(["L1", "text", "sentence-length", "27"], rows)
        self.assertEqual(len(rows), 2)

    def test_contractions_semicolons_and_latin_abbreviations(self):
        doc = scope_doc(intent=SHORT, assumptions=[
            item("A1", "Stays that don't end are excluded; they're open.", rationale="The ward's rule applies."),
            item("A2", "Some codes are grouped, e.g. ICD-10 chapters.", rationale="Local use, i.e. the ward view."),
        ])
        rc, rows = self.rows(doc)
        self.assertEqual(rc, 10)
        self.assertIn(["A1", "text", "contraction", "don't, they're"], rows)
        self.assertIn(["A1", "text", "semicolon", "1"], rows)
        self.assertIn(["A2", "text", "abbreviation", "e.g."], rows)
        self.assertIn(["A2", "rationale", "abbreviation", "i.e."], rows)
        # a possessive is not a contraction
        self.assertFalse([r for r in rows if r[:2] == ["A1", "rationale"]])
        self.assertEqual(len(rows), 4)

    def test_abbreviation_does_not_split_the_sentence_count(self):
        text = "Codes are grouped by chapter, e.g. " + " ".join(["word"] * 22) + "."
        rc, rows = self.rows(scope_doc(intent=SHORT, assumptions=[item("A1", text)]))
        self.assertIn(["A1", "text", "sentence-length", "28"], rows)

    def test_plain_lint_is_unchanged(self):
        doc = scope_doc(intent=LONG, assumptions=[item("A1", LONG, rationale=LONG)])
        r = self.lint(doc)
        self.assertEqual((r.returncode, r.stdout), (0, ""))

    def test_errors(self):
        with tempfile.TemporaryDirectory() as tmp:
            self.assertEqual(run(["lint", "--ste", f"{tmp}/nope.json"], tmp).returncode, 2)
            with open(f"{tmp}/bad.json", "w") as f:
                f.write("{not json")
            self.assertEqual(run(["lint", "--ste", f"{tmp}/bad.json"], tmp).returncode, 4)
            self.assertEqual(run(["lint", "--ste"], tmp).returncode, 1)
            self.assertEqual(run(["lint", "--bogus", f"{tmp}/bad.json"], tmp).returncode, 1)


class SkillsRunIt(unittest.TestCase):
    """Bootstrap and analyse run `lint --ste` before their question batches (canonical + packaged)."""

    def test_bootstrap_and_analyse_invoke_lint_ste(self):
        from pathlib import Path
        repo = Path(__file__).resolve().parent.parent
        for source, leaf, draft in (("data-request-bootstrap", "bootstrap", "scope.draft.json"),
                                    ("data-request-analyse", "analyse", "review.draft.json")):
            for path in (repo / "skills" / source / "SKILL.md",
                         repo / "plugins" / "data-request" / "skills" / leaf / "SKILL.md",
                         repo / "dist" / "codex" / "plugins" / "data-request" / "skills" / leaf / "SKILL.md"):
                with self.subTest(path=str(path.relative_to(repo))):
                    text = path.read_text()
                    self.assertIn(f'lint --ste ".sqlreview/reviews/$SLUG/{draft}"', text)
                    self.assertRegex(text, r"(?i)before each batch")


if __name__ == "__main__":
    unittest.main()
