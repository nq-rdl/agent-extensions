"""Tests for the skill validation in scripts/validate-plugins.sh (audit #3).

The local pre-merge check (`bash scripts/validate-plugins.sh`, per CLAUDE.md)
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
    write(repo / "scripts" / "validate-plugins.sh", SCRIPT.read_text())
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
    (repo / "agents").mkdir(parents=True, exist_ok=True)
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


if __name__ == "__main__":
    unittest.main()
