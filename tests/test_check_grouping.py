"""Tests for scripts/check_grouping.py — the skill-grouping contract checker.

Validates the spec §3 / CONTRIBUTING §6 rules: name==leaf, group==pluginName,
unique pluginName, no duplicate leaf, and that a flat skill is never descended
into as a group. Legacy flat bundles (e.g. swe with go-gh) must keep passing.
"""

import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))

import check_grouping  # noqa: E402

ENABLED = "targets:\n  claude:\n    enabled: true\n    pluginName: {p}\n"


def repo_with(tmp, bundles, skills):
    """skills maps a path under skills/ (e.g. 'obsidian/bases' or 'go-gh') to the
    SKILL.md frontmatter name to write there."""
    repo = Path(tmp)
    (repo / "registry" / "bundles").mkdir(parents=True)
    for stem, body in bundles.items():
        (repo / "registry" / "bundles" / f"{stem}.yaml").write_text(body)
    for path, name in skills.items():
        f = repo / "skills" / path / "SKILL.md"
        f.parent.mkdir(parents=True, exist_ok=True)
        f.write_text(f"---\nname: {name}\n---\n")
    return repo


class TestGrouping(unittest.TestCase):
    def test_clean_grouped(self):
        with tempfile.TemporaryDirectory() as t:
            repo = repo_with(
                t,
                {"obsidian": "id: obsidian\nskills:\n  - obsidian/bases\n" + ENABLED.format(p="obsidian")},
                {"obsidian/bases": "bases"},
            )
            self.assertEqual(check_grouping.find_grouping_issues(repo), [])

    def test_name_must_equal_leaf(self):
        with tempfile.TemporaryDirectory() as t:
            repo = repo_with(
                t,
                {"obsidian": "id: obsidian\nskills:\n  - obsidian/bases\n" + ENABLED.format(p="obsidian")},
                {"obsidian/bases": "WRONG"},
            )
            issues = check_grouping.find_grouping_issues(repo)
            self.assertTrue(any("name" in i and "bases" in i for i in issues), issues)

    def test_group_must_equal_pluginname(self):
        with tempfile.TemporaryDirectory() as t:
            repo = repo_with(
                t,
                {"obsidian": "id: obsidian\nskills:\n  - go/gh\n" + ENABLED.format(p="obsidian")},
                {"go/gh": "gh"},
            )
            issues = check_grouping.find_grouping_issues(repo)
            self.assertTrue(any("group" in i.lower() and "obsidian" in i for i in issues), issues)

    def test_flat_skill_not_descended_into(self):
        # A flat skill (skills/go/SKILL.md) must not be treated as a group folder.
        with tempfile.TemporaryDirectory() as t:
            repo = repo_with(
                t,
                {"go": "id: go\nskills:\n  - go/gh\n" + ENABLED.format(p="go")},
                {"go": "go", "go/gh": "gh"},  # skills/go/SKILL.md exists AND skills/go/gh/SKILL.md
            )
            issues = check_grouping.find_grouping_issues(repo)
            self.assertTrue(any("direct" in i and "SKILL.md" in i for i in issues), issues)

    def test_duplicate_leaf(self):
        with tempfile.TemporaryDirectory() as t:
            repo = repo_with(
                t,
                {"x": "id: x\nskills:\n  - x/gh\n  - x/gh\n" + ENABLED.format(p="x")},
                {"x/gh": "gh"},
            )
            issues = check_grouping.find_grouping_issues(repo)
            self.assertTrue(any("duplicate" in i.lower() and "gh" in i for i in issues), issues)

    def test_duplicate_pluginname(self):
        with tempfile.TemporaryDirectory() as t:
            repo = repo_with(
                t,
                {
                    "a": "id: a\nskills:\n  - dup/one\n" + ENABLED.format(p="dup"),
                    "b": "id: b\nskills:\n  - dup/two\n" + ENABLED.format(p="dup"),
                },
                {"dup/one": "one", "dup/two": "two"},
            )
            issues = check_grouping.find_grouping_issues(repo)
            self.assertTrue(any("pluginName" in i and "dup" in i for i in issues), issues)

    def test_flat_legacy_bundle_ok(self):
        # The current shipping shape: pluginName swe, flat member go-gh, name go-gh.
        with tempfile.TemporaryDirectory() as t:
            repo = repo_with(
                t,
                {"swe": "id: swe\nskills:\n  - go-gh\n  - sops\n" + ENABLED.format(p="swe")},
                {"go-gh": "go-gh", "sops": "sops"},
            )
            self.assertEqual(check_grouping.find_grouping_issues(repo), [])

    def test_disabled_bundle_ignored(self):
        with tempfile.TemporaryDirectory() as t:
            repo = repo_with(
                t,
                {"x": "id: x\nskills:\n  - go/gh\ntargets:\n  claude:\n    enabled: false\n    pluginName: x\n"},
                {"go/gh": "gh"},
            )
            self.assertEqual(check_grouping.find_grouping_issues(repo), [])

    def test_main_exit_codes(self):
        with tempfile.TemporaryDirectory() as t:
            clean = repo_with(
                t,
                {"obsidian": "id: obsidian\nskills:\n  - obsidian/bases\n" + ENABLED.format(p="obsidian")},
                {"obsidian/bases": "bases"},
            )
            self.assertEqual(check_grouping.main([str(clean)]), 0)


if __name__ == "__main__":
    unittest.main()
