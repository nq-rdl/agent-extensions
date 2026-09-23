"""Tests for the skill validation in scripts/validate-plugins.sh (audit #3).

The local pre-merge check (`bash scripts/validate-plugins.sh`, per AGENTS.md)
must fail when a bundle references a skill that is missing from skills/, or when
a declared skill's self-contained plugin copy is absent. Before this work the
word "skill" did not appear in the script at all.
"""

import subprocess
import tempfile
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
SCRIPT = REPO / "scripts" / "validate-plugins.sh"


def write(path: Path, text: str):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text)


def run_validate(repo: Path):
    import json
    import shutil
    import yaml
    for manifest in (repo / "plugins").glob("*/.codex-plugin/plugin.json"):
        plugin = manifest.parent.parent.name
        target = repo / "dist/codex/plugins" / plugin
        shutil.copytree(manifest.parent.parent, target, dirs_exist_ok=True)
        for path in (target / "skills").glob("*/SKILL.md"):
            text = path.read_text()
            path.write_text(text.replace("---\n", "---\nname: " + path.parent.name + "\n", 1))
        # This fixture represents a migrated package, not a second native manifest in Claude.
        if (repo / "registry/bundles" / (plugin + ".yaml")).exists():
            manifest.unlink()
            manifest.parent.rmdir()
        bundle_file = repo / "registry/bundles" / (plugin + ".yaml")
        if bundle_file.exists():
            bundle = yaml.safe_load(bundle_file.read_text())
            bundle.setdefault("description", "Test package")
            bundle["targets"]["codex"]["category"] = "Developer Tools"
            bundle_file.write_text(yaml.safe_dump(bundle))
            write(repo / "registry/marketplace.yaml", "name: test\npluginDefaults: {}\n")
            data = json.loads((target / ".codex-plugin/plugin.json").read_text())
            data.setdefault("interface", {})
            (target / ".codex-plugin/plugin.json").write_text(json.dumps(data))
    write(repo / "scripts" / "validate-plugins.sh", SCRIPT.read_text())
    for dependency in ("codex_package.py", "generate_manifests.py", "_registry.py"):
        (repo / "scripts" / dependency).write_text((REPO / "scripts" / dependency).read_text())
    return subprocess.run(
        ["bash", str(repo / "scripts" / "validate-plugins.sh")],
        cwd=repo,
        capture_output=True,
        text=True,
    )


def base_plugin(repo: Path, plugin="test"):
    write(
        repo / "plugins" / plugin / ".claude-plugin" / "plugin.json",
        '{"name": "%s", "description": "x"}' % plugin,
    )
    (repo / "skills").mkdir(parents=True, exist_ok=True)


class TestSkillValidation(unittest.TestCase):
    def test_fails_when_registry_skill_missing_from_skills_dir(self):
        with tempfile.TemporaryDirectory() as tmp:
            repo = Path(tmp)
            base_plugin(repo)
            write(
                repo / "registry" / "bundles" / "test.yaml",
                "id: test\nskills:\n  - gone-skill\n"
                "targets:\n  claude:\n    enabled: true\n    pluginName: test\n",
            )
            result = run_validate(repo)
            self.assertNotEqual(result.returncode, 0, result.stdout + result.stderr)
            self.assertIn("gone-skill", result.stdout + result.stderr)

    def test_fails_when_plugin_copy_missing(self):
        with tempfile.TemporaryDirectory() as tmp:
            repo = Path(tmp)
            base_plugin(repo)
            write(repo / "skills" / "present" / "SKILL.md", "---\nname: present\n---\n")
            # registry + source exist, but NO plugins/test/skills/present/ copy
            write(
                repo / "registry" / "bundles" / "test.yaml",
                "id: test\nskills:\n  - present\n"
                "targets:\n  claude:\n    enabled: true\n    pluginName: test\n",
            )
            result = run_validate(repo)
            self.assertNotEqual(result.returncode, 0, result.stdout + result.stderr)
            self.assertIn("present", result.stdout + result.stderr)

    def test_passes_when_skill_and_copy_present(self):
        with tempfile.TemporaryDirectory() as tmp:
            repo = Path(tmp)
            base_plugin(repo)
            write(repo / "skills" / "ok" / "SKILL.md", "---\nname: ok\n---\n")
            write(repo / "plugins" / "test" / "skills" / "ok" / "SKILL.md", "x")
            write(
                repo / "registry" / "bundles" / "test.yaml",
                "id: test\nskills:\n  - ok\n"
                "targets:\n  claude:\n    enabled: true\n    pluginName: test\n",
            )
            result = run_validate(repo)
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    def test_fails_when_plugin_copy_keeps_upstream_name(self):
        # The copy landed at the right leaf folder (gh) but kept the upstream
        # label (name: go-gh), so /-autocomplete shows the bare go-gh while the
        # command is go:gh. The guard must fail this.
        with tempfile.TemporaryDirectory() as tmp:
            repo = Path(tmp)
            base_plugin(repo, plugin="go")
            write(repo / "skills" / "go-gh" / "SKILL.md", "---\nname: go-gh\n---\n")
            write(
                repo / "plugins" / "go" / "skills" / "gh" / "SKILL.md",
                "---\nname: go-gh\n---\n",
            )
            write(
                repo / "registry" / "bundles" / "go.yaml",
                "id: go\nskills:\n  - source: go-gh\n    leaf: gh\n"
                "targets:\n  claude:\n    enabled: true\n    pluginName: go\n",
            )
            result = run_validate(repo)
            combined = result.stdout + result.stderr
            self.assertNotEqual(result.returncode, 0, combined)
            self.assertIn("go-gh", combined)
            self.assertIn("go:gh", combined)

    def test_fails_when_plugin_copy_name_equals_leaf(self):
        # A name equal to the leaf (gh) is ALSO wrong: `frontmatter.name ||
        # <plugin>:<leaf>` makes the label the bare `gh`, not `go:gh`. Any
        # present name fails — this is the case the earlier name==leaf rewrite
        # (issue #112) produced and shipped twice.
        with tempfile.TemporaryDirectory() as tmp:
            repo = Path(tmp)
            base_plugin(repo, plugin="go")
            write(repo / "skills" / "go-gh" / "SKILL.md", "---\nname: go-gh\n---\n")
            write(
                repo / "plugins" / "go" / "skills" / "gh" / "SKILL.md",
                "---\nname: gh\n---\n",
            )
            write(
                repo / "registry" / "bundles" / "go.yaml",
                "id: go\nskills:\n  - source: go-gh\n    leaf: gh\n"
                "targets:\n  claude:\n    enabled: true\n    pluginName: go\n",
            )
            result = run_validate(repo)
            combined = result.stdout + result.stderr
            self.assertNotEqual(result.returncode, 0, combined)
            self.assertIn("go:gh", combined)

    def test_fails_when_plugin_copy_name_is_non_string(self):
        # A non-string name (e.g. `name: 123`) still triggers the bare-label bug
        # — Claude Code coerces it via String(name). The guard must reject any
        # present, non-null name regardless of YAML type, not just strings.
        with tempfile.TemporaryDirectory() as tmp:
            repo = Path(tmp)
            base_plugin(repo, plugin="go")
            write(repo / "skills" / "go-gh" / "SKILL.md", "---\nname: go-gh\n---\n")
            write(
                repo / "plugins" / "go" / "skills" / "gh" / "SKILL.md",
                "---\nname: 123\n---\n",
            )
            write(
                repo / "registry" / "bundles" / "go.yaml",
                "id: go\nskills:\n  - source: go-gh\n    leaf: gh\n"
                "targets:\n  claude:\n    enabled: true\n    pluginName: go\n",
            )
            result = run_validate(repo)
            combined = result.stdout + result.stderr
            self.assertNotEqual(result.returncode, 0, combined)
            self.assertIn("go:gh", combined)

    def test_passes_when_plugin_copy_has_no_name(self):
        # No name: is required — Claude Code then labels the skill by its
        # <plugin>:<leaf> id — so the guard must pass it.
        with tempfile.TemporaryDirectory() as tmp:
            repo = Path(tmp)
            base_plugin(repo, plugin="go")
            write(repo / "skills" / "go-gh" / "SKILL.md", "---\nname: go-gh\n---\n")
            write(
                repo / "plugins" / "go" / "skills" / "gh" / "SKILL.md",
                "---\nlicense: CC-BY-4.0\n---\nbody\n",
            )
            write(
                repo / "registry" / "bundles" / "go.yaml",
                "id: go\nskills:\n  - source: go-gh\n    leaf: gh\n"
                "targets:\n  claude:\n    enabled: true\n    pluginName: go\n",
            )
            result = run_validate(repo)
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    def test_fails_when_plugin_copy_frontmatter_unparseable(self):
        # A frontmatter block that is present but not valid YAML must fail
        # validation, not silently skip the no-name guard on a broken header.
        with tempfile.TemporaryDirectory() as tmp:
            repo = Path(tmp)
            base_plugin(repo, plugin="go")
            write(repo / "skills" / "go-gh" / "SKILL.md", "---\nname: go-gh\n---\n")
            write(
                repo / "plugins" / "go" / "skills" / "gh" / "SKILL.md",
                "---\nname: [unterminated\n---\nbody\n",
            )
            write(
                repo / "registry" / "bundles" / "go.yaml",
                "id: go\nskills:\n  - source: go-gh\n    leaf: gh\n"
                "targets:\n  claude:\n    enabled: true\n    pluginName: go\n",
            )
            result = run_validate(repo)
            combined = result.stdout + result.stderr
            self.assertNotEqual(result.returncode, 0, combined)
            self.assertIn("frontmatter", combined)

    def test_does_not_crash_when_claude_target_is_null(self):
        # `targets: {claude: null}` (a bare `claude:` key) must not crash the
        # inline Python with AttributeError — dict.get(k, {}) returns None, not
        # {}, when the key is present with a null value (audit/verify #1).
        with tempfile.TemporaryDirectory() as tmp:
            repo = Path(tmp)
            base_plugin(repo)
            write(repo / "skills" / "ok" / "SKILL.md", "---\nname: ok\n---\n")
            write(
                repo / "registry" / "bundles" / "test.yaml",
                "id: test\nskills:\n  - ok\ntargets:\n  claude:\n",
            )
            result = run_validate(repo)
            combined = result.stdout + result.stderr
            self.assertNotIn("Traceback", combined, combined)
            self.assertNotIn("AttributeError", combined, combined)

    def test_scans_yml_extension_bundles(self):
        # validate.yml globbed *.yaml AND *.yml; the local validator must too,
        # or a .yml bundle's missing skill bypasses the pre-merge check.
        with tempfile.TemporaryDirectory() as tmp:
            repo = Path(tmp)
            base_plugin(repo)
            write(
                repo / "registry" / "bundles" / "legacy.yml",
                "id: legacy\nskills:\n  - gone-skill\n"
                "targets:\n  claude:\n    enabled: true\n    pluginName: test\n",
            )
            result = run_validate(repo)
            self.assertNotEqual(result.returncode, 0, result.stdout + result.stderr)
            self.assertIn("gone-skill", result.stdout + result.stderr)

    def test_codex_requires_explicit_name_with_description(self):
        with tempfile.TemporaryDirectory() as tmp:
            repo = Path(tmp)
            base_plugin(repo, plugin="go")
            write(
                repo / "plugins" / "go" / ".codex-plugin" / "plugin.json",
                '{"name":"go","version":"1.0.0","description":"Go",'
                '"skills":"./skills/"}',
            )
            write(
                repo / "skills" / "go-secure" / "SKILL.md",
                "---\nname: go-secure\ndescription: Secure Go\n---\n",
            )
            write(
                repo / "plugins" / "go" / "skills" / "secure" / "SKILL.md",
                "---\ndescription: Secure Go\n---\n",
            )
            write(
                repo / "registry" / "bundles" / "go.yaml",
                "id: go\nskills:\n  - {source: go-secure, leaf: secure}\n"
                "targets:\n  claude:\n    enabled: true\n    pluginName: go\n"
                "  codex:\n    enabled: true\n    pluginName: go\n",
            )
            result = run_validate(repo)
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    def test_codex_copy_requires_description(self):
        with tempfile.TemporaryDirectory() as tmp:
            repo = Path(tmp)
            base_plugin(repo, plugin="go")
            write(
                repo / "plugins" / "go" / ".codex-plugin" / "plugin.json",
                '{"name":"go","version":"1.0.0","description":"Go",'
                '"skills":"./skills/"}',
            )
            write(repo / "skills" / "go-secure" / "SKILL.md", "---\nname: go-secure\n---\n")
            write(
                repo / "plugins" / "go" / "skills" / "secure" / "SKILL.md",
                "---\nlicense: MIT\n---\n",
            )
            write(
                repo / "registry" / "bundles" / "go.yaml",
                "id: go\nskills:\n  - {source: go-secure, leaf: secure}\n"
                "targets:\n  claude:\n    enabled: true\n    pluginName: go\n"
                "  codex:\n    enabled: true\n    pluginName: go\n",
            )
            result = run_validate(repo)
            combined = result.stdout + result.stderr
            self.assertNotEqual(result.returncode, 0, combined)
            self.assertIn("missing required 'description'", combined)

    def test_codex_copy_requires_string_description(self):
        with tempfile.TemporaryDirectory() as tmp:
            repo = Path(tmp)
            base_plugin(repo, plugin="go")
            write(
                repo / "plugins" / "go" / ".codex-plugin" / "plugin.json",
                '{"name":"go","version":"1.0.0","description":"Go",'
                '"skills":"./skills/"}',
            )
            write(
                repo / "skills" / "go-secure" / "SKILL.md",
                "---\nname: go-secure\ndescription: Secure Go\n---\n",
            )
            write(
                repo / "plugins" / "go" / "skills" / "secure" / "SKILL.md",
                "---\ndescription: 123\n---\n",
            )
            write(
                repo / "registry" / "bundles" / "go.yaml",
                "id: go\nskills:\n  - {source: go-secure, leaf: secure}\n"
                "targets:\n  claude:\n    enabled: true\n    pluginName: go\n"
                "  codex:\n    enabled: true\n    pluginName: go\n",
            )
            result = run_validate(repo)
            combined = result.stdout + result.stderr
            self.assertNotEqual(result.returncode, 0, combined)
            self.assertIn("description must be a non-empty string", combined)

    def test_codex_rejects_leaf_name_over_64_characters(self):
        with tempfile.TemporaryDirectory() as tmp:
            repo = Path(tmp)
            leaf = "s" * 65
            base_plugin(repo, plugin="go")
            write(
                repo / "plugins" / "go" / ".codex-plugin" / "plugin.json",
                '{"name":"go","version":"1.0.0","description":"Go",'
                '"skills":"./skills/"}',
            )
            write(
                repo / "skills" / leaf / "SKILL.md",
                f"---\nname: {leaf}\ndescription: Test skill\n---\n",
            )
            write(
                repo / "plugins" / "go" / "skills" / leaf / "SKILL.md",
                "---\ndescription: Test skill\n---\n",
            )
            write(
                repo / "registry" / "bundles" / "go.yaml",
                f"id: go\nskills:\n  - {leaf}\n"
                "targets:\n  claude:\n    enabled: true\n    pluginName: go\n"
                "  codex:\n    enabled: true\n    pluginName: go\n",
            )
            result = run_validate(repo)
            combined = result.stdout + result.stderr
            self.assertNotEqual(result.returncode, 0, combined)
            self.assertIn("base skill name", combined)

    def test_codex_accepts_129_character_qualified_skill_name(self):
        with tempfile.TemporaryDirectory() as tmp:
            repo = Path(tmp)
            plugin = "p" * 64
            leaf = "s" * 64
            base_plugin(repo, plugin=plugin)
            write(
                repo / "plugins" / plugin / ".codex-plugin" / "plugin.json",
                '{"name":"%s","version":"1.0.0","description":"Test",'
                '"skills":"./skills/"}' % plugin,
            )
            write(
                repo / "skills" / leaf / "SKILL.md",
                f"---\nname: {leaf}\ndescription: Test skill\n---\n",
            )
            write(
                repo / "plugins" / plugin / "skills" / leaf / "SKILL.md",
                "---\ndescription: Test skill\n---\n",
            )
            write(
                repo / "registry" / "bundles" / f"{plugin}.yaml",
                f"id: {plugin}\nskills:\n  - {leaf}\n"
                "targets:\n  claude:\n    enabled: true\n"
                f"    pluginName: {plugin}\n"
                "  codex:\n    enabled: true\n"
                f"    pluginName: {plugin}\n",
            )
            result = run_validate(repo)
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    def test_codex_manifest_rejects_nonstandard_skills_path(self):
        with tempfile.TemporaryDirectory() as tmp:
            repo = Path(tmp)
            base_plugin(repo, plugin="go")
            write(
                repo / "plugins" / "go" / ".codex-plugin" / "plugin.json",
                '{"name":"go","version":"1.0.0","description":"Go",'
                '"skills":"./other-skills/"}',
            )
            result = run_validate(repo)
            combined = result.stdout + result.stderr
            self.assertNotEqual(result.returncode, 0, combined)
            self.assertIn("must be declared as './skills/'", combined)

    def test_codex_manifest_requires_string_metadata(self):
        with tempfile.TemporaryDirectory() as tmp:
            repo = Path(tmp)
            base_plugin(repo, plugin="go")
            write(
                repo / "plugins" / "go" / ".codex-plugin" / "plugin.json",
                '{"name":"go","version":"1.0.0","description":123,'
                '"keywords":["go"],"skills":"./skills/"}',
            )
            (repo / "plugins" / "go" / "skills").mkdir()
            result = run_validate(repo)
            combined = result.stdout + result.stderr
            self.assertNotEqual(result.returncode, 0, combined)
            self.assertIn("description must be a non-empty string", combined)


if __name__ == "__main__":
    unittest.main()


class TestDelegationReferences(unittest.TestCase):
    def test_outline_link_must_resolve_and_existing_outline_must_be_linked(self):
        with tempfile.TemporaryDirectory() as tmp:
            repo = Path(tmp)
            base_plugin(repo)
            skill = repo / "skills/review/SKILL.md"
            outline = repo / "skills/review/references/subagent.rst"
            linked = "---\nname: review\n---\n[Worker](references/subagent.rst)\n"
            write(skill, linked)
            result = run_validate(repo)
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("does not exist", result.stderr)
            write(outline, "Worker\n======\n\nRead only; return evidence.\n")
            self.assertEqual(run_validate(repo).returncode, 0)
            skill.write_text("---\nname: review\n---\nReview directly.\n")
            result = run_validate(repo)
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("does not link", result.stderr)

    def test_rejects_retired_agent_trees_and_registry_declarations(self):
        for location in ("agents/old/agent.md", "plugins/test/agents/old.md"):
            with self.subTest(location=location), tempfile.TemporaryDirectory() as tmp:
                repo = Path(tmp)
                base_plugin(repo)
                write(repo / location, "old agent")
                self.assertNotEqual(run_validate(repo).returncode, 0)
        with tempfile.TemporaryDirectory() as tmp:
            repo = Path(tmp)
            base_plugin(repo)
            write(repo / "registry/bundles/test.yaml", "id: test\nagents: [old]\n")
            result = run_validate(repo)
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("Standalone agents are retired", result.stderr)
