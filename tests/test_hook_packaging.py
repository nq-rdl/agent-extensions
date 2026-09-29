"""Canonical hook packaging contract (#311 work package A).

``scripts/sync-plugins.sh`` generates every hook-bearing plugin's
``hooks/hooks.json`` from the canonical ``hooks/<plugin>/hooks.json`` and copies
each registry hook to the destination that config names
(``${CLAUDE_PLUGIN_ROOT}/<dir>/<name>.sh``). ``--check`` must fail on any
stale, missing, content-drifted, or mode-drifted copy, on a copy left at a
legacy location, and on a ``${CLAUDE_PLUGIN_ROOT}`` path that does not resolve
inside the installed tree. Vendored files that share a destination directory
must never be pruned.

Fixture tests run the real script inside a throwaway repository (see
test_sync_plugins.py). ``RepoInvariants`` checks the checked-in catalog.
"""

from __future__ import annotations

import json
import os
import re
import shutil
import stat
import subprocess
import tempfile
import unittest
from pathlib import Path

import yaml

from test_sync_plugins import REPO, SCRIPT, run_sync, write


def check(repo: Path):
    (repo / "scripts").mkdir(parents=True, exist_ok=True)
    shutil.copy(SCRIPT, repo / "scripts/sync-plugins.sh")
    for dependency in ("codex_package.py", "generate_manifests.py", "_registry.py"):
        shutil.copy(REPO / "scripts" / dependency, repo / "scripts" / dependency)
    return subprocess.run(
        ["bash", str(repo / "scripts/sync-plugins.sh"), "--check"],
        cwd=repo, capture_output=True, text=True,
    )


def config(*commands: str) -> str:
    hooks = [{"type": "command", "command": c} for c in commands]
    return json.dumps({"hooks": {"SessionStart": [{"hooks": hooks}]}}) + "\n"


def bundle(repo: Path, hooks: list[str], plugin: str = "demo"):
    write(
        repo / f"registry/bundles/{plugin}.yaml",
        yaml.safe_dump({"id": plugin, "hooks": hooks,
                        "targets": {"claude": {"enabled": True, "pluginName": plugin}}}),
    )


def hook(repo: Path, name: str, body: str = "#!/bin/bash\nexit 0\n"):
    path = repo / "hooks" / f"{name}.sh"
    write(path, body)
    path.chmod(0o755)
    return path


def is_exec(path: Path) -> bool:
    return bool(path.stat().st_mode & stat.S_IXUSR)


class DestinationFromConfig(unittest.TestCase):
    def test_scripts_destination_keeps_vendored_files_and_checks_mode(self):
        with tempfile.TemporaryDirectory() as tmp:
            repo = Path(tmp)
            bundle(repo, ["reminder"])
            hook(repo, "reminder")
            write(repo / "hooks/demo/hooks.json",
                  config('"${CLAUDE_PLUGIN_ROOT}/scripts/reminder.sh"'))
            vendored = repo / "plugins/demo/scripts/runtime.mjs"
            write(vendored, "// vendored upstream runtime\n")
            result = run_sync(repo)
            self.assertEqual(result.returncode, 0, result.stderr)
            packaged = repo / "plugins/demo/scripts/reminder.sh"
            self.assertEqual(packaged.read_bytes(), (repo / "hooks/reminder.sh").read_bytes())
            self.assertTrue(is_exec(packaged), "executable bit must survive packaging")
            self.assertTrue(vendored.is_file(), "vendored runtime must never be pruned")
            self.assertEqual((repo / "plugins/demo/hooks/hooks.json").read_text(),
                             (repo / "hooks/demo/hooks.json").read_text())
            self.assertEqual(check(repo).returncode, 0, check(repo).stderr)

            packaged.chmod(0o644)
            drift = check(repo)
            self.assertNotEqual(drift.returncode, 0)
            self.assertIn("plugins/demo/scripts/reminder.sh", drift.stderr)
            self.assertEqual(run_sync(repo).returncode, 0)
            self.assertTrue(is_exec(packaged))

            packaged.write_text("stale")
            self.assertNotEqual(check(repo).returncode, 0)
            self.assertEqual(packaged.read_text(), "stale", "--check must not modify files")

            packaged.unlink()
            missing = check(repo)
            self.assertNotEqual(missing.returncode, 0)
            self.assertIn("missing", missing.stderr)

    def test_hand_edited_generated_config_is_drift(self):
        with tempfile.TemporaryDirectory() as tmp:
            repo = Path(tmp)
            bundle(repo, ["reminder"])
            hook(repo, "reminder")
            write(repo / "hooks/demo/hooks.json",
                  config('bash "${CLAUDE_PLUGIN_ROOT}/hooks/reminder.sh"'))
            self.assertEqual(run_sync(repo).returncode, 0)
            (repo / "plugins/demo/hooks/hooks.json").write_text('{"hooks": {}}\n')
            self.assertNotEqual(check(repo).returncode, 0)

    def test_copy_left_at_a_legacy_location_is_stale_and_pruned(self):
        with tempfile.TemporaryDirectory() as tmp:
            repo = Path(tmp)
            bundle(repo, ["reminder"])
            hook(repo, "reminder")
            write(repo / "hooks/demo/hooks.json",
                  config('bash "${CLAUDE_PLUGIN_ROOT}/hooks/reminder.sh"'))
            self.assertEqual(run_sync(repo).returncode, 0)
            legacy = repo / "plugins/demo/scripts/reminder.sh"
            write(legacy, (repo / "hooks/reminder.sh").read_text())
            vendored = repo / "plugins/demo/scripts/keep.mjs"
            write(vendored, "// vendored\n")
            result = check(repo)
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("plugins/demo/scripts/reminder.sh", result.stderr)
            self.assertTrue(legacy.exists())
            self.assertEqual(run_sync(repo).returncode, 0)
            self.assertFalse(legacy.exists())
            self.assertTrue(vendored.exists())

    def test_hooks_directory_without_canonical_config_is_stale(self):
        with tempfile.TemporaryDirectory() as tmp:
            repo = Path(tmp)
            bundle(repo, [])
            write(repo / "plugins/demo/hooks/hooks.json", '{"hooks": {}}\n')
            self.assertNotEqual(check(repo).returncode, 0)
            self.assertEqual(run_sync(repo).returncode, 0)
            self.assertFalse((repo / "plugins/demo/hooks").exists())


class MappingErrors(unittest.TestCase):
    def assert_sync_and_check_fail(self, repo: Path, needle: str):
        for runner in (check, run_sync):
            result = runner(repo)
            self.assertNotEqual(result.returncode, 0, runner.__name__)
            self.assertIn(needle, result.stderr + result.stdout, runner.__name__)

    def test_registry_hooks_require_a_canonical_config(self):
        with tempfile.TemporaryDirectory() as tmp:
            repo = Path(tmp)
            bundle(repo, ["reminder"])
            hook(repo, "reminder")
            self.assert_sync_and_check_fail(repo, "hooks/demo/hooks.json")

    def test_listed_hook_must_be_wired(self):
        with tempfile.TemporaryDirectory() as tmp:
            repo = Path(tmp)
            bundle(repo, ["reminder", "unused"])
            hook(repo, "reminder")
            hook(repo, "unused")
            write(repo / "hooks/demo/hooks.json",
                  config('bash "${CLAUDE_PLUGIN_ROOT}/hooks/reminder.sh"'))
            self.assert_sync_and_check_fail(repo, "unused")

    def test_wired_script_must_be_a_registry_hook(self):
        with tempfile.TemporaryDirectory() as tmp:
            repo = Path(tmp)
            bundle(repo, ["reminder"])
            hook(repo, "reminder")
            hook(repo, "other")
            write(repo / "hooks/demo/hooks.json", config(
                'bash "${CLAUDE_PLUGIN_ROOT}/hooks/reminder.sh"',
                'bash "${CLAUDE_PLUGIN_ROOT}/hooks/other.sh"'))
            self.assert_sync_and_check_fail(repo, "other")

    def test_unquoted_plugin_root_is_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            repo = Path(tmp)
            bundle(repo, ["reminder"])
            hook(repo, "reminder")
            write(repo / "hooks/demo/hooks.json",
                  config("${CLAUDE_PLUGIN_ROOT}/scripts/reminder.sh"))
            self.assert_sync_and_check_fail(repo, "quote")

    def test_unresolved_plugin_root_helper_fails(self):
        with tempfile.TemporaryDirectory() as tmp:
            repo = Path(tmp)
            bundle(repo, ["reminder"])
            hook(repo, "reminder",
                 '#!/bin/bash\nbash "${CLAUDE_PLUGIN_ROOT:-/nonexistent}/skills/setup/scripts/helper.sh"\n')
            write(repo / "hooks/demo/hooks.json",
                  config('bash "${CLAUDE_PLUGIN_ROOT}/hooks/reminder.sh"'))
            self.assert_sync_and_check_fail(repo, "skills/setup/scripts/helper.sh")

    def test_resolved_skill_helper_passes(self):
        with tempfile.TemporaryDirectory() as tmp:
            repo = Path(tmp)
            write(repo / "registry/bundles/demo.yaml", yaml.safe_dump({
                "id": "demo", "hooks": ["reminder"],
                "skills": [{"source": "demo-setup", "leaf": "setup"}],
                "targets": {"claude": {"enabled": True, "pluginName": "demo"}}}))
            write(repo / "skills/demo-setup/SKILL.md", "---\nname: demo-setup\ndescription: x\n---\n")
            write(repo / "skills/demo-setup/scripts/helper.sh", "#!/bin/bash\n")
            hook(repo, "reminder",
                 '#!/bin/bash\nbash "${CLAUDE_PLUGIN_ROOT:-/nonexistent}/skills/setup/scripts/helper.sh"\n')
            write(repo / "hooks/demo/hooks.json",
                  config('bash "${CLAUDE_PLUGIN_ROOT}/hooks/reminder.sh"'))
            result = run_sync(repo)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual(check(repo).returncode, 0)


PLUGIN_ROOT_REF = re.compile(r"\$\{CLAUDE_PLUGIN_ROOT(?::-[^}]*)?\}/([A-Za-z0-9._-]+(?:/[A-Za-z0-9._-]+)*)")


class RepoInvariants(unittest.TestCase):
    def bundles(self):
        for path in sorted((REPO / "registry/bundles").glob("*.yaml")):
            data = yaml.safe_load(path.read_text()) or {}
            claude = (data.get("targets") or {}).get("claude") or {}
            if claude.get("enabled"):
                yield data, claude.get("pluginName") or data["id"]

    def test_every_hook_bundle_has_a_canonical_claude_config(self):
        for data, plugin in self.bundles():
            if data.get("hooks"):
                with self.subTest(plugin=plugin):
                    self.assertTrue((REPO / "hooks" / plugin / "hooks.json").is_file())

    def test_no_generated_hooks_dir_without_a_canonical_config(self):
        for data, plugin in self.bundles():
            if (REPO / "plugins" / plugin / "hooks").exists():
                with self.subTest(plugin=plugin):
                    self.assertTrue((REPO / "hooks" / plugin / "hooks.json").is_file())

    def test_installed_plugin_root_references_resolve(self):
        roots = [REPO / "plugins" / p for _, p in self.bundles()]
        roots += sorted((REPO / "dist/codex/plugins").glob("*"))
        for root in roots:
            for script in sorted(root.glob("hooks/*.sh")) + sorted(root.glob("scripts/*.sh")):
                for ref in PLUGIN_ROOT_REF.findall(script.read_text()):
                    with self.subTest(script=str(script.relative_to(REPO)), ref=ref):
                        self.assertTrue((root / ref).exists())

    def test_packaged_hook_scripts_are_executable(self):
        for data, plugin in self.bundles():
            for name in data.get("hooks") or []:
                copies = list((REPO / "plugins" / plugin).glob(f"*/{name}.sh"))
                with self.subTest(plugin=plugin, hook=name):
                    self.assertEqual(len(copies), 1, copies)
                    self.assertTrue(os.access(copies[0], os.X_OK))


if __name__ == "__main__":
    unittest.main()
