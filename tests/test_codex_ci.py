"""CI contracts for the native Codex publication target."""

import re
import unittest
from pathlib import Path

import yaml

from scripts._registry import normalize_member


REPO = Path(__file__).resolve().parent.parent


class TestCodexCi(unittest.TestCase):
    def test_required_plugin_job_runs_pinned_codex_smoke(self):
        workflow = (REPO / ".github" / "workflows" / "validate.yml").read_text()

        self.assertIn("name: Validate Claude plugin structure, hooks, and agents", workflow)
        self.assertIn("@openai/codex@0.152.0", workflow)
        self.assertIn("scripts/smoke-codex-marketplace.sh", workflow)

    def test_local_generated_drift_hook_includes_codex_marketplace(self):
        lefthook = (REPO / "lefthook.yml").read_text()

        self.assertIn(".agents/**", lefthook)

    def test_smoke_checks_every_installed_plugin_skill(self):
        smoke = (REPO / "scripts" / "smoke-codex-marketplace.sh").read_text()

        self.assertIn('expected_skills+=("$plugin:$(basename "$skill_dir")")', smoke)
        self.assertIn('for qualified in "${expected_skills[@]}"', smoke)
        self.assertIn("cmp -s", smoke)
        self.assertNotIn("mapfile", smoke)
        self.assertNotIn("go:naming", smoke)

    def test_codex_pilot_skills_do_not_require_claude_runtime(self):
        forbidden_literals = ("${CLAUDE_PLUGIN_ROOT}", "AskUserQuestion")
        slash_invocation = re.compile(r"(?<![A-Za-z0-9])/[a-z0-9][a-z0-9-]*:[a-z0-9]")

        for bundle_path in sorted((REPO / "registry" / "bundles").glob("*.yaml")):
            bundle = yaml.safe_load(bundle_path.read_text()) or {}
            codex = ((bundle.get("targets") or {}).get("codex") or {})
            if not codex.get("enabled"):
                continue

            for member in bundle.get("skills") or []:
                source, _leaf = normalize_member(member)
                skill_path = REPO / "skills" / source / "SKILL.md"
                content = skill_path.read_text()
                with self.subTest(bundle=bundle_path.stem, skill=source):
                    for marker in forbidden_literals:
                        self.assertNotIn(marker, content)
                    self.assertIsNone(slash_invocation.search(content))


if __name__ == "__main__":
    unittest.main()
