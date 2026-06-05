"""Tests for scripts/generate_bundles_doc.py — docs/bundles.md generation.

The bundles doc is generated from registry/marketplace.yaml (order + meta) and
registry/bundles/*.yaml, mirroring generate_manifests. These tests pin the
section ordering, the leaf rename in skill invocations, empty-section
suppression, disabled-bundle exclusion, null-description handling, the
no-double-period guard, and the --check drift detector — all on a hermetic
synthetic repo.
"""

import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))

import generate_bundles_doc  # noqa: E402

MARKETPLACE_YAML = """\
name: rdl
order: [go, infra]
meta:
  name: rdl
  enabled: true
"""


def _bundle(p, d, enabled=True, skills="[]", agents="[]", mcp="[]", hooks="[]"):
    return (
        f"id: {p}\n"
        f"description: {d}\n"
        f"skills: {skills}\n"
        f"agents: {agents}\n"
        f"mcp: {mcp}\n"
        f"hooks: {hooks}\n"
        "targets:\n"
        "  claude:\n"
        f"    enabled: {str(enabled).lower()}\n"
        f"    pluginName: {p}\n"
    )


def make_repo(tmp, go_desc="Go tools"):
    repo = Path(tmp)
    (repo / "registry" / "bundles").mkdir(parents=True)
    (repo / "docs").mkdir()
    (repo / "registry" / "marketplace.yaml").write_text(MARKETPLACE_YAML)
    # go: a renamed leaf ({source, leaf}) and a flat member (leaf == source) + an agent.
    (repo / "registry" / "bundles" / "go.yaml").write_text(
        _bundle("go", go_desc, skills="[{source: go-secure, leaf: secure}, naming]", agents="[go-mcp-expert]")
    )
    # infra: no skills, no agents — exercises empty-section suppression.
    (repo / "registry" / "bundles" / "infra.yaml").write_text(_bundle("infra", "Infra tools"))
    return repo


class TestGenerate(unittest.TestCase):
    def test_leaf_rename_in_invocation(self):
        with tempfile.TemporaryDirectory() as t:
            out = generate_bundles_doc.generate(make_repo(t))
            self.assertIn("- `/go:secure`", out)   # {source, leaf} → renamed facet
            self.assertIn("- `/go:naming`", out)    # flat member → leaf == source
            self.assertNotIn("/go:go-secure", out)  # never the source name

    def test_agents_rendered_as_subagents(self):
        with tempfile.TemporaryDirectory() as t:
            out = generate_bundles_doc.generate(make_repo(t))
            self.assertIn("- `go-mcp-expert` (subagent)", out)

    def test_marketplace_order_respected(self):
        with tempfile.TemporaryDirectory() as t:
            out = generate_bundles_doc.generate(make_repo(t))
            self.assertLess(out.index("## go"), out.index("## infra"))

    def test_empty_sections_suppressed(self):
        with tempfile.TemporaryDirectory() as t:
            out = generate_bundles_doc.generate(make_repo(t))
            infra_block = out[out.index("## infra"):]
            self.assertNotIn("**Skills**", infra_block)
            self.assertNotIn("**Agents**", infra_block)

    def test_disabled_bundle_excluded(self):
        with tempfile.TemporaryDirectory() as t:
            repo = make_repo(t)
            (repo / "registry" / "bundles" / "off.yaml").write_text(
                _bundle("off", "Disabled", enabled=False)
            )
            self.assertNotIn("## off", generate_bundles_doc.generate(repo))

    def test_unordered_bundle_appended_sorted(self):
        with tempfile.TemporaryDirectory() as t:
            repo = make_repo(t)
            # 'zzz' is not in the order list → appended after the ordered ones.
            (repo / "registry" / "bundles" / "zzz.yaml").write_text(_bundle("zzz", "Zed"))
            out = generate_bundles_doc.generate(repo)
            self.assertGreater(out.index("## zzz"), out.index("## infra"))

    def test_null_description_does_not_crash(self):
        with tempfile.TemporaryDirectory() as t:
            repo = make_repo(t)
            (repo / "registry" / "bundles" / "go.yaml").write_text(
                "id: go\ndescription: null\nskills: []\nagents: []\n"
                "targets:\n  claude:\n    enabled: true\n    pluginName: go\n"
            )
            out = generate_bundles_doc.generate(repo)  # must not raise TypeError
            self.assertIn("## go", out)
            self.assertNotRegex(out, r"\n\.\n")  # empty description → no bare-period line

    def test_no_double_period(self):
        with tempfile.TemporaryDirectory() as t:
            out = generate_bundles_doc.generate(make_repo(t, go_desc="Go tools."))
            self.assertIn("Go tools.", out)
            self.assertNotIn("Go tools..", out)

    def test_mcp_and_hooks_rendered(self):
        with tempfile.TemporaryDirectory() as t:
            repo = make_repo(t)
            (repo / "registry" / "bundles" / "go.yaml").write_text(
                _bundle("go", "Go tools", mcp="[playwright]", hooks="[format]")
            )
            out = generate_bundles_doc.generate(repo)
            self.assertIn("**MCP server(s):** `playwright`", out)
            self.assertIn("**Hooks:** `format`", out)

    def test_meta_disabled_omits_install_command(self):
        with tempfile.TemporaryDirectory() as t:
            repo = make_repo(t)
            (repo / "registry" / "marketplace.yaml").write_text(
                "name: rdl\norder: [go, infra]\nmeta:\n  name: rdl\n  enabled: false\n"
            )
            out = generate_bundles_doc.generate(repo)
            self.assertNotIn("/plugin install rdl@rdl", out)


class TestCheck(unittest.TestCase):
    def test_write_then_check_clean(self):
        with tempfile.TemporaryDirectory() as t:
            repo = make_repo(t)
            self.assertEqual(generate_bundles_doc.main([str(repo)]), 0)           # write
            self.assertEqual(generate_bundles_doc.main([str(repo), "--check"]), 0)  # in sync

    def test_check_detects_drift(self):
        with tempfile.TemporaryDirectory() as t:
            repo = make_repo(t)
            generate_bundles_doc.main([str(repo)])
            (repo / "docs" / "bundles.md").write_text("tampered\n")
            self.assertEqual(generate_bundles_doc.main([str(repo), "--check"]), 1)

    def test_check_reports_missing(self):
        with tempfile.TemporaryDirectory() as t:
            repo = make_repo(t)
            self.assertEqual(generate_bundles_doc.main([str(repo), "--check"]), 1)


if __name__ == "__main__":
    unittest.main()
