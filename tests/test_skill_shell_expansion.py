"""Claude Code load-time shell syntax, checked with 2.1.284 temp plugins.

Whitespace/start-of-body introduces a command; fences do not protect it.
A bang inside an inline code span is not an opener. See the live probe matrix
in docs/skill-review/finish.md. This guards entrypoints, not prose references.
"""
from pathlib import Path
import re
import unittest


ROOT = Path(__file__).resolve().parents[1]


def shell_commands(body):
    return re.findall(r"(?<!\S)!`([^`]+)`", body)


class SkillShellExpansion(unittest.TestCase):
    def test_executable_forms_including_fenced_examples(self):
        for text in ("!`printf PROBE`", "Run !`printf PROBE`.",
                     "  !`printf PROBE`", "```text\n!`printf PROBE`\n```",
                     "`` !`printf PROBE` ``"):
            with self.subTest(text=text):
                self.assertEqual(["printf PROBE"], shell_commands(text))
        self.assertEqual(["printf\nPROBE"], shell_commands("!`printf\nPROBE`"))

    def test_literal_forms_do_not_open_commands(self):
        for text in ("Example: `!` then `printf PROBE`.", r"\!`printf PROBE`",
                     "env!`printf PROBE`", "(!`printf PROBE`)",
                     "`env!`/`include_str!`", "Operators: `||`, `!`, and arithmetic"):
            with self.subTest(text=text):
                self.assertEqual([], shell_commands(text))

    def test_all_canonical_entrypoints_avoid_executable_shell_examples(self):
        paths = sorted((ROOT / "skills").glob("*/SKILL.md"))
        self.assertTrue(paths)
        for path in paths:
            with self.subTest(skill=path.parent.name):
                body = path.read_text().split("---", 2)[2]
                self.assertEqual([], shell_commands(body), "load-time shell command")
