"""Contract tests for the pre-release logic change path (issue #390).

`/data-request:amend` governs presentation changes before or after release (#424), so a decided logic change
made before an extract's first release goes to `/data-request:fix`. These checks pin
that routing in both skills, their frontmatter descriptions (what skill discovery
shows) and their packaged Claude Code and Codex copies, plus the three rules the path
carries: a full logic change is allowed only while no release exists (confirmed, never
inferred from absent signals; an unclear status means ask and edit nothing), the runbook
and UAT checklist change together with the SQL (renamed validation/UAT columns included),
and the existing `.sqlreview` review is stale in meaning so `/data-request:analyse`
re-runs with a full re-walk. They also own and grade the `prerelease-*` eval cases in
Python always and in Node when it is on PATH. No model call is made.
"""

import json
import os
import re
import shutil
import subprocess
import tempfile
import time
import unittest
from pathlib import Path

import yaml

REPO = Path(__file__).resolve().parent.parent
HOOK = REPO / "skills/cc-setup/assets/forced-eval-hook.sh"
SUITE = REPO / "evals/claude/data-request"
# Eval case -> the regex graders its answer is decided by.
CASES = {
    "prerelease-change-routes-to-fix": {
        "workflow-fix", "no-amd-entry", "runbook-uat-same-change", "review-stale",
        "analyse-full-rewalk", "renamed-column"},
    "prerelease-unclear-asks": {"release-unconfirmed", "asks-first", "no-edits"},
}


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
    def test_presentation_changes_go_to_amend_before_or_after_release(self):
        for target, path in FIX.items():
            with self.subTest(target=target):
                body = frontmatter(path)[1]
                routing = next(s for s in sentences(body) if "change request" in s)
                self.assertIn("/data-request:amend", routing)
                self.assertIn("presentation", routing)
                self.assertIn("before or after release", flat(body))
                self.assertIn("*Pre-release logic change*", flat(body))

    def test_release_needs_positive_confirmation(self):
        for target, path in FIX.items():
            with self.subTest(target=target):
                text = flat(section(frontmatter(path)[1], "## Pre-release logic change"))
                for signal in ("data/Released/v*/", "release tag", "reached the requester"):
                    self.assertIn(signal, text)
                self.assertIn("unreleased only on positive confirmation", text)
                self.assertIn("service-desk issue", text)
                self.assertIn("Absent signals do not prove it", text)
                self.assertIn("legacy or seed repositories and manual deliveries", text)
                # A UAT drop in data/Review/ is a candidate, but delivery makes it a release.
                self.assertIn("A `data/Review/` pointer is a release candidate, not a release", text)
                self.assertIn("for UAT or otherwise, the extract is released", text)

    def test_unclear_status_means_ask_and_edit_nothing(self):
        for target, path in FIX.items():
            with self.subTest(target=target):
                body = flat(frontmatter(path)[1])
                self.assertIn("If you cannot tell, ask, and make no edit here or in "
                              "`/data-request:amend` until answered", body)
                self.assertIn("make no edit in either skill until answered", body)
                # The first cut sent an unclear status to amend, which edits and records.
                self.assertNotRegex(body, r"(?i)treat the extract as released and use")

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
                self.assertIn("every live reference (queries, checklist items, "
                              "expected-output tables)", text)
                self.assertIn("history line that records the rename may keep the old name", text)
                self.assertRegex(text, r"incomplete; report it as a blocker")

    def test_no_amendment_record_before_a_release(self):
        for target, path in FIX.items():
            with self.subTest(target=target):
                text = flat(section(frontmatter(path)[1], "## Pre-release logic change"))
                self.assertIn("Do not add an `AMD-` entry to `specs/amendments.md`", text)

    def test_review_is_stale_and_analyse_re_walks_every_item(self):
        for target, path in FIX.items():
            with self.subTest(target=target):
                text = flat(section(frontmatter(path)[1], "## Pre-release logic change"))
                self.assertIn("`.sqlreview/` review is stale in meaning", text)
                self.assertIn("even where a fingerprint still matches", text)
                self.assertIn("re-run `/data-request:analyse` on each changed SQL file with a "
                              "full re-walk", text)
                # analyse's carry-forward keeps unchanged-line items unless every item is re-walked.
                self.assertIn("`--reconfirm-all`", text)
                self.assertIn("Carry-forward would otherwise keep items", text)
                self.assertIn("does not replace it", text)


class AmendSupportsPreReleasePresentation(unittest.TestCase):
    def test_description_supports_operator_run_and_points_logic_to_fix(self):
        for target, path in AMEND.items():
            with self.subTest(target=target):
                desc = flat(frontmatter(path)[0]["description"])
                self.assertIn("operator-run or released", desc)
                self.assertIn("before the first release, a logic change goes to fix", desc)

    def test_body_routes_pre_release_logic_to_fix_and_requires_baseline(self):
        for target, path in AMEND.items():
            with self.subTest(target=target):
                body = flat(frontmatter(path)[1])
                self.assertIn("Before the first release, use the operator-run extract as the baseline", body)
                self.assertNotIn("Before the first release there is no extract to amend", body)
                self.assertIn("a `data/Review/` drop that reached them counts", body)
                self.assertIn("goes to `/data-request:fix` (*Pre-release logic change*)", body)
                self.assertIn("If you cannot tell whether the extract is released, ask, and make "
                              "no edit until answered", body)
                self.assertLess(body.index("Pre-release logic change"),
                                body.index("## 1. Classify before any edit"))

    def test_runbook_and_uat_checklist_co_change(self):
        for target, path in AMEND.items():
            with self.subTest(target=target):
                body = frontmatter(path)[1]
                text = flat(section(body, "### Runbook, UAT checklist and validation outputs"))
                self.assertIn("together with the SQL, in the same change", text)
                self.assertIn("a column that a validation or UAT output shows", text)
                self.assertIn("every live reference (queries, checklist items, "
                              "expected-output tables)", text)
                self.assertIn("report it as a blocker", text)
                handoff = next(l for l in body.splitlines() if l.startswith("affected files:"))
                self.assertIn("runbook and UAT checklist", handoff)
                validate = flat(section(body, "## 6. Validate"))
                self.assertIn("no live reference (a query, a checklist item or an expected-output "
                              "table) uses an old name", validate)
                # A changelog line that mentions the old name is history, not a blocker.
                self.assertNotIn("no old name remains", validate)

    def test_review_is_stale_and_analyse_re_walks_every_item(self):
        for target, path in AMEND.items():
            with self.subTest(target=target):
                report = flat(section(frontmatter(path)[1], "## Report"))
                self.assertIn("renamed validation or UAT output column", report)
                self.assertIn("stale in meaning, even where its fingerprint still matches", report)
                self.assertIn("re-run `/data-request:analyse` on each changed SQL file with a full "
                              "re-walk", report)
                self.assertIn("`--reconfirm-all`", report)
                # The pre-#390 wording made the re-run optional.
                self.assertNotIn("recommend `/data-request:analyse` when a refreshed", report)


class DefectVersusReleasedChange(unittest.TestCase):
    """A defect in a released extract stays with fix; only different output goes to amend (#306).

    The bodies already said so; the descriptions did not. With "A change to a released extract
    goes to amend" in fix's description, a triage co-development run routed a released
    identifier-formatting defect to amend (docs/skill-review/new-plugins.md).
    """

    TRIAGE = copies("data-request-triage", "triage")

    def test_fix_description_keeps_released_defects(self):
        for target, path in FIX.items():
            with self.subTest(target=target):
                desc = flat(frontmatter(path)[0]["description"])
                self.assertIn("a defect with a concrete expected result, released or not", desc)
                self.assertIn("A request for different output from a released extract goes to amend", desc)
                self.assertNotIn("A change to a released extract goes to amend", desc)

    def test_amend_description_sends_defects_to_fix(self):
        for target, path in AMEND.items():
            with self.subTest(target=target):
                desc = flat(frontmatter(path)[0]["description"])
                self.assertIn("different output than was agreed", desc)
                self.assertIn("a defect in delivered output goes to fix", desc)

    def test_triage_routes_defects_and_released_changes_apart(self):
        for target, path in self.TRIAGE.items():
            with self.subTest(target=target):
                rows = {l.rsplit("|", 2)[1].strip(): l for l in frontmatter(path)[1].splitlines()
                        if l.startswith("| ") and "/data-request:" in l}
                self.assertIn("released or not", rows["`/data-request:fix`"])
                self.assertIn("different output than was agreed", rows["`/data-request:amend`"])
                self.assertIn("release body", rows["`/data-request:release`"])


@unittest.skipUnless(shutil.which("jq"), "plugin discovery requires jq")
class Discovery(unittest.TestCase):
    def catalog(self) -> dict[str, str]:
        """The data-request lines exactly as forced-eval-hook.sh shows them (80-char cut)."""
        with tempfile.TemporaryDirectory() as tmp:
            home = Path(tmp)
            manifest = home / ".claude/plugins/installed_plugins.json"
            manifest.parent.mkdir(parents=True)
            manifest.write_text(json.dumps({"plugins": {"data-request@rdl-agent-extensions": [
                {"installPath": str(REPO / "plugins/data-request")}]}}))
            env = {**os.environ, "HOME": str(home), "XDG_CACHE_HOME": str(home / ".cache")}
            prompt = "Re-key the cohort SQL on site code and MRN"
            result = subprocess.run(["bash", str(HOOK)], input=json.dumps({"prompt": prompt}),
                                    text=True, capture_output=True, env=env, check=True)
            context = json.loads(result.stdout)["hookSpecificOutput"]["additionalContext"]
        return {l.split(":", 2)[1]: l.split(": ", 1)[1] for l in context.splitlines()
                if l.startswith("  - data-request:")}

    def test_displayed_lines_keep_the_release_routing_word(self):
        lines = self.catalog()
        self.assertTrue(lines["fix"].endswith("..."), "the fix description is long enough to be cut")
        self.assertIn("pre-release", lines["fix"])
        self.assertIn("released", lines["amend"])


NODE = shutil.which("node")
NODE_SCRIPT = """
const {patterns, reply} = JSON.parse(require('fs').readFileSync(0, 'utf8'));
const out = {};
for (const [name, source] of Object.entries(patterns)) out[name] = new RegExp(source).test(reply);
process.stdout.write(JSON.stringify(out));
"""
MUTATING_TOOLS = {"Bash", "Write", "Edit", "NotebookEdit"}


def grader_meta(path: Path) -> dict:
    return yaml.safe_load(path.read_text().split("\n---\n")[0].removeprefix("---\n"))


def graders(case: str) -> dict:
    return {p.stem: grader_meta(p) for p in sorted((SUITE / case / "graders").glob("*.md"))}


def regex_sources(case: str) -> dict:
    return {name: g["pattern"] for name, g in graders(case).items() if g["type"] == "regex"}


class EvalCases(unittest.TestCase):
    def test_this_module_owns_every_prerelease_case(self):
        # test_eval_data_request_graders skips prerelease-* directories, so an unowned one
        # would otherwise go ungraded.
        found = {p.parent.name for p in SUITE.glob("prerelease-*/prompt.md")}
        self.assertEqual(found, set(CASES))
        dirs = {p.name for p in SUITE.glob("prerelease-*") if p.is_dir()}
        self.assertEqual(dirs, set(CASES))
        source = (REPO / "tests/test_eval_data_request_graders.py").read_text()
        self.assertIn('"prerelease-"', source)

    def test_case_shape(self):
        for case, expected in CASES.items():
            with self.subTest(case=case):
                meta = grader_meta(SUITE / case / "prompt.md")
                prompt = (SUITE / case / "prompt.md").read_text()
                self.assertTrue(meta["description"])
                self.assertIn("pre-release", meta["tags"])
                self.assertGreaterEqual(meta["runs"], 3)
                self.assertIn("Skill", meta["allowed_tools"])
                self.assertNotIn("Bash", meta["allowed_tools"])
                self.assertIn("End your reply with one fenced `yaml` block", prompt)
                self.assertEqual(set(regex_sources(case)), expected)
                for name, source in regex_sources(case).items():
                    re.compile(source)
                    self.assertEqual(graders(case)[name]["target"], "last_message")
                    self.assertIn("`{3,}ya?ml", source, f"{name} must read the yaml block")

    def test_routing_case_loads_fix_and_writes_nothing(self):
        case = "prerelease-change-routes-to-fix"
        meta = grader_meta(SUITE / case / "prompt.md")
        self.assertFalse(MUTATING_TOOLS & set(meta["allowed_tools"]))
        matcher = re.compile(graders(case)["skill-fired"]["input_match"])
        self.assertTrue(matcher.search('{"skill": "data-request:fix"}'))
        self.assertTrue(matcher.search('{"skill":"fix"}'))
        self.assertFalse(matcher.search('{"skill": "data-request:amend"}'))

    def test_unclear_case_forbids_edits_with_the_tools_granted(self):
        case = "prerelease-unclear-asks"
        meta = grader_meta(SUITE / case / "prompt.md")
        forbidden = {g["tool"] for g in graders(case).values()
                     if g["type"] == "tool_used" and g.get("max") == 0}
        self.assertEqual(forbidden, {"Write", "Edit"})
        for g in graders(case).values():
            if g["type"] == "tool_used" and g.get("max") == 0:
                self.assertEqual((g["min"], g["max"], g["arm"]), (0, 0, "both"))
                self.assertIn(g["tool"], meta["allowed_tools"], "a must-not check needs the tool")
        matcher = re.compile(graders(case)["skill-fired"]["input_match"])
        for skill in ("data-request:fix", "data-request:amend", "fix"):
            self.assertTrue(matcher.search(f'{{"skill": "{skill}"}}'))
        self.assertFalse(matcher.search('{"skill": "data-request:triage"}'))


class EvalFixtures(unittest.TestCase):
    def grade(self, sources: dict, reply: str) -> set:
        """Names of the regex graders that FAIL the reply (both engines when node exists)."""
        python = {name: bool(re.search(src, reply)) for name, src in sources.items()}
        if NODE:
            result = subprocess.run(
                [NODE, "-e", NODE_SCRIPT], input=json.dumps({"patterns": sources, "reply": reply}),
                capture_output=True, text=True, check=True, timeout=30)
            self.assertEqual(json.loads(result.stdout), python, "JavaScript and Python disagree")
        return {name for name, ok in python.items() if not ok}

    def test_empty_reply_fails_every_regex_grader(self):
        for case in CASES:
            with self.subTest(case=case):
                sources = regex_sources(case)
                self.assertEqual(self.grade(sources, ""), set(sources))

    def test_fixtures(self):
        for case in CASES:
            sources = regex_sources(case)
            fixtures = yaml.safe_load((SUITE / case / "fixtures.yaml").read_text())
            self.assertTrue(fixtures["pass"], case)
            for fixture in fixtures["pass"]:
                with self.subTest(case=case, fixture=fixture["name"]):
                    self.assertEqual(self.grade(sources, fixture["reply"]), set())
            covered = set()
            for fixture in fixtures["fail"]:
                with self.subTest(case=case, fixture=fixture["name"]):
                    self.assertTrue(fixture["fails"])
                    self.assertEqual(self.grade(sources, fixture["reply"]), set(fixture["fails"]))
                    covered |= set(fixture["fails"])
            self.assertEqual(covered, set(sources), f"{case}: every grader needs a failing fixture")

    def test_large_replies_grade_quickly(self):
        reply = ("```yaml\n" + "workflow: amend\n" * 2000 + "```\n" + "renamed: x\n" * 2000) * 3
        for case in CASES:
            with self.subTest(case=case):
                start = time.monotonic()
                self.grade(regex_sources(case), reply)
                self.assertLess(time.monotonic() - start, 5)


if __name__ == "__main__":
    unittest.main()
