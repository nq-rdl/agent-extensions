"""Guard client discovery, including workflows absent from automatic prompts."""

import copy
from pathlib import Path
import unittest

from scripts.check_codex_runtime import check_skill_inventory


class TestSkillInventory(unittest.TestCase):
    def setUp(self):
        self.path = Path("/cache with spaces/git/0.30.0/skills/pr-comments/SKILL.md")
        self.expected = {"git:pr-comments": self.path}
        self.skill = {
            "name": "git:pr-comments",
            "path": str(self.path),
            "enabled": True,
            "pluginId": "git@rdl-agent-extensions",
        }

    def response(self, skills=None, errors=None):
        return {"data": [{"skills": skills if skills is not None else [self.skill],
                          "errors": errors or []}]}

    def test_explicit_only_skill_is_required_even_without_automatic_prompt_entry(self):
        # skills/list includes explicit-only entries without an invocation-policy
        # field. Require the installed entrypoint independently of prompt input.
        check_skill_inventory(self.response(), self.expected)
        with self.assertRaisesRegex(RuntimeError, "git:pr-comments; got 0"):
            check_skill_inventory(self.response(skills=[]), self.expected)

    def test_rejects_disabled_wrong_owner_stale_path_and_unqualified_name(self):
        for field, value in (
            ("enabled", False),
            ("pluginId", "other@rdl-agent-extensions"),
            ("pluginId", None),
            ("path", "/old-cache/git/0.29.0/skills/pr-comments/SKILL.md"),
            ("name", "pr-comments"),
        ):
            with self.subTest(field=field, value=value):
                skill = {**self.skill, field: value}
                with self.assertRaises(RuntimeError):
                    check_skill_inventory(self.response(skills=[skill]), self.expected)

    def test_rejects_duplicate_name_and_parse_errors(self):
        with self.assertRaisesRegex(RuntimeError, "got 2"):
            check_skill_inventory(self.response(skills=[self.skill, copy.copy(self.skill)]), self.expected)
        with self.assertRaisesRegex(RuntimeError, "rejected skill configuration"):
            check_skill_inventory(self.response(errors=[{"message": "invalid skill"}]), self.expected)

    def test_allows_unrelated_system_skills_and_mcp_only_packages(self):
        system = {"name": "skill-creator", "enabled": True, "path": "/system/SKILL.md"}
        check_skill_inventory(self.response(skills=[system, self.skill]), self.expected)
        check_skill_inventory(self.response(skills=[system]), {})


if __name__ == "__main__":
    unittest.main()
