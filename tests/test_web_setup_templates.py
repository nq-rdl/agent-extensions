"""Tests for the cc-web-setup portable web-bootstrap assets.

These guard the data and helper that `/claude-code:web-setup` ships into other
repos: the two settings templates, the `marketplaces.json` single source of
truth, and the `web-settings.sh` guard helper (cover/ensure/strip-self). They are
the durable defence against regressing #157 (every enabled plugin's marketplace
must be declared in extraKnownMarketplaces) and against the templates drifting
from the marketplace source of truth or the engine assets being silently edited.
"""

import json
import os
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
SKILL = REPO / "skills" / "cc-web-setup"
ASSETS = SKILL / "assets"
SCRIPTS = SKILL / "scripts"

MARKETPLACES = ASSETS / "marketplaces.json"
RDL_TMPL = ASSETS / "settings.json.tmpl"
EXT_TMPL = ASSETS / "settings.externals.json.tmpl"
HELPER = SCRIPTS / "web-settings.sh"
SYNCED_HELPER = REPO / "plugins" / "claude-code" / "skills" / "web-setup" / "scripts" / "web-settings.sh"
LIVE_SCRIPTS = REPO / ".claude" / "scripts"

# The two SessionStart hook commands, in the exact order the platform must run them.
HOOK_CMDS = [
    '"$CLAUDE_PROJECT_DIR"/.claude/scripts/install-deps.sh',
    '"$CLAUDE_PROJECT_DIR"/.claude/scripts/announce-capabilities.sh',
]

HAVE_JQ = shutil.which("jq") is not None


def load(path):
    return json.loads(path.read_text())


def session_start_commands(settings):
    """Return the ordered list of SessionStart command strings in a settings dict."""
    groups = settings.get("hooks", {}).get("SessionStart", [])
    cmds = []
    for group in groups:
        for hook in group.get("hooks", []):
            cmds.append(hook.get("command"))
    return cmds


def run_helper(helper, *args, env=None):
    extra = dict(os.environ)
    if env:
        extra.update(env)
    return subprocess.run(
        ["bash", str(helper), *args],
        capture_output=True,
        text=True,
        env=extra,
    )


class TestMarketplacesJson(unittest.TestCase):
    """assets/marketplaces.json is the source of truth; it must be internally sound."""

    def setUp(self):
        self.data = load(MARKETPLACES)
        self.marketplaces = self.data["marketplaces"]
        self.externals = self.data["teamExternals"]

    def test_marketplace_entries_use_nested_schema(self):
        for name, entry in self.marketplaces.items():
            with self.subTest(marketplace=name):
                src = entry["source"]
                self.assertIsInstance(src, dict, "source must be a nested object")
                self.assertEqual(src["source"], "github")
                self.assertIsInstance(src["repo"], str)
                self.assertRegex(src["repo"], r"^[^/]+/[^/]+$")
                self.assertIsInstance(entry["autoUpdate"], bool)

    def test_every_external_references_a_known_marketplace(self):
        for ext in self.externals:
            with self.subTest(plugin=ext["id"]):
                name, _, mkt = ext["id"].partition("@")
                self.assertTrue(name and mkt, f"id must be name@marketplace: {ext['id']}")
                self.assertEqual(mkt, ext["marketplace"], "id suffix must match marketplace field")
                self.assertIn(ext["marketplace"], self.marketplaces)

    def test_externals_have_tags(self):
        for ext in self.externals:
            with self.subTest(plugin=ext["id"]):
                self.assertIn(ext["tag"], {"agnostic", "go", "python", "workflow"})

    def test_rdl_is_lookup_only_not_a_team_external(self):
        # rdl is in the lookup (for the rdl+externals composition path) but must never be
        # a curated team external, or strip-self's self-marketplace target would reappear.
        for ext in self.externals:
            with self.subTest(plugin=ext["id"]):
                self.assertNotEqual(ext["marketplace"], "rdl")
                self.assertNotEqual(ext["id"], "rdl@rdl")


class TestTemplates(unittest.TestCase):
    """The contract every shipped settings template must satisfy (both checked)."""

    TEMPLATES = {"rdl": RDL_TMPL, "externals": EXT_TMPL}

    def test_two_session_start_hooks_in_order(self):
        for label, path in self.TEMPLATES.items():
            with self.subTest(template=label):
                self.assertEqual(session_start_commands(load(path)), HOOK_CMDS)

    def test_enabled_plugins_are_true_and_qualified(self):
        for label, path in self.TEMPLATES.items():
            enabled = load(path).get("enabledPlugins", {})
            self.assertTrue(enabled, f"{label}: must enable at least one plugin")
            for pid, val in enabled.items():
                with self.subTest(template=label, plugin=pid):
                    self.assertIs(val, True)
                    name, _, mkt = pid.partition("@")
                    self.assertTrue(name and mkt, f"plugin id must be name@marketplace: {pid}")

    def test_every_enabled_marketplace_is_declared(self):
        # The #157 invariant: no enabled plugin may reference an undeclared marketplace.
        for label, path in self.TEMPLATES.items():
            settings = load(path)
            declared = set(settings.get("extraKnownMarketplaces", {}))
            for pid in settings.get("enabledPlugins", {}):
                mkt = pid.split("@", 1)[1]
                with self.subTest(template=label, plugin=pid):
                    self.assertIn(mkt, declared, f"{pid} references undeclared marketplace {mkt}")

    def test_marketplace_schema_and_source_of_truth(self):
        lookup = load(MARKETPLACES)["marketplaces"]
        for label, path in self.TEMPLATES.items():
            for name, entry in load(path).get("extraKnownMarketplaces", {}).items():
                with self.subTest(template=label, marketplace=name):
                    src = entry["source"]
                    self.assertIsInstance(src, dict)
                    self.assertEqual(src["source"], "github")
                    self.assertIsInstance(src["repo"], str)
                    self.assertIsInstance(entry["autoUpdate"], bool)
                    # Must match the single source of truth.
                    self.assertIn(name, lookup, f"{name} absent from marketplaces.json")
                    # Full-entry match (source object + autoUpdate), not just repo, so an
                    # autoUpdate flip or a nested-shape typo can't drift from the SoT.
                    self.assertEqual(
                        entry, lookup[name],
                        f"{name} in {label} template drifted from marketplaces.json",
                    )


class TestTemplateExactSets(unittest.TestCase):
    def test_rdl_template_enables_exactly_rdl(self):
        self.assertEqual(load(RDL_TMPL)["enabledPlugins"], {"rdl@rdl": True})

    def test_externals_template_matches_team_externals_and_excludes_rdl(self):
        external_ids = {e["id"] for e in load(MARKETPLACES)["teamExternals"]}
        enabled = load(EXT_TMPL)["enabledPlugins"]
        self.assertEqual(set(enabled), external_ids)
        self.assertNotIn("rdl@rdl", enabled)


class TestEngineByteIdentity(unittest.TestCase):
    """Invariant 0.1: the proven engine assets are never edited by this work."""

    @unittest.skipUnless(LIVE_SCRIPTS.is_dir(), "no live .claude/scripts to compare")
    def test_engine_assets_match_live_copies(self):
        for name in ("install-deps.sh", "announce-capabilities.sh"):
            with self.subTest(asset=name):
                self.assertEqual(
                    (ASSETS / name).read_bytes(),
                    (LIVE_SCRIPTS / name).read_bytes(),
                    f"{name} drifted from the live .claude/scripts copy",
                )


class TestPortabilityLint(unittest.TestCase):
    """web-settings.sh must stay bash-3.2 / macOS safe (no GNU/bash-4-only constructs)."""

    def test_no_bash4_or_gnu_only_constructs(self):
        # Scan code only — the header comment legitimately names these constructs.
        code = "\n".join(
            ln for ln in HELPER.read_text().splitlines() if not ln.lstrip().startswith("#")
        )
        for bad in ("declare -A", "mapfile", "readarray"):
            self.assertNotIn(bad, code, f"web-settings.sh uses non-portable {bad!r}")


@unittest.skipUnless(HAVE_JQ, "jq not available")
class TestWebSettingsHelper(unittest.TestCase):
    """Behavioural tests for the cover/ensure/strip-self guard helper."""

    def _write(self, obj):
        fd, path = tempfile.mkstemp(suffix=".json", dir=self.tmp)
        with os.fdopen(fd, "w") as fh:
            json.dump(obj, fh)
        return path

    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.tmp)
        self.externals = load(EXT_TMPL)

    def _externals_plus_rdl(self):
        """The 'rdl + externals' composition: the 7 externals + rdl@rdl enabled."""
        both = dict(self.externals)
        both["enabledPlugins"] = dict(both["enabledPlugins"], **{"rdl@rdl": True})
        return both

    # --- cover ---
    def test_cover_passes_on_covered_template(self):
        res = run_helper(HELPER, "cover", str(EXT_TMPL))
        self.assertEqual(res.returncode, 0, res.stderr)
        self.assertEqual(res.stdout.strip(), "")

    def test_cover_flags_orphan(self):
        path = self._write({"enabledPlugins": {"foo@bar": True}, "extraKnownMarketplaces": {}})
        res = run_helper(HELPER, "cover", path)
        self.assertEqual(res.returncode, 1)
        self.assertIn("foo@bar", res.stdout)

    # --- ensure ---
    def test_ensure_adds_known_marketplace(self):
        path = self._write(self._externals_plus_rdl())
        res = run_helper(HELPER, "ensure", path)
        self.assertEqual(res.returncode, 0, res.stderr)
        out = json.loads(res.stdout)
        # Assert the exact key set, so "right count, wrong marketplace" can't pass.
        self.assertEqual(
            set(out["extraKnownMarketplaces"]),
            {
                "claude-plugins-official", "openai-codex", "goland-claude-marketplace",
                "astral-sh", "worktrunk", "rdl",
            },
        )

    def test_ensure_is_noop_when_complete(self):
        res = run_helper(HELPER, "ensure", str(EXT_TMPL))
        self.assertEqual(res.returncode, 0, res.stderr)
        self.assertEqual(
            set(json.loads(res.stdout)["extraKnownMarketplaces"]),
            set(self.externals["extraKnownMarketplaces"]),
        )

    def test_ensure_unknown_emits_no_stdout_and_exits_4(self):
        path = self._write({"enabledPlugins": {"x@mystery": True}, "extraKnownMarketplaces": {}})
        res = run_helper(HELPER, "ensure", path)
        self.assertEqual(res.returncode, 4)
        self.assertEqual(res.stdout, "", "must not emit partial JSON on failure")
        self.assertIn("mystery", res.stderr)

    def test_ensure_rejects_unqualified_plugin_id(self):
        # A bare id with no @marketplace can never install; ensure must flag it (exit 4,
        # no stdout) rather than silently ignore it.
        path = self._write({"enabledPlugins": {"superpowers": True}, "extraKnownMarketplaces": {}})
        res = run_helper(HELPER, "ensure", path)
        self.assertEqual(res.returncode, 4)
        self.assertEqual(res.stdout, "")
        self.assertIn("superpowers", res.stderr)

    def test_cover_rejects_malformed_json(self):
        path = os.path.join(self.tmp, "bad.json")
        with open(path, "w") as fh:
            fh.write("{not valid json,,}")
        res = run_helper(HELPER, "cover", path)
        self.assertEqual(res.returncode, 2)
        self.assertEqual(res.stdout, "")

    def test_composed_rdl_plus_externals(self):
        # The 'rdl + externals' outcome: externals template + the single rdl line,
        # reconciled by ensure. No duplicate hooks, exactly one rdl@rdl, all 8
        # plugins, 6 marketplaces, and top-level keys preserved.
        both = self._externals_plus_rdl()
        path = self._write(both)
        res = run_helper(HELPER, "ensure", path)
        self.assertEqual(res.returncode, 0, res.stderr)
        out = json.loads(res.stdout)
        self.assertEqual(session_start_commands(out), HOOK_CMDS)
        self.assertEqual(set(out["enabledPlugins"]), set(both["enabledPlugins"]))
        self.assertIs(out["enabledPlugins"]["rdl@rdl"], True)
        self.assertIn("rdl", out["extraKnownMarketplaces"])
        self.assertEqual(len(out["extraKnownMarketplaces"]), 6)
        # ensure must only touch extraKnownMarketplaces — model/env/effortLevel survive.
        for key in ("model", "env", "effortLevel"):
            self.assertEqual(out.get(key), both.get(key))

    # --- strip-self ---
    def _marketplace_repo(self, name="rdl"):
        root = tempfile.mkdtemp(dir=self.tmp)
        plugin_dir = Path(root) / ".claude-plugin"
        plugin_dir.mkdir()
        (plugin_dir / "marketplace.json").write_text(
            json.dumps({"name": name, "plugins": [{"name": "go", "source": "./plugins/go"}]})
        )
        return root

    def test_strip_self_removes_self_reference(self):
        both = self._externals_plus_rdl()
        both["extraKnownMarketplaces"] = dict(
            both["extraKnownMarketplaces"],
            rdl={"source": {"source": "github", "repo": "nq-rdl/agent-extensions"}, "autoUpdate": True},
        )
        path = self._write(both)
        root = self._marketplace_repo("rdl")
        res = run_helper(HELPER, "strip-self", root, path)
        self.assertEqual(res.returncode, 0, res.stderr)
        out = json.loads(res.stdout)
        self.assertNotIn("rdl@rdl", out["enabledPlugins"])
        self.assertNotIn("rdl", out["extraKnownMarketplaces"])
        self.assertEqual(set(out["enabledPlugins"]), set(self.externals["enabledPlugins"]))

    def test_strip_self_keeps_a_differently_named_marketplace(self):
        # strip-self must remove ONLY its own marketplace name, never a foreign one.
        settings = {
            "enabledPlugins": {"rdl@rdl": True, "foo@other": True},
            "extraKnownMarketplaces": {
                "rdl": {"source": {"source": "github", "repo": "nq-rdl/agent-extensions"}, "autoUpdate": True},
                "other": {"source": {"source": "github", "repo": "acme/other"}, "autoUpdate": True},
            },
        }
        path = self._write(settings)
        root = self._marketplace_repo("someothermarket")  # self-name matches neither
        res = run_helper(HELPER, "strip-self", root, path)
        self.assertEqual(res.returncode, 0, res.stderr)
        out = json.loads(res.stdout)
        self.assertEqual(set(out["enabledPlugins"]), {"rdl@rdl", "foo@other"})
        self.assertEqual(set(out["extraKnownMarketplaces"]), {"rdl", "other"})

    def test_strip_self_passthrough_when_not_a_marketplace(self):
        path = self._write(self.externals)
        res = run_helper(HELPER, "strip-self", self.tmp, path)
        self.assertEqual(res.returncode, 0, res.stderr)
        # Whole document unchanged (not just enabledPlugins) for the passthrough path.
        self.assertEqual(json.loads(res.stdout), self.externals)

    def test_strip_self_rejects_nonexistent_repo_root(self):
        # A bad repo-root must fail fast, not silently skip the Phase 0 guard.
        path = self._write(self.externals)
        res = run_helper(HELPER, "strip-self", os.path.join(self.tmp, "nope"), path)
        self.assertEqual(res.returncode, 2)
        self.assertEqual(res.stdout, "")

    def test_strip_self_rejects_malformed_marketplace_json(self):
        root = tempfile.mkdtemp(dir=self.tmp)
        plugin_dir = Path(root) / ".claude-plugin"
        plugin_dir.mkdir()
        (plugin_dir / "marketplace.json").write_text("{not valid json,,}")
        path = self._write(self.externals)
        res = run_helper(HELPER, "strip-self", root, path)
        self.assertEqual(res.returncode, 2)
        self.assertEqual(res.stdout, "")

    def test_ensure_rejects_malformed_marketplaces_lookup(self):
        bad = os.path.join(self.tmp, "bad-marketplaces.json")
        with open(bad, "w") as fh:
            fh.write("{not valid json")
        path = self._write(
            {"enabledPlugins": {"superpowers@claude-plugins-official": True}, "extraKnownMarketplaces": {}}
        )
        res = run_helper(HELPER, "ensure", path, env={"WEB_SETTINGS_MARKETPLACES": bad})
        self.assertEqual(res.returncode, 2)
        self.assertEqual(res.stdout, "")

    def test_ensure_rejects_lookup_without_marketplaces_object(self):
        # A well-formed lookup that lacks an object .marketplaces must be exit 2, not a bare jq 5.
        bad = os.path.join(self.tmp, "no-marketplaces.json")
        with open(bad, "w") as fh:
            fh.write('{"teamExternals": []}')
        path = self._write({"enabledPlugins": {"x@y": True}, "extraKnownMarketplaces": {}})
        res = run_helper(HELPER, "ensure", path, env={"WEB_SETTINGS_MARKETPLACES": bad})
        self.assertEqual(res.returncode, 2)
        self.assertEqual(res.stdout, "")

    # --- shape gate: valid-JSON-but-wrong-shape must collapse to exit 2, no stdout ---
    def test_shape_gate_rejects_non_object_inputs(self):
        for sub in ("cover", "ensure", "strip-self"):
            for blob in ("null", "[]", '{"enabledPlugins": []}', '{"enabledPlugins": true}'):
                with self.subTest(sub=sub, blob=blob):
                    path = os.path.join(self.tmp, "shape.json")
                    with open(path, "w") as fh:
                        fh.write(blob)
                    args = [sub, self.tmp, path] if sub == "strip-self" else [sub, path]
                    res = run_helper(HELPER, *args)
                    self.assertEqual(res.returncode, 2, f"{sub} {blob}: {res.stderr}")
                    self.assertEqual(res.stdout, "", f"{sub} {blob} leaked stdout")

    # --- composition: the headline #157 / Phase 0→2→5 invariants under round-trip ---
    def test_cover_passes_on_ensure_output(self):
        # The literal #157 invariant: ensure's result is fully covered.
        path = self._write(self._externals_plus_rdl())
        ensured = run_helper(HELPER, "ensure", path)
        self.assertEqual(ensured.returncode, 0, ensured.stderr)
        out_path = self._write(json.loads(ensured.stdout))
        covered = run_helper(HELPER, "cover", out_path)
        self.assertEqual(covered.returncode, 0, covered.stderr)
        self.assertEqual(covered.stdout.strip(), "")

    def test_strip_self_then_ensure_then_cover_pipeline(self):
        # Full Phase 0→2→5 on a marketplace repo: strip the self ref, reconcile, assert covered.
        both = self._externals_plus_rdl()
        both["extraKnownMarketplaces"] = dict(
            both["extraKnownMarketplaces"],
            rdl={"source": {"source": "github", "repo": "nq-rdl/agent-extensions"}, "autoUpdate": True},
        )
        path = self._write(both)
        root = self._marketplace_repo("rdl")
        stripped = run_helper(HELPER, "strip-self", root, path)
        self.assertEqual(stripped.returncode, 0, stripped.stderr)
        p2 = self._write(json.loads(stripped.stdout))
        ensured = run_helper(HELPER, "ensure", p2)
        self.assertEqual(ensured.returncode, 0, ensured.stderr)
        p3 = self._write(json.loads(ensured.stdout))
        covered = run_helper(HELPER, "cover", p3)
        self.assertEqual(covered.returncode, 0, covered.stderr)
        self.assertEqual(covered.stdout.strip(), "")
        # No rdl left anywhere after the pipeline.
        final = json.loads(ensured.stdout)
        self.assertNotIn("rdl@rdl", final["enabledPlugins"])
        self.assertNotIn("rdl", final["extraKnownMarketplaces"])

    # --- dispatch contract ---
    def test_dispatch_errors_exit_2(self):
        for args in ([], ["bogus-subcommand"], ["cover"], ["cover", "a", "b"], ["strip-self", "only-one"]):
            with self.subTest(args=args):
                res = run_helper(HELPER, *args)
                self.assertEqual(res.returncode, 2, f"{args}: rc={res.returncode}")

    # --- dual-path asset resolution ---
    @unittest.skipUnless(SYNCED_HELPER.is_file(), "synced plugin copy not present (run sync-plugins)")
    def test_synced_copy_resolves_marketplaces(self):
        path = self._write(self._externals_plus_rdl())
        res = run_helper(SYNCED_HELPER, "ensure", path)
        self.assertEqual(res.returncode, 0, res.stderr)
        self.assertEqual(len(json.loads(res.stdout)["extraKnownMarketplaces"]), 6)


if __name__ == "__main__":
    unittest.main()
