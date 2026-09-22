"""Behavioural tests for the local `claude plugin eval` runner and its pre-push helper.

scripts/eval-claude-plugin.sh and scripts/eval-changed-plugins.sh are copied into a
throwaway git repository and driven with a fake `claude` binary (via CLAUDE_BIN) that
records the staged plugin it was pointed at. No model call, network, or real CLI.
"""

import os
import shutil
import stat
import subprocess
import tempfile
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
SCRIPTS = ("eval-claude-plugin.sh", "eval-changed-plugins.sh")

FAKE_CLAUDE = """#!/bin/bash
# args: plugin eval <staged-dir> ... | plugin eval --help | --version
[ "$1" = "--version" ] && { echo "9.9.9 (fake)"; exit 0; }
[ "$3" = "--help" ] && exit 0
{
  echo "RUN"
  cat "$3/skills/naming/SKILL.md"
  cat "$3/evals/case/prompt.md"
} >>"$FAKE_CLAUDE_LOG"
stage="$3"
while [ "$#" -gt 0 ]; do
  if [ "$1" = "--output-dir" ]; then
    cp "$stage/evals/case/prompt.md" "$2/report.html"
    cp "$stage/skills/naming/SKILL.md" "$2/aggregate-result.json"
    break
  fi
  shift
done
exit "${FAKE_CLAUDE_EXIT:-0}"
"""


def git(cwd: Path, *args: str) -> str:
    return subprocess.run(
        ["git", "-C", str(cwd), *args], check=True, capture_output=True, text=True
    ).stdout.strip()


class EvalHookTest(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.tmp, ignore_errors=True)
        self.repo = self.tmp / "repo"
        (self.repo / "scripts").mkdir(parents=True)
        for name in SCRIPTS:
            shutil.copy(REPO / "scripts" / name, self.repo / "scripts" / name)
        self.write("plugins/go/.claude-plugin/plugin.json", '{"name": "go"}\n')
        self.write("plugins/go/skills/naming/SKILL.md", "skill v1\n")
        git(self.repo, "init", "-q", "-b", "main")
        git(self.repo, "config", "user.email", "t@example.invalid")
        git(self.repo, "config", "user.name", "t")
        git(self.repo, "add", "-A")
        git(self.repo, "commit", "-q", "-m", "base")
        git(self.repo, "update-ref", "refs/remotes/origin/main", "HEAD")
        git(self.repo, "checkout", "-q", "-b", "feature")

        self.fake = self.tmp / "claude"
        self.fake.write_text(FAKE_CLAUDE)
        self.fake.chmod(self.fake.stat().st_mode | stat.S_IXUSR)
        self.log = self.tmp / "claude.log"

    def write(self, rel: str, text: str) -> None:
        path = self.repo / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text)

    def commit_suite(self, prompt: str = "prompt v1\n") -> str:
        self.write("evals/claude/go/case/prompt.md", prompt)
        git(self.repo, "add", "-A")
        git(self.repo, "commit", "-q", "-m", "suite")
        return git(self.repo, "rev-parse", "HEAD")

    def hook(self, stdin: str = "", **extra):
        env = {k: v for k, v in os.environ.items() if not k.startswith(("CLAUDE_EVAL", "EVAL_"))}
        env.update(
            HOME=str(self.tmp),
            XDG_CACHE_HOME=str(self.tmp / "cache"),
            CLAUDE_BIN=str(self.fake),
            FAKE_CLAUDE_LOG=str(self.log),
        )
        env.update(extra)
        return subprocess.run(
            ["bash", str(self.repo / "scripts" / "eval-changed-plugins.sh")],
            input=stdin, capture_output=True, text=True, env=env,
        )

    def logged(self) -> str:
        return self.log.read_text() if self.log.exists() else ""

    def test_disabled_by_default_never_calls_the_cli(self):
        self.commit_suite()
        result = self.hook()
        self.assertEqual(result.returncode, 0)
        self.assertIn("CLAUDE_EVAL_ENABLE=1", result.stdout)
        self.assertEqual(self.logged(), "")

    def test_unrelated_change_is_skipped(self):
        self.commit_suite()
        git(self.repo, "update-ref", "refs/remotes/origin/main", "HEAD")
        self.write("README.md", "docs\n")
        git(self.repo, "add", "-A")
        git(self.repo, "commit", "-q", "-m", "docs")
        result = self.hook(CLAUDE_EVAL_ENABLE="1")
        self.assertEqual(result.returncode, 0)
        self.assertEqual(self.logged(), "")

    def test_dirty_working_tree_does_not_reach_the_evaluated_copy(self):
        sha = self.commit_suite()
        self.write("plugins/go/skills/naming/SKILL.md", "UNCOMMITTED FIX\n")
        self.write("evals/claude/go/case/prompt.md", "UNCOMMITTED PROMPT\n")
        result = self.hook(CLAUDE_EVAL_ENABLE="1")
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn("skill v1", self.logged())
        self.assertIn("prompt v1", self.logged())
        self.assertNotIn("UNCOMMITTED", self.logged())
        revision = (self.repo / ".eval-results" / "go" / sha / "revision.txt").read_text().strip()
        self.assertEqual(revision, sha)

    def test_pushed_ref_other_than_head_is_the_one_evaluated(self):
        pushed = self.commit_suite("prompt pushed\n")
        git(self.repo, "checkout", "-q", "main")  # HEAD has no suite at all
        stdin = f"refs/heads/feature {pushed} refs/heads/feature {'0' * 40}\n"
        result = self.hook(stdin, CLAUDE_EVAL_ENABLE="1")
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn("prompt pushed", self.logged())

    def test_deletion_only_push_never_calls_cli_even_in_strict_mode(self):
        self.commit_suite()
        stdin = f"(delete) {'0' * 40} refs/heads/gone {'1' * 40}\n"
        result = self.hook(stdin, CLAUDE_EVAL_ENABLE="1", CLAUDE_EVAL_STRICT="1", FAKE_CLAUDE_EXIT="1")
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertEqual(self.logged(), "")
        self.assertIn("only ref deletions", result.stdout)

    def test_duplicate_refs_and_annotated_tags_evaluate_commit_once(self):
        sha = self.commit_suite()
        git(self.repo, "tag", "-a", "release", "-m", "release")
        tag = git(self.repo, "rev-parse", "release")
        stdin = "".join(
            f"{ref} {rev} {ref} {'0' * 40}\n"
            for ref, rev in (("refs/heads/feature", sha),
                             ("refs/tags/lightweight", sha),
                             ("refs/tags/release", tag))
        )
        result = self.hook(stdin, CLAUDE_EVAL_ENABLE="1")
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertEqual(self.logged().count("RUN"), 1)
        self.assertEqual(
            (self.repo / ".eval-results/go" / sha / "revision.txt").read_text().strip(), sha
        )

    def test_runner_mismatch_skips_paid_calls_and_obeys_strict_mode(self):
        pushed = self.commit_suite()
        runner = self.repo / "scripts/eval-claude-plugin.sh"
        runner.write_text(runner.read_text() + '\necho WRONG-RUNNER\n')
        stdin = f"refs/heads/feature {pushed} refs/heads/feature {'0' * 40}\n"
        for state in ("dirty", "staged", "committed"):
            if state == "staged":
                git(self.repo, "add", "scripts/eval-claude-plugin.sh")
            elif state == "committed":
                git(self.repo, "commit", "-q", "-m", "different runner at HEAD")
            for strict in ("0", "1"):
                with self.subTest(state=state, strict=strict):
                    result = self.hook(stdin, CLAUDE_EVAL_ENABLE="1", CLAUDE_EVAL_STRICT=strict)
                    self.assertEqual(result.returncode, int(strict), result.stdout + result.stderr)
                    self.assertIn("runner differs from " + pushed, result.stdout)
                    self.assertNotIn("WRONG-RUNNER", result.stdout)
                    self.assertEqual(self.logged(), "")
                    self.assertFalse((self.repo / ".eval-results").exists())

    def test_existing_ref_only_evaluates_plugins_changed_since_remote_tip(self):
        previous = self.commit_suite()
        self.write("plugins/other/.claude-plugin/plugin.json", '{"name":"other"}\n')
        self.write("plugins/other/skills/naming/SKILL.md", "other skill\n")
        self.write("evals/claude/other/case/prompt.md", "other prompt\n")
        git(self.repo, "add", "-A")
        git(self.repo, "commit", "-q", "-m", "other suite")
        tip = git(self.repo, "rev-parse", "HEAD")
        result = self.hook(f"refs/heads/feature {tip} refs/heads/feature {previous}\n",
                           CLAUDE_EVAL_ENABLE="1")
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertEqual(self.logged().count("RUN"), 1)
        self.assertIn("other prompt", self.logged())
        self.assertNotIn("prompt v1", self.logged())

    def test_same_tip_with_different_remote_bases_preserves_union(self):
        base = git(self.repo, "rev-parse", "HEAD")
        tip = self.commit_suite()
        # The first update selects nothing; the second must still select go.
        stdin = (f"refs/heads/first {tip} refs/heads/first {tip}\n"
                 f"refs/heads/second {tip} refs/heads/second {base}\n"
                 f"refs/tags/new {tip} refs/tags/new {'0' * 40}\n")
        result = self.hook(stdin, CLAUDE_EVAL_ENABLE="1")
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertEqual(self.logged().count("RUN"), 1)

    def test_missing_remote_base_does_not_fall_back_to_main(self):
        tip = self.commit_suite()
        stdin = f"refs/heads/feature {tip} refs/heads/feature {'1' * 40}\n"
        for strict in ("0", "1"):
            result = self.hook(stdin, CLAUDE_EVAL_ENABLE="1", CLAUDE_EVAL_STRICT=strict)
            self.assertEqual(result.returncode, int(strict), result.stdout + result.stderr)
            self.assertIn("cannot resolve comparison base", result.stdout)
            self.assertEqual(self.logged(), "")

    def test_multiple_tips_keep_separate_reports(self):
        first = self.commit_suite("first prompt\n")
        second = self.commit_suite("second prompt\n")
        stdin = (f"refs/heads/first {first} refs/heads/first {'0' * 40}\n"
                 f"(delete) {'0' * 40} refs/heads/gone {'1' * 40}\n"
                 f"refs/heads/second {second} refs/heads/second {'0' * 40}\n")
        for override in (None, self.tmp / "custom reports"):
            with self.subTest(override=override):
                extra = {"EVAL_OUTPUT_DIR": str(override)} if override else {}
                result = self.hook(stdin, CLAUDE_EVAL_ENABLE="1", **extra)
                self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
                root = (override / "go") if override else self.repo / ".eval-results" / "go"
                for sha, prompt in ((first, "first prompt\n"), (second, "second prompt\n")):
                    report = root / sha
                    self.assertEqual((report / "revision.txt").read_text().strip(), sha)
                    self.assertEqual((report / "report.html").read_text(), prompt)
                    self.assertEqual((report / "aggregate-result.json").read_text(), "skill v1\n")
                    self.assertIn(str(report / "report.html"), result.stdout)
        self.assertEqual(self.logged().count("RUN"), 4)

    def test_custom_reports_separate_plugins_at_same_tip(self):
        self.commit_suite()
        self.write("plugins/other/.claude-plugin/plugin.json", '{"name":"other"}\n')
        self.write("plugins/other/skills/naming/SKILL.md", "other skill\n")
        self.write("evals/claude/other/case/prompt.md", "other prompt\n")
        git(self.repo, "add", "-A")
        git(self.repo, "commit", "-q", "-m", "other suite")
        tip = git(self.repo, "rev-parse", "HEAD")
        root = self.tmp / "custom reports"
        result = self.hook(CLAUDE_EVAL_ENABLE="1", EVAL_OUTPUT_DIR=str(root))
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertEqual(self.logged().count("RUN"), 2)
        for plugin, prompt, skill in (("go", "prompt v1\n", "skill v1\n"),
                                      ("other", "other prompt\n", "other skill\n")):
            report = root / plugin / tip
            self.assertEqual((report / "revision.txt").read_text().strip(), tip)
            self.assertEqual((report / "report.html").read_text(), prompt)
            self.assertEqual((report / "aggregate-result.json").read_text(), skill)
            self.assertIn(f"evaluating {plugin} @ {tip} (per-plugin-per-revision cap $5",
                          result.stdout)

    def test_low_score_only_blocks_in_strict_mode(self):
        self.commit_suite()
        relaxed = self.hook(CLAUDE_EVAL_ENABLE="1", FAKE_CLAUDE_EXIT="1")
        self.assertEqual(relaxed.returncode, 0)
        self.assertIn("go(exit 1)", relaxed.stdout)
        strict = self.hook(CLAUDE_EVAL_ENABLE="1", CLAUDE_EVAL_STRICT="1", FAKE_CLAUDE_EXIT="1")
        self.assertEqual(strict.returncode, 1)
        # One CLI run per invocation: a retry repeats the spend, it is never cached.
        self.assertEqual(self.logged().count("RUN"), 2)

    def test_manual_run_uses_the_working_tree(self):
        self.commit_suite()
        self.write("plugins/go/skills/naming/SKILL.md", "UNCOMMITTED FIX\n")
        env = dict(os.environ, HOME=str(self.tmp), XDG_CACHE_HOME=str(self.tmp / "cache"),
                   CLAUDE_BIN=str(self.fake), FAKE_CLAUDE_LOG=str(self.log))
        env.pop("EVAL_REV", None)
        result = subprocess.run(
            ["bash", str(self.repo / "scripts" / "eval-claude-plugin.sh"), "go"],
            capture_output=True, text=True, env=env,
        )
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn("UNCOMMITTED FIX", self.logged())
        self.assertFalse((self.repo / "plugins" / "go" / "evals").exists())


if __name__ == "__main__":
    unittest.main()
