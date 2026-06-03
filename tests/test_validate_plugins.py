"""Tests for scripts/validate-plugins.sh — skill plugin-copy resolution.

Codex caught that the skill check resolved the plugin copy by the raw member
name, while sync-plugins.sh writes the copy at the LEAF. For a mapped
{source, leaf} member those differ, so the validator must look for the copy at
plugins/<plugin>/skills/<leaf>/ (resolving the source against skills/<source>/).

The script derives its repo root from its own location, so each test copies it
into a throwaway fixture and runs it there (mirrors test_sync_plugins.py).
"""

import shutil
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
    (repo / "scripts").mkdir(parents=True, exist_ok=True)
    shutil.copy(SCRIPT, repo / "scripts" / "validate-plugins.sh")
    return subprocess.run(
        ["bash", str(repo / "scripts" / "validate-plugins.sh")],
        cwd=repo,
        capture_output=True,
        text=True,
    )


def mapped_bundle_fixture(repo: Path, leaf_copy_dir: str):
    """One enabled bundle, pluginName go, mapped member go-gh -> gh. The plugin
    copy is planted at ``leaf_copy_dir`` so each test can place it right or wrong."""
    write(
        repo / "registry" / "bundles" / "go.yaml",
        "id: go\nskills:\n  - source: go-gh\n    leaf: gh\n"
        "targets:\n  claude:\n    enabled: true\n    pluginName: go\n",
    )
    write(repo / "skills" / "go-gh" / "SKILL.md", "---\nname: go-gh\n---\n")
    write(
        repo / "plugins" / "go" / ".claude-plugin" / "plugin.json",
        '{"name": "go", "description": "Go subject"}',
    )
    write(repo / leaf_copy_dir / "SKILL.md", "x")


class TestSkillCopyResolvesByLeaf(unittest.TestCase):
    def test_passes_when_copy_at_leaf(self):
        with tempfile.TemporaryDirectory() as tmp:
            repo = Path(tmp)
            mapped_bundle_fixture(repo, "plugins/go/skills/gh")
            result = run_validate(repo)
            self.assertEqual(result.returncode, 0, result.stderr)

    def test_fails_when_copy_at_source_name_not_leaf(self):
        with tempfile.TemporaryDirectory() as tmp:
            repo = Path(tmp)
            # Copy wrongly placed at the source name; the leaf copy is absent.
            mapped_bundle_fixture(repo, "plugins/go/skills/go-gh")
            result = run_validate(repo)
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("skills/gh", result.stderr)


if __name__ == "__main__":
    unittest.main()
