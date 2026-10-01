"""Contract tests for the Codex skill family (epic #312: #305-#310).

Each assertion encodes a runtime fact checked against the vendored companion
(`plugins/codex/scripts/`) or a decision recorded in docs/skill-review/codex.md.
They guard the skill text; the runtime itself is tested in tests/codex/.
"""

import re
import shlex
import unittest
from pathlib import Path

import yaml

REPO = Path(__file__).resolve().parent.parent
SKILLS = REPO / "skills"
SCRIPTS = REPO / "plugins" / "codex" / "scripts"


def read(rel: str) -> str:
    return (SKILLS / rel).read_text()


def frontmatter(rel: str) -> dict:
    return yaml.safe_load(read(rel).split("---\n", 2)[1]) or {}


class ShellPermissionContracts(unittest.TestCase):
    """#476: instruction guards, not an emulation of Claude's permission engine."""

    ACTIONS = {
        "review": "Read, Glob, Grep, Bash(node:*), Bash(git:*), AskUserQuestion",
        "adversarial-review": "Read, Glob, Grep, Bash(node:*), Bash(git:*), AskUserQuestion",
        "rescue": "Bash(node:*), AskUserQuestion, Agent",
        "setup": "Bash(node:*), Bash(npm:*), AskUserQuestion",
        "result": "Bash(node:*)",
        "status": "Bash(node:*)",
        "transfer": "Bash(node:*)",
        "cancel": "Bash(node:*)",
        "report-defect": "Bash(node:*), Bash(gh:*), AskUserQuestion",
    }

    def test_preflights_are_single_node_invocations_under_unchanged_grants(self):
        for action, grants in self.ACTIONS.items():
            rel = f"codex-{action}/SKILL.md"
            with self.subTest(action=action):
                self.assertEqual(frontmatter(rel)["allowed-tools"], grants)
                section = read(rel).split("## Preflight — Node.js runtime\n", 1)[1]
                command = re.search(r"```bash\n(.*?)\n```", section, re.S).group(1)
                # Quoted JS contains semicolons/operators; shell-level ones would
                # produce extra tokens, rather than belonging to the -e argument.
                tokens = list(shlex.shlex(command, posix=True, punctuation_chars=True))
                self.assertEqual(tokens[:2], ["node", "-e"])
                self.assertEqual(len(tokens), 3)
                self.assertEqual(tokens[2], 'const [a,b]=process.versions.node.split(".").map(Number); process.exit(a>18||(a===18&&b>=18)?0:1)')
                self.assertIn("Bash(node:*)", grants)

    def test_preflight_instructions_forbid_composition_and_read_tool_status(self):
        for action in self.ACTIONS:
            with self.subTest(action=action):
                text = read(f"codex-{action}/SKILL.md")
                self.assertIn("exactly as written, as a single `Bash` command", text)
                self.assertIn("Read the exit status and output from the Bash tool result", text)
                self.assertIn("empty stdout on success is expected", text)
                self.assertIn("Do not append `echo`, `;`, `&&`, pipes, or other shell separators, wrappers, or redirects", text)
                self.assertIn("non-zero exit or `node` not found", text)
                self.assertIn("stop and tell the user exactly: `Codex plugin requires Node.js >=18.18.0", text)

    def test_review_size_checks_are_separate_plain_git_commands(self):
        expected = {
            "git status --short --untracked-files=all",
            "git diff --shortstat --cached",
            "git diff --shortstat",
            "git diff --shortstat <base>...HEAD",
        }
        for action in ("review", "adversarial-review"):
            with self.subTest(action=action):
                rel = f"codex-{action}/SKILL.md"
                text = read(rel)
                size = text.split("estimate the review size before asking:", 1)[1].split("  - Treat untracked", 1)[0]
                self.assertIn("as a separate, plain `git` invocation", size)
                self.assertIn("Read each tool result directly; do not combine commands or add `echo`, `;`, `&&`, pipes, or other shell separators, wrappers, or redirects", size)
                commands = re.findall(r"`(git [^`]+)`", size)
                self.assertEqual(set(commands), expected)
                self.assertEqual(len(commands), len(expected))
                for command in commands:
                    tokens = list(shlex.shlex(command.replace("<base>", "main"), posix=True, punctuation_chars=True))
                    self.assertEqual(tokens[0], "git")
                    self.assertFalse(set(tokens) & {";", "&&", "||", "|", "&", ">", "<", "echo"})
                self.assertIn("Bash(git:*)", frontmatter(rel)["allowed-tools"])

    def test_review_scope_arguments_and_question_boundary_remain(self):
        for action in ("review", "adversarial-review"):
            with self.subTest(action=action):
                text = read(f"codex-{action}/SKILL.md")
                for instruction in (
                    "This command is review-only.",
                    "Do not fix issues, apply patches",
                    "Preserve the user's arguments exactly.",
                    "Do not strip `--wait` or `--background` yourself.",
                    "use `AskUserQuestion` exactly once with two options",
                    "`Wait for results`",
                    "`Run in background`",
                    'review "$ARGUMENTS"',
                ):
                    self.assertIn(instruction, text)
                self.assertLess(text.index("use `AskUserQuestion`"), text.index("Foreground flow:"))


class ReviewContracts(unittest.TestCase):
    """#307: shared mechanics, deliberately different public contracts."""

    def test_no_route_sends_staged_or_unstaged_scope_to_adversarial_review(self):
        # resolveReviewTarget rejects staged/unstaged for BOTH review commands.
        git = (SCRIPTS / "lib" / "git.mjs").read_text()
        self.assertIn('new Set(["auto", "working-tree", "branch"])', git)
        for rel in (
            "codex-review/SKILL.md",
            "codex-review/references/codex.rst",
            "codex-adversarial-review/SKILL.md",
            "codex-adversarial-review/references/codex.rst",
        ):
            with self.subTest(rel=rel):
                text = " ".join(read(rel).split())
                self.assertNotRegex(text, r"(?i)staged-only or unstaged-only scope requires")
                self.assertRegex(text, r"(?i)(staged-only|--scope staged)")

    def test_native_review_keeps_the_focus_text_rejection(self):
        # The runtime rejects focus text for `review`; the skill must return that
        # rejection instead of silently rerunning without the user's focus text.
        text = " ".join(read("codex-review/SKILL.md").split())
        self.assertIn("does not support custom focus text", (SCRIPTS / "codex-companion.mjs").read_text())
        self.assertRegex(text, r"(?i)do not drop the focus text")
        self.assertRegex(text, r"(?i)do not (switch|run) .*adversarial-review.* unless the user")

    def test_adversarial_review_preserves_focus_text(self):
        text = read("codex-adversarial-review/SKILL.md")
        self.assertIn("rewrite the user's focus text", text)
        self.assertIn("[focus ...]", frontmatter("codex-adversarial-review/SKILL.md")["argument-hint"])
        self.assertNotIn("focus", frontmatter("codex-review/SKILL.md")["argument-hint"])


class RescueContracts(unittest.TestCase):
    """#309/#310: argument, resume, write-scope and failure semantics."""

    def test_task_never_receives_wait(self):
        # handleTask does not parse --wait, so a forwarded --wait becomes prompt text.
        src = (SCRIPTS / "codex-companion.mjs").read_text()
        task = re.search(r"async function handleTask\(argv\) \{(.*?)\n\}", src, re.S).group(1)
        self.assertNotIn('"wait"', task)
        for rel in ("codex-rescue/SKILL.md", "codex-cli-runtime/SKILL.md"):
            with self.subTest(rel=rel):
                self.assertRegex(" ".join(read(rel).split()), r"`--wait`[^.]*prompt text")

    def test_write_only_for_edit_requests(self):
        for rel in ("codex-rescue/SKILL.md", "codex-cli-runtime/SKILL.md", "codex-rescue/references/subagent.rst"):
            with self.subTest(rel=rel):
                text = " ".join(read(rel).split())
                self.assertNotRegex(text, r"(?i)default to (a )?write-capable")
                self.assertRegex(text, r"(?i)continuing .*does not authori[sz]e edits")

    def test_continuation_without_a_thread_is_not_forwarded(self):
        # --resume-last with no tracked thread fails in executeTaskRun, and a bare
        # "keep going" sent as a fresh task gives Codex nothing to do.
        src = (SCRIPTS / "codex-companion.mjs").read_text()
        self.assertIn("No previous Codex task thread was found", src)
        for rel in ("codex-rescue/SKILL.md", "codex-cli-runtime/SKILL.md", "codex-rescue/references/subagent.rst"):
            with self.subTest(rel=rel):
                text = " ".join(read(rel).split())
                self.assertNotRegex(text, r"(?i)add ``?--resume-last``? unless ``?--fresh``? is present")
                self.assertNotRegex(text, r"(?i)internal helper for \"keep going\"")
        rescue = " ".join(read("codex-rescue/SKILL.md").split())
        self.assertRegex(rescue, r"(?i)no Codex thread to continue")

    def test_failure_is_reported_not_swallowed(self):
        for rel in ("codex-cli-runtime/SKILL.md", "codex-rescue/references/subagent.rst"):
            with self.subTest(rel=rel):
                self.assertNotIn("return nothing", read(rel))
        rescue = " ".join(read("codex-rescue/SKILL.md").split())
        self.assertIn("/codex:setup", rescue)
        self.assertRegex(rescue, r"(?i)do not (write|give|generate) a substitute answer")

    def test_result_handling_keeps_its_owned_rules(self):
        text = read("codex-result-handling/SKILL.md")
        self.assertIn("do not generate a substitute answer", text)
        self.assertIn("After presenting review findings, STOP", text)
        self.assertIn("/codex:setup", text)


class RuntimeSkillProvenance(unittest.TestCase):
    """#306/#308: no decorative pin; runtime support separated from provenance."""

    def test_description_has_no_version_pin(self):
        desc = frontmatter("codex-cli-runtime/SKILL.md")["description"]
        self.assertNotRegex(desc, r"\d+\.\d+\.\d+")

    def test_no_stale_approval_policy_list(self):
        # codex-cli 0.158.0 lists on-request and never; the companion always
        # passes approvalPolicy "never" over app-server.
        self.assertNotIn("untrusted", read("codex-cli-runtime/SKILL.md"))

    def test_states_the_checked_runtime_requirement(self):
        text = read("codex-cli-runtime/SKILL.md")
        self.assertIn('binaryAvailable("codex", ["app-server", "--help"]', (SCRIPTS / "lib" / "codex.mjs").read_text())
        self.assertIn("app-server", text)
        self.assertRegex(text, r"Tested with `codex-cli \d+\.\d+\.\d+` on \d{4}-\d{2}-\d{2}")


class PromptingContracts(unittest.TestCase):
    """#305: companion-specific prompting guidance without unsupported controls."""

    FILES = (
        "gpt-5-6-prompting/SKILL.md",
        "gpt-5-6-prompting/references/prompt-blocks.rst",
        "gpt-5-6-prompting/references/codex-prompt-antipatterns.rst",
        "gpt-5-6-prompting/references/codex-prompt-recipes.rst",
    )

    def test_no_control_the_companion_cannot_set(self):
        src = (SCRIPTS / "codex-companion.mjs").read_text() + (SCRIPTS / "lib" / "codex.mjs").read_text()
        self.assertNotIn("verbosity", src)
        for rel in self.FILES:
            with self.subTest(rel=rel):
                text = read(rel)
                self.assertNotRegex(text, r"(?i)(set|prefer setting|steer [^.]*with) ``?text\.verbosity")
                for api_only in ("prompt_cache_options", "reasoning.context"):
                    self.assertNotIn(api_only, text)

    def test_canonical_source_and_verification_date(self):
        text = read("gpt-5-6-prompting/SKILL.md")
        self.assertIn("https://developers.openai.com/api/docs/guides/prompt-guidance-gpt-5p6", text)
        self.assertRegex(text, r"[Vv]erified \d{4}-\d{2}-\d{2}")

    def test_companion_specific_constraints_remain(self):
        text = read("gpt-5-6-prompting/SKILL.md")
        for needle in ("<autonomy_policy>", "task --resume-last", "adversarial-review", "codex:model-guide"):
            self.assertIn(needle, text)


class ReportDefectContracts(unittest.TestCase):
    """#308: the runtime owns the marker structure; the skill keeps the gates."""

    def test_named_fields_exist_in_the_runtime_marker(self):
        procedure = read("codex-report-defect/references/reporting.rst")
        draft = re.search(r"Assemble a body from the marker(.*?)\n\n", procedure, re.S).group(1)
        fields = set(re.findall(r"``([A-Za-z]+)``", draft))
        marker = re.search(r"const marker = \{(.*?)\n    \};", (SCRIPTS / "lib" / "defect-log.mjs").read_text(), re.S).group(1)
        # Explicit (`key: value`) and shorthand (`key,`) properties; `show` adds classification.
        keys = set(re.findall(r"^\s{6}([A-Za-z]+)[:,]", marker, re.M)) | {"classification"}
        self.assertTrue(fields, "draft names no fields")
        self.assertLessEqual(fields, keys)

    def test_environment_structure_is_not_restated(self):
        procedure = read("codex-report-defect/references/reporting.rst")
        self.assertNotIn("``isGitRepo``", procedure)
        self.assertRegex(procedure, r"``environment`` object as emitted")

    def test_gates_remain(self):
        procedure = read("codex-report-defect/references/reporting.rst")
        for needle in ("homeScrubbed", "Never include tokens", "Never file without showing the draft first", "--body-file", "Only after successful publication"):
            self.assertIn(needle, procedure)


if __name__ == "__main__":
    unittest.main()
