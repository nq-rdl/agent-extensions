"""Fixture tests for the hand-written graders of evals/claude/prompting/.

`claude plugin eval` applies each regex grader's `pattern` as a JavaScript regex to the
agent's final message. Each fixture is graded by Python's `re` and, when `node` is on
PATH, by the JavaScript engine too; the two must agree. No model call is made.
"""

import json
import re
import shutil
import subprocess
import time
import unittest
from pathlib import Path

import yaml

REPO = Path(__file__).resolve().parent.parent
SUITE = REPO / "evals" / "claude" / "prompting"
NODE = shutil.which("node")
NODE_SCRIPT = """
const {patterns, reply} = JSON.parse(require('fs').readFileSync(0, 'utf8'));
const out = {};
for (const [name, source] of Object.entries(patterns)) out[name] = new RegExp(source).test(reply);
process.stdout.write(JSON.stringify(out));
"""


def split_frontmatter(path: Path) -> tuple[dict, str]:
    parts = path.read_text().split("---\n", 2)
    return (yaml.safe_load(parts[1]) or {}), parts[2]


def graders(case: str) -> dict[str, dict]:
    return {p.stem: split_frontmatter(p)[0] for p in sorted((SUITE / case / "graders").glob("*.md"))}


def regex_sources(case: str) -> dict[str, str]:
    return {name: meta["pattern"] for name, meta in graders(case).items() if meta["type"] == "regex"}


MIGRATE_GOOD = """Four changes for Opus 5.5.

1. **Thinking:** remove `"thinking": {"type": "disabled"}`. Opus 5.5 rejects it with a 400 at every effort level; thinking is always on.
2. **Effort:** the default effort is now `medium`, not `high`. Set it explicitly: start at `low` for this ex-thinking-off route and sweep up.
3. **max_tokens:** raise it. Thinking counts toward max_tokens even when the text isn't returned, so 8000 can cut replies off.
4. **System prompt:** delete the `Reasoning:` instruction. It can be declined with the reasoning_extraction refusal category. Read `display: "summarized"` thinking blocks instead.
"""

UNATTENDED_GOOD = """Harness:

- Treat a text-only `end_turn` as a report, not completion. Keep the task in a checklist the model updates.
- If items are still open, send a user message naming them. Allow two or three automatic continuations, then stop for review.
- Set `thinking.display: "updates"`; the notes between tool calls now arrive as thinking blocks and are empty by default.

System prompt: add the paragraph that names the unwanted early stops, from the first request of the session.
"""

CASES = {
    "migrate-thinking-disabled": {
        "good": MIGRATE_GOOD,
        "graders": {"thinking-disabled-rejected", "default-medium", "max-tokens-headroom", "reasoning-extraction"},
        "cases": [
            ("disabled thinking kept", [
                ('remove `"thinking": {"type": "disabled"}`. Opus 5.5 rejects it with a 400 at every effort level; '
                 "thinking is always on.", "keep your current settings."),
            ], {"thinking-disabled-rejected"}),
            ("carries over high effort", [
                ("the default effort is now `medium`, not `high`. Set it explicitly: start at `low` for this "
                 "ex-thinking-off route and sweep up.", "keep `high`."),
            ], {"default-medium"}),
            ("max_tokens untouched", [
                ("raise it. Thinking counts toward max_tokens even when the text isn't returned, so 8000 can cut "
                 "replies off.", "leave it at 8000."),
            ], {"max-tokens-headroom"}),
            ("reasoning instruction kept", [
                ("It can be declined with the reasoning_extraction refusal category.", "It still works."),
            ], {"reasoning-extraction"}),
        ],
    },
    "unattended-early-stop": {
        "good": UNATTENDED_GOOD,
        "graders": {"checklist", "bounded-continuations", "display-updates", "first-request"},
        "cases": [
            ("no checklist", [("Keep the task in a checklist the model updates.", "")], {"checklist"}),
            ("unbounded continuations", [
                ("Allow two or three automatic continuations, then stop for review.", "Keep continuing."),
            ], {"bounded-continuations"}),
            ("progress notes left hidden", [
                ('Set `thinking.display: "updates"`; the notes between tool calls now arrive as thinking blocks and '
                 "are empty by default.", "Render text blocks."),
            ], {"display-updates"}),
            ("added mid-session without a warning", [
                ("from the first request of the session.", "when a run stalls."),
            ], {"first-request"}),
            ("stopping partway through is not placement advice", [
                ("from the first request of the session.", "because runs stop partway through."),
            ], {"first-request"}),
        ],
    },
}


class SuiteShape(unittest.TestCase):
    def test_every_case_has_a_fixture_and_every_regex_grader_is_covered(self):
        self.assertEqual({p.name for p in SUITE.iterdir() if p.is_dir()}, set(CASES))
        for case, spec in CASES.items():
            with self.subTest(case=case):
                self.assertEqual(set(regex_sources(case)), spec["graders"])

    def test_prompts_declare_runs_turns_timeout_and_tools(self):
        for case in CASES:
            meta, prompt = split_frontmatter(SUITE / case / "prompt.md")
            with self.subTest(case=case):
                for key in ("description", "runs", "max_turns", "timeout_seconds", "allowed_tools"):
                    self.assertIn(key, meta)
                self.assertGreaterEqual(meta["runs"], 3)
                self.assertIn("Skill", meta["allowed_tools"])
                self.assertNotIn("Bash", meta["allowed_tools"])

    def test_skill_fired_matches_the_packaged_leaf(self):
        for case in CASES:
            fired = graders(case)["skill-fired"]
            with self.subTest(case=case):
                self.assertEqual((fired["type"], fired["tool"]), ("tool_used", "Skill"))
                self.assertRegex('"skill": "prompting:claude-opus-5-5"', fired["input_match"])
                self.assertRegex('"skill":"claude-opus-5-5"', fired["input_match"])
                self.assertNotRegex('"skill": "prompting:engineer"', fired["input_match"])
                self.assertNotRegex('"skill": "prompting:claude-sonnet-5-5"', fired["input_match"])


class GraderFixtures(unittest.TestCase):
    def grade(self, sources: dict, reply: str) -> set:
        """Names of the graders that FAIL the reply (checked in both engines when node exists)."""
        python = {name: bool(re.search(src, reply)) for name, src in sources.items()}
        if NODE:
            result = subprocess.run(
                [NODE, "-e", NODE_SCRIPT], input=json.dumps({"patterns": sources, "reply": reply}),
                capture_output=True, text=True, check=True, timeout=30,
            )
            self.assertEqual(json.loads(result.stdout), python, "JavaScript and Python disagree")
        return {name for name, ok in python.items() if not ok}

    def test_fixtures(self):
        for case, spec in CASES.items():
            sources = regex_sources(case)
            with self.subTest(case=case, fixture="good"):
                self.assertEqual(self.grade(sources, spec["good"]), set())
            with self.subTest(case=case, fixture="empty reply fails every grader"):
                self.assertEqual(self.grade(sources, ""), set(sources))
            for name, edits, fails in spec["cases"]:
                reply = spec["good"]
                for old, new in edits:
                    self.assertIn(old, reply, f"{case}: fixture '{name}' replaces missing text")
                    reply = reply.replace(old, new)
                with self.subTest(case=case, fixture=name):
                    self.assertEqual(self.grade(sources, reply), fails)

    def test_the_case_prompt_alone_passes_no_grader(self):
        # Echoing the question back must not score: every grader needs content the prompt lacks.
        for case in CASES:
            _, prompt = split_frontmatter(SUITE / case / "prompt.md")
            with self.subTest(case=case):
                self.assertEqual(self.grade(regex_sources(case), prompt), set(regex_sources(case)))

    def test_long_replies_grade_quickly(self):
        filler = "Line of explanation with `code`, a - dash and thinking.\n" * 400
        for case, spec in CASES.items():
            with self.subTest(case=case):
                start = time.monotonic()
                self.grade(regex_sources(case), filler + spec["good"] + filler)
                self.assertLess(time.monotonic() - start, 5)


if __name__ == "__main__":
    unittest.main()
