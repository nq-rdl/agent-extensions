"""Run the team's hook against isolated installs; never touch contributor settings."""

import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest


REPO = Path(__file__).resolve().parent.parent
HOOK = REPO / "skills/cc-setup/assets/forced-eval-hook.sh"


@unittest.skipUnless(shutil.which("jq"), "plugin discovery requires jq")
class SqlDiscovery(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.home = Path(self.tmp.name)
        self.manifest = self.home / ".claude/plugins/installed_plugins.json"
        self.manifest.parent.mkdir(parents=True)
        self.cache = self.home / ".cache/claude-hooks/skill-catalog.cache"
        self.env = {**os.environ, "HOME": str(self.home),
                    "XDG_CACHE_HOME": str(self.home / ".cache")}
        self.install(sql=True)

    def install(self, sql):
        plugins = {"go@rdl-agent-extensions": [
            {"installPath": str(REPO / "plugins/go")}]}
        if sql:
            plugins["sql-code@rdl-agent-extensions"] = [
                {"installPath": str(REPO / "plugins/sql-code")}]
        self.manifest.write_text(json.dumps({"plugins": plugins}))

    def run_hook(self, prompt):
        result = subprocess.run(["bash", str(HOOK)],
                                input=json.dumps({"prompt": prompt}), text=True,
                                capture_output=True, env=self.env, check=True)
        if not result.stdout:
            return ""
        output = json.loads(result.stdout)["hookSpecificOutput"]
        self.assertEqual(output["hookEventName"], "UserPromptSubmit")
        self.assertNotIn("permissionDecision", output)
        return output["additionalContext"]

    def test_ordinary_cohort_and_sql_requests_surface_installed_guardrails(self):
        for prompt in ("Draft the diabetes cohort", "Review requests/1186.sql",
                       "Fix the CLINICAL_EVENT join", "Map a query-builder resolver",
                       "Validate SQL against the request"):
            with self.subTest(prompt=prompt):
                context = self.run_hook(prompt)
                self.assertIn("sql-code:guardrails", context)
                self.assertIn("sql-code:draft", context)
                self.assertNotIn("go:naming", context)
                self.assertIn("Advisory only", context)

    def test_unrelated_prompts_are_quiet(self):
        for prompt in ("Fix the CSS button", "skills should always be reviewed", "", None):
            with self.subTest(prompt=prompt):
                self.assertEqual(self.run_hook(prompt), "")

    def test_absent_plugin_is_quiet_even_with_a_cached_full_catalogue(self):
        self.assertIn("sql-code:guardrails", self.run_hook("Use a skill"))
        self.install(sql=False)
        self.assertEqual(self.run_hook("Draft cohort SQL"), "")

    def test_standalone_sql_names_do_not_trigger_sql_discovery(self):
        self.install(sql=False)
        for name in ("sql-code-custom", "sql-code"):
            skill = self.home / ".claude/skills" / name / "SKILL.md"
            skill.parent.mkdir(parents=True)
            skill.write_text("---\nname: custom\ndescription: Standalone SQL\n---\n")
        self.assertEqual(self.run_hook("Draft cohort SQL"), "")
        self.assertIn("Standalone SQL", self.run_hook("Use a skill"))

    def test_same_plugin_name_from_another_marketplace_is_excluded(self):
        self.manifest.write_text(json.dumps({"plugins": {
            "sql-code@another-marketplace": [
                {"installPath": str(REPO / "plugins/sql-code")}]
        }}))
        self.assertEqual(self.run_hook("Draft cohort SQL"), "")
        self.assertIn("sql-code:guardrails", self.run_hook("Use a skill"))

    def test_sql_mode_does_not_parse_unrelated_files_or_commands(self):
        standalone = self.home / ".claude/skills/sql-code-custom/SKILL.md"
        standalone.parent.mkdir(parents=True)
        standalone.write_text("---\ndescription: Unrelated standalone\n---\n")
        plugin = self.home / "unrelated-plugin"
        for rel in ("skills/unrelated/SKILL.md", "commands/unrelated.md"):
            path = plugin / rel
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text("---\ndescription: Unrelated plugin entry\n---\n")
        plugins = json.loads(self.manifest.read_text())
        plugins["plugins"]["unrelated@example"] = [{"installPath": str(plugin)}]
        self.manifest.write_text(json.dumps(plugins))
        result = subprocess.run(
            ["bash", "-x", str(HOOK)], input=json.dumps({"prompt": "Draft SQL"}),
            text=True, capture_output=True, env=self.env, check=True)
        self.assertIn("sql-code:guardrails", result.stdout)
        self.assertNotIn(str(standalone), result.stderr)
        self.assertNotIn(str(plugin), result.stderr)
        self.assertNotIn("scan_plugin_commands", result.stderr)
        self.assertNotIn(str(REPO / "plugins/go/skills"), result.stderr)

    def test_installation_is_visible_after_cache_was_built_without_sql(self):
        self.install(sql=False)
        self.assertNotIn("sql-code:guardrails", self.run_hook("Use a skill"))
        self.install(sql=True)
        self.assertIn("sql-code:guardrails", self.run_hook("Draft cohort SQL"))

    def test_sql_discovery_neither_uses_nor_overwrites_full_catalogue_cache(self):
        full = self.run_hook("Use a skill")
        self.assertIn("go:naming", full)
        cached = self.cache.read_bytes()
        self.assertNotIn("go:naming", self.run_hook("Draft cohort SQL"))
        self.assertEqual(self.cache.read_bytes(), cached)
        self.assertEqual(self.run_hook("Use a skill"), full)

    def test_sql_first_does_not_create_a_partial_catalogue_cache(self):
        self.assertIn("sql-code:guardrails", self.run_hook("Draft cohort SQL"))
        self.assertFalse(self.cache.exists())
        self.assertIn("go:naming", self.run_hook("Use a skill"))

    def test_explicit_skill_use_keeps_full_catalogue_for_sql_too(self):
        context = self.run_hook("Use a skill to draft SQL")
        self.assertIn("sql-code:guardrails", context)
        self.assertIn("go:naming", context)


if __name__ == "__main__":
    unittest.main()
