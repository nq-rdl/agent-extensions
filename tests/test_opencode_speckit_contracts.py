"""Content contracts for the opencode-dev and speckit-dev skills (#305-#308).

These guard facts that were verified against upstream source and must not
regress: one owner for OpenCode SDK provenance, claims that upstream source
disproved (2026-09-29, OpenCode v1.18.33, opencode-sdk-go v0.19.2), and the
Spec Kit installer-oracle contract. Sources and evidence are recorded in
docs/skill-review/opencode-speckit.md.
"""
import re
import unittest
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
SKILLS = ROOT / "skills"
OPENCODE = [
    "opencode-plugin", "opencode-sdk", "opencode-agent", "opencode-tools",
    "opencode-skill", "opencode-policies", "opencode-delegate",
]
SPECKIT = ["speckit-create", "speckit-validate", "speckit-manage", "speckit-publish"]


def frontmatter(skill):
    text = (SKILLS / skill / "SKILL.md").read_text()
    return yaml.safe_load(text.split("---", 2)[1])


def body(skill):
    return (SKILLS / skill / "SKILL.md").read_text().split("---", 2)[2]


def skill_files(skill):
    return [p for p in (SKILLS / skill).rglob("*") if p.is_file()]


class OpenCodeSdkProvenanceTest(unittest.TestCase):
    def test_sdk_skill_owns_the_go_and_js_pins(self):
        compat = frontmatter("opencode-sdk")["compatibility"]
        self.assertIn("github.com/sst/opencode-sdk-go", compat)
        self.assertIn("v0.19.2", compat)
        self.assertRegex(compat, r"Go 1\.22")
        self.assertIn("@opencode-ai/sdk", compat)
        self.assertLessEqual(len(compat), 500)

    def test_other_skills_route_to_sdk_instead_of_copying_the_pin(self):
        for skill in OPENCODE:
            if skill == "opencode-sdk":
                continue
            for path in skill_files(skill):
                text = path.read_text(errors="ignore")
                with self.subTest(path=str(path.relative_to(ROOT))):
                    self.assertNotIn("v0.19.2", text)
                    self.assertNotRegex(text, r"Go\s*\**1\.22")


class OpenCodeVerifiedFactsTest(unittest.TestCase):
    def test_no_claim_that_create_opencode_server_is_missing(self):
        # packages/sdk/js/src/server.ts exports createOpencodeServer (v1.18.33).
        pattern = re.compile(r"\bno\s+[`*]*createOpencodeServer|createOpencodeServer[`*]*\s+does\s+not", re.I)
        for skill in OPENCODE:
            for path in skill_files(skill):
                with self.subTest(path=str(path.relative_to(ROOT))):
                    self.assertIsNone(pattern.search(path.read_text(errors="ignore")))

    def test_structured_output_field_is_structured(self):
        # AssistantMessage.structured in the v2 generated types; the docs page says structured_output.
        for path in [SKILLS / "opencode-sdk/SKILL.md", *sorted((SKILLS / "opencode-sdk/assets").iterdir())]:
            with self.subTest(path=path.name):
                self.assertNotRegex(path.read_text(), r"info\.structured_output")
        self.assertRegex(body("opencode-sdk"), r"info\.structured\b")

    def test_go_example_sets_the_base_url(self):
        # opencode-sdk-go v0.19.2 defaults to http://localhost:54321/, not :4096.
        self.assertIn("option.WithBaseURL", (SKILLS / "opencode-sdk/assets/hello-sdk.go").read_text())
        self.assertIn("54321", body("opencode-sdk"))

    def test_singular_directories_are_not_called_broken(self):
        # config/plugin.ts and tool/registry.ts glob {plugin,plugins} and {tool,tools}.
        for skill in ("opencode-plugin", "opencode-tools"):
            with self.subTest(skill=skill):
                text = body(skill)
                self.assertNotIn("silently loads nothing", text)
                self.assertNotIn("Singular is wrong", text)

    def test_delegate_uses_the_documented_auto_approval_flag(self):
        text = body("opencode-delegate")
        self.assertIn("--auto", text)

    def test_skill_routes_resolve_in_the_bundle(self):
        leaves = {s.removeprefix("opencode-") for s in OPENCODE}
        for skill in OPENCODE:
            for leaf in re.findall(r"/?opencode-dev:([a-z-]+)", body(skill)):
                with self.subTest(skill=skill, route=leaf):
                    self.assertIn(leaf, leaves)


class SpecKitOracleTest(unittest.TestCase):
    def test_validate_defines_the_installer_oracle(self):
        text = body("speckit-validate")
        self.assertRegex(text, r"specify-cli[^\n]*\d+\.\d+\.\d+")
        self.assertIn("HOME", text)
        for needle in ("credential", "network", "cleanup", "not run", "approval"):
            with self.subTest(needle=needle):
                self.assertIn(needle, text.lower())

    def test_validate_separates_upstream_rejection_from_local_convention(self):
        text = body("speckit-validate")
        self.assertIn("Rejects", text)
        self.assertIn("Local", text)
        self.assertIn("before_converge", text)

    def test_compatibility_names_checked_releases(self):
        for skill in SPECKIT:
            compat = frontmatter(skill)["compatibility"]
            with self.subTest(skill=skill):
                self.assertIn("1.0.12", compat)
                self.assertLessEqual(len(compat), 500)


if __name__ == "__main__":
    unittest.main()
