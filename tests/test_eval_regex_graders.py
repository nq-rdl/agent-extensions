"""Spec-driven tests for the generated `claude plugin eval` regex graders.

scripts/generate_eval_graders.py turns each evals/claude/<plugin>/<case>/graders.spec.yaml
into graders/*.md. These tests keep the generated files in sync with their specs and
grade every spec's fixtures with the generated patterns — in Python's `re` and, when
`node` is on PATH, in the JavaScript engine that actually runs them, requiring the two
to agree. No model call is made.
"""

import json
import re
import shutil
import subprocess
import sys
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
    def test_generated_files_match_their_specs(self):
        self.assertEqual(gen.main([str(REPO), "--check"]), 0)

    def test_every_generated_grader_is_marked_and_loadable(self):
        for spec_path in gen.specs(REPO):
            for path, text in gen.expected_files(spec_path).items():
                meta = yaml.safe_load(text.split("\n---\n")[0].removeprefix("---\n"))
                self.assertEqual(meta["type"], "regex", path)
                re.compile(meta["pattern"])


class SpecFixturesTest(unittest.TestCase):
    def grade(self, sources: dict, reply: str) -> set:
        """Names of the graders that FAIL the reply (checked in both engines)."""
        python = {name: bool(re.search(src, reply)) for name, src in sources.items()}
        if NODE:
            result = subprocess.run(
                [NODE, "-e", NODE_SCRIPT], input=json.dumps({"patterns": sources, "reply": reply}),
                capture_output=True, text=True, check=True, timeout=30,
            )
            self.assertEqual(json.loads(result.stdout), python, "JavaScript and Python disagree")
        return {name for name, ok in python.items() if not ok}

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
