"""Tests for scripts/check_grouping.py — the Option-2 grouping contract.

A bundle skill member is either a flat string (``leaf == source``) or an
explicit ``{source, leaf}`` mapping (a flat upstream skill packaged under a
different leaf, e.g. ``go-gh`` -> ``go:gh``). Grouping is owned in the registry;
the upstream ``skills/`` tree stays flat, so there are no upstream group folders
(the leaf folder drives invocation; sync-plugins.sh strips the plugin copy's
frontmatter ``name`` so the /-autocomplete label falls back to ``<plugin>:<leaf>``).

The checker enforces only the structural invariants that keep the generated
plugin tree coherent: valid member shape, no duplicate leaf within a bundle, and
a pluginName unique across bundles.
"""

import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))

import check_grouping  # noqa: E402

ENABLED = "targets:\n  claude:\n    enabled: true\n    pluginName: {p}\n"


def repo_with(tmp, bundles):
    repo = Path(tmp)
    (repo / "registry" / "bundles").mkdir(parents=True)
    for stem, body in bundles.items():
        (repo / "registry" / "bundles" / f"{stem}.yaml").write_text(body)
    return repo


class TestGrouping(unittest.TestCase):
    def test_clean_flat_bundle(self):
        # The current shipping shape: flat members, pluginName == id.
        with tempfile.TemporaryDirectory() as t:
            repo = repo_with(
                t, {"swe": "id: swe\nskills:\n  - go-gh\n  - sops\n" + ENABLED.format(p="swe")}
            )
            self.assertEqual(check_grouping.find_grouping_issues(repo), [])

    def test_clean_mapped_bundle(self):
        with tempfile.TemporaryDirectory() as t:
            repo = repo_with(
                t,
                {
                    "go": "id: go\nskills:\n  - source: go-gh\n    leaf: gh\n"
                    "  - source: go-naming\n    leaf: naming\n" + ENABLED.format(p="go")
                },
            )
            self.assertEqual(check_grouping.find_grouping_issues(repo), [])

    def test_duplicate_leaf_mapped(self):
        # Two mapped members colliding on the same leaf -> same plugin dest dir.
        with tempfile.TemporaryDirectory() as t:
            repo = repo_with(
                t,
                {
                    "go": "id: go\nskills:\n  - source: go-gh\n    leaf: gh\n"
                    "  - source: other\n    leaf: gh\n" + ENABLED.format(p="go")
                },
            )
            issues = check_grouping.find_grouping_issues(repo)
            self.assertTrue(any("duplicate" in i.lower() and "gh" in i for i in issues), issues)

    def test_duplicate_leaf_flat(self):
        with tempfile.TemporaryDirectory() as t:
            repo = repo_with(
                t, {"x": "id: x\nskills:\n  - sops\n  - sops\n" + ENABLED.format(p="x")}
            )
            issues = check_grouping.find_grouping_issues(repo)
            self.assertTrue(any("duplicate" in i.lower() and "sops" in i for i in issues), issues)

    def test_duplicate_pluginname(self):
        with tempfile.TemporaryDirectory() as t:
            repo = repo_with(
                t,
                {
                    "a": "id: a\nskills:\n  - one\n" + ENABLED.format(p="dup"),
                    "b": "id: b\nskills:\n  - two\n" + ENABLED.format(p="dup"),
                },
            )
            issues = check_grouping.find_grouping_issues(repo)
            self.assertTrue(any("pluginName" in i and "dup" in i for i in issues), issues)

    def test_malformed_member_reported(self):
        # A mapping missing 'leaf' is malformed — surfaced, not crashed on.
        with tempfile.TemporaryDirectory() as t:
            repo = repo_with(
                t, {"go": "id: go\nskills:\n  - source: go-gh\n" + ENABLED.format(p="go")}
            )
            issues = check_grouping.find_grouping_issues(repo)
            self.assertTrue(any("malformed" in i.lower() for i in issues), issues)

    def test_disabled_bundle_ignored(self):
        with tempfile.TemporaryDirectory() as t:
            repo = repo_with(
                t,
                {
                    "x": "id: x\nskills:\n  - source: go-gh\n    leaf: gh\n"
                    "targets:\n  claude:\n    enabled: false\n    pluginName: x\n"
                },
            )
            self.assertEqual(check_grouping.find_grouping_issues(repo), [])

    def test_main_exit_codes(self):
        with tempfile.TemporaryDirectory() as t:
            clean = repo_with(
                t, {"go": "id: go\nskills:\n  - source: go-gh\n    leaf: gh\n" + ENABLED.format(p="go")}
            )
            self.assertEqual(check_grouping.main([str(clean)]), 0)


if __name__ == "__main__":
    unittest.main()
