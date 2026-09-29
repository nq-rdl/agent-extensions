"""Import the analyst's answers sidecar without rebadging its confirmations."""
import copy
import json
import subprocess
import tempfile
import unittest
from pathlib import Path

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
            for fault in ("confirmer", "duplicate", "date", "schema", "shape"):
                value = copy.deepcopy(intake())
                if fault == "confirmer": value["decisions"][0]["confirmed_by"] = "secret@example.com"
                elif fault == "duplicate": value["decisions"].append(value["decisions"][0])
                elif fault == "date": value["decisions"][0]["confirmed_at"] = "SECRET"
                elif fault == "schema": value["schemaVersion"] = 99
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
            for stage in ("setup", "bootstrap", "draft", "analyse"):
                leaf = "data-request-" + stage if tree == "skills" else stage
                text = (REPO / tree / leaf / "SKILL.md").read_text()
                self.assertIn("Data Engineer", text)
                self.assertIn("analyst", text.lower())
            bootstrap = (REPO / tree / ("data-request-bootstrap" if tree == "skills" else "bootstrap") / "SKILL.md").read_text()
            self.assertIn("answers.intake.json", bootstrap)
            self.assertIn("Do not ask the engineer", bootstrap)
