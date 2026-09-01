"""Tests for scripts/generate_manifests.py — manifest generation (D-3).

plugin.json + marketplace.json are generated from registry/marketplace.yaml,
registry/bundles/*.yaml, and VERSION. These tests pin the structure, ordering,
key order (needed for byte-identical no-diff output), that unknown top-level
keys (e.g. the removed `external:` block) are ignored with a ::warning::,
version stamping, and the --check drift detector — all on a hermetic synthetic
repo.
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
displayName: RDL Test Marketplace
description: Test marketplace
pluginRoot: ./plugins
pluginDefaults:
  author:
    name: nq-rdl
  repository: https://github.com/nq-rdl/agent-extensions
  license: MIT
order: [swe, infra]
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

BUNDLE = (
    "id: {p}\ndisplayName: {p}\ndescription: {d}\nkeywords: {k}\n"
    "skills: [skill]\ntargets:\n  claude:\n    enabled: true\n    pluginName: {p}\n"
)


def enable_codex(repo, bundle="swe", plugin=None, category="Developer Tools", interface=""):
    path = repo / "registry" / "bundles" / f"{bundle}.yaml"
    plugin = plugin or bundle
    path.write_text(
        path.read_text()
        + "  codex:\n"
        + "    enabled: true\n"
        + f"    pluginName: {plugin}\n"
        + "    marketplaceName: rdl\n"
        + f"    category: {category}\n"
        + "    components:\n"
        + "      skills: true\n"
        + interface
    )


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

    def test_duplicate_marketplace_order_entry_rejected(self):
        with tempfile.TemporaryDirectory() as t:
            repo = make_repo(t)
            marketplace = repo / "registry" / "marketplace.yaml"
            marketplace.write_text(
                marketplace.read_text().replace(
                    "order: [swe, infra]", "order: [swe, swe, infra]"
                )
            )
            with self.assertRaisesRegex(ValueError, "duplicate plugin.*order"):
                generate_manifests.generate(repo)

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
            self.assertEqual(names, ["swe", "infra"])
            self.assertIn("::warning::", err.getvalue())
            # Pin the dedicated migration message, not just the substring
            # "external" (which the generic fallback warning also emits) — so
            # this guards the tailored `if "external" in unknown` branch.
            self.assertIn("user-level Claude Code config", err.getvalue())

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

    def test_codex_marketplace_and_plugin_manifest(self):
        with tempfile.TemporaryDirectory() as t:
            repo = make_repo(t)
            enable_codex(repo)
            generated = generate_manifests.generate(repo)

            self.assertEqual(
                generated["codex_marketplace"],
                {
                    "name": "rdl",
                    "interface": {"displayName": "RDL Test Marketplace"},
                    "plugins": [
                        {
                            "name": "swe",
                            "source": {"source": "local", "path": "./plugins/swe"},
                            "policy": {
                                "installation": "AVAILABLE",
                                "authentication": "ON_INSTALL",
                            },
                            "category": "Developer Tools",
                        }
                    ],
                },
            )
            manifest = generated["codex_plugins"]["swe"]
            self.assertEqual(manifest["skills"], "./skills/")
            self.assertEqual(manifest["keywords"], ["go", "ci"])
            self.assertEqual(manifest["interface"]["displayName"], "swe")
            self.assertEqual(manifest["interface"]["capabilities"], ["Skills"])

            targets = [
                path.relative_to(repo)
                for path, _content in generate_manifests._targets(repo, generated)
            ]
            self.assertIn(Path(".agents/plugins/marketplace.json"), targets)
            self.assertIn(Path("plugins/swe/.codex-plugin/plugin.json"), targets)

    def test_codex_interface_override(self):
        with tempfile.TemporaryDirectory() as t:
            repo = make_repo(t)
            enable_codex(
                repo,
                interface=(
                    "    interface:\n"
                    "      shortDescription: Short Codex description\n"
                    "      capabilities: [Review]\n"
                ),
            )
            manifest = generate_manifests.generate(repo)["codex_plugins"]["swe"]
            self.assertEqual(
                manifest["interface"]["shortDescription"], "Short Codex description"
            )
            self.assertEqual(manifest["interface"]["capabilities"], ["Review"])

    def test_unsupported_codex_interface_field_rejected(self):
        with tempfile.TemporaryDirectory() as t:
            repo = make_repo(t)
            enable_codex(
                repo,
                interface="    interface:\n      supportURL: https://example.com/help\n",
            )
            with self.assertRaisesRegex(ValueError, "unknown Codex interface field.*supportURL"):
                generate_manifests.generate(repo)

    def test_malformed_codex_interface_value_rejected(self):
        with tempfile.TemporaryDirectory() as t:
            repo = make_repo(t)
            enable_codex(
                repo,
                interface="    interface:\n      capabilities: Review\n",
            )
            with self.assertRaisesRegex(ValueError, "interface.capabilities must be a list"):
                generate_manifests.generate(repo)

    def test_invalid_codex_plugin_name_rejected(self):
        with tempfile.TemporaryDirectory() as t:
            repo = make_repo(t)
            bundle = repo / "registry" / "bundles" / "swe.yaml"
            bundle.write_text(bundle.read_text().replace("pluginName: swe", "pluginName: bad/name"))
            marketplace = repo / "registry" / "marketplace.yaml"
            marketplace.write_text(
                marketplace.read_text().replace("order: [swe, infra]", "order: [bad/name, infra]")
            )
            enable_codex(repo, plugin="bad/name")
            with self.assertRaisesRegex(ValueError, "invalid Codex plugin name"):
                generate_manifests.generate(repo)

    def test_non_string_codex_keyword_rejected(self):
        with tempfile.TemporaryDirectory() as t:
            repo = make_repo(t)
            bundle = repo / "registry" / "bundles" / "swe.yaml"
            bundle.write_text(bundle.read_text().replace("[go, ci]", "[go, 1]"))
            enable_codex(repo)
            with self.assertRaisesRegex(ValueError, "keywords must be a list of strings"):
                generate_manifests.generate(repo)

    def test_malformed_codex_marketplace_interface_defaults_rejected(self):
        cases = [
            ("displayName: RDL Test Marketplace", "displayName: 123", "displayName"),
            (
                "  repository: https://github.com/nq-rdl/agent-extensions",
                "  repository: 123",
                "repository",
            ),
            ("  author:\n    name: nq-rdl", "  author:\n    name: 123", "author.name"),
        ]
        for original, replacement, message in cases:
            with self.subTest(field=message), tempfile.TemporaryDirectory() as t:
                repo = make_repo(t)
                marketplace = repo / "registry" / "marketplace.yaml"
                marketplace.write_text(marketplace.read_text().replace(original, replacement))
                enable_codex(repo)
                with self.assertRaisesRegex(ValueError, message):
                    generate_manifests.generate(repo)

    def test_disabled_codex_hooks_are_not_emitted(self):
        with tempfile.TemporaryDirectory() as t:
            repo = make_repo(t)
            bundle = repo / "registry" / "bundles" / "swe.yaml"
            bundle.write_text(
                bundle.read_text().replace("skills: [skill]\n", "skills: [skill]\nhooks: [format]\n")
            )
            enable_codex(repo)
            manifest = generate_manifests.generate(repo)["codex_plugins"]["swe"]
            self.assertNotIn("hooks", manifest)

    def test_enabling_codex_does_not_change_claude_artifacts(self):
        with tempfile.TemporaryDirectory() as t:
            repo = make_repo(t)
            before = generate_manifests.generate(repo)
            enable_codex(repo)
            after = generate_manifests.generate(repo)

            self.assertEqual(after["marketplace"], before["marketplace"])
            self.assertEqual(after["plugins"], before["plugins"])

    def test_duplicate_codex_plugin_name_rejected(self):
        with tempfile.TemporaryDirectory() as t:
            repo = make_repo(t)
            for bundle in ("swe", "infra"):
                path = repo / "registry" / "bundles" / f"{bundle}.yaml"
                path.write_text(
                    path.read_text().replace(f"pluginName: {bundle}", "pluginName: shared")
                )
            marketplace = repo / "registry" / "marketplace.yaml"
            marketplace.write_text(
                marketplace.read_text().replace("order: [swe, infra]", "order: [shared]")
            )
            enable_codex(repo, "swe", plugin="shared")
            enable_codex(repo, "infra", plugin="shared")
            with self.assertRaisesRegex(ValueError, "used by both"):
                generate_manifests.generate(repo)

    def test_unsupported_codex_component_rejected(self):
        with tempfile.TemporaryDirectory() as t:
            repo = make_repo(t)
            enable_codex(repo)
            bundle = repo / "registry" / "bundles" / "swe.yaml"
            bundle.write_text(bundle.read_text() + "      hooks: true\n")
            with self.assertRaisesRegex(ValueError, "does not support.*hooks"):
                generate_manifests.generate(repo)

    def test_malformed_codex_components_rejected(self):
        with tempfile.TemporaryDirectory() as t:
            repo = make_repo(t)
            enable_codex(repo)
            bundle = repo / "registry" / "bundles" / "swe.yaml"
            bundle.write_text(
                bundle.read_text().replace(
                    "    components:\n      skills: true\n", "    components: []\n"
                )
            )
            with self.assertRaisesRegex(ValueError, "components must be a mapping"):
                generate_manifests.generate(repo)

    def test_long_codex_short_description_requires_override(self):
        with tempfile.TemporaryDirectory() as t:
            repo = make_repo(t)
            bundle = repo / "registry" / "bundles" / "swe.yaml"
            bundle.write_text(bundle.read_text().replace("SWE desc", "x" * 81))
            enable_codex(repo)
            with self.assertRaisesRegex(ValueError, "exceeds 80 characters"):
                generate_manifests.generate(repo)

    def test_per_bundle_license_override(self):
        # A bundle may override the default license (e.g. Apache-2.0 for a
        # vendored fork); bundles that omit `license:` keep the pluginDefaults
        # license (MIT).
        with tempfile.TemporaryDirectory() as t:
            repo = make_repo(t)
            (repo / "registry" / "bundles" / "forked.yaml").write_text(
                "id: forked\ndescription: Forked desc\nkeywords: [x]\n"
                "license: Apache-2.0\n"
                "targets:\n  claude:\n    enabled: true\n    pluginName: forked\n"
            )
            with contextlib.redirect_stderr(io.StringIO()):
                gen = generate_manifests.generate(repo)["plugins"]
            self.assertEqual(gen["forked"]["license"], "Apache-2.0")
            self.assertEqual(gen["swe"]["license"], "MIT")

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

    def test_write_removes_disabled_codex_artifacts(self):
        with tempfile.TemporaryDirectory() as t:
            repo = make_repo(t)
            enable_codex(repo)
            generate_manifests.write(repo)

            codex_marketplace = repo / ".agents" / "plugins" / "marketplace.json"
            codex_manifest = repo / "plugins" / "swe" / ".codex-plugin" / "plugin.json"
            self.assertTrue(codex_marketplace.is_file())
            self.assertTrue(codex_manifest.is_file())

            bundle = repo / "registry" / "bundles" / "swe.yaml"
            bundle.write_text(
                bundle.read_text().replace(
                    "  codex:\n    enabled: true\n",
                    "  codex:\n    enabled: false\n",
                )
            )
            self.assertTrue(
                any("obsolete" in issue for issue in generate_manifests.check(repo))
            )
            generate_manifests.write(repo)

            self.assertFalse(codex_marketplace.exists())
            self.assertFalse(codex_manifest.exists())

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
