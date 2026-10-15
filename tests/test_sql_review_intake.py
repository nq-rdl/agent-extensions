"""Import the analyst's answers sidecar without rebadging its confirmations."""
import copy
import hashlib
import json
import subprocess
import tempfile
import unittest

import yaml

try:
    from test_sql_review_scripts import Project, REPO, run, scope_doc
except ModuleNotFoundError:
    from tests.test_sql_review_scripts import Project, REPO, run, scope_doc


def intake():
    return {"schemaVersion": 1, "approval_number": "THHSAQUIRE-042", "decisions": [
        {"id": "age", "topic": "cohort", "text": "Include adults aged 18 and over.",
         "rationale": "The requester studies adults.", "confirmed_by": "analyst-login",
         "confirmed_at": "2026-09-29T10:00:00Z", "confirmed_role": "analyst",
         "decided": {"by": "requester-login", "role": "requester", "at": "2026-09-28T10:00:00Z",
                     "source": "enquiry reply"}}], "open_questions": ["Which TIA subcodes?"]}


FINGERPRINT_FIELDS = ("cohort_entry_event", "inclusion_criteria", "exclusion_criteria", "requested_data_elements")
STAMP = {"confirmed_by": "analyst-login", "confirmed_role": "analyst", "confirmed_at": "2026-10-13T01:00:00Z"}


def criteria_intake():
    """A schema 2 sidecar: every kind, a researcher-applied exclusion and a withdrawn one with its replacement."""
    value = intake()
    value["schemaVersion"] = 2
    value["criteria"] = [
        {"id": "N1", "kind": "entry_event", "text": "First AAA admission", **STAMP},
        {"id": "I1", "kind": "inclusion", "text": "Aged 65 and over", "applied_by": "rdl", **STAMP,
         "decided": {"by": "requester-login", "role": "requester", "at": "2026-10-12", "source": "enquiry reply"}},
        {"id": "E1", "kind": "exclusion", "text": "Deceased patients", "applied_by": "researcher", **STAMP,
         "withdrawn": {"reason": "Narrowed to death before index", "at": "2026-10-20", "replaced_by": "E4"}},
        {"id": "E4", "kind": "exclusion", "text": "Died before the index admission", **STAMP},
        {"id": "D1", "kind": "data_element", "text": "Admission date", **STAMP},
    ]
    value["fingerprints"] = {k: "sha256:" + format(n, "x") * 64 for n, k in enumerate(FINGERPRINT_FIELDS, 1)}
    return value


def criteria_fault(value, fault):
    """Break one schema 2 rule; the SECRET marker must never reach a diagnostic."""
    c, w = value["criteria"], value["criteria"][2]["withdrawn"]
    if fault == "schema1-criteria": value["schemaVersion"] = 1; value.pop("fingerprints")
    elif fault == "schema1-fingerprints": value["schemaVersion"] = 1; value.pop("criteria")
    elif fault == "version-3": value["schemaVersion"] = 3
    elif fault == "criteria-object": value["criteria"] = {"SECRET": 1}
    elif fault == "criteria-null": value["criteria"] = None
    elif fault == "entry-not-object": c.append("SECRET")
    elif fault == "id-pattern": c[0]["id"] = "N01"
    elif fault == "id-trailing-newline": c[0]["id"] = "N1\n"
    elif fault == "id-prefix": c[0]["id"] = "I9"
    elif fault == "id-duplicate": c[3]["id"] = "E1"
    elif fault == "kind": c[0]["kind"] = "SECRET"
    elif fault == "text-blank": c[0]["text"] = "  "
    elif fault == "confirmed-by-email": c[0]["confirmed_by"] = "secret@example.com"
    elif fault == "confirmed-role": c[0]["confirmed_role"] = "engineer"
    elif fault == "confirmed-at": c[0]["confirmed_at"] = "2026-10-13"
    elif fault == "confirmed-at-day": c[0]["confirmed_at"] = "2026-02-30T01:00:00Z"
    elif fault == "applied-by-value": c[1]["applied_by"] = "SECRET"
    elif fault == "applied-by-entry": c[0]["applied_by"] = "rdl"
    elif fault == "applied-by-data-element": c[4]["applied_by"] = "researcher"
    elif fault == "decided-source": c[1]["decided"]["source"] = ""
    elif fault == "decided-at": c[1]["decided"]["at"] = "SECRET"
    elif fault == "withdrawn-shape": c[2]["withdrawn"] = "SECRET"
    elif fault == "withdrawn-reason": w["reason"] = " "
    elif fault == "withdrawn-at": w["at"] = "2026-13-01"
    elif fault == "replaced-by-missing": w["replaced_by"] = "E9"
    elif fault == "replaced-by-other-kind": w["replaced_by"] = "I1"
    elif fault == "replaced-by-self": w["replaced_by"] = "E1"
    elif fault == "replaced-by-number": w["replaced_by"] = 4
    elif fault == "fingerprints-missing": value.pop("fingerprints")
    elif fault == "fingerprints-null": value["fingerprints"] = None
    elif fault == "fingerprints-array": value["fingerprints"] = ["SECRET"]
    elif fault == "fingerprints-unknown-key": value["fingerprints"]["SECRET"] = "sha256:" + "a" * 64
    elif fault == "fingerprints-key-missing": del value["fingerprints"]["inclusion_criteria"]
    elif fault == "fingerprints-uppercase": value["fingerprints"]["inclusion_criteria"] = "sha256:" + "A" * 64
    elif fault == "fingerprints-short": value["fingerprints"]["inclusion_criteria"] = "sha256:abc"
    elif fault == "fingerprints-prefix": value["fingerprints"]["inclusion_criteria"] = "md5:" + "a" * 64
    elif fault == "fingerprints-trailing-newline": value["fingerprints"]["inclusion_criteria"] = "sha256:" + "a" * 64 + "\n"
    elif fault == "fingerprints-leading-newline": value["fingerprints"]["inclusion_criteria"] = "x\nsha256:" + "a" * 64
    elif fault == "id-leading-newline": c[0]["id"] = "x\nN1"
    elif fault == "fingerprints-number": value["fingerprints"]["inclusion_criteria"] = 7
    else: raise AssertionError(fault)
    return value


CRITERIA_FAULTS = (
    "schema1-criteria", "schema1-fingerprints", "version-3", "criteria-object", "criteria-null",
    "entry-not-object", "id-pattern", "id-trailing-newline", "id-prefix", "id-duplicate", "kind", "text-blank",
    "confirmed-by-email", "confirmed-role", "confirmed-at", "confirmed-at-day", "applied-by-value",
    "applied-by-entry", "applied-by-data-element", "decided-source", "decided-at", "withdrawn-shape",
    "withdrawn-reason", "withdrawn-at", "replaced-by-missing", "replaced-by-other-kind", "replaced-by-self",
    "replaced-by-number", "fingerprints-missing", "fingerprints-null", "fingerprints-array",
    "fingerprints-unknown-key", "fingerprints-key-missing", "fingerprints-uppercase", "fingerprints-short",
    "fingerprints-prefix", "fingerprints-trailing-newline", "fingerprints-leading-newline", "id-leading-newline", "fingerprints-number")

# sha256 of today's `sqlreview.sh intake answers.intake.json 1` stdout for intake(): schema 1 must not change.
SCHEMA_1_OUTPUT_SHA256 = "1c152e9b43f16d6d9a67222144b30a1062583bcc4ed6b1723c68e9ed1baf2617"

TREES = ("skills/data-request-setup", "plugins/data-request/skills/setup",
         "dist/codex/plugins/data-request/skills/setup")


class IntakeReviewRegressions(unittest.TestCase):
    def invoke(self, tree, root, *args):
        return subprocess.run(["bash", str(REPO / tree / "scripts/sqlreview.sh"), *args],
                              cwd=root, capture_output=True, text=True, timeout=30)

    def successful(self, tree, root, *args):
        result = self.invoke(tree, root, *args)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        return result.stdout

    def test_existing_item_approvals_checked_without_document_approval(self):
        for tree in TREES:
            with self.subTest(tree=tree), tempfile.TemporaryDirectory() as tmp:
                p = Project(tmp)
                source = p.root / "answers.intake.json"
                source.write_text(json.dumps(intake()))
                imported = json.loads(self.successful(tree, p.root, "intake", str(source), "1"))
                d = scope_doc(sql_sha256=None, assumptions=imported["assumptions"])
                self.assertNotIn("approval_number", d)
                draft = p.write_json(d["slug"], "scope.draft.json", d)
                other = intake()
                other["approval_number"] = "SECRET-OTHER-APPROVAL"
                other["decisions"][0]["id"] = "noncolliding"
                # Empty intake must not bypass the existing-item approval check either.
                for decisions in (other["decisions"], []):
                    with self.subTest(decisions=len(decisions)):
                        other["decisions"] = decisions
                        source.write_text(json.dumps(other))
                        before = draft.read_bytes()
                        result = self.invoke(tree, p.root, "intake", str(source), "1", str(draft))
                        self.assertEqual(result.returncode, 4, result.stdout + result.stderr)
                        self.assertEqual(result.stdout, "")
                        self.assertNotIn("SECRET", result.stderr)
                        self.assertEqual(draft.read_bytes(), before)
                # Same-approval additions still work without a document-level identifier.
                other["approval_number"] = intake()["approval_number"]
                other["decisions"] = intake()["decisions"]
                other["decisions"][0]["id"] = "noncolliding"
                source.write_text(json.dumps(other))
                merged = json.loads(self.successful(tree, p.root, "intake", str(source), "1", str(draft)))
                self.assertEqual(len(merged["assumptions"]), 2)

    def test_refresh_removes_only_sidecar_owned_questions(self):
        for tree in TREES:
            with self.subTest(tree=tree), tempfile.TemporaryDirectory() as tmp:
                p = Project(tmp)
                source = p.root / "answers.intake.json"
                source.write_text(json.dumps(intake()))
                manual = ["Which wards?", "Analyst question: Confirm the follow-up window."]
                d = scope_doc(sql_sha256=None, open_questions=manual)
                draft = p.write_json(d["slug"], "scope.draft.json", d)
                first = self.successful(tree, p.root, "intake", str(source), "1", str(draft))
                draft.write_text(first)
                self.successful(tree, p.root, "publish", d["slug"], "scope", str(draft))
                d = json.loads(first)
                d["revision"] = 2
                draft.write_text(json.dumps(d))
                carried = json.loads(self.successful(tree, p.root, "carryforward", d["slug"], "scope", str(draft)))
                by_id = {row["id"]: row["set"] for row in carried["carry"]}
                for item in d["assumptions"]:
                    item.update(by_id[item["id"]])
                draft.write_text(json.dumps(d))
                answered = intake()
                decision = copy.deepcopy(answered["decisions"][0])
                decision.update(id="tia", topic="codes", text="Include the recorded TIA subcodes.")
                answered["decisions"].append(decision)
                for questions in (["Which outcome window?"], []):
                    with self.subTest(questions=questions):
                        answered["open_questions"] = questions
                        source.write_text(json.dumps(answered))
                        merged_text = self.successful(tree, p.root, "intake", str(source), "2", str(draft))
                        merged = json.loads(merged_text)
                        expected = manual + ["Analyst question: " + q for q in questions]
                        self.assertEqual(sorted(merged["open_questions"]), sorted(expected))
                        draft.write_text(merged_text)
                        repeated = self.successful(tree, p.root, "intake", str(source), "2", str(draft))
                        self.assertEqual(json.loads(repeated), merged)
                self.successful(tree, p.root, "publish", d["slug"], "scope", str(draft))
                self.successful(tree, p.root, "render", d["slug"], "scope")
                rendered = (draft.parent / "scope.md").read_text()
                self.assertNotIn("Which TIA subcodes?", rendered)
                self.assertNotIn("Which outcome window?", rendered)
                self.assertIn(manual[1], rendered)

    def test_legacy_question_ownership_is_explicit_and_does_not_erase_other_gaps(self):
        for tree in TREES:
            with self.subTest(tree=tree), tempfile.TemporaryDirectory() as tmp:
                p = Project(tmp)
                source = p.root / "answers.intake.json"
                answered = intake()
                answered["open_questions"] = []
                source.write_text(json.dumps(answered))
                old = "Analyst question: Which TIA subcodes?"
                manual = "Analyst question: Confirm the follow-up window."
                d = scope_doc(sql_sha256=None, open_questions=[old, manual])
                draft = p.write_json(d["slug"], "scope.draft.json", d)
                unowned = json.loads(self.successful(tree, p.root, "intake", str(source), "1", str(draft)))
                self.assertEqual(sorted(unowned["open_questions"]), sorted([old, manual]))
                # Seed known legacy sidecar ownership, never infer it from the prefix.
                d["intake_questions"] = [old]
                draft.write_text(json.dumps(d))
                migrated = json.loads(self.successful(tree, p.root, "intake", str(source), "1", str(draft)))
                self.assertEqual(migrated["open_questions"], [manual])
                # The same wording may also have been raised independently; don't claim it.
                answered["open_questions"] = [manual.removeprefix("Analyst question: ")]
                source.write_text(json.dumps(answered))
                draft.write_text(json.dumps(migrated))
                overlap = json.loads(self.successful(tree, p.root, "intake", str(source), "1", str(draft)))
                self.assertEqual(overlap["intake_questions"], [])
                draft.write_text(json.dumps(overlap))
                answered["open_questions"] = []
                source.write_text(json.dumps(answered))
                cleared = json.loads(self.successful(tree, p.root, "intake", str(source), "1", str(draft)))
                self.assertEqual(cleared["open_questions"], [manual])
                for invalid in (None, "SECRET", ["Which wards?"], [42]):
                    with self.subTest(invalid=invalid):
                        d["intake_questions"] = invalid
                        draft.write_text(json.dumps(d))
                        result = self.invoke(tree, p.root, "intake", str(source), "1", str(draft))
                        self.assertEqual(result.returncode, 4, result.stdout + result.stderr)
                        self.assertEqual(result.stdout, "")
                        self.assertNotIn("SECRET", result.stderr)

    def test_merge_rejects_sql_location_on_imported_confirmation(self):
        for tree in TREES:
            with self.subTest(tree=tree), tempfile.TemporaryDirectory() as tmp:
                p = Project(tmp)
                source = p.root / "answers.intake.json"
                source.write_text(json.dumps(intake()))
                imported = json.loads(self.successful(tree, p.root, "intake", str(source), "1"))
                imported["assumptions"][0]["location"] = {"lines": [1, 2]}
                d = scope_doc(sql_sha256=None, assumptions=imported["assumptions"])
                draft = p.write_json(d["slug"], "scope.draft.json", d)
                before = draft.read_bytes()
                result = self.invoke(tree, p.root, "intake", str(source), "1", str(draft))
                self.assertEqual(result.returncode, 4, result.stdout + result.stderr)
                self.assertEqual(result.stdout, "")
                self.assertEqual(draft.read_bytes(), before)

    def test_source_filename_is_portable_in_import_merge_and_render(self):
        for tree in TREES:
            with self.subTest(tree=tree), tempfile.TemporaryDirectory() as tmp:
                p = Project(tmp)
                source = p.root / "private workstation" / "answers.intake.json"
                source.parent.mkdir()
                original = json.dumps(intake())
                source.write_text(original)
                absolute = json.loads(self.successful(tree, p.root, "intake", str(source), "1"))
                self.assertEqual(absolute["assumptions"][0]["upstream"]["file"], source.name)
                relative = json.loads(self.successful(tree, p.root, "intake", str(source.relative_to(p.root)), "1"))
                self.assertEqual(absolute, relative)
                d = scope_doc(sql_sha256=None)
                draft = p.write_json(d["slug"], "scope.draft.json", d)
                draft.write_text(self.successful(tree, p.root, "intake", str(source), "1", str(draft)))
                merged = json.loads(draft.read_text())
                again = self.successful(tree, p.root, "intake", str(source.relative_to(p.root)), "1", str(draft))
                self.assertEqual(json.loads(again), merged)
                self.successful(tree, p.root, "publish", d["slug"], "scope", str(draft))
                self.successful(tree, p.root, "render", d["slug"], "scope")
                rendered = (draft.parent / "scope.md").read_text()
                self.assertIn("answers.intake.json#age", rendered)
                self.assertNotIn(str(p.root), rendered)
                self.assertNotIn("private workstation", rendered)
                self.assertEqual(source.read_text(), original)

    def test_schema_2_returns_criteria_and_fingerprints_verbatim(self):
        value = criteria_intake()
        for tree in TREES:
            with self.subTest(tree=tree), tempfile.TemporaryDirectory() as tmp:
                p = Project(tmp)
                source = p.root / "answers.intake.json"
                source.write_text(json.dumps(value))
                result = json.loads(self.successful(tree, p.root, "intake", str(source), "1"))
                self.assertEqual(list(result), ["present", "approval_number", "assumptions", "analyst_questions",
                                                "criteria", "fingerprints"])
                self.assertIs(result["present"], True)
                self.assertEqual(result["criteria"], value["criteria"])
                self.assertEqual(result["fingerprints"], value["fingerprints"])
                self.assertEqual([c["id"] for c in result["criteria"]], ["N1", "I1", "E1", "E4", "D1"])
                self.assertEqual(result["criteria"][2]["withdrawn"]["replaced_by"], "E4")
                self.assertEqual(result["criteria"][1]["applied_by"], "rdl")
                # The decisions and questions still import exactly as under schema 1.
                self.assertEqual([a["id"] for a in result["assumptions"]], ["A-intake-age"])
                self.assertEqual(result["analyst_questions"], ["Analyst question: Which TIA subcodes?"])

    def test_schema_2_without_criteria_is_valid_and_empty(self):
        for tree in TREES:
            with self.subTest(tree=tree), tempfile.TemporaryDirectory() as tmp:
                p = Project(tmp)
                source = p.root / "answers.intake.json"
                value = intake()
                value["schemaVersion"] = 2
                source.write_text(json.dumps(value))
                result = json.loads(self.successful(tree, p.root, "intake", str(source), "1"))
                self.assertEqual((result["criteria"], result["fingerprints"]), ([], None))
                value["criteria"] = []
                source.write_text(json.dumps(value))
                self.assertEqual(json.loads(self.successful(tree, p.root, "intake", str(source), "1"))["criteria"], [])
                # Fingerprints may stand alone, but must be exact when present.
                value["fingerprints"] = criteria_intake()["fingerprints"]
                source.write_text(json.dumps(value))
                self.assertEqual(json.loads(self.successful(tree, p.root, "intake", str(source), "1"))["fingerprints"],
                                 value["fingerprints"])

    def test_schema_2_edge_forms_the_validator_accepts(self):
        value = criteria_intake()
        value["criteria"][2]["withdrawn"]["replaced_by"] = "E4"
        value["criteria"][3]["withdrawn"] = {"reason": "Dropped", "at": "2026-10-21T02:03:04Z", "replaced_by": "E1"}
        value["criteria"].append({"id": "I10", "kind": "inclusion", "text": "Adults", **STAMP,
                                  "withdrawn": {"reason": "Merged", "at": "2026-10-21"}})
        for tree in TREES:
            with self.subTest(tree=tree), tempfile.TemporaryDirectory() as tmp:
                p = Project(tmp)
                source = p.root / "answers.intake.json"
                source.write_text(json.dumps(value))
                result = json.loads(self.successful(tree, p.root, "intake", str(source), "1"))
                self.assertEqual(result["criteria"], value["criteria"])

    def test_schema_1_output_is_byte_identical_to_before_schema_2(self):
        for tree in TREES:
            with self.subTest(tree=tree), tempfile.TemporaryDirectory() as tmp:
                p = Project(tmp)
                source = p.root / "answers.intake.json"
                source.write_text(json.dumps(intake()))
                out = self.successful(tree, p.root, "intake", str(source), "1")
                self.assertEqual(hashlib.sha256(out.encode()).hexdigest(), SCHEMA_1_OUTPUT_SHA256)
                self.assertNotIn("criteria", out)
                self.assertNotIn("fingerprints", out)

    def test_invalid_schema_2_exits_4_without_echoing_values(self):
        for tree in TREES:
            for fault in CRITERIA_FAULTS:
                with self.subTest(tree=tree, fault=fault), tempfile.TemporaryDirectory() as tmp:
                    p = Project(tmp)
                    source = p.root / "answers.intake.json"
                    source.write_text(json.dumps(criteria_fault(criteria_intake(), fault)))
                    result = self.invoke(tree, p.root, "intake", str(source), "1")
                    self.assertEqual(result.returncode, 4, result.stdout + result.stderr)
                    self.assertEqual(result.stdout, "")
                    for secret in ("SECRET", "secret@example.com", "sha256:", "Deceased"):
                        self.assertNotIn(secret, result.stderr)

    def test_schema_2_merges_into_a_scope_draft_without_criteria_leaking_in(self):
        for tree in TREES:
            with self.subTest(tree=tree), tempfile.TemporaryDirectory() as tmp:
                p = Project(tmp)
                source = p.root / "answers.intake.json"
                source.write_text(json.dumps(criteria_intake()))
                d = scope_doc(sql_sha256=None, approval_number="THHSAQUIRE-042")
                draft = p.write_json(d["slug"], "scope.draft.json", d)
                merged = json.loads(self.successful(tree, p.root, "intake", str(source), "1", str(draft)))
                self.assertNotIn("criteria", merged)
                self.assertNotIn("fingerprints", merged)
                self.assertIn("A-intake-age", [a["id"] for a in merged["assumptions"]])


class Intake(unittest.TestCase):
    def test_calendar_dates_and_utc_clock_match_python_validator(self):
        with tempfile.TemporaryDirectory() as tmp:
            p = Project(tmp)
            for field, date, valid in (
                ("origin", "2026-02-30", False), ("origin", "2025-02-29", False),
                ("origin", "2000-02-29", True), ("origin", "1900-02-29", False),
                ("origin", "2024-02-29", True), ("confirmation", "2026-02-30T10:00:00Z", False),
                ("confirmation", "2024-02-29T23:59:59Z", True),
                ("confirmation", "2026-09-29T24:00:00Z", False),
                ("confirmation", "2026-09-29T10:00:60Z", False)):
                with self.subTest(field=field, date=date):
                    value = intake()
                    if field == "origin": value["decisions"][0]["decided"]["at"] = date
                    else: value["decisions"][0]["confirmed_at"] = date
                    source = p.root / "answers.intake.json"
                    source.write_text(json.dumps(value))
                    result = run(["intake", str(source), "1"], p.root)
                    self.assertEqual(result.returncode, 0 if valid else 4, result.stderr)

    def test_installed_helpers_import_same_confirmations(self):
        with tempfile.TemporaryDirectory() as tmp:
            p = Project(tmp)
            source = p.root / "answers.intake.json"
            source.write_text(json.dumps(intake()))
            expected = json.loads(run(["intake", str(source), "1"], p.root).stdout)
            for tree in ("plugins/data-request", "dist/codex/plugins/data-request"):
                helper = REPO / tree / "skills/setup/scripts/sqlreview.sh"
                result = subprocess.run(["bash", str(helper), "intake", str(source), "1"],
                                        cwd=p.root, capture_output=True, text=True)
                self.assertEqual(result.returncode, 0, result.stderr)
                self.assertEqual(json.loads(result.stdout), expected)

    def test_missing_intake_is_a_legacy_noop(self):
        with tempfile.TemporaryDirectory() as tmp:
            p = Project(tmp)
            r = run(["intake", "answers.intake.json", "1"], p.root)
            self.assertEqual(r.returncode, 0, r.stderr)
            self.assertEqual(json.loads(r.stdout), {"present": False, "assumptions": [], "analyst_questions": []})

    def test_import_publish_render_and_carry_preserve_both_actors(self):
        with tempfile.TemporaryDirectory() as tmp:
            p = Project(tmp)
            source = p.root / "answers.intake.json"
            source.write_text(json.dumps(intake()))
            r = run(["intake", str(source), "1"], p.root)
            self.assertEqual(r.returncode, 0, r.stderr)
            imported = json.loads(r.stdout)
            a = imported["assumptions"][0]
            self.assertEqual(a["confirmed_by"], "analyst-login")
            self.assertEqual(a["confirmed_at"], intake()["decisions"][0]["confirmed_at"])
            self.assertEqual(a["decided"], intake()["decisions"][0]["decided"])
            self.assertEqual(a["upstream"]["role"], "analyst")
            d = scope_doc(assumptions=[a], sql_sha256=None,
                          open_questions=imported["analyst_questions"])
            draft = p.write_json(d["slug"], "scope.draft.json", d)
            result = run(["publish", d["slug"], "scope", str(draft)], p.root)
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            self.assertEqual(run(["render", d["slug"], "scope"], p.root).returncode, 0)
            rendered = (draft.parent / "scope.md").read_text()
            self.assertIn("analyst-intake", rendered)
            self.assertIn("analyst-login", rendered)
            self.assertIn("Analyst question:", rendered)
            d["revision"] = 2
            draft.write_text(json.dumps(d))
            result = run(["carryforward", d["slug"], "scope", str(draft)], p.root)
            self.assertEqual(result.returncode, 0, result.stderr)
            carried = json.loads(result.stdout)["carry"][0]["set"]
            self.assertEqual(carried["upstream"], a["upstream"])
            self.assertEqual(carried["decided"], a["decided"])
            d["assumptions"][0].update(carried)
            draft.write_text(json.dumps(d))
            merged = run(["intake", str(source), "2", str(draft)], p.root)
            self.assertEqual(merged.returncode, 0, merged.stderr)
            draft.write_text(merged.stdout)
            result = run(["publish", d["slug"], "scope", str(draft)], p.root)
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            final = json.loads((draft.parent / "scope.json").read_text())["assumptions"][0]
            self.assertEqual((final["confirmed_revision"], final["carried_from_revision"]), (1, 1))
            self.assertEqual(final["confirmed_by"], "analyst-login")

    def test_grain_and_finer_outputs_survive_import_publish_and_carry(self):
        for tree in ("skills/data-request-setup", "plugins/data-request/skills/setup",
                     "dist/codex/plugins/data-request/skills/setup"):
            with self.subTest(tree=tree), tempfile.TemporaryDirectory() as tmp:
                p = Project(tmp)
                helper = REPO / tree / "scripts/sqlreview.sh"

                def invoke(*args):
                    result = subprocess.run(["bash", str(helper), *args], cwd=p.root,
                                            capture_output=True, text=True, timeout=30)
                    self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
                    return result.stdout

                value = intake()
                grain = copy.deepcopy(value["decisions"][0])
                grain.update(id="grain", topic="grain", unit="admission",
                             text="One cohort row per admission.",
                             rationale="The requester studies admissions.",
                             finer_outputs=[{"name": "procedures", "unit": "procedure",
                                             "description": "Procedure rows linked by admission key."}])
                grain["decided"]["at"] = "2026-09-28"
                value["decisions"].append(grain)
                source = p.root / "answers.intake.json"
                original = json.dumps(value)
                source.write_text(original)
                d = scope_doc(sql_sha256=None, approval_number=value["approval_number"])
                d["assumptions"][0]["confirmed_by"] = "engineer-login"
                draft = p.write_json(d["slug"], "scope.draft.json", d)
                draft.write_text(invoke("intake", str(source), "1", str(draft)))
                merged = json.loads(draft.read_text())
                imported = next(a for a in merged["assumptions"] if a["id"] == "A-intake-grain")
                self.assertEqual(imported["upstream"]["unit"], "admission")
                self.assertEqual(imported["upstream"]["finer_outputs"], grain["finer_outputs"])
                self.assertEqual(imported["decided"], grain["decided"])
                self.assertEqual(imported["confirmed_at"], grain["confirmed_at"])
                self.assertEqual(imported["confirmed_by"], "analyst-login")
                # Engineer and analyst confirmations coexist; config labels identify neither.
                engineer_item = next(a for a in merged["assumptions"] if a["id"] == "A1")
                self.assertEqual(engineer_item["confirmed_by"], "engineer-login")
                invoke("publish", d["slug"], "scope", str(draft))
                published = json.loads((draft.parent / "scope.json").read_text())
                self.assertEqual(published, merged)
                published["revision"] = 2
                draft.write_text(json.dumps(published))
                carried = json.loads(invoke("carryforward", d["slug"], "scope", str(draft)))
                self.assertEqual(carried["walk"], [])
                by_id = {row["id"]: row["set"] for row in carried["carry"]}
                self.assertEqual(by_id[imported["id"]]["upstream"], imported["upstream"])
                self.assertEqual(by_id[imported["id"]]["decided"], grain["decided"])
                for item in published["assumptions"]:
                    item.update(by_id[item["id"]])
                draft.write_text(json.dumps(published))
                again = invoke("intake", str(source), "2", str(draft))
                self.assertEqual(json.loads(again), published)
                draft.write_text(again)
                invoke("publish", d["slug"], "scope", str(draft))
                final = json.loads((draft.parent / "scope.json").read_text())
                final_grain = next(a for a in final["assumptions"] if a["id"] == imported["id"])
                self.assertEqual(final_grain, imported | by_id[imported["id"]])
                self.assertEqual((final_grain["confirmed_revision"], final_grain["carried_from_revision"]), (1, 1))
                invoke("render", d["slug"], "scope")
                rendered = (draft.parent / "scope.md").read_text()
                for token in ("One cohort row per admission", "analyst-login", "engineer-login", "analyst-intake"):
                    self.assertIn(token, rendered)
                self.assertEqual(source.read_text(), original)

    def test_date_only_origin_is_preserved(self):
        with tempfile.TemporaryDirectory() as tmp:
            p = Project(tmp)
            value = intake()
            value["decisions"][0]["decided"]["at"] = "2026-09-28"
            source = p.root / "answers.intake.json"
            source.write_text(json.dumps(value))
            result = run(["intake", str(source), "1"], p.root)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual(json.loads(result.stdout)["assumptions"][0]["decided"]["at"], "2026-09-28")

    def test_invalid_intake_does_not_print_sensitive_values(self):
        with tempfile.TemporaryDirectory() as tmp:
            p = Project(tmp)
            for fault in ("confirmer", "duplicate", "date", "schema", "shape", "finer-null"):
                value = copy.deepcopy(intake())
                if fault == "confirmer": value["decisions"][0]["confirmed_by"] = "secret@example.com"
                elif fault == "duplicate": value["decisions"].append(value["decisions"][0])
                elif fault == "date": value["decisions"][0]["confirmed_at"] = "SECRET"
                elif fault == "schema": value["schemaVersion"] = 99
                elif fault == "finer-null": value["decisions"][0].update(topic="grain", unit="patient", finer_outputs=None)
                else: value["decisions"] = "SECRET"
                source = p.root / "answers.intake.json"
                source.write_text(json.dumps(value))
                r = run(["intake", str(source), "1"], p.root)
                self.assertEqual(r.returncode, 4, r.stdout + r.stderr)
                self.assertNotIn("SECRET", r.stdout + r.stderr)
                self.assertNotIn("secret@example.com", r.stdout + r.stderr)

    def test_merge_is_idempotent_and_rejects_collision_and_wrong_approval(self):
        with tempfile.TemporaryDirectory() as tmp:
            p = Project(tmp)
            source = p.root / "answers.intake.json"
            source.write_text(json.dumps(intake()))
            d = scope_doc(sql_sha256=None, approval_number="THHSAQUIRE-042")
            draft = p.write_json(d["slug"], "scope.draft.json", d)
            first = run(["intake", str(source), "1", str(draft)], p.root)
            self.assertEqual(first.returncode, 0, first.stderr)
            merged = json.loads(first.stdout)
            self.assertEqual(len(merged["assumptions"]), 2)
            draft.write_text(first.stdout)
            second = run(["intake", str(source), "1", str(draft)], p.root)
            self.assertEqual(second.returncode, 0, second.stderr)
            self.assertEqual(json.loads(second.stdout), merged)
            for field, value in (("approval_number", "SECRET"), ("revision", 2)):
                broken = copy.deepcopy(merged)
                broken[field] = value
                draft.write_text(json.dumps(broken))
                result = run(["intake", str(source), "1", str(draft)], p.root)
                self.assertEqual(result.returncode, 4, result.stderr)
                self.assertNotIn("SECRET", result.stderr)
            merged["assumptions"][-1]["text"] = "Engineer replacement"
            draft.write_text(json.dumps(merged))
            self.assertEqual(run(["intake", str(source), "1", str(draft)], p.root).returncode, 4)

    def test_role_and_handoff_contracts(self):
        for tree in ("skills", "plugins/data-request/skills", "dist/codex/plugins/data-request/skills"):
            owners = {
                "setup": ("Data Engineer",), "bootstrap": ("Data Engineer",),
                "draft": ("Data Engineer",), "analyse": ("Data Engineer",),
                "map": ("Data Engineer",), "validate": ("Data Engineer",),
                "fix": ("Data Engineer",), "lift": ("Data Engineer",),
                "explain": ("Data Analyst",), "release": ("Data Analyst",),
                "amend": ("Data Analyst",), "lookup": ("Data Analyst",), "intake": ("Data Analyst",),
                "triage": ("Data Analyst", "Data Engineer"),
                "guardrails": ("Data Engineer", "Data Analyst"),
            }
            registry = yaml.safe_load((REPO / "registry/bundles/data-request.yaml").read_text())
            self.assertEqual(set(owners), {member["leaf"] for member in registry["skills"]})
            for stage, roles in owners.items():
                with self.subTest(tree=tree, stage=stage):
                    leaf = "data-request-" + stage if tree == "skills" else stage
                    body = (REPO / tree / leaf / "SKILL.md").read_text().split("\n# Data Request", 1)[1]
                    opening = " ".join(body.split("\n## ", 1)[0].split())[:500]
                    for role in roles:
                        self.assertIn(role, opening)
            bootstrap = (REPO / tree / ("data-request-bootstrap" if tree == "skills" else "bootstrap") / "SKILL.md").read_text()
            self.assertIn("answers.intake.json", bootstrap)
            self.assertIn("Do not ask the engineer", bootstrap)
