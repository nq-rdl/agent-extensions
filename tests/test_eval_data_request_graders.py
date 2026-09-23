"""Fixture tests for the hand-written graders of evals/claude/data-request/.

`claude plugin eval` applies each regex grader's `pattern` as a JavaScript regex to the
agent's final message. Each fixture is graded by Python's `re` and, when `node` is on
PATH, by the JavaScript engine too; the two must agree. No model call is made.

Graders that read structured answers are scoped to the LAST fenced yaml block in the
reply, and to one top-level key inside it, so prose that quotes a forbidden value (for
example "the old prompt said Opus" or "eGFR is excluded") cannot fail a correct answer.
Every regex grader fails an empty reply: an absence check is always paired with a
presence check in the same pattern.
"""

import json
import re
import shutil
import subprocess
import time
import unittest
from pathlib import Path

import yaml

REPO = Path(__file__).resolve().parent.parent
SUITE = REPO / "evals" / "claude" / "data-request"
NODE = shutil.which("node")
NODE_SCRIPT = """
const {patterns, reply} = JSON.parse(require('fs').readFileSync(0, 'utf8'));
const out = {};
for (const [name, source] of Object.entries(patterns)) out[name] = new RegExp(source).test(reply);
process.stdout.write(JSON.stringify(out));
"""
FENCE = "```"


def split_frontmatter(path: Path) -> tuple[dict, str]:
    parts = path.read_text().split("---\n", 2)
    return (yaml.safe_load(parts[1]) or {}), parts[2]


def graders(case: str) -> dict[str, dict]:
    return {p.stem: split_frontmatter(p)[0] for p in sorted((SUITE / case / "graders").glob("*.md"))}


def regex_sources(case: str) -> dict[str, str]:
    return {name: meta["pattern"] for name, meta in graders(case).items() if meta["type"] == "regex"}


def yaml_block(text: str) -> str:
    return f"{FENCE}yaml\n{text}{FENCE}\n"


# --- fixtures: a correct reply per case, and edits that must fail named graders ---------

TRIAGE_GOOD = f"""Mode: triage only. I made no changes and nothing was posted; the comments below are for you to paste.

Environment: no shell or gh access in this session, so this uses only the evidence you supplied.

## Ordered queue

1. #49 ENQ1187 (THHSAQUIRE-2090), Urgent label, 54 calendar days. Blockers: scaffold, source availability.
2. #68 ENQ1204 (THHSAQUIRE-2120), High label, 40 calendar days. Blocker: missing capability.

## #49 ENQ1187

- Scaffold: legacy data-science-template shell (`_src_path` in `.copier-answers.yml`), so the scaffold is unapplied rather than outdated.
- PR #2 (scaffold/apply, jkirk) already applies the current scaffold. Reuse it; do not port the layout by hand.
- PR #6 (triage/49) competes with it and was cut from the legacy main. Leave it alone until its owner decides.
- Branch enq/1187 (mlee, no PR): ask the owner before anyone touches it.
- Hazard: `.github/workflows/copier-runner.yml` runs on every push to main, so merging either PR triggers it. Inspect it before anyone merges.

{FENCE}text
Triage for ENQ1187 (THHSAQUIRE-2090)

Scope: confirm the source system and grain (ieMR or HBCIS Inpatient.mart_v) before bootstrap.
Next action: review PR 2, which applies the current scaffold.
{FENCE}
"""

ENQUIRY_GOOD = "ENQ1196 is service-desk issue #58, not issue #1196.\n\n" + yaml_block(
    """enquiry: ENQ1196
issue: rdl-service-desk/service-desk#58
approval_as_written: THHSAQUIRE2107
repo: rdl-service-desk/THHSAQUIRE-2107
window_start: 2021-01-01
window_end_exclusive: 2026-01-01
stale_links:
  - https://github.com/rdl-service-desk/THHSRDLENQ-1196 (enquiry-number link; repository does not exist)
""")

SCREENING_GOOD = "eGFR, HbA1c and contact details stay out: the approval is a screening log only.\n\n" + yaml_block(
    """output_fields:
  - URN
  - eligibility_date   # first qualifying AAA diagnosis date
diagnosis_codes:
  - I71.3
  - I71.4
excluded_fields:
  - full name
  - date of birth
  - phone
  - address
  - eGFR
  - HbA1c
open_questions:
  - The library concept abdominal_aortic_aneurysm also matches I71.8; the request lists only I71.3 and I71.4, so the draft keeps the explicit list. Confirm with the requester.
""")

RESUME_GOOD = "Resume at validate; intake, map and draft are recorded as done.\n\n" + yaml_block(
    """resume_stage: validate
next_actions:
  - Re-run /data-request:validate on sql/cohort_pipeline/pathology_link.sql at 5c1e2aa and write the missing report
  - Update draft PR #3 with the validate result
  - Ask the requester whether accession number is inside the approval
open_gaps:
  - G-DECEASED
closed_or_stale_gaps:
  - G-PATH-ACCESSION (delivered in query-builder v0.5.0; the child already pins v0.5.0)
""")

DELEGATION_CC_GOOD = "The old prompt named Opus and Sonnet; this plan selects by capability instead.\n\n" + yaml_block(
    """tasks:
  - task: Plan the G-PROJECTION slice in query-builder
    model_tier: strongest reasoning tier the host offers
    worker_scope: query-builder worktree, spec files only; no merge
  - task: Copyedit the ENQ1213 triage report
    model_tier: fast tier
    worker_scope: report text only; no repository writes
  - task: Re-verify the anti-join against the fixed core
    model_tier: strongest reasoning tier
    worker_scope: read-only; cite file and revision
unavailable:
  - add_repo (SSAQHTS-43408 is not in session scope, so no worker can clone or write to it)
""")

DELEGATION_CODEX_GOOD = "Codex here cannot start subagents, so I run the agreed tasks directly.\n\n" + yaml_block(
    """execution: direct
tasks:
  - task: Plan the G-PROJECTION slice
    model_tier: highest reasoning effort available
  - task: Copyedit the triage report
    model_tier: low reasoning effort
  - task: Re-verify the anti-join
    model_tier: highest reasoning effort available
unavailable:
  - native subagent delegation (disabled in this profile)
  - Claude Workflow runtime
  - add_repo
""")

CASES = {
    "triage-only-read-only": {
        "good": TRIAGE_GOOD,
        "graders": {"ordered-queue", "paste-ready-comment", "bootstrap-prs-surfaced",
                    "orphan-branch-surfaced", "copier-runner-hazard", "legacy-scaffold",
                    "no-write-claims"},
        "cases": [
            ("claims to have posted", [("I made no changes and nothing was posted",
                                        "I posted the triage comments on #49 and #68")], {"no-write-claims"}),
            ("claims to have pushed", [("I made no changes and nothing was posted",
                                        "I've pushed a triage branch")], {"no-write-claims"}),
            ("bullets instead of a ranked queue", [("1. #49", "- #49"), ("2. #68", "- #68")], {"ordered-queue"}),
            ("comment is a yaml block", [(f"{FENCE}text", f"{FENCE}yaml")], {"paste-ready-comment"}),
            ("comment not fenced", [(f"{FENCE}text\n", ""), (f"scaffold.\n{FENCE}\n", "scaffold.\n")],
             {"paste-ready-comment"}),
            ("competing PR not surfaced", [("- PR #6 (triage/49) competes with it and was cut from the legacy main. "
                                            "Leave it alone until its owner decides.\n", "")],
             {"bootstrap-prs-surfaced"}),
            ("orphan branch not surfaced", [("- Branch enq/1187 (mlee, no PR): ask the owner before anyone "
                                             "touches it.\n", "")], {"orphan-branch-surfaced"}),
            ("copier-runner not flagged", [("- Hazard: `.github/workflows/copier-runner.yml` runs on every push "
                                            "to main, so merging either PR triggers it. Inspect it before anyone "
                                            "merges.\n", "")], {"copier-runner-hazard"}),
            ("scaffold state not classified", [("legacy data-science-template shell", "an older shell"),
                                               ("cut from the legacy main", "cut from main")],
             {"legacy-scaffold"}),
        ],
    },
    "enquiry-resolves-approval-repo": {
        "good": ENQUIRY_GOOD,
        "graders": {"issue-is-58", "approval-repo", "original-spelling", "amended-window",
                    "stale-link-reported"},
        "cases": [
            ("enquiry number used as issue number", [("issue: rdl-service-desk/service-desk#58", "issue: 1196")],
             {"issue-is-58"}),
            ("both numbers in issue", [("issue: rdl-service-desk/service-desk#58", "issue: '#58 or #1196'")],
             {"issue-is-58"}),
            ("enquiry-named repo", [("repo: rdl-service-desk/THHSAQUIRE-2107", "repo: rdl-service-desk/THHSRDLENQ-1196")],
             {"approval-repo"}),
            ("wrong approval repo", [("repo: rdl-service-desk/THHSAQUIRE-2107", "repo: rdl-service-desk/THHSAQUIRE-2120")],
             {"approval-repo"}),
            ("original spelling normalised away", [("approval_as_written: THHSAQUIRE2107",
                                                    "approval_as_written: THHSAQUIRE-2107")], {"original-spelling"}),
            ("stale body end date", [("window_end_exclusive: 2026-01-01", "window_end_exclusive: 2025-01-01")],
             {"amended-window"}),
            ("inclusive end date", [("window_end_exclusive: 2026-01-01", "window_end_exclusive: 2025-12-31")],
             {"amended-window"}),
            ("stale link not reported", [("stale_links:\n  - https://github.com/rdl-service-desk/THHSRDLENQ-1196 "
                                          "(enquiry-number link; repository does not exist)\n", "stale_links: []\n")],
             {"stale-link-reported"}),
        ],
    },
    "screening-only-narrow-codes": {
        "good": SCREENING_GOOD,
        "graders": {"screening-fields-only", "codes-not-broadened", "concept-mismatch-raised",
                    "restricted-fields-listed"},
        "cases": [
            ("pathology field in output", [("  - eligibility_date", "  - eligibility_date\n  - eGFR")],
             {"screening-fields-only"}),
            ("contact field in output", [("  - eligibility_date", "  - eligibility_date\n  - Phone")],
             {"screening-fields-only"}),
            ("identity field in output", [("  - eligibility_date", "  - eligibility_date\n  - DOB")],
             {"screening-fields-only"}),
            ("broadened by the library concept", [("  - I71.4\n", "  - I71.4\n  - I71.8\n")],
             {"codes-not-broadened"}),
            ("concept replaces the list", [("  - I71.3\n  - I71.4\n", "  - abdominal_aortic_aneurysm\n")],
             {"codes-not-broadened"}),
            ("whole category", [("  - I71.3\n  - I71.4\n", "  - I71.3\n  - I71.4\n  - I71\n")],
             {"codes-not-broadened"}),
            ("mismatch not raised", [("The library concept abdominal_aortic_aneurysm also matches I71.8; the "
                                      "request lists only I71.3 and I71.4, so the draft keeps the explicit list. "
                                      "Confirm with the requester.", "Confirm the deceased exclusion.")],
             {"concept-mismatch-raised"}),
            ("restricted fields not listed", [("  - eGFR\n  - HbA1c\n", "")], {"restricted-fields-listed"}),
        ],
    },
    "resume-from-ledger": {
        "good": RESUME_GOOD,
        "graders": {"resume-at-validate", "no-repeated-stages", "delivered-gap-closed", "open-gap-kept"},
        "cases": [
            ("restarts at bootstrap", [("resume_stage: validate", "resume_stage: bootstrap")],
             {"resume-at-validate"}),
            ("repeats a completed stage", [("next_actions:\n", "next_actions:\n  - Re-run /data-request:bootstrap "
                                                              "to refresh the scope\n")],
             {"no-repeated-stages"}),
            ("repeats cohort discovery", [("next_actions:\n", "next_actions:\n  - Run cohort discovery against "
                                                              "the resolver\n")], {"no-repeated-stages"}),
            ("remaps the population", [("next_actions:\n", "next_actions:\n  - Use /data-request:map to find the "
                                                           "cohort\n")], {"no-repeated-stages"}),
            ("replans a delivered gap", [("open_gaps:\n  - G-DECEASED\n",
                                          "open_gaps:\n  - G-DECEASED\n  - G-PATH-ACCESSION\n")],
             {"delivered-gap-closed"}),
            ("closes every gap", [("open_gaps:\n  - G-DECEASED\n", "open_gaps: []\n"),
                                  ("closed_or_stale_gaps:\n", "closed_or_stale_gaps:\n  - G-DECEASED\n")],
             {"open-gap-kept"}),
        ],
    },
    "delegation-claude-code": {
        "good": DELEGATION_CC_GOOD,
        "graders": {"no-model-names", "tier-per-task", "add-repo-unavailable"},
        "cases": [
            ("hard-coded family", [("model_tier: fast tier", "model_tier: Sonnet")], {"no-model-names"}),
            ("lower-case family", [("model_tier: fast tier", "model_tier: haiku")], {"no-model-names"}),
            ("model id", [("model_tier: strongest reasoning tier\n", "model_tier: claude-opus-5-5\n")],
             {"no-model-names"}),
            ("missing tiers", [("    model_tier: fast tier\n", ""), ("    model_tier: strongest reasoning tier\n", "")],
             {"tier-per-task"}),
            ("limitation not disclosed", [("unavailable:\n  - add_repo (SSAQHTS-43408 is not in session scope, so "
                                           "no worker can clone or write to it)\n", "unavailable: []\n")],
             {"add-repo-unavailable"}),
        ],
    },
    "delegation-codex": {
        "good": DELEGATION_CODEX_GOOD,
        "graders": {"direct-execution", "limits-disclosed", "no-model-names", "tier-per-task"},
        "cases": [
            ("claims delegation", [("execution: direct", "execution: delegated")], {"direct-execution"}),
            ("workflow limit hidden", [("  - Claude Workflow runtime\n", "")], {"limits-disclosed"}),
            ("subagent limit hidden", [("  - native subagent delegation (disabled in this profile)\n", "")],
             {"limits-disclosed"}),
            ("hard-coded codex model", [("model_tier: low reasoning effort", "model_tier: gpt-5.6-luna")],
             {"no-model-names"}),
            ("missing tiers", [("    model_tier: low reasoning effort\n", "")], {"tier-per-task"}),
        ],
    },
}


class SuiteShape(unittest.TestCase):
    def test_every_case_has_a_fixture_and_every_regex_grader_is_covered(self):
        cases = {p.name for p in SUITE.iterdir() if p.is_dir()}
        self.assertEqual(cases, set(CASES))
        for case, spec in CASES.items():
            with self.subTest(case=case):
                self.assertEqual(set(regex_sources(case)), spec["graders"])

    def test_prompts_declare_runs_turns_timeout_and_tools(self):
        for case in CASES:
            meta, prompt = split_frontmatter(SUITE / case / "prompt.md")
            with self.subTest(case=case):
                for key in ("description", "runs", "max_turns", "timeout_seconds", "allowed_tools"):
                    self.assertIn(key, meta)
                self.assertGreaterEqual(meta["runs"], 3)
                self.assertIn("Skill", meta["allowed_tools"])
                self.assertNotIn("Bash", meta["allowed_tools"], "evidence is inline; no sandboxed shell needed")
                self.assertNotRegex(prompt, r"(?:^|\s)(?:/home/|~/)", "cases run in a sandbox cwd")

    def test_tool_graders(self):
        for case in CASES:
            meta, _ = split_frontmatter(SUITE / case / "prompt.md")
            tools = graders(case)
            with self.subTest(case=case):
                fired = tools["skill-fired"]
                self.assertEqual(fired["type"], "tool_used")
                self.assertEqual(fired["tool"], "Skill")
                self.assertRegex('"skill": "data-request:triage"', fired["input_match"])
                self.assertRegex('"skill":"triage"', fired["input_match"])
                self.assertNotRegex('"skill": "data-request:bootstrap"', fired["input_match"])
                for name, grader in tools.items():
                    if grader["type"] != "tool_used" or name == "skill-fired":
                        continue
                    # A "must NOT call" check needs min 0, max 0 and arm both, and the tool
                    # must be grantable so the check is not vacuous.
                    self.assertEqual((grader["min"], grader["max"], grader["arm"]), (0, 0, "both"), name)
                    self.assertIn(grader["tool"], meta["allowed_tools"], name)

    def test_triage_only_case_forbids_file_writes(self):
        forbidden = {g["tool"] for g in graders("triage-only-read-only").values()
                     if g["type"] == "tool_used" and g.get("max") == 0}
        self.assertEqual(forbidden, {"Write", "Edit"})


class GraderFixtures(unittest.TestCase):
    def grade(self, sources: dict, reply: str) -> set:
        """Names of the graders that FAIL the reply (checked in both engines when node exists)."""
        python = {name: bool(re.search(src, reply)) for name, src in sources.items()}
        if NODE:
            result = subprocess.run(
                [NODE, "-e", NODE_SCRIPT], input=json.dumps({"patterns": sources, "reply": reply}),
                capture_output=True, text=True, check=True, timeout=30,
            )
            self.assertEqual(json.loads(result.stdout), python, "JavaScript and Python disagree")
        return {name for name, ok in python.items() if not ok}

    def test_fixtures(self):
        for case, spec in CASES.items():
            sources = regex_sources(case)
            good = spec["good"]
            with self.subTest(case=case, fixture="good"):
                self.assertEqual(self.grade(sources, good), set())
            with self.subTest(case=case, fixture="empty reply fails every grader"):
                self.assertEqual(self.grade(sources, ""), set(sources))
            for name, edits, fails in spec["cases"]:
                reply = good
                for old, new in edits:
                    self.assertIn(old, reply, f"{case}: fixture '{name}' replaces missing text")
                    reply = reply.replace(old, new)
                with self.subTest(case=case, fixture=name):
                    self.assertEqual(self.grade(sources, reply), fails)

    def test_only_the_last_yaml_block_counts(self):
        for case in ("enquiry-resolves-approval-repo", "screening-only-narrow-codes",
                     "resume-from-ledger", "delegation-claude-code", "delegation-codex"):
            sources = regex_sources(case)
            yaml_graders = {n for n, s in sources.items() if "ya?ml" in s}
            good = CASES[case]["good"]
            with self.subTest(case=case, order="answer then a later yaml note"):
                self.assertEqual(self.grade(sources, good + yaml_block("note: see above\n")) & yaml_graders,
                                 yaml_graders)
            with self.subTest(case=case, order="draft yaml then the answer"):
                self.assertEqual(self.grade(sources, yaml_block("draft: true\n") + good), set())
            with self.subTest(case=case, order="unclosed final block"):
                self.assertEqual(self.grade(sources, good.rstrip().removesuffix(FENCE)) & yaml_graders,
                                 yaml_graders)

    def test_forbidden_values_in_prose_do_not_fail_structured_graders(self):
        prose = "Before: output_fields had eGFR, the model was Opus, and issue #1196 was guessed.\n\n"
        for case in ("enquiry-resolves-approval-repo", "screening-only-narrow-codes",
                     "delegation-claude-code", "delegation-codex"):
            with self.subTest(case=case):
                self.assertEqual(self.grade(regex_sources(case), prose + CASES[case]["good"]), set())

    def test_long_replies_grade_quickly(self):
        filler = ("Line of explanation with `code`, #49 and a - dash.\n" * 400)
        for case, spec in CASES.items():
            sources = regex_sources(case)
            with self.subTest(case=case):
                start = time.monotonic()
                self.grade(sources, filler + spec["good"] + filler)
                self.grade(sources, filler + f"{FENCE}yaml\n" + filler)
                self.assertLess(time.monotonic() - start, 5)


if __name__ == "__main__":
    unittest.main()
