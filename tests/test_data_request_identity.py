"""Records name people by handle, never by email address (issue #419).

A `.sqlreview` record is committed to the request repository. When a skill filled a `by` or
`*_by` field from `git config user.email`, the analyst's personal address was published with
the request. These tests pin:

* `sqlreview.sh check` refuses a review or scope whose `by`/`*_by` value contains an `@`;
* `release.sh check` refuses a release record with one;
* the guard refuses an `explain.json` Write with one, and denies an `explain.json` Edit;
* each skill that writes such a field names the handle and never `user.email` as a source;
* the plugin copies ship the shared jq rule.

No model call is made.
"""

import json
import re
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

try:  # `unittest discover -s tests` puts tests/ on sys.path; `-m unittest tests.x` does not
    from test_sql_review_scripts import review_doc, run as run_sqlreview, scope_doc
    from test_data_request_release import RELEASE, clean_env, record, violations
except ModuleNotFoundError:
    from tests.test_sql_review_scripts import review_doc, run as run_sqlreview, scope_doc
    from tests.test_data_request_release import RELEASE, clean_env, record, violations

REPO = Path(__file__).resolve().parent.parent
GUARD = REPO / "hooks" / "data-request-guard.sh"
RULE = "scripts/sqlreview-identity.jq"
EMAIL = "someone@example.com"
MESSAGE = "must be a handle (GitHub login or git user.name), not an email address"


@unittest.skipUnless(shutil.which("jq"), "sqlreview.sh needs jq")
class SqlreviewCheck(unittest.TestCase):
    def check(self, doc):
        with tempfile.TemporaryDirectory() as tmp:
            r = run_sqlreview(["check", "--stdin"], tmp, stdin=json.dumps(doc))
        return r.returncode, r.stdout + r.stderr

    def assertRefused(self, doc, path):
        code, out = self.check(doc)
        self.assertEqual(code, 4, out)
        self.assertIn(f"{path}: ", out)
        self.assertIn(MESSAGE, out)
        self.assertNotIn(EMAIL, out)  # the violation never echoes the address

    def test_handles_pass(self):
        self.assertEqual(self.check(review_doc())[0], 0)
        self.assertEqual(self.check(scope_doc())[0], 0)

    def test_email_in_any_identity_field_is_refused(self):
        doc = review_doc()
        doc["assumptions"][0]["confirmed_by"] = EMAIL
        self.assertRefused(doc, "A1")
        self.assertRefused(review_doc(recorded_by=EMAIL), "recorded_by")
        doc = review_doc()
        doc["changes"][0]["by"] = EMAIL
        self.assertRefused(doc, "changes.0.by")
        self.assertRefused(scope_doc(recorded_by=EMAIL), "recorded_by")

    def test_any_at_sign_is_refused(self):
        self.assertRefused(review_doc(recorded_by="@analyst"), "recorded_by")

    def test_other_fields_may_carry_an_at_sign(self):
        doc = review_doc()
        doc["assumptions"][0]["text"] = "Contact addresses such as x@y.org are dropped."
        self.assertEqual(self.check(doc)[0], 0, self.check(doc)[1])


@unittest.skipUnless(shutil.which("jq"), "release.sh needs jq")
class ReleaseCheck(unittest.TestCase):
    def assertRefused(self, doc, path):
        code, out = violations(doc)
        self.assertEqual(code, 4, out)
        self.assertIn(f"{path}: ", out)
        self.assertIn(MESSAGE, out)

    def test_email_in_release_identity_fields_is_refused(self):
        self.assertRefused(record(recorded_by=EMAIL), "recorded_by")
        doc = record()
        doc["claims"][0]["decided_by"] = EMAIL
        self.assertRefused(doc, "C1")
        doc = record()
        resolved = [i for i, q in enumerate(doc["questions"]) if q.get("resolved_by")]
        self.assertTrue(resolved, "fixture needs a resolved question")
        doc["questions"][resolved[0]]["resolved_by"] = EMAIL
        self.assertRefused(doc, doc["questions"][resolved[0]]["id"])

    def test_render_still_works(self):
        with tempfile.TemporaryDirectory() as tmp:
            f = Path(tmp) / "release.json"
            f.write_text(json.dumps(record()))
            r = subprocess.run(["bash", str(RELEASE), "render", str(f)], capture_output=True,
                               text=True, env=clean_env(), timeout=60)
        self.assertEqual(r.returncode, 0, r.stderr)


@unittest.skipUnless(shutil.which("jq"), "the guard needs jq")
class ExplainGuard(unittest.TestCase):
    REL = "reviews/reports__monthly/explain.json"

    def decide(self, tool, content=None):
        with tempfile.TemporaryDirectory() as tmp:
            (Path(tmp) / ".sqlreview").mkdir()
            event = {"tool_name": tool, "cwd": tmp,
                     "tool_input": {"file_path": f"{tmp}/.sqlreview/{self.REL}"}}
            if content is not None:
                event["tool_input"]["content"] = content
            r = subprocess.run(["bash", str(GUARD)], input=json.dumps(event), text=True,
                               capture_output=True, env=clean_env(), timeout=60)
        if not r.stdout.strip():
            return "allow", ""
        out = json.loads(r.stdout)["hookSpecificOutput"]
        return out["permissionDecision"], out["permissionDecisionReason"]

    @staticmethod
    def marker(by):
        return json.dumps({"sql_sha256": "0" * 64, "review_revision": 1, "at": "2026-09-29T00:00:00Z",
                           "by": by, "completed": True, "last_step": "outputs"})

    def test_handle_passes(self):
        self.assertEqual(self.decide("Write", self.marker("analyst-login")), ("allow", ""))

    def test_email_is_denied(self):
        decision, reason = self.decide("Write", self.marker(EMAIL))
        self.assertEqual(decision, "deny")
        self.assertIn(MESSAGE, reason)
        self.assertIn("never user.email", reason)
        self.assertNotIn(EMAIL, reason)

    def test_edit_is_denied(self):
        decision, reason = self.decide("Edit")
        self.assertEqual(decision, "deny")
        self.assertIn("Write the complete file", reason)


class SkillContract(unittest.TestCase):
    SKILLS = ("explain", "analyse", "bootstrap", "release")

    def test_skills_name_a_handle_and_never_source_the_email(self):
        for leaf in self.SKILLS:
            body = " ".join((REPO / f"skills/data-request-{leaf}/SKILL.md").read_text().split())
            with self.subTest(leaf):
                self.assertIn("handle", body)
                self.assertIn("GitHub login", body)
                for m in re.finditer(r"user\.email", body):
                    self.assertIn("never", body[max(0, m.start() - 12):m.start()].lower(),
                                  f"user.email offered as a source near: {body[m.start() - 60:m.end() + 20]}")

    def test_definitions_state_the_rule(self):
        body = " ".join((REPO / "skills/data-request-setup/references/definitions.rst").read_text().split())
        self.assertIn("Recorded identity", body)
        self.assertIn("Never use ``git config user.email``", body)

    def test_rule_ships_with_every_copy(self):
        for root in (REPO / "skills/data-request-setup",
                     REPO / "plugins/data-request/skills/setup",
                     REPO / "dist/codex/plugins/data-request/skills/setup"):
            with self.subTest(str(root.relative_to(REPO))):
                self.assertEqual((root / RULE).read_text(), (REPO / "skills/data-request-setup" / RULE).read_text())


if __name__ == "__main__":
    unittest.main()
