"""Contract tests for the pre-release logic change path (issue #390).

`/data-request:amend` governs released extracts only (#356), so a decided logic change
made before an extract's first release goes to `/data-request:fix`. These checks pin
that routing in both skills, their frontmatter descriptions (what skill discovery
shows) and their packaged Claude Code and Codex copies, plus the three rules the path
carries: a full logic change is allowed while no release exists, the runbook and UAT
checklist change together with the SQL (renamed validation/UAT columns included), and
the existing `.sqlreview` review is stale in meaning so `/data-request:analyse` must
re-run. They also grade the fixtures of the `prerelease-change-routes-to-fix` eval case
in Python and Node. No model call is made.
"""

import json
import os
import re
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

import yaml

REPO = Path(__file__).resolve().parent.parent
HOOK = REPO / "skills/cc-setup/assets/forced-eval-hook.sh"
CASE = REPO / "evals/claude/data-request/prerelease-change-routes-to-fix"


def copies(source: str, leaf: str) -> dict[str, Path]:
    return {
        "canonical": REPO / f"skills/{source}/SKILL.md",
        "claude": REPO / f"plugins/data-request/skills/{leaf}/SKILL.md",
        "codex": REPO / f"dist/codex/plugins/data-request/skills/{leaf}/SKILL.md",
    }


FIX = copies("data-request-fix", "fix")
AMEND = copies("data-request-amend", "amend")


def frontmatter(path: Path) -> tuple[dict, str]:
    # The Codex copy invokes siblings as `$data-request:<leaf>`; compare in Claude's form.
    _, meta, body = path.read_text().replace("$data-request:", "/data-request:").split("---\n", 2)
    return yaml.safe_load(meta), body


def flat(text: str) -> str:
    return " ".join(text.split())


def sentences(text: str) -> list[str]:
    return re.split(r"(?<=[.;:])\s+", flat(text))


def section(body: str, heading: str) -> str:
    start = body.index(heading)
    end = body.find("\n## ", start + len(heading))
    return body[start:] if end < 0 else body[start:end]


class FixOwnsPreReleaseChanges(unittest.TestCase):
    def test_change_requests_go_to_amend_only_once_released(self):
        for target, path in FIX.items():
            with self.subTest(target=target):
                body = frontmatter(path)[1]
                routing = next(s for s in sentences(body) if "change request" in s)
                self.assertIn("/data-request:amend", routing)
                self.assertRegex(routing, r"only when the extract is released")
                self.assertIn("*Pre-release logic change*", flat(body))

    def test_release_is_defined_and_unclear_status_defaults_to_released(self):
        for target, path in FIX.items():
            with self.subTest(target=target):
                text = flat(section(frontmatter(path)[1], "## Pre-release logic change"))
                for signal in ("data/Released/v*/", "release tag", "requester has received"):
                    self.assertIn(signal, text)
                self.assertRegex(text, r"If you cannot tell, ask; until then, treat the extract "
                                       r"as released and use `/data-request:amend`")

    def test_full_logic_change_is_allowed_for_a_settled_decision(self):
        for target, path in FIX.items():
            with self.subTest(target=target):
                text = flat(section(frontmatter(path)[1], "## Pre-release logic change"))
                self.assertIn("While no release exists, a full logic change is allowed here", text)
                for part in ("keys", "grain", "joins", "filters"):
                    self.assertIn(part, text)
                self.assertIn("settled decision", text)
                self.assertIn("never hand-edit generated SQL", text)
                self.assertIn("/data-request:bootstrap --update", text)

    def test_runbook_and_uat_checklist_change_with_the_sql(self):
        for target, path in FIX.items():
            with self.subTest(target=target):
                text = flat(section(frontmatter(path)[1], "## Pre-release logic change"))
                self.assertIn("Change the runbook and the UAT checklist", text)
                self.assertIn("together with the SQL, in the same change", text)
                self.assertIn("renamed validation or UAT output column", text)
                self.assertRegex(text, r"incomplete; report it as a blocker")

    def test_no_amendment_record_before_a_release(self):
        for target, path in FIX.items():
            with self.subTest(target=target):
                text = flat(section(frontmatter(path)[1], "## Pre-release logic change"))
                self.assertIn("Do not add an `AMD-` entry to `specs/amendments.md`", text)

    def test_review_is_stale_in_meaning_and_analyse_must_rerun(self):
        for target, path in FIX.items():
            with self.subTest(target=target):
                text = flat(section(frontmatter(path)[1], "## Pre-release logic change"))
                self.assertIn("`.sqlreview/` review is stale in meaning", text)
                self.assertIn("even where a fingerprint still matches", text)
                self.assertIn("`/data-request:analyse` must re-run", text)
                self.assertIn("does not replace it", text)

    def test_description_names_the_path_within_the_catalog_line(self):
        # forced-eval-hook.sh shows each description cut at 80 characters.
        for target, path in FIX.items():
            with self.subTest(target=target):
                desc = flat(frontmatter(path)[0]["description"])
                self.assertIn("before an extract's first", desc[:80])
                self.assertIn("A change to a released extract goes to amend", desc)


class AmendIsReleasedOnly(unittest.TestCase):
    def test_description_says_released_and_points_pre_release_to_fix(self):
        for target, path in AMEND.items():
            with self.subTest(target=target):
                desc = flat(frontmatter(path)[0]["description"])
                self.assertIn("released", desc[:80])
                self.assertIn("before the first release, a logic change goes to fix", desc)

    def test_body_routes_pre_release_changes_to_fix(self):
        for target, path in AMEND.items():
            with self.subTest(target=target):
                body = flat(frontmatter(path)[1])
                self.assertIn("This skill applies only to a released extract", body)
                self.assertIn("goes to `/data-request:fix` (*Pre-release logic change*)", body)
                self.assertLess(body.index("Pre-release logic change"),
                                body.index("## 1. Classify before any edit"))

    def test_runbook_and_uat_checklist_co_change(self):
        for target, path in AMEND.items():
            with self.subTest(target=target):
                body = frontmatter(path)[1]
                text = flat(section(body, "### Runbook, UAT checklist and validation outputs"))
                self.assertIn("together with the SQL, in the same change", text)
                self.assertIn("a column that a validation or UAT output shows", text)
                self.assertIn("report it as a blocker", text)
                handoff = next(l for l in body.splitlines() if l.startswith("affected files:"))
                self.assertIn("runbook and UAT checklist", handoff)
                self.assertIn("the runbook and UAT checklist name the new columns", flat(body))

    def test_review_is_stale_in_meaning_and_analyse_must_rerun(self):
        for target, path in AMEND.items():
            with self.subTest(target=target):
                report = flat(section(frontmatter(path)[1], "## Report"))
                self.assertIn("renamed validation or UAT output column", report)
                self.assertIn("stale in meaning, even where its fingerprint still matches", report)
                self.assertIn("`/data-request:analyse` must re-run", report)
                # The pre-#390 wording made the re-run optional.
                self.assertNotIn("recommend `/data-request:analyse` when a refreshed", report)


@unittest.skipUnless(shutil.which("jq"), "plugin discovery requires jq")
class Discovery(unittest.TestCase):
    def test_catalog_lines_separate_pre_release_fix_from_released_amend(self):
        with tempfile.TemporaryDirectory() as tmp:
            home = Path(tmp)
            manifest = home / ".claude/plugins/installed_plugins.json"
            manifest.parent.mkdir(parents=True)
            manifest.write_text(json.dumps({"plugins": {"data-request@rdl-agent-extensions": [
                {"installPath": str(REPO / "plugins/data-request")}]}}))
            env = {**os.environ, "HOME": str(home), "XDG_CACHE_HOME": str(home / ".cache")}
            prompt = "Re-key the cohort SQL on site code and MRN before the first release"
            result = subprocess.run(["bash", str(HOOK)], input=json.dumps({"prompt": prompt}),
                                    text=True, capture_output=True, env=env, check=True)
            context = json.loads(result.stdout)["hookSpecificOutput"]["additionalContext"]
        lines = {l.split(":", 2)[1]: l for l in context.splitlines()
                 if l.startswith("  - data-request:")}
        self.assertIn("before an extract's first", lines["fix"])
        self.assertIn("released", lines["amend"])


NODE = shutil.which("node")
NODE_SCRIPT = """
const {patterns, reply} = JSON.parse(require('fs').readFileSync(0, 'utf8'));
const out = {};
for (const [name, source] of Object.entries(patterns)) out[name] = new RegExp(source).test(reply);
process.stdout.write(JSON.stringify(out));
"""


def grader_meta(path: Path) -> dict:
    return yaml.safe_load(path.read_text().split("\n---\n")[0].removeprefix("---\n"))


def graders() -> dict:
    return {p.stem: grader_meta(p) for p in sorted((CASE / "graders").glob("*.md"))}


def regex_sources() -> dict:
    return {name: g["pattern"] for name, g in graders().items() if g["type"] == "regex"}


class EvalCase(unittest.TestCase):
    def test_case_shape(self):
        front = grader_meta(CASE / "prompt.md")
        self.assertTrue(front["description"])
        self.assertIn("pre-release", front["tags"])
        self.assertGreaterEqual(front["runs"], 3)
        self.assertIn("Skill", front["allowed_tools"])
        self.assertFalse({"Bash", "Write", "Edit", "NotebookEdit"} & set(front["allowed_tools"]))
        self.assertEqual(set(regex_sources()), {"not-amended", "runbook-uat", "analyse-rerun"})
        for name, source in regex_sources().items():
            re.compile(source)
            self.assertEqual(graders()[name]["target"], "last_message")

    def test_skill_fired_matches_fix_not_amend(self):
        fired = graders()["skill-fired"]
        self.assertEqual((fired["type"], fired["tool"]), ("tool_used", "Skill"))
        matcher = re.compile(fired["input_match"])
        self.assertTrue(matcher.search('{"skill": "data-request:fix"}'))
        self.assertTrue(matcher.search('{"skill":"fix"}'))
        self.assertFalse(matcher.search('{"skill": "data-request:amend"}'))

    def test_other_suite_modules_leave_this_case_to_us(self):
        # test_eval_data_request_graders owns every non-amend-* case except prerelease-* ones.
        self.assertTrue(CASE.name.startswith("prerelease-"))
        self.assertFalse(CASE.name.startswith("amend-"))
        source = (REPO / "tests/test_eval_data_request_graders.py").read_text()
        self.assertIn('"prerelease-"', source)


@unittest.skipUnless(NODE, "Node required for Python/JavaScript grader agreement")
class EvalFixtures(unittest.TestCase):
    def grade(self, reply: str) -> set:
        """Names of the regex graders that FAIL the reply (checked in both engines)."""
        sources = regex_sources()
        python = {name: bool(re.search(src, reply)) for name, src in sources.items()}
        result = subprocess.run(
            [NODE, "-e", NODE_SCRIPT], input=json.dumps({"patterns": sources, "reply": reply}),
            capture_output=True, text=True, check=True, timeout=30)
        self.assertEqual(json.loads(result.stdout), python, "JavaScript and Python disagree")
        return {name for name, ok in python.items() if not ok}

    def test_empty_reply_fails_every_regex_grader(self):
        self.assertEqual(self.grade(""), set(regex_sources()))

    def test_fixtures(self):
        fixtures = yaml.safe_load((CASE / "fixtures.yaml").read_text())
        self.assertTrue(fixtures["pass"])
        for fixture in fixtures["pass"]:
            with self.subTest(fixture=fixture["name"]):
                self.assertEqual(self.grade(fixture["reply"]), set())
        covered = set()
        for fixture in fixtures["fail"]:
            with self.subTest(fixture=fixture["name"]):
                self.assertTrue(fixture["fails"])
                self.assertEqual(self.grade(fixture["reply"]), set(fixture["fails"]))
                covered |= set(fixture["fails"])
        self.assertEqual(covered, set(regex_sources()), "every grader needs a failing fixture")


if __name__ == "__main__":
    unittest.main()
