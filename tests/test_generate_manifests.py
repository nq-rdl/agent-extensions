"""Tests for scripts/generate_manifests.py — manifest generation (D-3).

plugin.json + marketplace.json are generated from registry/marketplace.yaml,
registry/bundles/*.yaml, and VERSION. These tests pin the structure, ordering,
key order (needed for byte-identical no-diff output), that unknown top-level
keys (e.g. the removed `external:` block) are ignored with a ::warning::,
version stamping, the rdl meta-plugin dependency list, and the --check drift
detector — all on a hermetic synthetic repo.
"""

import contextlib
import io
import json
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))

import generate_manifests  # noqa: E402

MARKETPLACE_YAML = """\
name: rdl
owner:
  name: nq-rdl
  email: x@y.z
description: Test marketplace
pluginRoot: ./plugins
pluginDefaults:
  author:
    name: nq-rdl
  repository: https://github.com/nq-rdl/agent-extensions
  license: MIT
order: [swe, infra]
meta:
  name: rdl
  enabled: true
  description: Install everything
  keywords: [meta]
"""

# A legacy `external:` passthrough block — the mechanism it fed was removed. The
# ignore/warn test appends this to the fixture so the rest of the suite isn't
# coupled to it (and doesn't emit the migration ::warning:: on every run).
EXTERNAL_BLOCK = """\
external:
  - name: worktrunk
    source: {source: github, repo: max-sixty/worktrunk}
    description: External tool
    keywords: [git]
"""

BUNDLE = "id: {p}\ndescription: {d}\nkeywords: {k}\ntargets:\n  claude:\n    enabled: true\n    pluginName: {p}\n"


def make_repo(tmp):
    repo = Path(tmp)
    (repo / "registry" / "bundles").mkdir(parents=True)
    (repo / "VERSION").write_text("1.2.3\n")
    (repo / "registry" / "marketplace.yaml").write_text(MARKETPLACE_YAML)
    (repo / "registry" / "bundles" / "swe.yaml").write_text(
        BUNDLE.format(p="swe", d="SWE desc", k="[go, ci]")
    )
    (repo / "registry" / "bundles" / "infra.yaml").write_text(
        BUNDLE.format(p="infra", d="Infra desc", k="[ansible]")
    )
    return repo


class TestGenerate(unittest.TestCase):
    def test_marketplace_top_level(self):
        with tempfile.TemporaryDirectory() as t:
            m = generate_manifests.generate(make_repo(t))["marketplace"]
            self.assertEqual(m["name"], "rdl")
            self.assertEqual(m["owner"], {"name": "nq-rdl", "email": "x@y.z"})
            self.assertEqual(
                m["metadata"],
                {"description": "Test marketplace", "version": "1.2.3", "pluginRoot": "./plugins"},
            )

    def test_local_entries_in_order(self):
        with tempfile.TemporaryDirectory() as t:
            m = generate_manifests.generate(make_repo(t))["marketplace"]
            names = [p["name"] for p in m["plugins"]]
            self.assertEqual(names[:2], ["swe", "infra"])
            self.assertEqual(
                m["plugins"][0],
                {
                    "name": "swe",
                    "source": "./plugins/swe",
                    "description": "SWE desc",
                    "version": "1.2.3",
                    "keywords": ["go", "ci"],
                },
            )

    def test_external_key_ignored(self):
        # The external passthrough mechanism was removed: a legacy `external:`
        # key in marketplace.yaml must be ignored (not re-hosted as a plugin),
        # but it must NOT vanish silently — generate() emits a ::warning:: so a
        # stale block is noticed instead of masked.
        with tempfile.TemporaryDirectory() as t:
            repo = make_repo(t)
            mkt = repo / "registry" / "marketplace.yaml"
            mkt.write_text(mkt.read_text() + EXTERNAL_BLOCK)
            err = io.StringIO()
            with contextlib.redirect_stderr(err):
                m = generate_manifests.generate(repo)["marketplace"]
            names = [p["name"] for p in m["plugins"]]
            self.assertNotIn("worktrunk", names)
            self.assertEqual(names, ["swe", "infra", "rdl"])
            self.assertIn("::warning::", err.getvalue())
            # Pin the dedicated migration message, not just the substring
            # "external" (which the generic fallback warning also emits) — so
            # this guards the tailored `if "external" in unknown` branch.
            self.assertIn("extraKnownMarketplaces", err.getvalue())

    def test_unknown_top_level_key_warns(self):
        # Any unrecognized top-level key (e.g. a typo like `oder:`) is ignored
        # but warned about, so the mistake surfaces instead of silently no-op'ing.
        with tempfile.TemporaryDirectory() as t:
            repo = make_repo(t)
            mkt = repo / "registry" / "marketplace.yaml"
            mkt.write_text(mkt.read_text() + "oder: [swe]\n")
            err = io.StringIO()
            with contextlib.redirect_stderr(err):
                generate_manifests.generate(repo)
            self.assertIn("::warning::", err.getvalue())
            self.assertIn("oder", err.getvalue())

    def test_no_warning_for_known_keys(self):
        # The clean fixture uses only recognized top-level keys → no warnings,
        # so the guard never cries wolf on a well-formed registry.
        with tempfile.TemporaryDirectory() as t:
            err = io.StringIO()
            with contextlib.redirect_stderr(err):
                generate_manifests.generate(make_repo(t))
            self.assertEqual(err.getvalue(), "")

    def test_meta_plugin_marketplace_entry(self):
        with tempfile.TemporaryDirectory() as t:
            m = generate_manifests.generate(make_repo(t))["marketplace"]
            rdl = next(p for p in m["plugins"] if p["name"] == "rdl")
            self.assertEqual(rdl["source"], "./plugins/rdl")
            self.assertEqual(rdl["version"], "1.2.3")
            self.assertEqual(rdl["keywords"], ["meta"])

    def test_plugin_json_fields_and_key_order(self):
        with tempfile.TemporaryDirectory() as t:
            pj = generate_manifests.generate(make_repo(t))["plugins"]["swe"]
            self.assertEqual(
                list(pj.keys()), ["name", "version", "description", "author", "repository", "license"]
            )
            self.assertEqual(pj["name"], "swe")
            self.assertEqual(pj["version"], "1.2.3")
            self.assertEqual(pj["description"], "SWE desc")
            self.assertEqual(pj["author"], {"name": "nq-rdl"})
            self.assertEqual(pj["license"], "MIT")

    def test_meta_plugin_dependencies(self):
        with tempfile.TemporaryDirectory() as t:
            mp = generate_manifests.generate(make_repo(t))["plugins"]["rdl"]
            self.assertEqual(mp["dependencies"], ["swe", "infra"])
            self.assertNotIn("rdl", mp["dependencies"])
            # dependencies sits after description, before author
            self.assertEqual(
                list(mp.keys()),
                ["name", "version", "description", "dependencies", "author", "repository", "license"],
            )

    def test_check_clean_after_write(self):
        with tempfile.TemporaryDirectory() as t:
            repo = make_repo(t)
            generate_manifests.write(repo)
            self.assertEqual(generate_manifests.check(repo), [])

    def test_check_detects_drift(self):
        with tempfile.TemporaryDirectory() as t:
            repo = make_repo(t)
            generate_manifests.write(repo)
            pj = repo / "plugins" / "swe" / ".claude-plugin" / "plugin.json"
            data = json.loads(pj.read_text())
            data["description"] = "HAND EDITED"
            pj.write_text(json.dumps(data, indent=2) + "\n")
            issues = generate_manifests.check(repo)
            self.assertTrue(any("swe" in i for i in issues), issues)

    def test_check_reports_missing_before_write(self):
        with tempfile.TemporaryDirectory() as t:
            repo = make_repo(t)
            self.assertNotEqual(generate_manifests.check(repo), [])

    def test_null_description_renders_empty_string(self):
        # `description: null` (present-but-null key) must not propagate JSON null
        # into the manifest — the `or ""` guard collapses it to an empty string.
        with tempfile.TemporaryDirectory() as t:
            repo = make_repo(t)
            (repo / "registry" / "bundles" / "swe.yaml").write_text(
                "id: swe\ndescription: null\nkeywords: [x]\n"
                "targets:\n  claude:\n    enabled: true\n    pluginName: swe\n"
            )
            pj = generate_manifests.generate(repo)["plugins"]["swe"]
            self.assertEqual(pj["description"], "")

    def test_disabled_bundle_excluded(self):
        with tempfile.TemporaryDirectory() as t:
            repo = make_repo(t)
            (repo / "registry" / "bundles" / "off.yaml").write_text(
                "id: off\ndescription: d\nkeywords: [x]\n"
                "targets:\n  claude:\n    enabled: false\n    pluginName: off\n"
            )
            gen = generate_manifests.generate(repo)
            self.assertNotIn("off", gen["plugins"])
            self.assertNotIn("off", [p["name"] for p in gen["marketplace"]["plugins"]])


if __name__ == "__main__":
    unittest.main()
