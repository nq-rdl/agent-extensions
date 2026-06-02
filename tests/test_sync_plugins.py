"""Tests for scripts/sync-plugins.sh — the plugin-tree refresher.

Focus: when an upstream skill is removed but a bundle still lists it, the stale
plugin copy must be pruned (audit finding #2 — the keep-set must be the
registry list intersected with skills that still have a canonical source).

The script derives its repo root from its own location, so each test copies the
real script into a throwaway fixture and runs it there.
"""

import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
SCRIPT = REPO / "scripts" / "sync-plugins.sh"


def run_sync(repo: Path):
    (repo / "scripts").mkdir(parents=True, exist_ok=True)
    shutil.copy(SCRIPT, repo / "scripts" / "sync-plugins.sh")
    return subprocess.run(
        ["bash", str(repo / "scripts" / "sync-plugins.sh")],
        cwd=repo,
        capture_output=True,
        text=True,
    )


def write(path: Path, text: str):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text)


class TestPruneStaleCopies(unittest.TestCase):
    def _fixture(self, repo: Path):
        # Bundle still lists both 'alpha' and 'stale'; only 'alpha' has a source.
        write(
            repo / "registry" / "bundles" / "myplugin.yaml",
            "id: myplugin\nskills:\n  - alpha\n  - stale\n"
            "targets:\n  claude:\n    enabled: true\n    pluginName: myplugin\n",
        )
        write(repo / "skills" / "alpha" / "SKILL.md", "---\nname: alpha\n---\n")
        # Pre-existing plugin copies: alpha (valid) and stale (orphaned).
        write(repo / "plugins" / "myplugin" / "skills" / "alpha" / "SKILL.md", "x")
        write(repo / "plugins" / "myplugin" / "skills" / "stale" / "SKILL.md", "x")
        write(
            repo / "plugins" / "myplugin" / ".claude-plugin" / "plugin.json",
            '{"name": "myplugin", "description": "x"}',
        )

    def test_prunes_plugin_copy_when_skill_source_removed(self):
        with tempfile.TemporaryDirectory() as tmp:
            repo = Path(tmp)
            self._fixture(repo)
            run_sync(repo)
            self.assertTrue(
                (repo / "plugins" / "myplugin" / "skills" / "alpha").is_dir(),
                "alpha has a source and must remain",
            )
            self.assertFalse(
                (repo / "plugins" / "myplugin" / "skills" / "stale").exists(),
                "stale plugin copy must be pruned once its skills/ source is gone",
            )


class TestGroupedMembers(unittest.TestCase):
    """Grouped members `<group>/<leaf>` copy to plugins/<plugin>/skills/<leaf>/,
    dropping the `<group>/` prefix so the plugin tree stays one level deep
    (spec §3 / CONTRIBUTING §6). Flat members must stay byte-identical (no-diff)."""

    def test_grouped_member_drops_group_prefix(self):
        with tempfile.TemporaryDirectory() as tmp:
            repo = Path(tmp)
            write(
                repo / "registry" / "bundles" / "obsidian.yaml",
                "id: obsidian\nskills:\n  - obsidian/bases\n"
                "targets:\n  claude:\n    enabled: true\n    pluginName: obsidian\n",
            )
            write(repo / "skills" / "obsidian" / "bases" / "SKILL.md", "---\nname: bases\n---\n")
            run_sync(repo)
            self.assertTrue(
                (repo / "plugins" / "obsidian" / "skills" / "bases" / "SKILL.md").is_file(),
                "grouped member must land at plugins/obsidian/skills/bases/ (prefix dropped)",
            )
            self.assertFalse(
                (repo / "plugins" / "obsidian" / "skills" / "obsidian").exists(),
                "group prefix must NOT appear in the plugin tree",
            )

    def test_flat_member_unchanged(self):
        with tempfile.TemporaryDirectory() as tmp:
            repo = Path(tmp)
            write(
                repo / "registry" / "bundles" / "swe.yaml",
                "id: swe\nskills:\n  - go-gh\n"
                "targets:\n  claude:\n    enabled: true\n    pluginName: swe\n",
            )
            write(repo / "skills" / "go-gh" / "SKILL.md", "---\nname: go-gh\n---\n")
            run_sync(repo)
            self.assertTrue(
                (repo / "plugins" / "swe" / "skills" / "go-gh" / "SKILL.md").is_file(),
                "flat member must remain at plugins/swe/skills/go-gh/ (unchanged)",
            )

    def test_grouped_prune_keys_on_leaf(self):
        # A grouped member's stale sibling (a leaf no longer listed) must be pruned
        # by LEAF name, since the plugin tree is keyed by leaf.
        with tempfile.TemporaryDirectory() as tmp:
            repo = Path(tmp)
            write(
                repo / "registry" / "bundles" / "obsidian.yaml",
                "id: obsidian\nskills:\n  - obsidian/bases\n"
                "targets:\n  claude:\n    enabled: true\n    pluginName: obsidian\n",
            )
            write(repo / "skills" / "obsidian" / "bases" / "SKILL.md", "---\nname: bases\n---\n")
            # Pre-existing stale leaf copy from a removed member.
            write(repo / "plugins" / "obsidian" / "skills" / "cli" / "SKILL.md", "x")
            run_sync(repo)
            self.assertTrue((repo / "plugins" / "obsidian" / "skills" / "bases").is_dir())
            self.assertFalse(
                (repo / "plugins" / "obsidian" / "skills" / "cli").exists(),
                "stale leaf 'cli' must be pruned (keep-set is keyed by leaf)",
            )


if __name__ == "__main__":
    unittest.main()
