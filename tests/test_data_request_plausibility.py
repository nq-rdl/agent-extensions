"""#440 offline instruction contracts and real scope-record persistence.

These do not run a model, SQL engine or database. Helper round trips establish
that the existing scope schema renders and carries the proposed record shape.
"""
import json
import subprocess
import tempfile
import unittest

from test_data_request_facility_default import TREES, path, text
from test_sql_review_scripts import Project, item, scope_doc


class PlausibilityContracts(unittest.TestCase):
    def test_bootstrap_records_each_population_dimension_before_both_paths(self):
        for tree in TREES:
            with self.subTest(tree=tree):
                rule = text(tree, "bootstrap")
                for token in ("## Population limits", "age, sex and facility", "A-population-age",
                              "A-population-sex", "tuh-facility", "no stated limit",
                              "unclear", "not yet written", "applied", "missing", "contradicted",
                              "age anchor", "age at index surgery", "SQL lines", "request wording",
                              "Analyst question:", "not an analyst research answer",
                              "Do not infer adult", "Do not add a filter", "already answered",
                              "existing scope item", "open_questions", "intent",
                              "shared `questions.draft.json` / `questions.json` store",
                              "do not add a new embedded list"):
                    self.assertIn(token, rule)
                self.assertLess(rule.index("## Population limits"), rule.index("## Existing scope"))

    def test_population_record_kind_separates_request_facts_choices_and_defects(self):
        for tree in TREES:
            with self.subTest(tree=tree):
                rule = text(tree, "bootstrap").split("## Population limits", 1)[1].split("## Existing scope", 1)[0]
                for token in ("Stated requester limits belong in `intent`", "actual RDL interpretation choice",
                              "`A-population-age`", "`A-population-sex`", "missing or contradicted",
                              "`L-population-age`", "`L-population-sex`", "`limitations`",
                              "not confirmed decisions", "reclassification"):
                    self.assertIn(token, rule)
                self.assertNotIn("Reuse `A-population-age` and `A-population-sex`;", rule)

    def test_population_sql_status_does_not_rewrite_imported_confirmations(self):
        for tree in TREES:
            with self.subTest(tree=tree):
                rule = text(tree, "bootstrap").split("## Population limits", 1)[1].split("## Existing scope", 1)[0]
                for token in ("Keep imported `A-intake-<id>` items verbatim", "text, rationale, actor/date",
                              "`upstream` and `decided`", "Do not duplicate", "separately",
                              "engineer-confirmed SQL implementation", "house-default wording"):
                    self.assertIn(token, rule)
                self.assertNotIn("In each item's text and rationale", rule)

    def test_independent_outputs_have_matching_materialisations_without_per_column_scans(self):
        for tree in TREES:
            with self.subTest(tree=tree):
                rule = text(tree, "guardrails", "references/performance.rst").split("Pre-run plausibility", 1)[1].split("Read isolation", 1)[0]
                for token in ("one bounded source scan per independent source/cohort result",
                              "reuse each materialisation", "same joins, filters, grain and label conversions",
                              "admissions and procedures", "do not pool their populations",
                              "identify its materialisation", "do not re-scan a source per column",
                              "matching bounded materialisation"):
                    self.assertIn(token, rule)
                self.assertNotIn("then reuse it for every label aggregate", rule)

    def test_validate_and_analyse_always_return_operator_proposals_not_execution(self):
        for tree in TREES:
            with self.subTest(tree=tree):
                validate = text(tree, "validate")
                analyse = text(tree, "analyse")
                for rule in (validate, analyse):
                    for token in ("references/performance.rst", "Pre-run plausibility", "each label column",
                                  "proposed", "not executed", "operator", "no SQL", "expensive"):
                        self.assertIn(token, rule)
                self.assertIn("must not connect to a database", validate)
                self.assertIn("does not establish plausibility", validate)
                self.assertLess(analyse.index("Pre-run plausibility"), analyse.index("## Existing review"))

    def test_label_inventory_covers_all_outputs_and_format_edge_cases(self):
        for tree in TREES:
            with self.subTest(tree=tree):
                rule = text(tree, "guardrails", "references/performance.rst")
                for token in ("Pre-run plausibility", "every final result set", "one row per label column",
                              "low-cardinality", "sex", "status", "facility", "NULL", "blank",
                              "unmapped", "raw spelling", "case", "trailing spaces", "binary",
                              "count-only", "no label columns", "patient", "staff or person keys",
                              "Column | Expected labels/format and source | Proposed probe | Bound/cost | Status",
                              "Do not UPPER", "data dictionary", "not a population filter"):
                    self.assertIn(token, rule)

    def test_all_probe_proposals_share_bounds_suppression_and_expensive_age_gate(self):
        for tree in TREES:
            with self.subTest(tree=tree):
                rule = text(tree, "guardrails", "references/performance.rst")
                for token in ("one bounded source scan", "#temp", "@min_cell", "threshold",
                              "Probe disclosure control", "no patient rows",
                              "feeds no delivered extract", "NOLOCK", "READ UNCOMMITTED",
                              "expensive requests only", "estimated rows", "runtime",
                              "cost is unknown", "age at index surgery", "not age today",
                              "no automatic exclusion", "OBSERVED", "INFERRED", "validation_counts",
                              "follow-up", "authorisation"):
                    self.assertIn(token, rule)
                self.assertNotIn("before pipeline SQL exists.", rule)


class PopulationScopeRoundTrip(unittest.TestCase):
    def test_imported_age_and_sex_survive_separate_implementation_update_and_merge(self):
        # Real helper regression, not evidence of a model choosing the right records.
        from test_sql_review_intake import intake

        for tree in TREES:
            with self.subTest(tree=tree), tempfile.TemporaryDirectory() as tmp:
                p = Project(tmp)
                helper = path(tree, "setup", "scripts/sqlreview.sh")

                def invoke(*args):
                    r = subprocess.run(["bash", str(helper), *args], cwd=p.root,
                                       capture_output=True, text=True, timeout=30)
                    self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
                    return r.stdout

                value = intake()
                value["decisions"].append(dict(value["decisions"][0], id="sex",
                                                text="No stated sex limit.",
                                                rationale="The request covers every sex category."))
                source = p.root / "answers.intake.json"
                original = json.dumps(value)
                source.write_text(original)
                d = scope_doc(schemaVersion=2, sql_sha256=None, assumptions=[],
                              limitations=[], open_questions=[],
                              intent="Adults at index surgery; no stated sex limit. SQL is not yet written.")
                draft = p.write_json(d["slug"], "scope.draft.json", d)
                draft.write_text(invoke("intake", str(source), "1", str(draft)))
                d = json.loads(draft.read_text())
                imported = json.loads(json.dumps(d["assumptions"]))
                invoke("publish", d["slug"], "scope", str(draft))
                # Synthetic engineer confirmation of a defect, separate from analyst answers.
                d["revision"] = 2
                d["intent"] = "Adults at index surgery; no stated sex limit. SQL assessment at revision abc."
                d["limitations"] = [item("L-population-age", "The adult restriction is missing from SQL.",
                                          revision=2, rationale="Scope requires adults at index surgery; SQL lines 10-20 omit the filter.",
                                          confirmed_by="engineer-login")]
                draft.write_text(json.dumps(d))
                carry = json.loads(invoke("carryforward", d["slug"], "scope", str(draft)))
                self.assertEqual({row["id"] for row in carry["carry"]}, {a["id"] for a in imported})
                by_id = {row["id"]: row["set"] for row in carry["carry"]}
                for a in d["assumptions"]:
                    a.update(by_id[a["id"]])
                draft.write_text(json.dumps(d))
                merged = invoke("intake", str(source), "2", str(draft))
                self.assertEqual(json.loads(merged), d)
                draft.write_text(merged)
                invoke("publish", d["slug"], "scope", str(draft))
                final = json.loads((draft.parent / "scope.json").read_text())
                self.assertEqual(final["assumptions"], [a | by_id[a["id"]] for a in imported])
                self.assertEqual(final["limitations"], d["limitations"])
                invoke("render", d["slug"], "scope")
                rendered = (draft.parent / "scope.md").read_text()
                for a in imported:
                    for field in ("text", "rationale", "confirmed_by"):
                        self.assertIn(a[field], rendered)
                self.assertIn("L-population-age", rendered)
                self.assertIn("engineer-login", rendered)
                self.assertEqual(source.read_text(), original)

    def test_confirmed_none_applied_missing_and_pending_population_answers_render_and_carry(self):
        cases = (
            ("No stated age limit.", "Request at abc does not say adult. SQL lines 10-20 have no age filter.", [], "intent"),
            ("Age at index surgery is at least 18.", "Recorded requester limit at abc. Applied at SQL lines 10-12.", [], "intent"),
            ("Use the index surgery as the age anchor.", "RDL chooses the first eligible surgery to implement the agreed age boundary.", [], "assumptions"),
            ("The adult restriction is missing from SQL.", "Confirmed scope at abc says age at index surgery is at least 18. SQL lines 10-20 omit it.", [], "limitations"),
            ("The age limit is unclear; SQL is not yet written.", "Request wording at abc says adult service but gives no age anchor.",
             ["Analyst question: Does adult mean age at index surgery is at least 18?"], "limitations"),
        )
        for tree in TREES:
            for answer, rationale, questions, record_kind in cases:
                with self.subTest(tree=tree, answer=answer), tempfile.TemporaryDirectory() as tmp:
                    p = Project(tmp)
                    helper = path(tree, "setup", "scripts/sqlreview.sh")

                    def invoke(*args):
                        r = subprocess.run(["bash", str(helper), *args], cwd=p.root,
                                           capture_output=True, text=True, timeout=30)
                        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
                        return r.stdout

                    # Synthetic fixtures stand in for answered engineer confirmations;
                    # they are not live analyst consent or automatic detection.
                    sex_answer = "No stated sex limit. Request wording at abc has no sex restriction."
                    facility = item("L-population-facility", "The facility set is unresolved.",
                                    rationale="Request wording at abc says whole HHS; TUH alone does not apply.",
                                    confirmed_by="engineer-login")
                    d = scope_doc(schemaVersion=2, sql_sha256=None, assumptions=[],
                                  limitations=[facility], intent=sex_answer, open_questions=questions)
                    if record_kind == "intent":
                        d["intent"] += " " + answer + " " + rationale
                    else:
                        prefix = "A" if record_kind == "assumptions" else "L"
                        d[record_kind].append(item(f"{prefix}-population-age", answer,
                                                   rationale=rationale, confirmed_by="engineer-login"))
                    records = d["assumptions"] + d["limitations"]
                    draft = p.write_json(d["slug"], "scope.draft.json", d)
                    invoke("publish", d["slug"], "scope", str(draft))
                    invoke("render", d["slug"], "scope")
                    rendered = (draft.parent / "scope.md").read_text()
                    self.assertIn(answer, rendered)
                    self.assertIn(rationale, rendered)
                    self.assertIn(sex_answer, rendered)
                    for record in records:
                        self.assertIn(record["text"], rendered)
                        self.assertIn(record["rationale"], rendered)
                    for question in questions:
                        self.assertIn(question, rendered)
                    d["revision"] = 2
                    draft.write_text(json.dumps(d))
                    carry = json.loads(invoke("carryforward", d["slug"], "scope", str(draft)))
                    self.assertEqual(carry["walk"], [])
                    self.assertEqual(len(carry["carry"]), len(records))
                    by_id = {row["id"]: row["set"] for row in carry["carry"]}
                    for record in records:
                        record.update(by_id[record["id"]])
                    draft.write_text(json.dumps(d))
                    invoke("publish", d["slug"], "scope", str(draft))
                    final = json.loads((draft.parent / "scope.json").read_text())
                    self.assertEqual(len(final["assumptions"]) + len(final["limitations"]), len(records))
                    self.assertEqual(final["intent"], d["intent"])
                    self.assertEqual(final["open_questions"], questions)


if __name__ == "__main__":
    unittest.main()
