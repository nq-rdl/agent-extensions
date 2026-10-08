"""#444 authored-content contracts and executable Bash/jq grain rendering.

Routing tests are offline instruction contracts, not live agent/model evidence.
Round trips run shipped helpers in temporary repos, never against a warehouse.
"""
import json
import subprocess
import tempfile
import unittest

from test_data_request_facility_default import TREES, path, text
from test_sql_review_scripts import Project, item, review_doc, scope_doc


class GrainContracts(unittest.TestCase):
    def test_every_consumer_routes_to_one_shared_grain_rule(self):
        for tree in TREES:
            for leaf in ("guardrails", "triage", "map", "bootstrap", "draft", "analyse", "release"):
                with self.subTest(tree=tree, leaf=leaf):
                    self.assertIn("references/grain.rst", text(tree, leaf))

    def rule(self, tree):
        self.assertTrue(path(tree, "guardrails", "references/grain.rst").is_file(),
                        "missing shared grain-evidence rule")
        return text(tree, "guardrails", "references/grain.rst")

    def test_bare_patient_and_other_legacy_values_are_not_confirmations(self):
        for tree in TREES:
            with self.subTest(tree=tree):
                rule = self.rule(tree)
                for token in ("measurement_granularity: Patient", "Grain unconfirmed",
                              "bare default is never evidence", "Admission", "unspecified",
                              "actual recorded analyst answer", "patient grain remains valid"):
                    self.assertIn(token, rule)
                for leaf in ("triage", "map"):
                    self.assertIn("Patient", text(tree, leaf))
                    self.assertIn("unconfirmed", text(tree, leaf))

    def test_evidence_and_formal_confirmation_remain_separate(self):
        for tree in TREES:
            with self.subTest(tree=tree):
                rule = self.rule(tree)
                for token in ("answers.intake.json", "prior version", "requested data elements",
                              "path and revision", "A-grain", "A-intake-",
                              "text and rationale", "Engineer decision (<login>, <date>)",
                              "agent-applied technical default", "decided", "confirmed_by",
                              "answered engineer question", "not analyst-confirmed",
                              "prior SQL is evidence of intent, not correctness"):
                    self.assertIn(token, rule)

    def test_intake_explicitly_asks_clinical_unit_and_finer_outputs(self):
        for tree in TREES:
            with self.subTest(tree=tree):
                intake = text(tree, "setup", "references/analyst-intake.rst")
                for token in ("Ask explicitly", "one row per <unit>", "clinical terms",
                              "per surgery", "per ward stay", "finer_outputs",
                              "measurement_granularity", "open_questions"):
                    self.assertIn(token, intake)
                rule = self.rule(tree)
                for token in ("one row per admission", "one row per ED presentation",
                              "one row per transfer episode", "one row per patient",
                              "per surgery", "per ward stay", "Do not collapse",
                              "do not build an unrequested detail output", "read the prior SQL"):
                    self.assertIn(token, rule)

    def test_mismatch_is_one_persistent_record_not_a_repeated_blocker(self):
        for tree in TREES:
            with self.subTest(tree=tree):
                rule = self.rule(tree)
                for token in ("L-grain-answers", "once", "same ID", "bootstrap", "analyse",
                              "before the unchanged-SQL", "each delivered file", "expected finer output",
                              "Offer to update", "answers.yaml", "same change", "validate-answers",
                              "not permission to change SQL", "released row count", "not a blocker",
                              "resolved", "do not duplicate"):
                    self.assertIn(token, rule)

    def test_unchanged_sql_exit_is_gated_on_review_content(self):
        for tree in TREES:
            with self.subTest(tree=tree):
                analyse = text(tree, "analyse")
                unchanged = analyse.split("### Unchanged SQL: complete publication before stopping", 1)[1]
                unchanged = unchanged.split("### ", 1)[0]
                unchanged = " ".join(unchanged.split())
                self.assertIn("Only when the grain precheck requires no review-content change", unchanged)
                self.assertIn("Otherwise bypass this early return", unchanged)
                metadata = analyse.split("### Metadata-only changes: update despite unchanged SQL", 1)[1]
                metadata = " ".join(metadata.split("### ", 1)[0].split())
                for change in ("newly confirmed grain", "add or revise `L-grain-answers`",
                               "retire a resolved drift finding"):
                    self.assertIn(change, metadata)
                for gate in ("steps 3–4", "carryforward", "increment", "changes[]",
                             "Confirm, write, render", "no SQL hunks", "unconfirmed"):
                    self.assertIn(gate, metadata)

    def test_release_does_not_elevate_bare_answers_to_scope(self):
        for tree in TREES:
            with self.subTest(tree=tree):
                example = text(tree, "release", "references/worked-example.rst")
                self.assertIn("bare default, not a confirmed grain", example)
                self.assertNotIn("The confirmed ``.copier-answers.yml``", example)
                self.assertNotIn("The scope says ``measurement_granularity: Patient``", example)
                self.assertIn("L-grain-answers", example)
                release = text(tree, "release")
                self.assertIn("bare answers-file default", release)
                self.assertIn("not a blocking discrepancy", release)


class GrainRendering(unittest.TestCase):
    def test_review_metadata_updates_add_retire_and_change_grain_without_sql_edits(self):
        # Execute the publication/carry gates with authored confirmation fixtures.
        # This is not a live-model routing test or evidence of real human answers.
        for tree in TREES:
            with self.subTest(tree=tree), tempfile.TemporaryDirectory() as tmp:
                p = Project(tmp)
                helper = path(tree, "setup", "scripts/sqlreview.sh")

                def invoke(*args, code=0):
                    result = subprocess.run(["bash", str(helper), *args], cwd=p.root,
                                            capture_output=True, text=True, timeout=30)
                    self.assertEqual(result.returncode, code, result.stdout + result.stderr)
                    return result.stdout

                sql = p.sql("q.sql", "select admission_id from admissions;\n")
                original_sql = sql.read_bytes()
                p.commit()
                sha = json.loads(invoke("fingerprint", "q.sql"))["sql_sha256"]
                grain = item("A-grain", "One row per admission.",
                             rationale="Prior delivery admissions.csv at v1.0.0 uses admission keys.")
                doc = review_doc("q", "q.sql", sql_sha256=sha, grain="one row per admission",
                                 assumptions=[grain], limitations=[], open_questions=[])
                draft = p.write_json("q", "review.draft.json", doc)
                invoke("publish", "q", "review", str(draft))
                invoke("snapshot", "q", "q.sql")
                prior_bytes = (draft.parent / "review.json").read_bytes()
                for revision, change in ((2, "add drift"), (3, "retire drift"), (4, "change grain")):
                    self.assertIn("unchanged since the reviewed snapshot", invoke("delta", "q"))
                    doc["revision"] = revision
                    doc["changes"].append({"revision": revision, "at": "2026-09-30T10:00:00Z",
                                           "by": "engineer-login", "summary": change})
                    if change == "add drift":
                        doc["limitations"] = [item("L-grain-answers", "Answers says Patient.", revision,
                                                   rationale="The evidenced main grain is admission.", status="candidate")]
                    elif change == "retire drift":
                        doc["limitations"] = []
                    else:
                        doc["grain"] = "one row per patient"
                        doc["assumptions"] = [item("A-grain", "One row per patient.", revision,
                                                  rationale="Amended analyst intake records patient grain.",
                                                  status="candidate")]
                    draft.write_text(json.dumps(doc))
                    carry = json.loads(invoke("carryforward", "q", "review", str(draft)))
                    self.assertTrue(carry["sql_unchanged"])
                    self.assertEqual([row["id"] for row in carry["carry"]],
                                     [] if change == "change grain" else ["A-grain"])
                    self.assertEqual([row["id"] for row in carry["walk"]],
                                     {"add drift": ["L-grain-answers"], "retire drift": [],
                                      "change grain": ["A-grain"]}[change])
                    for row in carry["carry"]:
                        next(i for i in doc[row["kind"]] if i["id"] == row["id"]).update(row["set"])
                    draft.write_text(json.dumps(doc))
                    if change != "retire drift":
                        invoke("publish", "q", "review", str(draft), code=4)
                        self.assertEqual((draft.parent / "review.json").read_bytes(), prior_bytes)
                        # Authored answered-question fixture, not inferred confirmation.
                        for candidate in doc["assumptions"] + doc["limitations"]:
                            if candidate["status"] == "candidate":
                                candidate.update(status="confirmed", confirmed_by="engineer-login",
                                                 confirmed_at="2026-09-30T10:00:00Z",
                                                 confirmed_revision=revision)
                    draft.write_text(json.dumps(doc))
                    invoke("publish", "q", "review", str(draft))
                    invoke("snapshot", "q", "q.sql")
                    invoke("render", "q", "review")
                    prior_bytes = (draft.parent / "review.json").read_bytes()
                    published = json.loads(prior_bytes)
                    self.assertEqual(published["revision"], revision)
                    self.assertEqual(len(published["changes"]), revision)
                    rendered = (draft.parent / "review.md").read_text()
                    self.assertEqual(rendered.count("L-grain-answers"), int(change == "add drift"))
                    self.assertIn(doc["grain"], rendered)
                    self.assertEqual(sql.read_bytes(), original_sql)
                    self.assertEqual((draft.parent / "source.sql").read_bytes(), original_sql)
                self.assertEqual(sorted(f.name for f in (draft.parent / "history").iterdir()),
                                 ["1.sql", "2.sql", "3.sql", "4.sql"])

    def test_confirmed_patient_admission_presentation_and_finer_detail_are_visible_and_carry_once(self):
        for tree in TREES:
            for unit, finer in (("patient", []), ("admission", []), ("ED presentation", []),
                                ("patient", [{"name": "surgeries", "unit": "surgery",
                                              "description": "Linked by patient key."},
                                             {"name": "ward_stays", "unit": "ward stay",
                                              "description": "Ward | stay\nlinked by encounter key."}])):
                with self.subTest(tree=tree, unit=unit, finer=bool(finer)), tempfile.TemporaryDirectory() as tmp:
                    p = Project(tmp)
                    helper = path(tree, "setup", "scripts/sqlreview.sh")

                    def invoke(*args):
                        result = subprocess.run(["bash", str(helper), *args], cwd=p.root,
                                                capture_output=True, text=True, timeout=30)
                        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
                        return result.stdout

                    # No new decision or confirmation is inferred from answers.yaml.
                    (p.root / "answers.yaml").write_text("measurement_granularity: Patient\n")
                    source = p.root / "answers.intake.json"
                    source.write_text(json.dumps({"schemaVersion": 1, "approval_number": "THHSAQUIRE-042",
                        "decisions": [{"id": "grain", "topic": "grain", "unit": unit,
                            "text": f"One row per {unit}.", "rationale": "The analyst records the requested clinical unit.",
                            "finer_outputs": finer, "confirmed_by": "analyst-login", "confirmed_role": "analyst",
                            "confirmed_at": "2026-09-29T10:00:00Z",
                            "decided": {"by": "requester-login", "role": "requester", "at": "2026-09-28",
                                        "source": "enquiry reply"}}], "open_questions": []}))
                    d = scope_doc(sql_sha256=None, assumptions=[])
                    draft = p.write_json(d["slug"], "scope.draft.json", d)
                    draft.write_text(invoke("intake", str(source), "1", str(draft)))
                    invoke("publish", d["slug"], "scope", str(draft))
                    invoke("render", d["slug"], "scope")
                    rendered = (draft.parent / "scope.md").read_text()
                    self.assertIn(f"One row per {unit}", rendered)
                    self.assertIn("analyst-intake:", rendered)
                    for detail in finer:
                        self.assertIn(f'{detail["name"]}: one row per {detail["unit"]}', rendered)
                    if finer:
                        self.assertIn("Ward &#124; stay<br>linked by encounter key.", rendered)
                    published = json.loads((draft.parent / "scope.json").read_text())
                    published["revision"] = 2
                    draft.write_text(json.dumps(published))
                    carry = json.loads(invoke("carryforward", d["slug"], "scope", str(draft)))
                    self.assertEqual(len(carry["carry"]), 1)
                    self.assertEqual(carry["walk"], [])
                    published["assumptions"][0].update(carry["carry"][0]["set"])
                    draft.write_text(json.dumps(published))
                    draft.write_text(invoke("intake", str(source), "2", str(draft)))
                    invoke("publish", d["slug"], "scope", str(draft))
                    final = json.loads((draft.parent / "scope.json").read_text())
                    self.assertEqual(len(final["assumptions"]), 1)
                    self.assertEqual(final["assumptions"][0]["upstream"]["finer_outputs"], finer)
                    self.assertEqual(final["assumptions"][0]["confirmed_by"], "analyst-login")
                    self.assertEqual(final["assumptions"][0]["decided"]["at"], "2026-09-28")
                    self.assertEqual((p.root / "answers.yaml").read_text(), "measurement_granularity: Patient\n")

    def test_legacy_evidenced_grain_and_single_drift_item_survive_rerun_then_retire(self):
        # This exercises persistence/carry, not an automatic YAML comparator.
        for tree in TREES:
            with self.subTest(tree=tree), tempfile.TemporaryDirectory() as tmp:
                p = Project(tmp)
                helper = path(tree, "setup", "scripts/sqlreview.sh")

                def invoke(*args):
                    result = subprocess.run(["bash", str(helper), *args], cwd=p.root,
                                            capture_output=True, text=True, timeout=30)
                    self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
                    return result.stdout

                grain = {"id": "A-grain", "text": "One row per admission.",
                         "rationale": "Engineer decision (engineer-login, 2026-09-29), flagged for the data analyst. Prior delivery admissions.csv at v1.0.0 uses admission keys.",
                         "location": None, "status": "confirmed", "confirmed_by": "engineer-login",
                         "confirmed_at": "2026-09-29T10:00:00Z", "confirmed_revision": 1,
                         "decided": {"by": "engineer-login", "role": "Data Engineer", "at": "2026-09-29",
                                     "source": "admissions.csv at v1.0.0"}}
                drift = {"id": "L-grain-answers", "text": "Answers says Patient; the output has one row per admission.",
                         "rationale": "Prior delivery admissions.csv at v1.0.0 establishes admission grain.",
                         "location": None, "status": "confirmed", "confirmed_by": "engineer-login",
                         "confirmed_at": "2026-09-29T10:00:00Z", "confirmed_revision": 1}
                d = scope_doc(sql_sha256=None, assumptions=[grain], limitations=[drift])
                draft = p.write_json(d["slug"], "scope.draft.json", d)
                invoke("publish", d["slug"], "scope", str(draft))
                d["revision"] = 2
                draft.write_text(json.dumps(d))
                carry = json.loads(invoke("carryforward", d["slug"], "scope", str(draft)))
                self.assertEqual(carry["walk"], [])
                by_id = {row["id"]: row["set"] for row in carry["carry"]}
                for item in d["assumptions"] + d["limitations"]:
                    item.update(by_id[item["id"]])
                draft.write_text(json.dumps(d))
                invoke("publish", d["slug"], "scope", str(draft))
                invoke("render", d["slug"], "scope")
                rendered = (draft.parent / "scope.md").read_text()
                self.assertEqual(rendered.count("L-grain-answers"), 1)
                self.assertIn("admissions.csv at v1.0.0", rendered)
                self.assertIn("Engineer decision (engineer-login, 2026-09-29)", rendered)
                published = json.loads((draft.parent / "scope.json").read_text())
                self.assertEqual(published["assumptions"][0]["decided"], grain["decided"])
                self.assertEqual(published["assumptions"][0]["confirmed_by"], "engineer-login")
                # Accepted configuration correction: normal next revision retires
                # the drift finding; no SQL, answer or confirmation is invented.
                d.update(revision=3, limitations=[])
                draft.write_text(json.dumps(d))
                carry = json.loads(invoke("carryforward", d["slug"], "scope", str(draft)))
                d["assumptions"][0].update(carry["carry"][0]["set"])
                draft.write_text(json.dumps(d))
                invoke("publish", d["slug"], "scope", str(draft))
                invoke("render", d["slug"], "scope")
                self.assertNotIn("L-grain-answers", (draft.parent / "scope.md").read_text())


if __name__ == "__main__":
    unittest.main()
