"""Strict target packaging, cache-safe command hooks and submission artifacts."""

import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest
from unittest.mock import patch
import zipfile
import yaml

from scripts import codex_package as package
from scripts import codex_directory as directory
from scripts import generate_manifests as manifests

REPO = Path(__file__).resolve().parents[1]


def fixture(root, *, mcp=False, hooks=False):
    (root / "registry/bundles").mkdir(parents=True)
    (root / "registry/marketplace.yaml").write_text(
        "name: test\nowner: {name: RDL}\norder: [sample]\npluginDefaults:\n  author: {name: RDL}\n  license: MIT\n"
    )
    (root / "VERSION").write_text("1.0.0\n")
    cfg = {
        "enabled": True,
        "category": "Developer Tools",
        "components": {"skills": True, "mcp": mcp, "hooks": hooks},
    }
    if mcp:
        cfg["mcpConfig"] = "mcp/source.json"
        (root / "mcp").mkdir()
        (root / "mcp/source.json").write_text(
            json.dumps(
                {
                    "mcpServers": {
                        "example": {"type": "http", "url": "https://example.com/mcp"}
                    }
                }
            )
        )
    if hooks:
        cfg["hookConfig"] = "hooks/codex/sample/hooks.json"
        dest = root / "hooks/codex/sample"
        dest.mkdir(parents=True)
        (dest / "hooks.json").write_text(
            json.dumps(
                {
                    "hooks": {
                        "SessionStart": [
                            {
                                "hooks": [
                                    {
                                        "type": "command",
                                        "command": 'bash "${PLUGIN_ROOT}/hooks/adapter.sh" codex-context',
                                        "timeout": 5,
                                    }
                                ]
                            }
                        ]
                    }
                }
            )
        )
        shutil.copy(REPO / "hooks/codex/adapter.sh", root / "hooks/codex/adapter.sh")
    data = {
        "id": "sample",
        "description": "Example task",
        "mcp": ["example"] if mcp else [],
        "skills": [{"source": "sample-task", "leaf": "task"}],
        "targets": {"claude": {"enabled": True}, "codex": cfg},
    }
    (root / "registry/bundles/sample.yaml").write_text(yaml.safe_dump(data))
    skill = root / "skills/sample-task"
    (skill / "references").mkdir(parents=True)
    (skill / "scripts").mkdir()
    (skill / "SKILL.md").write_text(
        "---\nname: sample-task\ndescription: Example task\n---\nRead [outline](references/subagent.rst) only when delegation helps.\n"
    )
    (skill / "references/subagent.rst").write_text("Return scoped findings.\n")
    helper = skill / "scripts/run.sh"
    helper.write_text("#!/bin/sh\nprintf done\\n\n")
    helper.chmod(0o755)
    return data


class StrictPackaging(unittest.TestCase):
    def test_native_override_preserves_tool_negation(self):
        with tempfile.TemporaryDirectory() as tmp:
            repo = Path(tmp)
            data = fixture(repo)
            native = (
                "Never call Claude's Bash, BashOutput, Agent, or AskUserQuestion tools from Codex.\n"
                "Use the host user-question tool to choose foreground or background.\n"
                "Read references/subagent.rst only when delegation helps.\n"
            )
            (repo / "skills/sample-task/references/codex.rst").write_text(native)
            data["targets"]["codex"]["skillOverrides"] = {"sample-task": "references/codex.rst"}
            (repo / "registry/bundles/sample.yaml").write_text(yaml.safe_dump(data))
            package.sync(repo)
            body = (repo / package.ROOT / "sample/skills/task/SKILL.md").read_text()
            self.assertIn(native, body)
            self.assertNotIn("tool tools", body)

    def test_legacy_user_question_phrases_are_grammatical(self):
        with tempfile.TemporaryDirectory() as tmp:
            repo = Path(tmp)
            fixture(repo)
            source = repo / "skills/sample-task/SKILL.md"
            with source.open("a") as out:
                for phrase in ("AskUserQuestion", "AskUserQuestion tool", "AskUserQuestion tools"):
                    out.write(f"Use {phrase} to ask.\n")
            package.sync(repo)
            body = (repo / package.ROOT / "sample/skills/task/SKILL.md").read_text()
            self.assertEqual(body.count("Use the host user-question tool to ask."), 3)
            self.assertNotIn("tool tools", body)

    def test_reference_only_invocations_receive_native_guidance(self):
        with tempfile.TemporaryDirectory() as tmp:
            repo = Path(tmp)
            fixture(repo)
            reference = repo / "skills/sample-task/references/publishing.rst"
            reference.write_text("Then invoke /sample:task.\n")
            package.sync(repo)
            root = repo / package.ROOT / "sample/skills/task"
            body = (root / "SKILL.md").read_text()
            self.assertIn("use $subject:facet in Codex", body)
            self.assertEqual((root / "references/publishing.rst").read_text(), reference.read_text())
            reference.write_text("See https://example.com/sample:task for an upstream example.\n")
            package.sync(repo)
            self.assertNotIn("use $subject:facet in Codex", (root / "SKILL.md").read_text())

    def test_independent_names_preserve_sources_and_delegation(self):
        with tempfile.TemporaryDirectory() as tmp:
            repo = Path(tmp)
            fixture(repo)
            original = (repo / "skills/sample-task/SKILL.md").read_bytes()
            package.sync(repo)
            self.assertEqual(package.validate(repo), [])
            root = repo / package.ROOT / "sample"
            self.assertEqual(
                package.frontmatter((root / "skills/task/SKILL.md").read_text())[0][
                    "name"
                ],
                "task",
            )
            self.assertEqual(
                (repo / "skills/sample-task/SKILL.md").read_bytes(), original
            )
            self.assertTrue((root / "skills/task/references/subagent.rst").exists())
            self.assertFalse(list(root.rglob("agents")))
            self.assertEqual(package.sync(repo, check=True), [])
            # Real install copies remain usable without their canonical source tree.
            cached = repo / "cache with spaces/sample"
            shutil.copytree(root, cached)
            shutil.rmtree(repo / "skills")
            proc = subprocess.run(
                ["sh", str(cached / "skills/task/scripts/run.sh")],
                capture_output=True,
                text=True,
            )
            self.assertEqual(proc.returncode, 0)

    def test_drift_detects_changed_bytes_modes_and_stale_agents(self):
        with tempfile.TemporaryDirectory() as tmp:
            repo = Path(tmp)
            fixture(repo)
            package.sync(repo)
            root = repo / package.ROOT / "sample"
            (root / "skills/task/scripts/run.sh").chmod(0o644)
            (root / "agents").mkdir()
            issues = package.sync(repo, check=True)
            self.assertTrue(any("mode" in x for x in issues), issues)
            self.assertTrue(any("agents" in x for x in issues), issues)
            package.sync(repo)
            self.assertFalse((root / "agents").exists())

    def test_source_symlink_escape_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            repo = Path(tmp)
            fixture(repo)
            (repo / "skills/sample-task/references/escape.rst").symlink_to(
                "/etc/passwd"
            )
            with self.assertRaisesRegex(ValueError, "symlinks"):
                package.sync(repo)

    def test_name_is_required_in_generated_package(self):
        with tempfile.TemporaryDirectory() as tmp:
            repo = Path(tmp)
            fixture(repo)
            package.sync(repo)
            path = repo / package.ROOT / "sample/skills/task/SKILL.md"
            path.write_text(path.read_text().replace("name: task\n", ""))
            self.assertTrue(any("skill name" in x for x in package.validate(repo)))

    def test_mcp_only_and_native_hooks(self):
        with tempfile.TemporaryDirectory() as tmp:
            repo = Path(tmp)
            data = fixture(repo, mcp=True, hooks=True)
            data["targets"]["codex"]["components"]["skills"] = False
            (repo / "registry/bundles/sample.yaml").write_text(yaml.safe_dump(data))
            package.sync(repo)
            self.assertEqual(package.validate(repo), [])
            root = repo / package.ROOT / "sample"
            self.assertFalse((root / "skills").exists())
            self.assertEqual(
                json.loads((root / "mcp.json").read_text())["mcpServers"]["example"][
                    "type"
                ],
                "streamable-http",
            )
            self.assertNotIn(
                "skills", json.loads((root / ".codex-plugin/plugin.json").read_text())
            )

    def test_exclusions_and_override_are_registry_scoped(self):
        with tempfile.TemporaryDirectory() as tmp:
            repo = Path(tmp)
            data = fixture(repo, mcp=True)
            data["targets"]["codex"]["excludeSkills"] = ["sample-task"]
            (repo / "registry/bundles/sample.yaml").write_text(yaml.safe_dump(data))
            package.sync(repo)
            self.assertFalse((repo / package.ROOT / "sample/skills").exists())
            data["targets"]["codex"]["excludeSkills"] = ["typo"]
            (repo / "registry/bundles/sample.yaml").write_text(yaml.safe_dump(data))
            with self.assertRaisesRegex(ValueError, "excludeSkills"):
                package.sync(repo)

    def test_no_agents_in_any_target(self):
        self.assertFalse((REPO / "agents").exists())
        self.assertFalse(list((REPO / "plugins").glob("*/agents")))
        self.assertFalse(list((REPO / package.ROOT).rglob("agents")))
        for path in (REPO / "registry/bundles").glob("*.yaml"):
            self.assertNotIn("agents", yaml.safe_load(path.read_text()))

    def test_native_manifest_is_the_only_entrypoint(self):
        for root in (REPO / package.ROOT).iterdir():
            native = json.loads((root / ".codex-plugin/plugin.json").read_text())
            self.assertEqual(native["name"], root.name)
            self.assertEqual(native["version"], (REPO / "VERSION").read_text().strip())
            self.assertFalse(
                (root / "plugin.json").exists(),
                "portable root suppresses hooks in the pinned runtime",
            )

    def test_invalid_hook_handler_event_and_missing_script_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            path = root / "hooks.json"
            for event, handler in [
                ("Stop", {"type": "agent", "prompt": "Review"}),
                (
                    "UserPromptExpansion",
                    {"type": "command", "command": 'bash "${PLUGIN_ROOT}/hooks/a.sh"'},
                ),
                (
                    "PreToolUse",
                    {"type": "command", "command": 'bash "${PLUGIN_ROOT}/hooks/a.sh"'},
                ),
            ]:
                path.write_text(json.dumps({"hooks": {event: [{"hooks": [handler]}]}}))
                with self.assertRaises(ValueError):
                    package.hook_config(path, root)


class NativeHookBehavior(unittest.TestCase):
    def run_hook(self, plugin, mode, event):
        root = REPO / package.ROOT / plugin
        with tempfile.TemporaryDirectory(prefix="codex hook cache ") as tmp:
            cached = Path(tmp) / plugin
            shutil.copytree(root, cached)
            env = {
                **os.environ,
                "PLUGIN_ROOT": str(cached),
                "HOME": tmp,
                "XDG_CONFIG_HOME": tmp,
            }
            for name in ("RH_OFFLINE_TOKEN", "RH_OFFLINE_TOKEN_FILE"):
                env.pop(name, None)
            proc = subprocess.run(
                ["bash", str(cached / "hooks/adapter.sh"), mode],
                input=json.dumps(event),
                text=True,
                capture_output=True,
                env=env,
                cwd=tmp,
            )
            self.assertEqual(proc.returncode, 0, proc.stderr)
            return json.loads(proc.stdout) if proc.stdout.strip() else {}

    def test_redhat_native_shell_denies_literal_secret(self):
        result = self.run_hook(
            "redhat",
            "redhat-docs-guard",
            {
                "hook_event_name": "PreToolUse",
                "tool_name": "Bash",
                "tool_input": {
                    "command": "RH_OFFLINE_TOKEN=literal-secret curl https://access.redhat.com/solutions/1"
                },
            },
        )
        self.assertEqual(result["hookSpecificOutput"]["permissionDecision"], "deny")

    def test_redhat_ask_becomes_supported_deny(self):
        result = self.run_hook(
            "redhat",
            "redhat-docs-guard",
            {
                "hook_event_name": "PreToolUse",
                "tool_name": "Bash",
                "tool_input": {"command": "curl https://sso.redhat.com/token"},
            },
        )
        self.assertEqual(result["hookSpecificOutput"]["permissionDecision"], "deny")

    def test_unrelated_shell_passes(self):
        self.assertEqual(
            self.run_hook(
                "redhat",
                "redhat-docs-guard",
                {
                    "hook_event_name": "PreToolUse",
                    "tool_name": "Bash",
                    "tool_input": {"command": "git status --short"},
                },
            ),
            {},
        )

    def test_sql_patch_protects_authoritative_paths_but_not_drafts(self):
        for path, blocked in [
            (".sqlreview/reviews/a/review.json", True),
            (".sqlreview/reviews/a/../a/scope.md", True),
            (".sqlreview/reviews/a/review.draft.json", False),
            ("src/main.go", False),
        ]:
            with self.subTest(path=path):
                result = self.run_hook(
                    "sql-code",
                    "sql-code-guard",
                    {
                        "hook_event_name": "PreToolUse",
                        "tool_name": "apply_patch",
                        "tool_input": {
                            "command": f"*** Begin Patch\n*** Update File: {path}\n@@\n-old\n+new\n*** End Patch"
                        },
                    },
                )
                self.assertEqual(
                    result.get("hookSpecificOutput", {}).get("permissionDecision")
                    == "deny",
                    blocked,
                )

    def test_skill_nudge_reads_native_patch_headers(self):
        result = self.run_hook(
            "claude-code",
            "skill-audit-nudge",
            {
                "hook_event_name": "PostToolUse",
                "tool_name": "apply_patch",
                "tool_input": {
                    "command": "*** Begin Patch\n*** Update File: skills/example/SKILL.md\n@@\n-old\n+new\n*** End Patch"
                },
            },
        )
        self.assertIn("skill-audit", result["hookSpecificOutput"]["additionalContext"])

    def test_writing_reminder_is_advisory_and_scoped(self):
        for prompt, expected in [
            ("Use $tech-writing:copyedit on this file", True),
            ("What is 2+2?", False),
        ]:
            result = self.run_hook(
                "tech-writing",
                "stylepedia-reminder",
                {"hook_event_name": "UserPromptSubmit", "prompt": prompt},
            )
            self.assertEqual(bool(result), expected)
            self.assertNotIn("decision", result)

    def test_prompt_hooks_match_and_skip_unrelated_tasks(self):
        for plugin, mode, prompt in [
            ("opencode-dev", "opencode-doc-review", "Develop an OpenCode tool"),
            ("speckit-dev", "speckit-publish-target", "Publish my spec-kit extension"),
        ]:
            result = self.run_hook(
                plugin, mode, {"hook_event_name": "UserPromptSubmit", "prompt": prompt}
            )
            self.assertIn("additionalContext", result["hookSpecificOutput"])
            self.assertEqual(
                self.run_hook(
                    plugin,
                    mode,
                    {"hook_event_name": "UserPromptSubmit", "prompt": "Hello"},
                ),
                {},
            )


class DirectoryArtifacts(unittest.TestCase):
    def test_rebuilding_archives_removes_only_previous_generated_files(self):
        with tempfile.TemporaryDirectory() as tmp:
            repo = Path(tmp)
            fixture(repo)
            package.sync(repo)
            data = directory.report(repo)
            destination = repo / "archives"
            directory.write_archives(repo, destination, data)
            unrelated = destination / "unrelated.zip"
            unrelated.write_bytes(b"keep")
            old = destination / "sample-1.0.0.zip"
            self.assertTrue(old.exists())
            (repo / "VERSION").write_text("2.0.0\n")
            package.sync(repo)
            data = directory.report(repo)
            directory.write_archives(repo, destination, data)
            self.assertFalse(old.exists())
            self.assertTrue((destination / "sample-2.0.0.zip").exists())
            self.assertEqual(unrelated.read_bytes(), b"keep")
            self.assertNotIn("1.0.0", (destination / "SHA256SUMS").read_text())
            # A removed bundle must also disappear from the output set.
            directory.write_archives(repo, destination, {**data, "plugins": []})
            self.assertEqual(list(destination.glob("*.zip")), [unrelated])
            directory.write_archives(repo, destination, data)
            self.assertTrue((destination / "sample-2.0.0.zip").exists())

    def test_archive_build_failure_preserves_previous_set(self):
        with tempfile.TemporaryDirectory() as tmp:
            repo = Path(tmp)
            fixture(repo)
            package.sync(repo)
            destination = repo / "archives"
            data = directory.report(repo)
            directory.write_archives(repo, destination, data)
            before = {p.name: p.read_bytes() for p in destination.iterdir()}
            with patch.object(directory, "archive", side_effect=OSError("build failed")):
                with self.assertRaisesRegex(OSError, "build failed"):
                    directory.write_archives(repo, destination, data)
            self.assertEqual({p.name: p.read_bytes() for p in destination.iterdir()}, before)

    def test_readiness_attestations_require_actual_booleans(self):
        with tempfile.TemporaryDirectory() as tmp:
            repo = Path(tmp)
            fixture(repo)
            package.sync(repo)
            manifest_path = repo / package.ROOT / "sample/.codex-plugin/plugin.json"
            manifest = json.loads(manifest_path.read_text())
            manifest["interface"].update(
                logo="logo.png", privacyPolicyURL="https://example.com/privacy",
                termsOfServiceURL="https://example.com/terms",
            )
            manifest_path.write_text(json.dumps(manifest))
            publisher = {
                "supportURL": "https://example.com/support", "identityVerified": True,
                "availabilityRegions": ["AU"], "behavioralEvidence": {"sample": True},
            }
            path = repo / "registry/codex-directory.yaml"
            path.write_text(yaml.safe_dump(publisher))
            self.assertTrue(directory.report(repo)["plugins"][0]["submissionReady"])
            for key in ("identityVerified", "behavioralEvidence"):
                for value in (False, "false", "true", 1, [], {"verified": True}, None):
                    with self.subTest(key=key, value=value):
                        malformed = {**publisher, key: {"sample": value} if key == "behavioralEvidence" else value}
                        path.write_text(yaml.safe_dump(malformed))
                        result = directory.report(repo)["plugins"][0]
                        self.assertFalse(result["submissionReady"])
                        self.assertEqual(len(result["blockers"]), 1)

    def test_archives_are_reproducible_and_keep_executable_modes(self):
        with tempfile.TemporaryDirectory() as tmp:
            repo = Path(tmp)
            fixture(repo)
            package.sync(repo)
            root = repo / package.ROOT / "sample"
            a, b = repo / "a.zip", repo / "b.zip"
            self.assertEqual(directory.archive(root, a), directory.archive(root, b))
            with zipfile.ZipFile(a) as z:
                self.assertIn(".codex-plugin/plugin.json", z.namelist())
                self.assertEqual(
                    z.getinfo("skills/task/scripts/run.sh").external_attr >> 16 & 0o111,
                    0o111,
                )

    def test_readiness_does_not_claim_external_acceptance(self):
        data = directory.report(REPO)
        self.assertEqual(len(data["plugins"]), 36)
        self.assertTrue(all(p["packageReady"] for p in data["plugins"]))
        self.assertFalse(any(p["submissionReady"] for p in data["plugins"]))
        self.assertEqual(
            next(x for x in data["plugins"] if x["plugin"] == "playwright")["route"],
            "local-mcp",
        )
        self.assertEqual(
            next(x for x in data["plugins"] if x["plugin"] == "lucid")["route"],
            "remote-mcp",
        )


if __name__ == "__main__":
    unittest.main()
