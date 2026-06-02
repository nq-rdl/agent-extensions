"""Tests for scripts/check_consistency.py — three-way registry health (audit #8).

Generalises the issue #100 failure mode: an enabled bundle, its
marketplace.json entry, and its plugins/<name>/ directory must all agree. This
catches a retired bundle still listed in the marketplace, an orphaned plugin
dir, etc. — drift that the skill-reference check alone would not surface.
"""

import json
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))

import check_consistency  # noqa: E402

ENABLED = "targets:\n  claude:\n    enabled: true\n    pluginName: {p}\n"


def make_repo(tmp, bundles=None, marketplace_plugins=None, plugin_dirs=()):
    repo = Path(tmp)
    (repo / "registry" / "bundles").mkdir(parents=True)
    for stem, body in (bundles or {}).items():
        (repo / "registry" / "bundles" / f"{stem}.yaml").write_text(body)
    (repo / ".claude-plugin").mkdir(parents=True)
    (repo / ".claude-plugin" / "marketplace.json").write_text(
        json.dumps({"plugins": marketplace_plugins or []})
    )
    for name in plugin_dirs:
        (repo / "plugins" / name / ".claude-plugin").mkdir(parents=True)
    return repo


def bundle(plugin):
    return f"id: {plugin}\nskills:\n  - x\n" + ENABLED.format(p=plugin)


def mkt(name):
    return {"name": name, "source": f"./plugins/{name}"}


class TestConsistency(unittest.TestCase):
    def test_clean_repo_has_no_issues(self):
        with tempfile.TemporaryDirectory() as tmp:
            repo = make_repo(
                tmp,
                bundles={"swe": bundle("swe")},
                marketplace_plugins=[mkt("swe")],
                plugin_dirs=["swe"],
            )
            self.assertEqual(check_consistency.find_consistency_issues(repo), [])

    def test_scans_yml_extension_bundles(self):
        # validate.yml globbed *.yaml AND *.yml; the consistency checker must too.
        with tempfile.TemporaryDirectory() as tmp:
            repo = make_repo(tmp, marketplace_plugins=[], plugin_dirs=[])
            (repo / "registry" / "bundles" / "legacy.yml").write_text(bundle("legacy"))
            issues = check_consistency.find_consistency_issues(repo)
            self.assertTrue(any("legacy" in i for i in issues), issues)

    def test_flags_bundle_missing_from_marketplace(self):
        with tempfile.TemporaryDirectory() as tmp:
            repo = make_repo(
                tmp,
                bundles={"swe": bundle("swe")},
                marketplace_plugins=[],  # not published
                plugin_dirs=["swe"],
            )
            issues = check_consistency.find_consistency_issues(repo)
            self.assertTrue(any("marketplace" in i and "swe" in i for i in issues), issues)

    def test_flags_marketplace_plugin_without_bundle(self):
        with tempfile.TemporaryDirectory() as tmp:
            repo = make_repo(
                tmp,
                bundles={},  # no bundle
                marketplace_plugins=[mkt("ghost")],
                plugin_dirs=[],
            )
            issues = check_consistency.find_consistency_issues(repo)
            self.assertTrue(any("ghost" in i for i in issues), issues)

    def test_flags_orphan_plugin_dir(self):
        with tempfile.TemporaryDirectory() as tmp:
            repo = make_repo(
                tmp,
                bundles={},
                marketplace_plugins=[],
                plugin_dirs=["orphan"],
            )
            issues = check_consistency.find_consistency_issues(repo)
            self.assertTrue(any("orphan" in i for i in issues), issues)

    def test_meta_plugin_not_flagged_as_orphan(self):
        # The rdl meta-plugin has a marketplace entry + plugins/rdl/ dir but no
        # content bundle by design — marketplace.yaml meta.enabled whitelists it.
        with tempfile.TemporaryDirectory() as tmp:
            repo = make_repo(
                tmp,
                bundles={"swe": bundle("swe")},
                marketplace_plugins=[mkt("swe"), mkt("rdl")],
                plugin_dirs=["swe", "rdl"],
            )
            (repo / "registry" / "marketplace.yaml").write_text(
                "meta:\n  name: rdl\n  enabled: true\n"
            )
            self.assertEqual(check_consistency.find_consistency_issues(repo), [])

    def test_ignores_external_github_source(self):
        with tempfile.TemporaryDirectory() as tmp:
            repo = make_repo(
                tmp,
                bundles={"swe": bundle("swe")},
                marketplace_plugins=[
                    mkt("swe"),
                    {"name": "worktrunk", "source": {"source": "github", "repo": "x/y"}},
                ],
                plugin_dirs=["swe"],
            )
            # worktrunk is external — must NOT be flagged as a missing bundle/dir
            self.assertEqual(check_consistency.find_consistency_issues(repo), [])


if __name__ == "__main__":
    unittest.main()
