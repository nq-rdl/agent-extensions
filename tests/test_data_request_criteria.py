"""Spec 017 (US2): bootstrap records a state per research criterion, analyse checks the SQL for it.

Token checks over the three skill trees (canonical, Claude, Codex) and the fixtures of the
bootstrap-criteria-states eval. No model call is made; the behavioural side is the eval.
"""

import json
import re
import shutil
import subprocess
import unittest
from pathlib import Path

import yaml

from test_data_request_facility_default import TREES, text

REPO = Path(__file__).resolve().parent.parent
SUITE = REPO / "evals/claude/data-request"
CASES = {
    "bootstrap-criteria-states": {"criteria-states", "flag-names-output-and-column", "derived-element-reason",
                                  "researcher-applies-gated"},
}


def section(body, start, end):
    return body.split(start, 1)[1].split(end, 1)[0]


class BootstrapCriteriaStates(unittest.TestCase):
    def criteria(self, tree):
        body = text(tree, "bootstrap")
        self.assertLess(body.index("## Population limits"), body.index("## Criteria states"))
        self.assertLess(body.index("## Criteria states"), body.index("## Existing scope"))
        return section(body, "## Criteria states", "## Existing scope")

    def test_every_state_is_named_per_kind(self):
        for tree in TREES:
            with self.subTest(tree=tree):
                rule = self.criteria(tree)
                for token in ("`sqlreview.sh intake`", "`criteria_status`", "one `criteria_status` row per live criterion",
                              "none for a withdrawn id",
                              "`entry_event` (`N`): `applied` or `not-doable`",
                              "`inclusion` and `exclusion` (`I`, `E`): `applied`, `partially-applied`, `flagged`, "
                              "`not-applied`, `researcher-applies` or `not-doable`",
                              "`data_element` (`D`): `delivered`, `not-delivered` or `not-doable`",
                              "alternatives that fix one index date"):
                    self.assertIn(token, rule)

    def test_reason_flag_and_derived_element_rules(self):
        for tree in TREES:
            with self.subTest(tree=tree):
                rule = self.criteria(tree)
                for token in ("A `reason` is required for `partially-applied`, `not-applied`, `not-delivered` "
                              "and `not-doable`", "names the part that is not applied",
                              "`flagged` names the delivered output and column", "`flag: {\"output\":",
                              "The column must be one the SQL delivers",
                              "A derived data element the researcher computes", "is `not-delivered`",
                              "Its reason names the delivered inputs"):
                    self.assertIn(token, rule)

    def test_researcher_applies_needs_applied_by_or_an_analyst_question(self):
        for tree in TREES:
            with self.subTest(tree=tree):
                rule = self.criteria(tree)
                for token in ("`researcher-applies` needs `applied_by: researcher` on that criterion in the sidecar",
                              "record `not-applied` for this iteration",
                              "names the open analyst question on who applies it", "one `Analyst question:`",
                              "data-request:intake`, which sets `applied_by`", "The scope can publish meanwhile",
                              "a later revision may record `researcher-applies`, confirmed afresh",
                              "An engineer's confirmation is not that answer"):
                    self.assertIn(token, rule)
                for gone in ("do not record the state", "without a row"):
                    self.assertNotIn(gone, rule)

    def test_broad_first_pass_default_for_exclusions(self):
        for tree in TREES:
            with self.subTest(tree=tree):
                rule = self.criteria(tree)
                for token in ("`broad-first-pass`", "without asking, like `tuh-facility`", "first pass",
                              "each exclusion that the request does not override", "state `not-applied`",
                              "`reason` the decision's `proposal.text`",
                              "\"source\": \"recurring-decision\"", "\"id\": \"broad-first-pass\"",
                              "Copy `confirmed_by` and `confirmed_at` from its `house_default`",
                              "set `confirmed_revision` to the import revision", "put no `decided` on the row",
                              "Invent no other confirmer", "leave inclusions, entry events and data elements alone",
                              "overrides the default for one criterion", "confirmed afresh",
                              "When it is not, the default is not applied and exclusions get ordinary "
                              "engineer-confirmed rows",
                              "references/recurring-decisions.rst"):
                    self.assertIn(token, rule)

    def test_row_filters_rdl_adds_stay_assumptions(self):
        for tree in TREES:
            with self.subTest(tree=tree):
                rule = self.criteria(tree)
                for token in ("Criteria hold only what the researcher asked for", "A row filter RDL adds on its own initiative",
                              "test patients", "cancelled admissions", "is not a criterion",
                              "engineer-confirmed assumption", "Extraction Assumptions / Important limitations",
                              "Do not repeat a criterion in that section"):
                    self.assertIn(token, rule)

    def test_owning_scope_check_before_publish_and_carry(self):
        for tree in TREES:
            with self.subTest(tree=tree):
                rule = self.criteria(tree)
                for token in ("Only one scope per repository carries `criteria_status`",
                              "bash \"$S/sqlreview.sh\" criteria \".sqlreview/reviews/$SLUG/scope.draft.json\"",
                              "exit 10", "never a value", "Publish runs the same check and refuses",
                              "`criteria_status` with basis `criteria-unchanged`",
                              "keep its confirmation", "are confirmed afresh"):
                    self.assertIn(token, rule)

    def test_other_matches_exclude_house_defaults(self):
        for tree in TREES:
            with self.subTest(tree=tree):
                body = text(tree, "bootstrap")
                self.assertIn("For each other match without a `house_default`", body)
                self.assertIn("For each other match without a `house_default`", text(tree, "analyse"))


class RecurringDecisionsReference(unittest.TestCase):
    def test_broad_first_pass_is_not_an_assumption_candidate_and_rows_match_the_ruling(self):
        for tree in TREES:
            with self.subTest(tree=tree):
                body = text(tree, "setup", "references/recurring-decisions.rst")
                detect = section(body, "Detect (bootstrap and analyse)", "Close out (lift)")
                for token in ("Apply the recorded house-default rules above first",
                              "other open decision without a ``house_default``",
                              "For each other match without a ``house_default``"):
                    self.assertIn(token, detect)
                self.assertNotIn("Apply the recorded house-default rule above first", detect)
                first = section(body, "Recorded house default: first pass", "Detect (bootstrap and analyse)")
                for token in ("``confirmed_by`` and ``confirmed_at`` from the entry's ``house_default``",
                              "``confirmed_revision`` is the import revision", "carries no ``decided``",
                              "never invent a confirmer for the entry or its rows"):
                    self.assertIn(token, first)
                self.assertNotIn("copy ``confirmed_by``, ``confirmed_at`` and ``decided``", first)


class AnalyseChecksCriteria(unittest.TestCase):
    def test_pre_run_plausibility_compares_criteria_status_with_the_sql(self):
        for tree in TREES:
            with self.subTest(tree=tree):
                rule = section(text(tree, "analyse"), "## Pre-run plausibility", "## Existing review")
                for token in ("`criteria_status`", "`applied` or `partially-applied`", "logic in the SQL",
                              "each `flagged` row's named column exists in the named output",
                              "each `delivered` row's data element is a column of an output",
                              "limitation `L-criterion-<id>`", "SQL lines", "does not change the state",
                              "no SQL"):
                    self.assertIn(token, rule)


class BootstrapCriteriaEval(unittest.TestCase):
    """Grade synthetic replies in both engines; no model calls."""

    def test_every_case_has_discriminating_graders_and_fixtures(self):
        self.assertEqual({p.parent.name for p in SUITE.glob("bootstrap-*/prompt.md")}, set(CASES))
        for case, names in CASES.items():
            with self.subTest(case=case):
                root = SUITE / case
                front = yaml.safe_load((root / "prompt.md").read_text().split("---\n")[1])
                self.assertIn("Skill", front["allowed_tools"])
                self.assertFalse(set(front["allowed_tools"]) & {"Bash", "Write", "Edit"})
                self.assertGreaterEqual(front["runs"], 3)
                prompt = (root / "prompt.md").read_text()
                self.assertIn("E1, exclusion", prompt)
                self.assertNotRegex(prompt.split("(no `applied_by`)")[0].splitlines()[-1], "applied_by:")
                metas = {p.stem: yaml.safe_load(p.read_text().split("---\n")[1])
                         for p in (root / "graders").glob("*.md")}
                sources = {k: v["pattern"] for k, v in metas.items() if v["type"] == "regex"}
                self.assertEqual(set(sources), names)
                fired = metas["skill-fired"]
                self.assertEqual((fired["type"], fired["tool"]), ("tool_used", "Skill"))
                self.assertRegex('"skill": "data-request:bootstrap"', fired["input_match"])
                self.assertNotRegex('"skill": "data-request:intake"', fired["input_match"])
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
