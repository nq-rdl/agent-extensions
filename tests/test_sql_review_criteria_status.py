"""Scope `criteria_status` (the scaffold's criteria design): the engineer's one confirmed state per research criterion.

Two checks, split because the guard hook cannot see the analyst's sidecar (research R6):

- `sqlreview.sh check` (sqlreview-check.jq, run on every scope write) checks the kind-independent
  shape of `criteria_status`;
- `sqlreview.sh criteria <slug|draft-path>` (sqlreview-criteria-check.jq) checks the scope against
  the schema 2 `answers.intake.json` at the repository root: states allowed for each kind, coverage
  of the non-withdrawn criteria, no state on a withdrawn criterion, a basis for `researcher-applies`
  and at most one owning scope per repository.

Every finding is `<id>\t<field>\t<rule>` and never carries a value.
"""

import copy
import json
import re
import subprocess
import tempfile
import unittest
from pathlib import Path

try:
    from test_sql_review_scripts import REPO, Project, review_doc, run, scope_doc
except ModuleNotFoundError:
    from tests.test_sql_review_scripts import REPO, Project, review_doc, run, scope_doc

FINDING = re.compile(r"^[^\t\n]+\t[^\t\n]+\t[^\t\n]+$")
LEAK_CANARY = "LEAK-CANARY"
STAMP = {"confirmed_by": "analyst-login", "confirmed_role": "analyst", "confirmed_at": "2026-10-13T01:00:00Z"}
FINGERPRINT_FIELDS = ("cohort_entry_event", "inclusion_criteria", "exclusion_criteria", "requested_data_elements")
TREES = ("skills/data-request-setup", "plugins/data-request/skills/setup",
         "dist/codex/plugins/data-request/skills/setup")


def sidecar(schema=2):
    """Every kind; E1 withdrawn (replaced by E4); E3 has no applied_by. Live: N1 I1 E3 E4 D1 D2."""
    value = {"schemaVersion": schema, "approval_number": "THHSAQUIRE-042", "decisions": [], "open_questions": []}
    if schema == 2:
        value["criteria"] = [
            {"id": "N1", "kind": "entry_event", "text": "First AAA admission " + LEAK_CANARY, **STAMP},
            {"id": "I1", "kind": "inclusion", "text": "Aged 65 and over", "applied_by": "rdl", **STAMP},
            {"id": "E1", "kind": "exclusion", "text": "Deceased patients", **STAMP,
             "withdrawn": {"reason": "Narrowed", "at": "2026-10-20", "replaced_by": "E4"}},
            {"id": "E3", "kind": "exclusion", "text": "Prior repair " + LEAK_CANARY, **STAMP},
            {"id": "E4", "kind": "exclusion", "text": "Died before the index admission", **STAMP},
            {"id": "D1", "kind": "data_element", "text": "Admission date", **STAMP},
            {"id": "D2", "kind": "data_element", "text": "Discharge date", **STAMP},
        ]
        value["fingerprints"] = {k: "sha256:" + format(n, "x") * 64 for n, k in enumerate(FINGERPRINT_FIELDS, 1)}
    return value


def row(criterion, state, revision=1, **over):
    d = {"criterion": criterion, "state": state, "confirmed_by": "eng-login",
         "confirmed_at": "2026-10-13T02:00:00Z", "confirmed_revision": revision}
    d.update(over)
    return d


def full_status(revision=1):
    """One state for every live sidecar criterion, each valid for its kind."""
    return [
        row("N1", "applied", revision),
        row("I1", "applied", revision),
        row("E3", "not-applied", revision, reason="First pass: cohort kept broad",
            upstream={"source": "recurring-decision", "id": "broad-first-pass"}),
        row("E4", "flagged", revision, flag={"output": "patients", "column": "excl_prior_repair"}),
        row("D1", "delivered", revision),
        row("D2", "not-delivered", revision, reason="Not held in the source"),
    ]


def scope_with(status, slug="q", sql_path="q.sql", revision=1):
    return scope_doc(slug, sql_path, revision=revision, criteria_status=status)


class Base(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.project = Project(self.tmp.name)
        self.root = self.project.root

    def assert_findings(self, result, expected, code):
        self.assertEqual(result.returncode, code, result.stdout + result.stderr)
        lines = result.stdout.splitlines()
        for line in lines:
            self.assertRegex(line, FINDING)
        self.assertNotIn(LEAK_CANARY, result.stdout + result.stderr)
        for line in expected:
            self.assertIn(line, lines, result.stdout)


class ShapeCheck(Base):
    """T027: `sqlreview.sh check` on a scope carrying criteria_status (kind-independent shape)."""

    def check(self, doc):
        path = self.root / "doc.json"
        path.write_text(json.dumps(doc))
        return run(["check", str(path)], self.root)

    def check_status(self, status, revision=1):
        return self.check(scope_with(status, revision=revision))

    def test_valid_status_passes_check(self):
        result = self.check_status(full_status())
        self.assertEqual((result.returncode, result.stdout), (0, "ok\n"), result.stderr)
        # Shape is kind-independent: an id the sidecar might not know, or a state the kind does
        # not allow, is for `sqlreview.sh criteria`, not for check.
        result = self.check_status([row("N1", "researcher-applies"), row("D7", "applied")])
        self.assertEqual((result.returncode, result.stdout), (0, "ok\n"), result.stderr)
        self.assertEqual(self.check_status([]).returncode, 0)

    def test_stdin_check_applies_the_same_rules(self):
        result = run(["check", "--stdin"], self.root, stdin=json.dumps(scope_with([row("N1", LEAK_CANARY)])))
        self.assert_findings(result, ["N1\tstate\tunknown"], 4)

    def test_non_array_is_rejected(self):
        for value in ({LEAK_CANARY: 1}, LEAK_CANARY, 7, None, True):
            with self.subTest(value=value):
                self.assert_findings(self.check_status(value), ["-\tcriteria_status\tnot-array"], 4)

    def test_rows_must_be_objects_with_a_well_formed_criterion(self):
        self.assert_findings(self.check_status([LEAK_CANARY]), ["-\tcriteria_status\tnot-object"], 4)
        for bad in (LEAK_CANARY, "N0", "X1", "n1", "N1\n", 7, None):
            with self.subTest(criterion=bad):
                self.assert_findings(self.check_status([row(bad, "applied")]), ["-\tcriterion\tinvalid"], 4)
        missing = row("N1", "applied")
        del missing["criterion"]
        self.assert_findings(self.check_status([missing]), ["-\tcriterion\tinvalid"], 4)

    def test_duplicate_criterion_is_rejected(self):
        result = self.check_status([row("N1", "applied"), row("I1", "applied"), row("N1", "not-doable", reason="r")])
        self.assert_findings(result, ["N1\tcriterion\tduplicate"], 4)
        self.assertEqual(result.stdout.count("N1\tcriterion\tduplicate"), 1)

    def test_unknown_state_is_rejected_without_its_value(self):
        for state in (LEAK_CANARY, "", None, 3, "Applied"):
            with self.subTest(state=state):
                self.assert_findings(self.check_status([row("E3", state)]), ["E3\tstate\tunknown"], 4)
        missing = row("E3", "applied")
        del missing["state"]
        self.assert_findings(self.check_status([missing]), ["E3\tstate\tunknown"], 4)

    def test_reason_required_for_each_reason_required_state(self):
        for state in ("partially-applied", "not-applied", "not-delivered", "not-doable"):
            for reason in (None, "", "   ", 7):
                with self.subTest(state=state, reason=reason):
                    r = row("E3", state) if reason is None else row("E3", state, reason=reason)
                    self.assert_findings(self.check_status([r]), ["E3\treason\trequired"], 4)
            with self.subTest(state=state, reason="given"):
                self.assertEqual(self.check_status([row("E3", state, reason=LEAK_CANARY)]).returncode, 0)

    def test_flagged_needs_output_and_column(self):
        cases = [
            (None, ["E4\tflag.output\trequired", "E4\tflag.column\trequired"]),
            (LEAK_CANARY, ["E4\tflag.output\trequired", "E4\tflag.column\trequired"]),
            ({}, ["E4\tflag.output\trequired", "E4\tflag.column\trequired"]),
            ({"output": "patients " + LEAK_CANARY}, ["E4\tflag.column\trequired"]),
            ({"column": "c", "output": ""}, ["E4\tflag.output\trequired"]),
            ({"output": "patients", "column": 7}, ["E4\tflag.column\trequired"]),
        ]
        for flag, expected in cases:
            with self.subTest(flag=flag):
                r = row("E4", "flagged") if flag is None else row("E4", "flagged", flag=flag)
                result = self.check_status([r])
                self.assert_findings(result, expected, 4)
                self.assertEqual(len(result.stdout.splitlines()), len(expected), result.stdout)
        ok = row("E4", "flagged", flag={"output": "patients", "column": "excl_prior_repair"})
        self.assertEqual(self.check_status([ok]).returncode, 0)

    def test_confirmation_fields_are_required(self):
        for field in ("confirmed_by", "confirmed_at", "confirmed_revision"):
            for value in (None, ""):
                with self.subTest(field=field, value=value):
                    r = row("D1", "delivered")
                    if value is None:
                        del r[field]
                    else:
                        r[field] = value
                    self.assert_findings(self.check_status([r]), ["D1\t%s\trequired" % field], 4)

    def test_confirmation_must_be_for_this_revision_or_carried(self):
        stale = row("D1", "delivered", revision=1)
        self.assert_findings(self.check_status([stale], revision=2), ["D1\tconfirmed_revision\tstale"], 4)
        future = row("D1", "delivered", revision=3)
        self.assert_findings(self.check_status([future], revision=2), ["D1\tconfirmed_revision\tstale"], 4)
        carried = row("D1", "delivered", revision=1, carried_from_revision=1, carried_basis="criteria-unchanged")
        self.assertEqual(self.check_status([carried], revision=2).returncode, 0)
        for over in ({"carried_from_revision": 3}, {"carried_from_revision": LEAK_CANARY}):
            with self.subTest(over=over):
                bad = dict(carried, **over)
                self.assert_findings(self.check_status([bad], revision=2), ["D1\tcarried_from_revision\tinvalid"], 4)
        fresh_with_carry = row("D1", "delivered", revision=2, carried_from_revision=1)
        self.assert_findings(self.check_status([fresh_with_carry], revision=2),
                             ["D1\tcarried_from_revision\tinvalid"], 4)
        for basis in (LEAK_CANARY, "sql-unchanged"):
            with self.subTest(basis=basis):
                bad = dict(carried, carried_basis=basis)
                self.assert_findings(self.check_status([bad], revision=2), ["D1\tcarried_basis\tinvalid"], 4)
        fresh_with_basis = row("D1", "delivered", revision=2, carried_basis="criteria-unchanged")
        self.assert_findings(self.check_status([fresh_with_basis], revision=2), ["D1\tcarried_basis\tinvalid"], 4)

    def test_upstream_when_present_names_its_source_and_id(self):
        for upstream in (LEAK_CANARY, {}, {"source": "recurring-decision"}, {"source": "", "id": "broad-first-pass"}):
            with self.subTest(upstream=upstream):
                r = row("E3", "not-applied", reason="r", upstream=upstream)
                self.assert_findings(self.check_status([r]), ["E3\tupstream\tinvalid"], 4)

    def test_findings_print_only_ids_fields_and_rules(self):
        status = [row("E3", "not-applied", confirmed_by="", flag=LEAK_CANARY),
                  row("E4", "flagged", flag={"output": LEAK_CANARY}), row("D1", LEAK_CANARY)]
        result = self.check_status(status)
        self.assert_findings(result, ["E3\treason\trequired", "E3\tconfirmed_by\trequired",
                                      "E4\tflag.column\trequired", "D1\tstate\tunknown"], 4)

    def test_scope_without_criteria_status_checks_exactly_as_before(self):
        doc = scope_doc("q", "q.sql")
        self.assertEqual(self.check(doc).stdout, "ok\n")
        pending = copy.deepcopy(doc)
        pending["assumptions"][0]["status"] = "pending"
        self.assertEqual(self.check(pending).stdout,
                         "A1: status is pending — every assumption and limitation must be confirmed by the human "
                         "before it is written\n")
        self.assertEqual(self.check(review_doc("q", "q.sql")).stdout, "ok\n")
        no_intent = copy.deepcopy(doc)
        del no_intent["intent"]
        self.assertEqual(self.check(no_intent).stdout, "scope requires intent\nmissing key: intent\n")


class CriteriaCoverage(Base):
    """T028: `sqlreview.sh criteria <slug|draft-path>` against the schema 2 sidecar at the repo root."""

    def write_sidecar(self, value):
        (self.root / "answers.intake.json").write_text(json.dumps(value))

    def publish_scope(self, status, slug="q"):
        self.project.write_json(slug, "scope.json", scope_with(status, slug=slug, sql_path=slug + ".sql"))

    def criteria(self, target="q", tree=None):
        if tree is None:
            return run(["criteria", target], self.root)
        return subprocess.run(["bash", str(REPO / tree / "scripts/sqlreview.sh"), "criteria", target],
                              cwd=self.root, capture_output=True, text=True, timeout=60)

    def without(self, criterion):
        return [r for r in full_status() if r["criterion"] != criterion]

    def test_full_coverage_is_clean(self):
        self.write_sidecar(sidecar())
        self.publish_scope(full_status())
        for tree in TREES:
            with self.subTest(tree=tree):
                result = self.criteria(tree=tree)
                self.assertEqual((result.returncode, result.stdout), (0, ""), result.stderr)

    def test_works_from_a_subdirectory(self):
        self.write_sidecar(sidecar())
        self.publish_scope(self.without("D2"))
        sub = self.root / "sql" / "deep"
        sub.mkdir(parents=True)
        result = run(["criteria", "q"], sub)
        self.assert_findings(result, ["D2\tstate\tmissing"], 10)

    def test_missing_live_criterion(self):
        self.write_sidecar(sidecar())
        self.publish_scope(self.without("D2"))
        result = self.criteria()
        self.assert_findings(result, ["D2\tstate\tmissing"], 10)
        self.assertEqual(result.stdout, "D2\tstate\tmissing\n")
        self.assertEqual(result.stderr, "")

    def test_state_on_withdrawn_criterion(self):
        self.write_sidecar(sidecar())
        self.publish_scope(full_status() + [row("E1", "applied")])
        self.assertEqual(self.criteria().stdout, "E1\tstate\twithdrawn\n")
        self.assertEqual(self.criteria().returncode, 10)

    def test_state_not_allowed_for_kind(self):
        self.write_sidecar(sidecar())
        cases = [("N1", "not-applied", "N1"), ("N1", "flagged", "N1"), ("N1", "researcher-applies", "N1"),
                 ("D1", "applied", "D1"), ("I1", "delivered", "I1"), ("E4", "not-delivered", "E4")]
        for cid, state, expected in cases:
            with self.subTest(criterion=cid, state=state):
                status = self.without(cid) + [row(cid, state, reason="r", flag={"output": "o", "column": "c"})]
                self.publish_scope(status)
                result = self.criteria()
                self.assert_findings(result, ["%s\tstate\tnot-allowed" % expected], 10)
                self.assertEqual(len(result.stdout.splitlines()), 1, result.stdout)

    def test_researcher_applies_needs_the_sidecar_basis(self):
        value = sidecar()
        self.write_sidecar(value)
        self.publish_scope(self.without("E3") + [row("E3", "researcher-applies")])
        self.assertEqual(self.criteria().stdout, "E3\tstate\tresearcher-applies-unbased\n")
        self.assertEqual(self.criteria().returncode, 10)
        for criterion in value["criteria"]:
            if criterion["id"] == "E3":
                criterion["applied_by"] = "rdl"
        self.write_sidecar(value)
        self.assertEqual(self.criteria().stdout, "E3\tstate\tresearcher-applies-unbased\n")
        for criterion in value["criteria"]:
            if criterion["id"] == "E3":
                criterion["applied_by"] = "researcher"
        self.write_sidecar(value)
        result = self.criteria()
        self.assertEqual((result.returncode, result.stdout), (0, ""), result.stderr)

    def test_questions_json_is_not_a_basis(self):
        self.write_sidecar(sidecar())
        self.publish_scope(self.without("E3") + [row("E3", "researcher-applies")])
        (self.root / ".sqlreview/reviews/q/questions.json").write_text(json.dumps(
            {"applied_by": "researcher", "E3": "researcher"}))
        self.assertIn("E3\tstate\tresearcher-applies-unbased", self.criteria().stdout)

    def test_criterion_unknown_to_the_sidecar(self):
        self.write_sidecar(sidecar())
        self.publish_scope(full_status() + [row("E9", "applied")])
        self.assertEqual(self.criteria().stdout, "E9\tcriterion\tunknown\n")

    def test_two_owning_scopes_are_ambiguous(self):
        self.write_sidecar(sidecar())
        self.publish_scope(full_status(), slug="q")
        self.publish_scope(full_status(), slug="r")
        for slug in ("q", "r"):
            with self.subTest(slug=slug):
                result = self.criteria(slug)
                self.assertEqual((result.returncode, result.stdout),
                                 (10, "-\tcriteria_status\towning-scope-ambiguous\n"), result.stderr)

    def test_other_scopes_without_criteria_status_do_not_own(self):
        self.write_sidecar(sidecar())
        self.publish_scope(full_status(), slug="q")
        self.project.write_json("r", "scope.json", scope_doc("r", "r.sql"))
        self.assertEqual(self.criteria("q").returncode, 0)
        self.assertEqual((self.criteria("r").returncode, self.criteria("r").stdout), (0, ""))

    def test_a_draft_stands_in_for_its_own_slug(self):
        self.write_sidecar(sidecar())
        self.publish_scope(self.without("D2"), slug="q")
        draft = self.root / ".sqlreview/reviews/q/scope.draft.json"
        draft.write_text(json.dumps(scope_with(full_status(), revision=2)))
        result = self.criteria(str(draft))
        self.assertEqual((result.returncode, result.stdout), (0, ""), result.stderr)
        relative = self.criteria(".sqlreview/reviews/q/scope.draft.json")
        self.assertEqual((relative.returncode, relative.stdout), (0, ""), relative.stderr)
        draft.write_text(json.dumps(scope_with(self.without("N1"), revision=2)))
        self.assertEqual(self.criteria(str(draft)).stdout, "N1\tstate\tmissing\n")
        # A draft for a new slug still meets the published owner.
        other = self.root / "other draft.json"
        other.write_text(json.dumps(scope_with(full_status(), slug="r", sql_path="r.sql")))
        self.assertEqual(self.criteria(str(other)).stdout, "-\tcriteria_status\towning-scope-ambiguous\n")

    def test_no_sidecar_or_schema_1_has_no_itemised_criteria(self):
        self.publish_scope(full_status())
        result = self.criteria()
        self.assertEqual((result.returncode, result.stdout), (10, "-\tcriteria_status\tno-itemised-criteria\n"))
        self.write_sidecar(sidecar(schema=1))
        result = self.criteria()
        self.assertEqual((result.returncode, result.stdout), (10, "-\tcriteria_status\tno-itemised-criteria\n"))
        empty = sidecar()
        empty["criteria"] = []
        del empty["fingerprints"]
        self.write_sidecar(empty)
        self.assertEqual(self.criteria().stdout, "-\tcriteria_status\tno-itemised-criteria\n")
        self.publish_scope([])
        self.assertEqual(self.criteria().stdout, "-\tcriteria_status\tno-itemised-criteria\n")

    def test_scope_without_criteria_status_is_clean_with_or_without_sidecar(self):
        self.project.write_json("q", "scope.json", scope_doc("q", "q.sql"))
        self.assertEqual((self.criteria().returncode, self.criteria().stdout), (0, ""))
        self.write_sidecar(sidecar())
        self.assertEqual((self.criteria().returncode, self.criteria().stdout), (0, ""))

    def test_findings_are_ordered_and_carry_no_values(self):
        self.write_sidecar(sidecar())
        status = [r for r in full_status() if r["criterion"] not in ("D1", "N1")]
        status += [row("E1", "applied"), row("I1", "researcher-applies")]
        status = [r for r in status if not (r["criterion"] == "I1" and r["state"] == "applied")]
        self.publish_scope(status)
        result = self.criteria()
        self.assertEqual(result.returncode, 10)
        self.assertEqual(result.stdout.splitlines(), [
            "N1\tstate\tmissing", "I1\tstate\tresearcher-applies-unbased", "E1\tstate\twithdrawn",
            "D1\tstate\tmissing"])

    def test_operational_errors_exit_2_without_values(self):
        self.publish_scope(full_status())
        self.write_sidecar({"schemaVersion": 2, "approval_number": LEAK_CANARY, "criteria": LEAK_CANARY})
        result = self.criteria()
        self.assertEqual(result.returncode, 2, result.stdout + result.stderr)
        self.assertEqual(result.stdout, "")
        self.assertNotIn(LEAK_CANARY, result.stderr)
        self.write_sidecar(sidecar())
        for target in ("nope", "../q", str(self.root / "missing.json")):
            with self.subTest(target=target):
                self.assertEqual(self.criteria(target).returncode, 2)
        bad = self.root / "bad draft.json"
        for content in (LEAK_CANARY, json.dumps(scope_with(full_status(), slug="../" + LEAK_CANARY)),
                        json.dumps(dict(scope_with(full_status()), kind="review"))):
            with self.subTest(content=content[:40]):
                bad.write_text(content)
                result = self.criteria(str(bad))
                self.assertEqual(result.returncode, 2, result.stdout + result.stderr)
                self.assertNotIn(LEAK_CANARY, result.stdout + result.stderr)
        self.assertEqual(run(["criteria"], self.root).returncode, 1)
        self.assertEqual(run(["criteria", "q", "r"], self.root).returncode, 1)

    def test_not_initialised_is_operational(self):
        with tempfile.TemporaryDirectory() as tmp:
            Project(tmp, init=False)
            self.assertEqual(run(["criteria", "q"], tmp).returncode, 3)


if __name__ == "__main__":
    unittest.main()
