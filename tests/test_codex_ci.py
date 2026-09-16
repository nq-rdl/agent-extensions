"""CI contracts for the native Codex publication target."""

import json
import re
import tempfile
import unittest
from pathlib import Path

import yaml

from scripts._registry import normalize_member


REPO = Path(__file__).resolve().parent.parent


def claude_runtime_dependencies(repo):
    """Scan all shipped text; NUL-containing or non-UTF-8 files are binary."""
    forbidden_literals = ("${CLAUDE_PLUGIN_ROOT}", "AskUserQuestion")
    slash_invocation = re.compile(r"(?<![A-Za-z0-9])/[a-z0-9][a-z0-9-]*:[a-z0-9]")
    bundles = repo / "registry" / "bundles"
    for bundle_path in sorted([*bundles.glob("*.yaml"), *bundles.glob("*.yml")]):
        bundle = yaml.safe_load(bundle_path.read_text()) or {}
        codex = (bundle.get("targets") or {}).get("codex") or {}
        if not codex.get("enabled"):
            continue
        for member in bundle.get("skills") or []:
            source, _leaf = normalize_member(member)
            for path in sorted((repo / "skills" / source).rglob("*")):
                if not path.is_file():
                    continue
                raw = path.read_bytes()
                if b"\x00" in raw:
                    continue
                try:
                    content = raw.decode("utf-8")
                except UnicodeDecodeError:
                    continue
                if any(marker in content for marker in forbidden_literals) or slash_invocation.search(content):
                    yield str(path.relative_to(repo))


class TestCodexCi(unittest.TestCase):
    def test_ci_python_commands_use_locked_pixi(self):
        for name in ("validate.yml", "codex-acceptance.yml", "changelog-check.yml"):
            workflow = yaml.safe_load((REPO / ".github/workflows" / name).read_text())
            for job_name, job in workflow["jobs"].items():
                setup_index = None
                for i, step in enumerate(job["steps"]):
                    if step.get("uses", "").startswith("prefix-dev/setup-pixi@"):
                        setup_index = i
                        self.assertTrue(step["with"]["locked"])
                    run = step.get("run", "")
                    if re.search(r"python3|scripts/(?:sync|validate)-plugins.sh", run):
                        with self.subTest(workflow=name, job=job_name, step=step.get("name")):
                            self.assertIsNotNone(setup_index)
                            self.assertLess(setup_index, i)
                            self.assertNotIn("pip install", run)
                            self.assertIn("pixi run --locked", run)
                            self.assertNotRegex(run, r"(?:^|\n)\s*(?:python3|bash scripts/(?:sync|validate)-plugins.sh)")

    def test_release_preparation_uses_locked_pixi_for_pipeline(self):
        workflow = yaml.safe_load((REPO / ".github/workflows/release-prepare.yml").read_text())
        steps = workflow["jobs"]["prepare"]["steps"]
        setup = next(s for s in steps if s.get("uses", "").startswith("prefix-dev/setup-pixi@"))
        self.assertTrue(setup["with"]["locked"])
        self.assertRegex(setup["with"]["pixi-version"], r"^v\d+\.\d+\.\d+$")
        generation = next(s for s in steps if s.get("name", "").startswith("Batch changelog"))
        self.assertLess(steps.index(setup), steps.index(generation))
        pipeline = [line.strip() for line in generation["run"].splitlines() if "scripts/" in line]
        self.assertEqual(len(pipeline), 4)
        self.assertTrue(all(line.startswith("pixi run --locked ") for line in pipeline))
        self.assertNotIn("pip install", generation["run"])

    def test_finalized_reruns_skip_codex_setup_and_remote_smoke(self):
        workflow = yaml.safe_load((REPO / ".github/workflows/release-finalize.yml").read_text())
        steps = workflow["jobs"]["finalize"]["steps"]
        setup = next(s for s in steps if s.get("uses", "").startswith("actions/setup-node@"))
        smoke = next(s for s in steps if "scripts/smoke-codex-marketplace.sh" in s.get("run", ""))
        for step in (setup, smoke):
            self.assertEqual(
                step.get("if"),
                "steps.v.outputs.do_tag == 'true' || steps.v.outputs.do_release == 'true'",
            )

    def test_required_plugin_job_runs_pinned_codex_smoke(self):
        workflow = (REPO / ".github" / "workflows" / "validate.yml").read_text()

        self.assertIn("name: Validate Claude plugin structure, hooks, and agents", workflow)
        self.assertIn("@openai/codex@0.152.0", workflow)
        self.assertIn("@openai/codex@0.154.0", workflow)
        self.assertIn("scripts/smoke-codex-marketplace.sh", workflow)

        job = yaml.safe_load(workflow)["jobs"]["validate-plugins"]
        self.assertFalse(job.get("continue-on-error", False))
        commands = [step for step in job["steps"] if "docker " in step.get("run", "")]
        self.assertEqual(len(commands), 2, "required job must build and run the container")
        self.assertTrue(all(not step.get("continue-on-error", False) for step in commands))
        build, run = [step["run"] for step in commands]
        config = json.loads((REPO / ".devcontainer/codex/devcontainer.json").read_text())
        version = config["build"]["args"]["CODEX_VERSION"]
        self.assertIn(f"CODEX_VERSION={version}", build)
        self.assertIn(".devcontainer/codex/Dockerfile", build)
        self.assertIn("scripts/smoke-codex-marketplace.sh", run)
        self.assertIn("--network none", run)
        self.assertIn("readonly", run)

    def test_local_generated_drift_hook_includes_codex_marketplace(self):
        lefthook = (REPO / "lefthook.yml").read_text()

        self.assertIn(".agents/**", lefthook)

    def test_smoke_checks_every_installed_plugin_skill(self):
        smoke = (REPO / "scripts" / "smoke-codex-marketplace.sh").read_text()

        self.assertIn('expected_skills+=("$plugin:$(basename "$skill_dir")")', smoke)
        self.assertIn('for qualified in "${expected_skills[@]}"', smoke)
        self.assertIn('diff -r "$REPO_ROOT/${source_path#./}"', smoke)
        self.assertNotIn("mapfile", smoke)
        self.assertNotIn("go:naming", smoke)

    def test_codex_pilot_skills_do_not_require_claude_runtime(self):
        from scripts.codex_package import validate
        self.assertEqual(validate(REPO), [])

    def test_host_neutrality_scans_both_bundle_extensions_and_supporting_files(self):
        for extension in ("yaml", "yml"):
            for filename, content in (
                ("SKILL.md", "${CLAUDE_PLUGIN_ROOT}"),
                ("references/usage.rst", "AskUserQuestion"),
                ("scripts/run.sh", "/go:naming"),
                ("assets/example.json", "${CLAUDE_PLUGIN_ROOT}"),
            ):
                with self.subTest(extension=extension, filename=filename), tempfile.TemporaryDirectory() as tmp:
                    repo = Path(tmp)
                    bundles = repo / "registry" / "bundles"
                    bundles.mkdir(parents=True)
                    (bundles / f"sample.{extension}").write_text(
                        "targets:\n  codex:\n    enabled: true\nskills: [sample]\n"
                    )
                    path = repo / "skills" / "sample" / filename
                    path.parent.mkdir(parents=True)
                    path.write_text(content)
                    self.assertEqual(list(claude_runtime_dependencies(repo)), [str(path.relative_to(repo))])
                    path.write_text("Portable content")
                    self.assertEqual(list(claude_runtime_dependencies(repo)), [])
                    for binary in (b"\x00AskUserQuestion", b"\xffAskUserQuestion"):
                        path.write_bytes(binary)
                        self.assertEqual(list(claude_runtime_dependencies(repo)), [])


if __name__ == "__main__":
    unittest.main()
