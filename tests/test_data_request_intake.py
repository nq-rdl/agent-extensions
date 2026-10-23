"""Instruction contracts for #504: the analyst intake interview and the per-pass roles."""

import json
import re
import shutil
import subprocess
import unittest
from pathlib import Path

import yaml

REPO = Path(__file__).resolve().parent.parent
SUITE = REPO / "evals/claude/data-request"
TREES = (REPO / "skills", REPO / "plugins/data-request/skills", REPO / "dist/codex/plugins/data-request/skills")
CASES = {
    "intake-grain-not-default": {"grain", "grain_owner", "technical_note_recorded", "writes_scope",
                                 "needs_setup_first"},
}


def flat(path):
    return " ".join(path.read_text().split())


def skill(tree, leaf, relative="SKILL.md"):
    folder = f"data-request-{leaf}" if tree == TREES[0] else leaf
    return tree / folder / relative


class IntakeContracts(unittest.TestCase):
    def test_registered_and_packaged_for_both_targets(self):
        bundle = yaml.safe_load((REPO / "registry/bundles/data-request.yaml").read_text())
        self.assertIn({"source": "data-request-intake", "leaf": "intake"}, bundle["skills"])
        for tree in TREES:
            with self.subTest(tree=tree):
                text = skill(tree, "intake").read_text()
                frontmatter = yaml.safe_load(text.split("---", 2)[1])
                self.assertEqual(frontmatter.get("name"), None if tree == TREES[1] else
                                 ("data-request-intake" if tree == TREES[0] else "intake"))
                self.assertLessEqual(len(text.split("---", 2)[2].splitlines()), 300)
        self.assertIn("/data-request:intake", (REPO / "docs/bundles.md").read_text())

    def test_intake_is_the_analyst_pass_and_needs_no_store(self):
        for tree in TREES:
            with self.subTest(tree=tree):
                body = flat(skill(tree, "intake"))
                for token in ("**Data Analyst**", "analyst-intake.rst", "answers.intake.json",
                              "Never write `.sqlreview/`, `scope.json`", "data-request:setup`: the engineer runs it later",
                              "validate_answers.py", "validate-answers", "never report a pass", "only the approved copier run",
                              "data-request:lookup`", "not its counts", "Leave open", "open_questions",
                              "Never an email", "confirm nothing"):
                    self.assertIn(token, body)
                self.assertNotIn("sqlreview.sh", body)

    def test_interview_covers_research_topics_and_asks_grain(self):
        body = flat(skill(TREES[0], "intake"))
        interview = body.split("## The interview", 1)[1].split("## Recording a decision", 1)[0]
        for topic in ("**cohort**", "**codes**", "**outcomes**", "**outputs**", "**governance**", "**grain**"):
            self.assertIn(topic, interview)
        self.assertIn("What does one row represent — one row per <unit>, in clinical terms?", interview)
        self.assertIn("never copy it into the sidecar", interview)
        self.assertIn("finer_outputs", interview)
        for lane in ("source tables", "joins", "keys", "timezones", "validity rules"):
            self.assertIn(lane, interview)
        self.assertIn("TUH house default", interview)

    def test_answers_field_ownership(self):
        for tree in TREES:
            with self.subTest(tree=tree):
                rows = {line.split("|")[1].strip(): line.split("|")[3].strip()
                        for line in skill(tree, "intake").read_text().splitlines()
                        if line.startswith("| `") or line.startswith("| research")}
                self.assertIn("`THHSRDLENQ-<n>`, no zero padding", rows["`request_id`"])
                self.assertIn("never from a default", rows["`measurement_granularity`"])
                self.assertIn("keeps the sidecar's approval equal", rows["`approval_number`, `governance_type`"])
                engineer = [v for k, v in rows.items() if k.startswith("`license`")]
                self.assertEqual(engineer, ["Never changes them; shows them before the render"])
                required = [k for k in rows if "`requestor_email`" in k]
                self.assertEqual(len(required), 1)
                body = flat(skill(tree, "intake"))
                self.assertIn("`Patient`, `Admission`, `Encounter` or `Observation`", body)
                self.assertIn("This skill does not create repositories.", body)
                self.assertNotIn("starts the central bootstrap", body)

    def test_render_step_is_approved_pinned_copy_over_the_seed(self):
        for tree in TREES:
            with self.subTest(tree=tree):
                body = flat(skill(tree, "intake"))
                render = body.split("## Render the scaffold (after approval)", 1)[1].split("## A cohort supplied", 1)[0]
                for token in ("only when the analyst approves", "Never render from a branch",
                              "copier copy --trust --overwrite --defaults --vcs-ref <tag> --data-file answers.yaml",
                              "gh:nq-rdl/data-analysis-scaffold", "not `recopy` or `update`",
                              "data-science-template", "already records `nq-rdl/data-analysis-scaffold`",
                              "`answers.intake.json` unchanged", "analyst_intake.py", "v0.5.1 or later",
                              "report that the sidecar was not validated", "do not run it"):
                    self.assertIn(token, render)
                cohort = body.split("## A cohort supplied by the requester", 1)[1].split("## Write and validate", 1)[0]
                for token in ("by shape only", "Never ask for, open, read, copy or print the file",
                              "data/00_raw/", "dvc add", "dvc push", "only the `.dvc` pointer"):
                    self.assertIn(token, cohort)

    def test_rerun_keeps_unchanged_confirmations_and_names_changed_ids(self):
        body = flat(skill(TREES[0], "intake"))
        rerun = body.split("## Re-run: walk what changed", 1)[1].split("## Hand over", 1)[0]
        for token in ("verbatim", "Do not re-stamp it", "Walk only", "A-intake-<id>", "changed or removed `id`"):
            self.assertIn(token, rerun)

    def test_each_pass_names_its_role(self):
        for tree in TREES:
            with self.subTest(tree=tree):
                bootstrap = flat(skill(tree, "bootstrap"))
                self.assertIn("data-request:intake`", bootstrap)
                self.assertIn("This skill is the engineer's interview, not the analyst's.", bootstrap)
                self.assertIn("**Role guard:**", bootstrap)
                self.assertNotIn("There is no separate intake skill", bootstrap)
                setup = flat(skill(tree, "setup"))
                self.assertIn("data-request:intake` (the analyst's interview", setup)
                reference = flat(skill(tree, "setup", "references/analyst-intake.rst"))
                for token in ("**Data Analyst** runs ``/data-request:intake``",
                              "**Data Engineer** runs ``/data-request:bootstrap``", "no ``.sqlreview/``"):
                    self.assertIn(token, reference)
                self.assertNotIn("not a new stage or skill", reference)
                self.assertNotIn("no separate intake skill", flat(skill(tree, "lookup")))
        readme = flat(REPO / "README.md")
        self.assertIn("The Data Analyst runs `intake`, the analyst's interview", readme)
        self.assertIn("`bootstrap`, the engineer's interview", readme)


class IntakeEvalFixtures(unittest.TestCase):
    """Grade synthetic replies in both engines; no model calls."""

    def test_every_intake_case_has_discriminating_graders_and_fixtures(self):
        self.assertEqual({p.parent.name for p in SUITE.glob("intake-*/prompt.md")}, set(CASES))
        for case, names in CASES.items():
            with self.subTest(case=case):
                root = SUITE / case
                front = yaml.safe_load((root / "prompt.md").read_text().split("---\n")[1])
                self.assertIn("Skill", front["allowed_tools"])
                self.assertFalse(set(front["allowed_tools"]) & {"Bash", "Write", "Edit"})
                self.assertGreaterEqual(front["runs"], 3)
                metas = {p.stem: yaml.safe_load(p.read_text().split("---\n")[1])
                         for p in (root / "graders").glob("*.md")}
                sources = {k: v["pattern"] for k, v in metas.items() if v["type"] == "regex"}
                self.assertEqual(set(sources), names)
                fired = metas["skill-fired"]
                self.assertEqual((fired["type"], fired["tool"]), ("tool_used", "Skill"))
                self.assertRegex('"skill": "data-request:intake"', fired["input_match"])
                self.assertNotRegex('"skill": "data-request:bootstrap"', fired["input_match"])
                fixtures = yaml.safe_load((root / "fixtures.yaml").read_text())
                self.assertTrue(fixtures["pass"])
                covered = set()
                for fixture in fixtures["pass"] + fixtures["fail"]:
                    reply = fixture["reply"]
                    python = {k: bool(re.search(v, reply)) for k, v in sources.items()}
                    if shutil.which("node"):
                        script = """
const x = JSON.parse(require('fs').readFileSync(0, 'utf8'));
const results = Object.fromEntries(Object.entries(x.patterns)
    .map(([key, pattern]) => [key, new RegExp(pattern).test(x.reply)]));
process.stdout.write(JSON.stringify(results));
"""
                        result = subprocess.run(["node", "-e", script],
                                                input=json.dumps({"patterns": sources, "reply": reply}),
                                                text=True, capture_output=True, check=True, timeout=30)
                        self.assertEqual(json.loads(result.stdout), python)
                    failed = {k for k, passed in python.items() if not passed}
                    self.assertEqual(failed, set(fixture.get("fails", [])), fixture["name"])
                    covered |= failed
                self.assertEqual(covered, names)


if __name__ == "__main__":
    unittest.main()
