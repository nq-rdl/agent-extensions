"""Spec-driven tests for the generated `claude plugin eval` regex graders.

scripts/generate_eval_graders.py turns each evals/claude/<plugin>/<case>/graders.spec.yaml
into graders/*.md. These tests keep the generated files in sync with their specs and
grade every spec's fixtures with the generated patterns in Python's `re` and Node's
JavaScript engine, requiring the two to agree. Fixture tests explicitly skip when
Node is unavailable; they never report Python-only checks as cross-engine passes.
No model call is made.
"""

import json
import re
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

import yaml

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO / "scripts"))

import generate_eval_graders as gen  # noqa: E402

NODE = shutil.which("node")
NODE_SCRIPT = """
const {patterns, reply} = JSON.parse(require('fs').readFileSync(0, 'utf8'));
const out = {};
for (const [name, source] of Object.entries(patterns)) out[name] = new RegExp(source).test(reply);
process.stdout.write(JSON.stringify(out));
"""


def block(code: str) -> str:
    return f"```go\n{code}```\n"


class GeneratedGradersTest(unittest.TestCase):
    def test_stale_graders_without_specs(self):
        for change in ("delete spec", "move spec", "remove grader"):
            with self.subTest(change=change), tempfile.TemporaryDirectory() as tmp:
                repo = Path(tmp)
                case = repo / "evals/claude/go/old-case"
                case.mkdir(parents=True)
                spec = case / gen.SPEC_NAME
                spec.write_text("package: demo\ngraders:\n  - name: sample\n    why: Test\n    need: ['foo']\n")
                self.assertEqual(gen.main([tmp]), 0)
                stale = case / "graders/sample.md"
                manual = case / "graders/manual.md"
                manual.write_text("---\ntype: tool_used\n---\n")
                if change == "delete spec":
                    spec.unlink()
                elif change == "move spec":
                    new_case = case.with_name("new-case")
                    new_case.mkdir()
                    spec.rename(new_case / gen.SPEC_NAME)
                else:
                    spec.write_text("package: demo\ngraders: []\n")
                self.assertEqual(gen.main([tmp, "--check"]), 1)
                self.assertTrue(stale.exists(), "check mode must not remove files")
                self.assertEqual(gen.main([tmp]), 0)
                self.assertFalse(stale.exists())
                self.assertEqual(manual.read_text(), "---\ntype: tool_used\n---\n")
                if change == "move spec":
                    self.assertTrue((new_case / "graders/sample.md").exists())
                self.assertEqual(gen.main([tmp, "--check"]), 0)

    def test_embedded_captures_are_rejected(self):
        for pattern in (r"(List|Fetch)", r"(?P<verb>List|Fetch)"):
            for field in ("need", "forbid"):
                with self.subTest(pattern=pattern, field=field):
                    with self.assertRaisesRegex(ValueError, "Capturing groups are not supported"):
                        gen.build_pattern("demo", [pattern] if field == "need" else [],
                                          pattern if field == "forbid" else None)

    def test_generated_files_match_their_specs(self):
        self.assertEqual(gen.main([str(REPO), "--check"]), 0)

    def test_every_generated_grader_is_marked_and_loadable(self):
        for spec_path in gen.specs(REPO):
            for path, text in gen.expected_files(spec_path).items():
                meta = yaml.safe_load(text.split("\n---\n")[0].removeprefix("---\n"))
                self.assertEqual(meta["type"], "regex", path)
                re.compile(meta["pattern"])


@unittest.skipUnless(NODE, "Node required for Python/JavaScript grader agreement")
class SpecFixturesTest(unittest.TestCase):
    def test_whitespace_before_info_string(self):
        sources = {"name": gen.build_pattern("demo", [r"\bGood\b"], r"\bBad\b")}
        for fence in ("```", "~~~~"):
            for space in (" ", "\t", " \t "):
                with self.subTest(fence=fence, space=space):
                    good = f"{fence}{space}go\npackage demo\nvar Good int\n{fence}\n"
                    bad = good.replace("Good", "Bad")
                    self.assertEqual(self.grade(sources, good), set())
                    self.assertEqual(self.grade(sources, good + bad), {"name"})
                    self.assertEqual(self.grade(sources, bad + good), set())

    def test_deleted_behavior_cannot_be_rescued_by_comments(self):
        for case, marker, body, failed in (
            ("errors-and-constants", "func (e InvalidPayloadError)", "",
             {"sentinel-errors", "error-type"}),
            ("interfaces-and-types", "func CountValid",
             "func CountValid(records []Record, v Validator) int { return 0 }\n",
             {"no-type-in-name"}),
        ):
            spec = yaml.safe_load((REPO / "evals/claude/go" / case / gen.SPEC_NAME).read_text())
            sources = {g["name"]: gen.build_pattern(spec["package"], g.get("need", []), g.get("forbid"))
                       for g in spec["graders"]}
            good = spec["fixtures"]["good"]
            stub = good[:good.index(marker)] + body
            with self.subTest(case=case):
                self.assertEqual(self.grade(sources, block(stub)), failed)
                self.assertEqual(self.grade(sources, block(stub + "/*\n" + good + "*/\n")), failed)

    def test_longer_closing_fences(self):
        sources = {"name": gen.build_pattern("demo", [r"\bGood\b"], r"\bBad\b")}
        for marker in ("`", "~"):
            for width in (3, 4, 6):
                with self.subTest(marker=marker, width=width):
                    opener, closer = marker * width, marker * (width + 2)
                    good = f"{opener}go\npackage demo\nvar Good int\n{closer}\n"
                    bad = good.replace("Good", "Bad")
                    unrelated = f"{opener}text\nexample\n{closer}\n"
                    self.assertEqual(self.grade(sources, unrelated + good + unrelated), set())
                    self.assertEqual(self.grade(sources, good + bad), {"name"})
                    self.assertEqual(self.grade(sources, bad + good), set())
                    for invalid in (marker * (width - 1), "~" * width if marker == "`" else "`" * width,
                                    opener + ("~" if marker == "`" else "`")):
                        reply = f"{opener}go\npackage demo\nvar Good int\n{invalid}\n"
                        self.assertEqual(self.grade(sources, reply), {"name"})

    def test_query_stub_cannot_pass(self):
        spec = yaml.safe_load((REPO / "evals/claude/go/expensive-getter" / gen.SPEC_NAME).read_text())
        sources = {g["name"]: gen.build_pattern(spec["package"], g.get("need", []), g.get("forbid"))
                   for g in spec["graders"]}
        good = spec["fixtures"]["good"]
        start = good.index("\trows, err :=")
        stub = good[:start] + "\treturn nil, nil\n}\n"
        self.assertEqual(self.grade(sources, block(stub)), {"expensive-getter"})
        # Even the original implementation quoted in a comment cannot rescue it.
        commented = stub + "/*\n" + good[start:] + "*/\n"
        self.assertEqual(self.grade(sources, block(commented)), {"expensive-getter"})

    def test_comments_before_package(self):
        sources = {"name": gen.build_pattern("demo", [r"\bGood\b"], r"\bBad\b")}
        for preamble in ("/* License */\n", "/* Multiple\n * lines **/\n",
                         "// First\n/* Second */ /* Third */\n// Fourth\n",
                         "/* package demo\nvar Bad int */\n"):
            with self.subTest(preamble=preamble):
                good = block(preamble + "package demo\nvar Good int\n")
                bad = block(preamble + "package demo\nvar Bad int\n")
                self.assertEqual(self.grade(sources, good), set())
                self.assertEqual(self.grade(sources, bad), {"name"})
                self.assertEqual(self.grade(sources, good + bad), {"name"})
                self.assertEqual(self.grade(sources, bad + good), set())
        # A package clause inside a comment cannot select a different package.
        unrelated = block("/* package demo */\npackage other\nvar Good int\n")
        self.assertEqual(self.grade(sources, unrelated), {"name"})

    def test_nested_fences_do_not_select_commented_examples(self):
        sources = {"name": gen.build_pattern("demo", [r"\bGood\b"], r"\bBad\b")}
        for fence, nested in (("````", "```"), ("~~~~", "~~~"), ("~~~", "```")):
            for outer, inner, fails in (("Good", "Bad", set()), ("Bad", "Good", {"name"})):
                with self.subTest(fence=fence, outer=outer):
                    code = (f"package demo\nvar {outer} int\n/*\n{nested}go\n"
                            f"package demo\nvar {inner} int\n{nested}\n*/\n")
                    reply = f"{fence}go\n{code}{fence}\n"
                    self.assertEqual(self.grade(sources, reply), fails)
                    # Nested examples in earlier/later unrelated Markdown blocks
                    # must not become candidates either.
                    unrelated = f"{fence}text\n{nested}go\npackage demo\nvar Bad int\n{nested}\n{fence}\n"
                    self.assertEqual(self.grade(sources, unrelated + reply + unrelated), fails)

    def test_last_top_level_file_controls_the_grade(self):
        sources = {"name": gen.build_pattern("demo", [r"\bGood\b"], r"\bBad\b")}
        good = block("package demo\nvar Good int\n")
        bad = block("package demo\nvar Bad int\n")
        self.assertEqual(self.grade(sources, good + bad), {"name"})
        self.assertEqual(self.grade(sources, bad + good), set())
        self.assertEqual(self.grade(sources, "```text\n```\n" + good + "```text\n```\n"), set())

    def test_query_fixture_only_changes_names(self):
        case = REPO / "evals/claude/go/expensive-getter"
        original = (case / "prompt.md").read_text().split("```go\n")[1].split("```")[0]
        good = yaml.safe_load((case / gen.SPEC_NAME).read_text())["fixtures"]["good"]
        expected = original.replace("GetName", "Name").replace("GetProducts", "ListProducts")
        # Ignore the explanatory comment; retain the query, scanning, error paths,
        # and returned collection exactly as supplied in the prompt.
        actual = good.replace("// ListProducts was GetProducts.\n", "")
        self.assertEqual(actual, expected)

    def grade(self, sources: dict, reply: str) -> set:
        """Names of the graders that FAIL the reply (checked in both engines)."""
        python = {name: bool(re.search(src, reply)) for name, src in sources.items()}
        result = subprocess.run(
            [NODE, "-e", NODE_SCRIPT], input=json.dumps({"patterns": sources, "reply": reply}),
            capture_output=True, text=True, check=True, timeout=30,
        )
        self.assertEqual(json.loads(result.stdout), python, "JavaScript and Python disagree")
        return {name for name, ok in python.items() if not ok}

    def test_noncapturing_groups_with_comments_and_literals(self):
        source = gen.build_pattern("demo", [r"\b(?:List|Fetch)Products\b", r"\breturn\b"],
                                   r"\b(?:GetProducts|Products)\b")
        code = 'package demo\n// GetProducts\nfunc FetchProducts() string { return "Products" }\n'
        self.assertEqual(self.grade({"verbs": source}, block(code)), set())
        self.assertEqual(self.grade({"verbs": source}, block(code.replace("FetchProducts", "GetProducts"))),
                         {"verbs"})

    def test_spec_fixtures(self):
        checked = 0
        for spec_path in gen.specs(REPO):
            spec = yaml.safe_load(spec_path.read_text())
            fixtures = spec.get("fixtures")
            if not fixtures:
                continue
            case = spec_path.parent.name
            sources = {g["name"]: gen.build_pattern(spec["package"], g.get("need", []), g.get("forbid"))
                       for g in spec["graders"]}
            good = fixtures["good"]
            original = (spec_path.parent / "prompt.md").read_text().split("```go\n")[1].split("```")[0]

            with self.subTest(case=case, fixture="good"):
                self.assertEqual(self.grade(sources, "Here you go:\n\n" + block(good)), set())
            with self.subTest(case=case, fixture="before and after, original quoted in prose"):
                reply = "Before:\n" + block(original) + "After:\n" + block(good) + "I renamed:\n" + original
                self.assertEqual(self.grade(sources, reply), set())
            with self.subTest(case=case, fixture="unchanged original fails every grader"):
                self.assertEqual(self.grade(sources, block(original)), set(sources))
            with self.subTest(case=case, fixture="empty reply fails every grader"):
                self.assertEqual(self.grade(sources, ""), set(sources))

            for fixture in fixtures.get("cases", []):
                code = good
                for old, new in fixture["replace"]:
                    self.assertIn(old, code, f"{case}: fixture '{fixture['name']}' replaces missing text")
                    code = code.replace(old, new)
                with self.subTest(case=case, fixture=fixture["name"]):
                    self.assertEqual(self.grade(sources, block(code)), set(fixture["fails"]))
                checked += 1
        self.assertGreater(checked, 0)


if __name__ == "__main__":
    unittest.main()
