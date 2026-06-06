"""Tests for scripts/sync-plugins.sh — the plugin-tree refresher.

Focus: when an upstream skill is removed but a bundle still lists it, the stale
plugin copy must be pruned (audit finding #2 — the keep-set must be the
registry list intersected with skills that still have a canonical source).

The script derives its repo root from its own location, so each test copies the
real script into a throwaway fixture and runs it there.
"""

from __future__ import annotations

import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

import yaml

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


class TestMappedMembers(unittest.TestCase):
    """An explicit {source, leaf} member copies the FLAT upstream skills/<source>/
    to plugins/<plugin>/skills/<leaf>/ — renaming to the leaf so the plugin tree
    stays one level deep and Claude Code invokes <plugin>:<leaf> (Option-2
    grouping). A flat string member keeps its FOLDER name (no rename); its copy's
    frontmatter name: is still stripped (see TestNameStrip)."""

    def test_mapped_member_renames_source_to_leaf(self):
        with tempfile.TemporaryDirectory() as tmp:
            repo = Path(tmp)
            write(
                repo / "registry" / "bundles" / "go.yaml",
                "id: go\nskills:\n  - source: go-gh\n    leaf: gh\n"
                "targets:\n  claude:\n    enabled: true\n    pluginName: go\n",
            )
            write(repo / "skills" / "go-gh" / "SKILL.md", "---\nname: go-gh\n---\n")
            run_sync(repo)
            self.assertTrue(
                (repo / "plugins" / "go" / "skills" / "gh" / "SKILL.md").is_file(),
                "mapped member must land at plugins/go/skills/gh/ (renamed to leaf)",
            )
            self.assertFalse(
                (repo / "plugins" / "go" / "skills" / "go-gh").exists(),
                "the flat source name must NOT appear in the plugin tree",
            )

    def test_flat_member_folder_not_renamed(self):
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
                "flat member keeps its folder name plugins/swe/skills/go-gh/ (no rename)",
            )

    def test_mapped_prune_keys_on_leaf(self):
        # A mapped member's stale sibling (a leaf no longer listed) must be pruned
        # by LEAF name, since the plugin tree is keyed by leaf.
        with tempfile.TemporaryDirectory() as tmp:
            repo = Path(tmp)
            write(
                repo / "registry" / "bundles" / "go.yaml",
                "id: go\nskills:\n  - source: go-gh\n    leaf: gh\n"
                "targets:\n  claude:\n    enabled: true\n    pluginName: go\n",
            )
            write(repo / "skills" / "go-gh" / "SKILL.md", "---\nname: go-gh\n---\n")
            # Pre-existing stale leaf copy from a removed member.
            write(repo / "plugins" / "go" / "skills" / "naming" / "SKILL.md", "x")
            run_sync(repo)
            self.assertTrue((repo / "plugins" / "go" / "skills" / "gh").is_dir())
            self.assertFalse(
                (repo / "plugins" / "go" / "skills" / "naming").exists(),
                "stale leaf 'naming' must be pruned (keep-set is keyed by leaf)",
            )


def _skill_name(skill_md: Path) -> str | None:
    """Return the frontmatter ``name:`` value of a SKILL.md, or None.

    Parses the leading YAML frontmatter block the same way the production
    ``frontmatter_name`` helper in scripts/validate-plugins.sh does, so the test
    and the code under test agree on what counts as a name."""
    if not skill_md.is_file():
        return None
    parts = skill_md.read_text().split("---\n", 2)
    if len(parts) < 3 or parts[0].strip():
        return None
    try:
        fm = yaml.safe_load(parts[1]) or {}
    except yaml.YAMLError:
        return None
    val = fm.get("name")
    return None if val is None else str(val)


class TestNameStrip(unittest.TestCase):
    """The plugin copy must carry NO frontmatter ``name:``. Claude Code labels a
    plugin skill in /-autocomplete as ``frontmatter.name || <plugin>:<leaf>`` —
    so ANY ``name:`` (the upstream ``go-gh`` or the leaf ``gh``) overrides the
    namespaced id with a bare label, and the user typing ``/go`` sees ``go-gh`` /
    ``gh`` instead of ``go:gh`` (issue #112). Stripping the copy's ``name:`` lets
    the label fall back to ``<plugin>:<leaf>``. The canonical skills/ tree keeps
    its flat upstream name — only the derivative plugin copy is stripped."""

    def test_mapped_member_strips_name(self):
        with tempfile.TemporaryDirectory() as tmp:
            repo = Path(tmp)
            write(
                repo / "registry" / "bundles" / "go.yaml",
                "id: go\nskills:\n  - source: go-gh\n    leaf: gh\n"
                "targets:\n  claude:\n    enabled: true\n    pluginName: go\n",
            )
            write(
                repo / "skills" / "go-gh" / "SKILL.md",
                "---\nname: go-gh\nlicense: CC-BY-4.0\ndescription: x\n---\nbody\n",
            )
            run_sync(repo)
            copy = repo / "plugins" / "go" / "skills" / "gh" / "SKILL.md"
            self.assertIsNone(
                _skill_name(copy),
                "plugin copy name: must be stripped so the /-autocomplete label "
                "falls back to the go:gh invocation",
            )
            # Canonical source must stay flat (untouched upstream label).
            self.assertEqual(
                _skill_name(repo / "skills" / "go-gh" / "SKILL.md"),
                "go-gh",
                "canonical skills/ name: must NOT be touched",
            )

    def test_strip_preserves_other_frontmatter_and_body(self):
        with tempfile.TemporaryDirectory() as tmp:
            repo = Path(tmp)
            write(
                repo / "registry" / "bundles" / "go.yaml",
                "id: go\nskills:\n  - source: go-gh\n    leaf: gh\n"
                "targets:\n  claude:\n    enabled: true\n    pluginName: go\n",
            )
            write(
                repo / "skills" / "go-gh" / "SKILL.md",
                "---\nname: go-gh\nlicense: CC-BY-4.0\n---\n# Heading\n\nbody text\n",
            )
            run_sync(repo)
            copy = repo / "plugins" / "go" / "skills" / "gh" / "SKILL.md"
            text = copy.read_text()
            self.assertIsNone(_skill_name(copy), "name: must be gone")
            self.assertIn("license: CC-BY-4.0", text)
            self.assertIn("# Heading", text)
            self.assertIn("body text", text)
            self.assertNotIn("go-gh", text)

    def test_block_scalar_name_is_stripped_without_orphans(self):
        # A folded/block scalar name: must be removed whole — key line AND its
        # indented continuation — so the strip never leaves orphaned lines that
        # corrupt the frontmatter. (No real skill uses this, but the strip must
        # not be able to emit broken YAML.)
        with tempfile.TemporaryDirectory() as tmp:
            repo = Path(tmp)
            write(
                repo / "registry" / "bundles" / "go.yaml",
                "id: go\nskills:\n  - source: go-gh\n    leaf: gh\n"
                "targets:\n  claude:\n    enabled: true\n    pluginName: go\n",
            )
            write(
                repo / "skills" / "go-gh" / "SKILL.md",
                "---\nname: >-\n  go\n  gh\nlicense: CC-BY-4.0\n---\nbody\n",
            )
            run_sync(repo)
            copy = repo / "plugins" / "go" / "skills" / "gh" / "SKILL.md"
            self.assertIsNone(_skill_name(copy), "block-scalar name: must be gone")
            text = copy.read_text()
            self.assertIn("license: CC-BY-4.0", text)
            self.assertNotIn("go\n  gh", text)
            # Frontmatter must still parse — no orphaned continuation lines.
            fm = yaml.safe_load(text.split("---\n", 2)[1]) or {}
            self.assertNotIn("name", fm)
            self.assertEqual(fm.get("license"), "CC-BY-4.0")

    def test_absent_name_is_left_untouched(self):
        # An absent name: is valid — Claude Code falls back to the directory name,
        # which is already the leaf — so sync must not inject one. Keeps sync, the
        # validator, and the docs in agreement (and avoids a needless rewrite).
        with tempfile.TemporaryDirectory() as tmp:
            repo = Path(tmp)
            write(
                repo / "registry" / "bundles" / "go.yaml",
                "id: go\nskills:\n  - source: go-gh\n    leaf: gh\n"
                "targets:\n  claude:\n    enabled: true\n    pluginName: go\n",
            )
            write(repo / "skills" / "go-gh" / "SKILL.md", "---\nlicense: x\n---\nbody\n")
            run_sync(repo)
            self.assertEqual(
                (repo / "plugins" / "go" / "skills" / "gh" / "SKILL.md").read_text(),
                "---\nlicense: x\n---\nbody\n",
                "no name: key — sync must leave the file byte-for-byte untouched",
            )

    def test_flat_member_name_is_stripped(self):
        # Even a flat member whose upstream name already equals its folder must
        # have the copy's name stripped: `frontmatter.name || <plugin>:<leaf>`
        # means a present `name: changie` shows the bare `changie`, not
        # `git:changie`.
        with tempfile.TemporaryDirectory() as tmp:
            repo = Path(tmp)
            write(
                repo / "registry" / "bundles" / "git.yaml",
                "id: git\nskills:\n  - changie\n"
                "targets:\n  claude:\n    enabled: true\n    pluginName: git\n",
            )
            write(
                repo / "skills" / "changie" / "SKILL.md",
                "---\nname: changie\n---\nbody\n",
            )
            run_sync(repo)
            self.assertIsNone(
                _skill_name(repo / "plugins" / "git" / "skills" / "changie" / "SKILL.md"),
                "flat member's copy name must be stripped so the label is git:changie",
            )


if __name__ == "__main__":
    unittest.main()
