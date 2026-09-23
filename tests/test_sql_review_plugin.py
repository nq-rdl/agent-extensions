"""Structural tests for the data-request plugin: registry, skills, hooks wiring, policy note.

These pin the packaging contract (docs/specs/2026-09-15-data-request-plugin-design.md) that
the generic validators do not know about: nine action facets, both hooks wired, every skill
user-invocable with AskUserQuestion available, the consumer skills pointing at /data-request:setup,
setup exempt from the initialisation gate, and the language-policy row that sanctions the shell helper.
"""

import json
import unittest
from pathlib import Path

import yaml

REPO = Path(__file__).resolve().parent.parent
BUNDLE = REPO / "registry" / "bundles" / "data-request.yaml"
PLUGIN = REPO / "plugins" / "data-request"
RECORD_STAGES = ("setup", "bootstrap", "analyse", "explain")
SKILLS = {leaf: REPO / "skills" / f"data-request-{leaf}"
          for leaf in (*RECORD_STAGES, "guardrails", "map", "draft", "validate", "fix", "amend", "lift")}


def frontmatter(skill_md: Path) -> dict:
    parts = skill_md.read_text().split("---\n", 2)
    return yaml.safe_load(parts[1]) or {}


class Registry(unittest.TestCase):
    def test_bundle_maps_nine_facets_and_two_hooks(self):
        data = yaml.safe_load(BUNDLE.read_text())
        self.assertEqual(data["targets"]["claude"]["pluginName"], "data-request")
        members = {m["source"]: m["leaf"] for m in data["skills"]}
        self.assertEqual(members, {f"data-request-{leaf}": leaf for leaf in SKILLS})
        self.assertEqual(sorted(data["hooks"]), ["data-request-guard", "data-request-preflight"])
        self.assertFalse(data["description"].endswith("."))

    def test_marketplace_order_lists_the_subject(self):
        order = yaml.safe_load((REPO / "registry" / "marketplace.yaml").read_text())["order"]
        self.assertIn("data-request", order)


class Skills(unittest.TestCase):
    def test_every_skill_is_user_invocable_with_ask_user_question(self):
        for leaf, d in SKILLS.items():
            with self.subTest(leaf):
                fm = frontmatter(d / "SKILL.md")
                self.assertEqual(fm["name"], f"data-request-{leaf}")
                self.assertTrue(fm.get("user-invocable"))
                self.assertIn("AskUserQuestion", fm.get("allowed-tools", ""))
                self.assertIn("argument-hint", fm)
                self.assertTrue(fm.get("compatibility"))
                if leaf in RECORD_STAGES:
                    self.assertIn("schema", fm["compatibility"])
                self.assertEqual(fm["metadata"]["repo"], "https://github.com/nq-rdl/agent-extensions")

    def test_consumer_skills_point_at_setup_and_setup_is_exempt(self):
        for leaf in ("bootstrap", "analyse", "explain"):
            body = (SKILLS[leaf] / "SKILL.md").read_text()
            with self.subTest(leaf):
                self.assertIn("/data-request:setup", body)
                self.assertIn("exit 3", body)            # the status gate is explicit
                self.assertIn("sqlreview.sh", body)
                self.assertIn("skills/setup/scripts", body)   # shared helper path inside the plugin
        setup = (SKILLS["setup"] / "SKILL.md").read_text()
        self.assertIn("init", setup)
        self.assertNotIn("stop and point", setup.lower())

    def test_stage_pointers(self):
        chain = {"setup": "/data-request:bootstrap", "bootstrap": "/data-request:analyse", "analyse": "/data-request:explain"}
        for leaf, nxt in chain.items():
            with self.subTest(leaf):
                self.assertIn(nxt, (SKILLS[leaf] / "SKILL.md").read_text())

    def test_definitions_live_once_in_setup(self):
        cfg = json.loads((SKILLS["setup"] / "assets" / "sqlreview" / "config.json").read_text())
        self.assertEqual(cfg["schemaVersion"], 2)
        self.assertIn("Decision points made by the RDL", cfg["definitions"]["assumption"])
        self.assertTrue((SKILLS["setup"] / "references" / "definitions.rst").is_file())
        for leaf in ("bootstrap", "analyse", "explain"):
            body = (SKILLS[leaf] / "SKILL.md").read_text()
            with self.subTest(leaf):
                self.assertNotIn("Decision points made by the RDL", body)   # referenced, never restated
                self.assertIn("definitions", body)

    def test_templates_and_helper_shipped(self):
        for rel in ("assets/sqlreview/config.json", "assets/sqlreview/templates/scope.md",
                    "assets/sqlreview/templates/review.md", "scripts/sqlreview.sh", "scripts/sqlreview-lib.sh",
                    "scripts/sqlreview-check.jq", "scripts/sqlreview-slug.jq"):
            with self.subTest(rel):
                self.assertTrue((SKILLS["setup"] / rel).is_file())
                self.assertTrue((PLUGIN / "skills" / "setup" / rel).is_file(), "plugin copy missing — run sync-plugins.sh")

    def test_confirmation_fields_come_only_from_answered_questions(self):
        for leaf in ("bootstrap", "analyse"):
            body = (SKILLS[leaf] / "SKILL.md").read_text()
            with self.subTest(leaf):
                self.assertIn("confirmed_by", body)
                self.assertRegex(body, r"(?i)never .*confirmed_by")


class Hooks(unittest.TestCase):
    def test_hooks_json_wires_both_scripts(self):
        hooks = json.loads((PLUGIN / "hooks" / "hooks.json").read_text())["hooks"]
        cmds = {h["command"] for groups in hooks.values() for g in groups for h in g["hooks"]}
        self.assertEqual(cmds, {"${CLAUDE_PLUGIN_ROOT}/hooks/data-request-preflight.sh", "${CLAUDE_PLUGIN_ROOT}/hooks/data-request-guard.sh"})
        self.assertEqual(hooks["PreToolUse"][0]["matcher"], "Write|Edit")
        for name in ("data-request-preflight.sh", "data-request-guard.sh"):
            self.assertTrue((PLUGIN / "hooks" / name).is_file())
            self.assertTrue((REPO / "hooks" / name).is_file())


class Policy(unittest.TestCase):
    def test_language_policy_names_shell_skill_helpers(self):
        for doc in ("AGENTS.md", "docs/ARCHITECTURE.md"):
            with self.subTest(doc):
                text = (REPO / doc).read_text()
                self.assertRegex(text, r"(?i)skill helper script")
                self.assertRegex(text, r"(?i)bash.*jq")


if __name__ == "__main__":
    unittest.main()
