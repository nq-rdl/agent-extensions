"""Leaves invoke the guardrails skill instead of reading its SKILL.md by path (#375).

Reading another skill's SKILL.md by path is the SkillSpector AS3 pattern. Every
data-request leaf that loads guardrails uses the skill invocation instead, and
pre-approves the Skill tool so the invocation does not prompt where the old
Read did not.
"""

from pathlib import Path
import unittest

import yaml

REPO = Path(__file__).resolve().parent.parent
LEAVES = ("map", "bootstrap", "analyse", "draft", "triage", "validate", "fix", "amend",
          "release", "explain")


def copies(leaf: str) -> dict[str, Path]:
    return {
        "canonical": REPO / "skills" / f"data-request-{leaf}" / "SKILL.md",
        "claude": REPO / "plugins" / "data-request" / "skills" / leaf / "SKILL.md",
        "codex": REPO / "dist" / "codex" / "plugins" / "data-request" / "skills" / leaf / "SKILL.md",
    }


class GuardrailsInvocation(unittest.TestCase):
    def test_no_leaf_reads_the_guardrails_skill_file(self):
        for leaf in LEAVES:
            for target, path in copies(leaf).items():
                with self.subTest(leaf=leaf, target=target):
                    self.assertNotIn("skills/guardrails/SKILL.md", path.read_text())

    def test_each_leaf_invokes_guardrails_with_its_target_sigil(self):
        for leaf in LEAVES:
            for target, path in copies(leaf).items():
                text = path.read_text()
                with self.subTest(leaf=leaf, target=target):
                    if target == "codex":
                        self.assertIn("`$data-request:guardrails`", text)
                        self.assertNotIn("/data-request:guardrails", text)
                    else:
                        self.assertIn("`/data-request:guardrails`", text)

    def test_each_leaf_pre_approves_the_skill_tool(self):
        for leaf in LEAVES:
            path = copies(leaf)["canonical"]
            meta = yaml.safe_load(path.read_text().split("---\n", 2)[1])
            tools = [t.strip() for t in meta["allowed-tools"].split(",")]
            with self.subTest(leaf=leaf):
                self.assertIn("Skill", tools)


HANDOVER_TOKENS = ("branch", "fast-forward", "pull request head", "HEAD", "exact path", "git add -A",
                   "commit, and only then push", "scaffold version", "extract runner", "verdict")
CITING_LEAVES = ("map", "validate")


class OperatorHandover(unittest.TestCase):
    def reference(self, target):
        base = {"canonical": REPO / "skills" / "data-request-guardrails",
                "claude": REPO / "plugins" / "data-request" / "skills" / "guardrails",
                "codex": REPO / "dist" / "codex" / "plugins" / "data-request" / "skills" / "guardrails"}[target]
        return base / "references" / "operator-handover.rst"

    def test_reference_names_every_handover_step(self):
        for target in ("canonical", "claude", "codex"):
            text = " ".join(self.reference(target).read_text().split())
            for token in HANDOVER_TOKENS:
                with self.subTest(target=target, token=token):
                    self.assertIn(token, text)
            self.assertIn("never ask the operator to run a probe with the extract runner", text.lower())

    def test_guardrails_and_leaves_cite_the_reference(self):
        paths = [copies(leaf) for leaf in CITING_LEAVES]
        for found in paths:
            for target, path in found.items():
                with self.subTest(path=str(path)):
                    self.assertIn("operator-handover.rst", path.read_text())
        guard = REPO / "skills" / "data-request-guardrails" / "SKILL.md"
        self.assertIn("references/operator-handover.rst", guard.read_text())


if __name__ == "__main__":
    unittest.main()
