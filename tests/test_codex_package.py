"""Strict target packaging, cache-safe command hooks and submission artifacts."""

import json
import os
import re
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
    def test_native_delegation_roots_execute_from_cache_and_host_examples_survive(self):
        with tempfile.TemporaryDirectory() as tmp:
            repo = Path(tmp)
            data = fixture(repo)
            source = repo / "skills/sample-task"
            commands = 'S="${CLAUDE_PLUGIN_ROOT}/skills/task/scripts"\nbash "$S/run.sh"\n'
            outline = source / "references/subagent.rst"
            outline.write_text(commands)
            example = source / "references/claude-config.rst"
            example.write_text('Claude hook example: "${CLAUDE_PLUGIN_ROOT}/hooks/check.sh"\n')
            package.sync(repo)
            cached = repo / "installed cache/sample"
            shutil.copytree(repo / package.ROOT / "sample", cached)
            workspace = repo / "unrelated workspace"
            workspace.mkdir()
            native = (cached / "skills/task/references/subagent.rst").read_text()
            env = {**os.environ, "PLUGIN_ROOT": str(cached)}
            env.pop("CLAUDE_PLUGIN_ROOT", None)
            result = subprocess.run(["bash", "-c", native], cwd=workspace, env=env,
                                    capture_output=True, text=True)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertIn("done", result.stdout)
            self.assertEqual((cached / "skills/task/references/claude-config.rst").read_bytes(), example.read_bytes())
            self.assertIn("set PLUGIN_ROOT", (cached / "skills/task/SKILL.md").read_text())
            # Outlines about authoring another host keep its executable examples.
            source.rename(repo / "skills/cc-hook")
            data["skills"] = [{"source": "cc-hook", "leaf": "task"}]
            (repo / "registry/bundles/sample.yaml").write_text(yaml.safe_dump(data))
            package.sync(repo)
            self.assertEqual((repo / package.ROOT / "sample/skills/task/references/subagent.rst").read_text(), commands)

    def test_skill_review_shares_procedure_but_keeps_host_output_defaults(self):
        native = REPO / package.ROOT / "claude-code/skills/skill-review"
        claude = REPO / "plugins/claude-code/skills/skill-review"
        self.assertIn("${CODEX_HOME}/skill-reviews", (native / "SKILL.md").read_text())
        self.assertNotIn("~/.claude/skill-reviews", (native / "SKILL.md").read_text())
        self.assertIn("~/.claude/skill-reviews", (claude / "SKILL.md").read_text())
        for root in (native, claude):
            self.assertIn("references/review.rst", (root / "SKILL.md").read_text())
            self.assertEqual((root / "references/review.rst").read_bytes(), (REPO / "skills/skill-review/references/review.rst").read_bytes())

    def test_skill_licenses_are_in_installed_package_and_archive(self):
        with tempfile.TemporaryDirectory() as tmp:
            repo = Path(tmp)
            fixture(repo)
            skill = repo / "skills/sample-task/SKILL.md"
            skill.write_text(skill.read_text().replace("name: sample-task", "name: sample-task\nlicense: CC-BY-4.0"))
            for name in ("LICENSE", "LICENSE-CC-BY-4.0", "NOTICE"):
                shutil.copy(REPO / name, repo / name)
            package.sync(repo)
            installed = repo / package.ROOT / "sample"
            archive = repo / "package.zip"
            directory.archive(installed, archive)
            shutil.rmtree(repo / "skills")
            with zipfile.ZipFile(archive) as contents:
                for name in ("LICENSE", "LICENSE-CC-BY-4.0", "NOTICE"):
                    self.assertEqual((installed / name).read_bytes(), (REPO / name).read_bytes())
                    self.assertEqual(contents.read(name), (REPO / name).read_bytes())

    def test_agent_teams_printed_enable_command_works_from_installed_cache(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            cache = root / "cache with spaces and 'quotes'"
            shutil.copytree(REPO / "dist/codex/plugins/claude-code/skills/agent-teams", cache)
            workspace = root / "unrelated workspace"
            workspace.mkdir()
            home = root / "isolated home"
            home.mkdir()
            env = {**os.environ, "HOME": str(home), "CLAUDE_CODE_EXPERIMENTAL_AGENT_TEAMS": ""}
            result = subprocess.run(["bash", str(cache / "scripts/check-config.sh")],
                                    cwd=workspace, env=env, capture_output=True, text=True)
            self.assertEqual(result.returncode, 0, result.stderr)
            command = next(line.strip() for line in result.stdout.splitlines() if line.startswith("  bash "))
            result = subprocess.run(["bash", "-c", command], cwd=workspace, env=env,
                                    capture_output=True, text=True)
            self.assertEqual(result.returncode, 0, result.stderr)
            settings = json.loads((home / ".claude/settings.json").read_text())
            self.assertEqual(settings["env"]["CLAUDE_CODE_EXPERIMENTAL_AGENT_TEAMS"], "1")
            self.assertFalse((workspace / ".claude/settings.json").exists())

    def test_bundled_helper_commands_run_from_an_unrelated_workspace(self):
        with tempfile.TemporaryDirectory() as tmp:
            repo = Path(tmp)
            fixture(repo)
            source = repo / "skills/sample-task"
            (source / "scripts/run.sh").write_text('#!/bin/sh\ncat "$1"\n')
            with (source / "SKILL.md").open("a") as out:
                out.write('\n[Helper](scripts/run.sh)\n')
                for command in ('bash scripts/run.sh', 'bash skills/sample-task/scripts/run.sh', 'bash "./scripts/run.sh"'):
                    out.write(f'```bash\n{command} "input file.txt"\n```\n')
                out.write('`bash scripts/project-only.sh`\n')
            (source / "references/helper.rst").write_text('bash scripts/run.sh "input file.txt"\n')
            package.sync(repo)
            cached = repo / "plugin cache with spaces/sample"
            shutil.copytree(repo / package.ROOT / "sample", cached)
            workspace = repo / "unrelated workspace"
            workspace.mkdir()
            (workspace / "input file.txt").write_text("workspace data")
            shutil.rmtree(repo / "skills")
            entrypoint = (cached / "skills/task/SKILL.md").read_text()
            self.assertIn('[Helper](scripts/run.sh)', entrypoint)
            self.assertIn('`bash scripts/project-only.sh`', entrypoint)
            commands = re.findall(r'```bash\n(.*?)\n```', entrypoint)
            commands.append((cached / "skills/task/references/helper.rst").read_text())
            self.assertEqual(len(commands), 4)
            for command in commands:
                with self.subTest(command=command):
                    result = subprocess.run(
                        ["bash", "-c", command], cwd=workspace,
                        env={**os.environ, "PLUGIN_ROOT": str(cached)},
                        capture_output=True, text=True,
                    )
                    self.assertEqual(result.returncode, 0, result.stderr)
                    self.assertEqual(result.stdout, "workspace data")

    def test_delegation_guidance_requires_a_real_linked_local_outline(self):
        with tempfile.TemporaryDirectory() as tmp:
            repo = Path(tmp)
            fixture(repo)
            outline = repo / "skills/sample-task/references/subagent.rst"
            package.sync(repo)
            installed = repo / package.ROOT / "sample/skills/task/SKILL.md"
            self.assertIn("Delegation is optional.", installed.read_text())
            outline.unlink()
            package.sync(repo)
            self.assertNotIn("Delegation is optional.", installed.read_text())
            outline.write_text("Worker instructions")
            source = repo / "skills/sample-task/SKILL.md"
            source.write_text(source.read_text().replace(
                "[outline](references/subagent.rst)", "the sibling skill's `references/subagent.rst`"
            ))
            package.sync(repo)
            self.assertNotIn("Delegation is optional.", installed.read_text())

    def test_native_description_override_preserves_canonical_source(self):
        with tempfile.TemporaryDirectory() as tmp:
            repo = Path(tmp)
            data = fixture(repo)
            source = repo / "skills/sample-task/SKILL.md"
            original = source.read_bytes()
            cfg = data["targets"]["codex"]
            cfg["skillDescriptions"] = {"sample-task": "Check native readiness"}
            (repo / "registry/bundles/sample.yaml").write_text(yaml.safe_dump(data))
            package.sync(repo)
            native = repo / package.ROOT / "sample/skills/task/SKILL.md"
            self.assertEqual(package.frontmatter(native.read_text())[0]["description"], "Check native readiness")
            self.assertEqual(source.read_bytes(), original)
            self.assertEqual(package.validate(repo), [])
            for invalid in ([], {"missing": "Description"}, {"sample-task": False}, {"sample-task": " "}, {"sample-task": "x" * 1025}):
                with self.subTest(invalid=invalid):
                    cfg["skillDescriptions"] = invalid
                    (repo / "registry/bundles/sample.yaml").write_text(yaml.safe_dump(data))
                    with self.assertRaisesRegex(ValueError, "skillDescriptions"):
                        package.sync(repo)

    def test_defect_reporting_procedure_is_available_in_both_installed_targets(self):
        source = REPO / "skills/codex-report-defect"
        relative = "references/reporting.rst"
        procedure = (source / relative).read_bytes()
        self.assertIn(relative, (source / "SKILL.md").read_text())
        for root in (REPO / "plugins/codex/skills/report-defect", REPO / package.ROOT / "codex/skills/report-defect"):
            with self.subTest(root=root):
                with tempfile.TemporaryDirectory() as tmp:
                    cached = Path(tmp) / "report-defect"
                    shutil.copytree(root, cached)
                    # The canonical source is not present in this isolated copy.
                    self.assertIn(relative, (cached / "SKILL.md").read_text())
                    self.assertEqual((cached / relative).read_bytes(), procedure)

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
            self.assertFalse((repo / package.ROOT / "sample/skills/task/references/codex.rst").exists())
            self.assertEqual(package.validate(repo), [])

    def test_installed_issue_reporting_retains_shared_publication_checks(self):
        native = REPO / package.ROOT / "claude-code/skills/skill-report-issue"
        source = REPO / "skills/report-skill-issue"
        claude = REPO / "plugins/claude-code/skills/skill-report-issue"
        with tempfile.TemporaryDirectory() as tmp:
            cache = Path(tmp) / "installed cache"
            shutil.copytree(native, cache)
            entrypoint = (cache / "SKILL.md").read_text()
            self.assertIn("resolved `SKILL.md` path", entrypoint)
            self.assertIn("discovered", entrypoint)
            self.assertIn("reporting skill's own metadata", entrypoint)
            self.assertIn("references/reporting.rst", entrypoint)
            procedure = (cache / "references/reporting.rst").read_text()
            self.assertIn("Do not proceed to step 6 until the user explicitly confirms", procedure)
            self.assertIn("--body-file", procedure)
            self.assertNotIn("mcp__plugin_github_github__", procedure)
            self.assertIn("Do NOT tell the user the issue was filed", procedure)
            self.assertEqual(procedure, (source / "references/reporting.rst").read_text())
            self.assertEqual(procedure, (claude / "references/reporting.rst").read_text())

    def test_release_documentation_uses_context_matched_host_edits(self):
        body = (REPO / package.ROOT / "gh/skills/document-release/SKILL.md").read_text()
        self.assertNotIn("old_string", body)
        self.assertNotIn("Edit tool", body)
        self.assertIn("exact current text as context", body)
        self.assertIn("Never overwrite CHANGELOG.md as a whole file", body)

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
    def test_displayed_routes_include_every_enabled_component(self):
        for mcp, hooks, remote, expected in (
            (False, False, False, "skills-only"), (False, True, False, "skills+hooks"),
            (True, False, True, "remote-mcp"), (True, True, True, "remote-mcp+hooks"),
            (True, False, False, "local-mcp"), (True, True, False, "local-mcp+hooks"),
        ):
            with self.subTest(route=expected), tempfile.TemporaryDirectory() as tmp:
                repo = Path(tmp)
                fixture(repo, mcp=mcp, hooks=hooks)
                if mcp and not remote:
                    (repo / "mcp/source.json").write_text(json.dumps({"mcpServers": {"example": {"command": "example"}}}))
                package.sync(repo)
                result = directory.report(repo)
                self.assertEqual(result["plugins"][0]["route"], expected)
                self.assertIn(f"| {expected} |", directory.markdown(result))

    def test_external_gates_clear_only_for_typed_plugin_specific_approvals(self):
        for remote, gate in ((True, "remoteMcpAuthorized"), (False, "localMcpApproved")):
            with self.subTest(gate=gate), tempfile.TemporaryDirectory() as tmp:
                repo = Path(tmp)
                fixture(repo, mcp=True)
                source = repo / "skills/sample-task/SKILL.md"
                source.write_text(source.read_text().replace("name: sample-task", "name: sample-task\ndisable-model-invocation: true"))
                if not remote:
                    (repo / "mcp/source.json").write_text(json.dumps({"mcpServers": {"example": {"command": "example"}}}))
                package.sync(repo)
                manifest_path = repo / package.ROOT / "sample/.codex-plugin/plugin.json"
                manifest = json.loads(manifest_path.read_text())
                manifest["interface"].update(logo="logo.png", privacyPolicyURL="https://example.com/privacy", termsOfServiceURL="https://example.com/terms")
                manifest_path.write_text(json.dumps(manifest))
                publisher = {
                    "supportURL": "https://example.com/support", "identityVerified": True,
                    "availabilityRegions": ["AU"], "behavioralEvidence": {"sample": True},
                    "explicitInvocationApproved": {"sample": True}, gate: {"sample": True},
                }
                settings = repo / "registry/codex-directory.yaml"
                settings.write_text(yaml.safe_dump(publisher))
                self.assertTrue(directory.report(repo)["plugins"][0]["submissionReady"])
                for key in ("explicitInvocationApproved", gate):
                    for value in ({}, {"other": True}, {"sample": False}, {"sample": "true"}, {"sample": 1}, True, []):
                        with self.subTest(key=key, value=value):
                            settings.write_text(yaml.safe_dump({**publisher, key: value}))
                            result = directory.report(repo)["plugins"][0]
                            self.assertFalse(result["submissionReady"])
                            self.assertEqual(len(result["blockers"]), 1)

    def test_submission_urls_require_absolute_https_urls(self):
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
            publisher = {
                "supportURL": "https://example.com/support", "identityVerified": True,
                "availabilityRegions": ["AU"], "behavioralEvidence": {"sample": True},
            }
            publisher_path = repo / "registry/codex-directory.yaml"
            manifest_path.write_text(json.dumps(manifest))
            publisher_path.write_text(yaml.safe_dump(publisher))
            self.assertTrue(directory.report(repo)["plugins"][0]["submissionReady"])
            for key in ("privacyPolicyURL", "termsOfServiceURL", "supportURL"):
                target = publisher if key == "supportURL" else manifest["interface"]
                original = target[key]
                for value in ("pending", "/privacy", "http://example.com/privacy", True, 1, [],
                              "https://", "https://example.com:bad", "https://bad host/path",
                              "https://bad|host/path", "https://a..b/path", "https://127.0.0.999",
                              "https://user:secret@example.com", "https://example.com/\x7f"):
                    with self.subTest(key=key, value=value):
                        target[key] = value
                        manifest_path.write_text(json.dumps(manifest))
                        publisher_path.write_text(yaml.safe_dump(publisher))
                        entry = directory.report(repo)["plugins"][0]
                        self.assertFalse(entry["submissionReady"])
                        self.assertEqual(len(entry["blockers"]), 1)
                target[key] = original
                manifest_path.write_text(json.dumps(manifest))
                publisher_path.write_text(yaml.safe_dump(publisher))
            for regions in ("AU", True, 1, {}, [], [""], [False]):
                with self.subTest(regions=regions):
                    publisher["availabilityRegions"] = regions
                    publisher_path.write_text(yaml.safe_dump(publisher))
                    self.assertFalse(directory.report(repo)["plugins"][0]["submissionReady"])

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
