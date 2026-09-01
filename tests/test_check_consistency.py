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
        manifest = repo / "plugins" / name / ".claude-plugin" / "plugin.json"
        manifest.parent.mkdir(parents=True)
        manifest.write_text("{}")
    return repo


def bundle(plugin):
    return f"id: {plugin}\nskills:\n  - x\n" + ENABLED.format(p=plugin)


def mkt(name):
    return {"name": name, "source": f"./plugins/{name}"}


def enable_codex(repo, name="swe"):
    bundle_path = repo / "registry" / "bundles" / f"{name}.yaml"
    bundle_path.write_text(
        bundle_path.read_text()
        + f"  codex:\n    enabled: true\n    pluginName: {name}\n"
    )
    (repo / ".agents" / "plugins").mkdir(parents=True)
    (repo / ".agents" / "plugins" / "marketplace.json").write_text(
        json.dumps(
            {
                "plugins": [
                    {
                        "name": name,
                        "source": {"source": "local", "path": f"./plugins/{name}"},
                    }
                ]
            }
        )
    )
    codex_manifest = repo / "plugins" / name / ".codex-plugin" / "plugin.json"
    codex_manifest.parent.mkdir(parents=True)
    codex_manifest.write_text("{}")


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

    def test_codex_object_source_is_consistent(self):
        with tempfile.TemporaryDirectory() as tmp:
            repo = make_repo(
                tmp,
                bundles={"swe": bundle("swe")},
                marketplace_plugins=[mkt("swe")],
                plugin_dirs=["swe"],
            )
            enable_codex(repo)
            self.assertEqual(check_consistency.find_consistency_issues(repo), [])

    def test_flags_codex_manifest_without_enabled_bundle(self):
        with tempfile.TemporaryDirectory() as tmp:
            repo = make_repo(tmp, bundles={}, marketplace_plugins=[], plugin_dirs=[])
            manifest = repo / "plugins" / "ghost" / ".codex-plugin" / "plugin.json"
            manifest.parent.mkdir(parents=True)
            manifest.write_text("{}")
            issues = check_consistency.find_consistency_issues(repo)
            self.assertTrue(any("codex" in issue and "ghost" in issue for issue in issues), issues)

    def test_flags_codex_marketplace_source_for_wrong_plugin(self):
        with tempfile.TemporaryDirectory() as tmp:
            repo = make_repo(
                tmp,
                bundles={"swe": bundle("swe")},
                marketplace_plugins=[mkt("swe")],
                plugin_dirs=["swe"],
            )
            enable_codex(repo)
            marketplace = repo / ".agents" / "plugins" / "marketplace.json"
            data = json.loads(marketplace.read_text())
            data["plugins"][0]["source"]["path"] = "./plugins/other"
            marketplace.write_text(json.dumps(data))
            issues = check_consistency.find_consistency_issues(repo)
            self.assertTrue(any("source" in issue and "./plugins/swe" in issue for issue in issues), issues)

    def test_flags_missing_codex_manifest_file(self):
        with tempfile.TemporaryDirectory() as tmp:
            repo = make_repo(
                tmp,
                bundles={"swe": bundle("swe")},
                marketplace_plugins=[mkt("swe")],
                plugin_dirs=["swe"],
            )
            enable_codex(repo)
            (repo / "plugins" / "swe" / ".codex-plugin" / "plugin.json").unlink()
            issues = check_consistency.find_consistency_issues(repo)
            self.assertTrue(any("plugin.json" in issue and "swe" in issue for issue in issues), issues)


if __name__ == "__main__":
    unittest.main()
