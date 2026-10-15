"""Issue 348: a revision bump carries unchanged, human-confirmed items forward instead of
invalidating every confirmation.

A carried item keeps the confirmation of the revision where a human answered for it and records
``carried_from_revision``. ``check`` validates the fields statelessly; ``publish`` proves the claim
against the previous published document and its SQL baseline; ``carryforward`` tells the skills
which draft items qualify, from the same jq definition publish uses.
"""
import hashlib
import json
import tempfile
import unittest

try:  # `unittest discover -s tests` puts tests/ on sys.path; `-m unittest tests.x` does not
    from test_sql_review_scripts import SQL_V1, Project, item, review_doc, run, scope_doc
except ModuleNotFoundError:
    from tests.test_sql_review_scripts import SQL_V1, Project, item, review_doc, run, scope_doc

try:
    from test_sql_review_criteria_status import full_status, row, sidecar
except ModuleNotFoundError:
    from tests.test_sql_review_criteria_status import full_status, row, sidecar

# SQL_V1, numbered:
#   1 WITH stays AS (            4 )                          7 GROUP BY month;
#   2   SELECT * FROM adm.stays  5 SELECT month, COUNT(*) AS n
#   3   WHERE discharge_date ... 6 FROM stays
UNRELATED_EDIT = SQL_V1.replace("adm.stays", "adm.stays_v2")          # line 2 only
LINE_SHIFT = "-- monthly admissions\n" + SQL_V1                       # every line moves down one (comment only)
CODE_SHIFT = "SET NOCOUNT ON;\n" + SQL_V1                             # every line moves down one (executable)
GOVERNED_EDIT = SQL_V1.replace("IS NOT NULL", "IS NOT NULL AND ward <> 'X'")  # line 3

WHO = {"confirmed_by": "analyst-login", "confirmed_at": "2026-09-15T00:00:00Z"}


def sha(text):
    return hashlib.sha256(text.encode()).hexdigest()


def items_v1(revision=1):
    """A1 has no location (governs the whole SQL); A2 governs line 3; L1 lines 5-7."""
    return dict(
        assumptions=[item("A1", "Only completed stays", revision, rationale="Open stays lack a discharge date."),
                     item("A2", "Discharge date marks completion", revision, rationale="Ward convention.",
                          location={"lines": [3, 3]})],
        limitations=[item("L1", "Monthly grain only", revision, rationale="Source has no daily data.",
                          location={"lines": [5, 7]})],
    )


def carried(it, revision, confirmed_revision=1, **over):
    """The item as carried into `revision` from `revision - 1`."""
    d = dict(it, confirmed_revision=confirmed_revision, carried_from_revision=revision - 1)
    d.update(over)
    return d


def fresh(it, revision, **over):
    d = dict(it, confirmed_revision=revision, confirmed_at="2026-09-23T00:00:00Z")
    d.pop("carried_from_revision", None)
    d.update(over)
    return d


def shift(it, by):
    lines = it["location"]["lines"]
    return dict(it, location={"lines": [lines[0] + by, lines[1] + by]})


class Check(unittest.TestCase):
    """Stateless field rules (sqlreview-check.jq `items`)."""

    def check(self, doc):
        with tempfile.TemporaryDirectory() as tmp:
            return run(["check", "--stdin"], tmp, stdin=json.dumps(doc))

    def assert_ok(self, doc):
        r = self.check(doc)
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)

    def assert_violation(self, doc, *needles):
        r = self.check(doc)
        self.assertEqual(r.returncode, 4, r.stdout)
        self.assertRegex(r.stdout, r"\bA1\b")
        for n in needles:
            self.assertIn(n, r.stdout)

    def test_accepts_a_carried_item(self):
        self.assert_ok(review_doc(revision=2, assumptions=[item("A1", "x", 1, carried_from_revision=1)]))
        self.assert_ok(review_doc(revision=3, assumptions=[item("A1", "x", 1, carried_from_revision=2)]))
        self.assert_ok(review_doc(revision=3, assumptions=[item("A1", "x", 2, carried_from_revision=2)]))
        self.assert_ok(scope_doc(revision=2, assumptions=[item("A1", "x", 1, carried_from_revision=1)]))

    def test_accepts_a_fresh_item_with_null_carried_from(self):
        self.assert_ok(review_doc(revision=2, assumptions=[item("A1", "x", 2, carried_from_revision=None)]))

    def test_confirmed_revision_above_revision(self):
        self.assert_violation(review_doc(revision=2, assumptions=[item("A1", "x", 3)]), "re-confirm for this revision")
        self.assert_violation(review_doc(revision=2, assumptions=[item("A1", "x", 3, carried_from_revision=1)]),
                              "re-confirm for this revision")

    def test_confirmed_revision_must_be_a_positive_integer(self):
        for bad in (0, "1", 1.5, None):
            with self.subTest(bad=bad):
                self.assert_violation(review_doc(revision=2, assumptions=[item("A1", "x", bad, carried_from_revision=1)]),
                                      "re-confirm for this revision")

    def test_earlier_confirmation_without_carried_from(self):
        self.assert_violation(review_doc(revision=2, assumptions=[item("A1", "x", 1)]), "re-confirm for this revision")

    def test_carried_from_must_be_the_previous_revision(self):
        for bad in (1, 3, "2", 0):
            with self.subTest(bad=bad):
                self.assert_violation(review_doc(revision=3, assumptions=[item("A1", "x", 1, carried_from_revision=bad)]),
                                      "carried_from_revision", "re-confirm for this revision")

    def test_fresh_item_must_not_claim_to_be_carried(self):
        self.assert_violation(review_doc(revision=2, assumptions=[item("A1", "x", 2, carried_from_revision=1)]),
                              "carried_from_revision")


class Base(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.p = Project(self.tmp.name)
        self.sql = self.p.sql("q.sql", SQL_V1)
        self.d = self.p.review_dir("q")
        self.draft = self.d / "draft.json"

    def publish(self, doc, *flags, expected=0):
        self.draft.write_text(json.dumps(doc))
        r = run(["publish", *flags, "q", doc["kind"], str(self.draft)], self.p.root)
        self.assertEqual(r.returncode, expected, r.stdout + r.stderr)
        return r

    def refused(self, doc, *needles, flags=()):
        before = (self.d / f"{doc['kind']}.json").read_bytes()
        r = self.publish(doc, *flags, expected=4)
        for n in needles:
            self.assertIn(n, r.stdout + r.stderr)
        self.assertEqual((self.d / f"{doc['kind']}.json").read_bytes(), before)
        return r

    def carryforward(self, kind, doc, expected=0):
        self.draft.write_text(json.dumps(doc))
        r = run(["carryforward", "q", kind, str(self.draft)], self.p.root)
        self.assertEqual(r.returncode, expected, r.stdout + r.stderr)
        return json.loads(r.stdout) if expected == 0 else r


class ReviewPublish(Base):
    """Review revisions: prior review.json + source.sql (written by snapshot after publish)."""

    def review(self, revision, sql=SQL_V1, **over):
        return review_doc("q", "q.sql", revision=revision, sql_sha256=sha(sql), **over)

    def setUp(self):
        super().setUp()
        self.v1 = items_v1()
        self.publish(self.review(1, **self.v1))
        r = run(["snapshot", "q", "q.sql"], self.p.root)
        self.assertEqual(r.returncode, 0, r.stderr)

    def edit(self, text):
        self.sql.write_text(text)

    def rev2(self, a1, a2, l1, sql):
        return self.review(2, sql=sql, assumptions=[a1, a2], limitations=[l1])

    def test_unchanged_sql_carries_every_item(self):
        a1, a2 = self.v1["assumptions"]
        l1, = self.v1["limitations"]
        self.publish(self.rev2(carried(a1, 2), carried(a2, 2), carried(l1, 2), SQL_V1))
        published = json.loads((self.d / "review.json").read_text())
        self.assertEqual(published["assumptions"][0]["carried_from_revision"], 1)
        self.assertEqual(published["assumptions"][0]["confirmed_revision"], 1)
        # the rendered table shows the revision a human confirmed it at, marked as carried
        self.assertEqual(run(["render", "q", "review"], self.p.root).returncode, 0)
        self.assertIn("| analyst-login | 1 (carried) |", (self.d / "review.md").read_text())

    def test_unrelated_edit_carries_located_items(self):
        self.edit(UNRELATED_EDIT)
        a1, a2 = self.v1["assumptions"]
        l1, = self.v1["limitations"]
        self.publish(self.rev2(fresh(a1, 2), carried(a2, 2), carried(l1, 2), UNRELATED_EDIT))

    def test_pure_line_shift_carries_remapped_items(self):
        self.edit(LINE_SHIFT)
        a1, a2 = self.v1["assumptions"]
        l1, = self.v1["limitations"]
        self.publish(self.rev2(fresh(a1, 2), carried(shift(a2, 1), 2), carried(shift(l1, 1), 2), LINE_SHIFT))

    def test_shift_without_remap_is_refused(self):
        self.edit(LINE_SHIFT)
        a1, a2 = self.v1["assumptions"]
        l1, = self.v1["limitations"]
        self.refused(self.rev2(fresh(a1, 2), carried(a2, 2), carried(shift(l1, 1), 2), LINE_SHIFT), "A2")

    def test_remap_that_changes_the_line_count_is_refused(self):
        a1, a2 = self.v1["assumptions"]
        l1, = self.v1["limitations"]
        wider = dict(l1, location={"lines": [5, 6]})
        self.refused(self.rev2(carried(a1, 2), carried(a2, 2), carried(wider, 2), SQL_V1), "L1")

    def test_governed_lines_changed_is_refused(self):
        self.edit(GOVERNED_EDIT)
        a1, a2 = self.v1["assumptions"]
        l1, = self.v1["limitations"]
        self.refused(self.rev2(fresh(a1, 2), carried(a2, 2), carried(l1, 2), GOVERNED_EDIT), "A2")

    def test_null_location_item_with_changed_sql_is_refused(self):
        self.edit(UNRELATED_EDIT)
        a1, a2 = self.v1["assumptions"]
        l1, = self.v1["limitations"]
        self.refused(self.rev2(carried(a1, 2), carried(a2, 2), carried(l1, 2), UNRELATED_EDIT), "A1")

    def test_changed_text_rationale_or_provenance_is_refused(self):
        a1, a2 = self.v1["assumptions"]
        l1, = self.v1["limitations"]
        for field, value in [("text", "Only finished stays"), ("rationale", "Reworded."),
                             ("confirmed_by", "someone@else"), ("confirmed_at", "2026-09-16T00:00:00Z")]:
            with self.subTest(field=field):
                self.refused(self.rev2(carried(a1, 2), carried(dict(a2, **{field: value}), 2), carried(l1, 2), SQL_V1),
                             "A2")

    def test_item_missing_from_the_prior_revision_is_refused(self):
        a1, a2 = self.v1["assumptions"]
        l1, = self.v1["limitations"]
        self.refused(self.rev2(carried(a1, 2), carried(dict(a2, id="A9"), 2), carried(l1, 2), SQL_V1), "A9")
        # same id, other list
        self.refused(self.review(2, assumptions=[carried(a1, 2), carried(a2, 2), carried(dict(l1, id="A3"), 2)],
                                 limitations=[]), "A3")

    def test_baseline_that_disagrees_with_the_prior_sha_is_not_evidence(self):
        self.edit(UNRELATED_EDIT)
        (self.d / "source.sql").write_text(UNRELATED_EDIT)  # not the bytes revision 1 recorded
        a1, a2 = self.v1["assumptions"]
        l1, = self.v1["limitations"]
        self.refused(self.rev2(fresh(a1, 2), carried(a2, 2), fresh(l1, 2), UNRELATED_EDIT), "A2")

    def test_missing_baseline_refuses_located_items_after_an_edit(self):
        self.edit(UNRELATED_EDIT)
        (self.d / "source.sql").unlink()
        a1, a2 = self.v1["assumptions"]
        l1, = self.v1["limitations"]
        self.refused(self.rev2(fresh(a1, 2), carried(a2, 2), fresh(l1, 2), UNRELATED_EDIT), "A2")

    def test_chained_carry_keeps_the_original_confirmation(self):
        a1, a2 = self.v1["assumptions"]
        l1, = self.v1["limitations"]
        self.publish(self.rev2(carried(a1, 2), carried(a2, 2), fresh(l1, 2), SQL_V1))
        self.assertEqual(run(["snapshot", "q", "q.sql"], self.p.root).returncode, 0)
        l1_2 = fresh(l1, 2)
        # revision 3: A1/A2 still carry revision 1's confirmation, L1 carries revision 2's
        self.publish(self.review(3, assumptions=[carried(a1, 3), carried(a2, 3)],
                                 limitations=[carried(l1_2, 3, confirmed_revision=2)]))
        # claiming revision 2 for A1 (never confirmed there) is refused
        self.refused(self.review(4, assumptions=[carried(a1, 4, confirmed_revision=2), carried(a2, 4)],
                                 limitations=[carried(l1_2, 4, confirmed_revision=2)]), "A1")

    def test_reconfirm_all_refuses_carried_items(self):
        a1, a2 = self.v1["assumptions"]
        l1, = self.v1["limitations"]
        self.refused(self.rev2(carried(a1, 2), carried(a2, 2), carried(l1, 2), SQL_V1), "--reconfirm-all",
                     flags=("--reconfirm-all",))
        self.publish(self.rev2(fresh(a1, 2), fresh(a2, 2), fresh(l1, 2), SQL_V1), "--reconfirm-all")

    def test_no_prior_revision(self):
        (self.d / "review.json").unlink()
        a1, a2 = self.v1["assumptions"]
        l1, = self.v1["limitations"]
        self.publish(self.rev2(carried(a1, 2), carried(a2, 2), carried(l1, 2), SQL_V1), expected=4)
        self.assertFalse((self.d / "review.json").exists())


class ScopePublish(Base):
    """Scope revisions: prior scope.json + scope.source.sql (copied by bootstrap after publish)."""

    def scope(self, revision, sql=SQL_V1, **over):
        return scope_doc("q", "q.sql", revision=revision, sql_sha256=sha(sql) if sql else None, **over)

    def publish_v1(self, sql=SQL_V1):
        self.v1 = items_v1()
        self.publish(self.scope(1, sql=sql, **self.v1))
        if sql is not None:
            (self.d / "scope.source.sql").write_text(sql)

    def test_line_shift_and_unrelated_edit_carry(self):
        self.publish_v1()
        self.sql.write_text(LINE_SHIFT)
        a1, a2 = self.v1["assumptions"]
        l1, = self.v1["limitations"]
        self.publish(self.scope(2, sql=LINE_SHIFT, assumptions=[fresh(a1, 2), carried(shift(a2, 1), 2)],
                                limitations=[carried(shift(l1, 1), 2)]))

    def test_null_location_item_with_changed_sql_carries_its_intent(self):
        # #366: a scope item states intent, not SQL lines (before #366 this was refused).
        self.publish_v1()
        self.sql.write_text(UNRELATED_EDIT)
        a1, a2 = self.v1["assumptions"]
        l1, = self.v1["limitations"]
        self.publish(self.scope(2, sql=UNRELATED_EDIT, assumptions=[carried(a1, 2, carried_basis="intent-unchanged"),
                                                                    carried(a2, 2)],
                                limitations=[carried(l1, 2)]))

    def test_baseline_sha_disagreement_is_refused(self):
        self.publish_v1()
        (self.d / "scope.source.sql").write_text(UNRELATED_EDIT)
        self.sql.write_text(UNRELATED_EDIT)
        a1, a2 = self.v1["assumptions"]
        l1, = self.v1["limitations"]
        self.refused(self.scope(2, sql=UNRELATED_EDIT, assumptions=[fresh(a1, 2), carried(a2, 2)],
                                limitations=[fresh(l1, 2)]), "A2")

    def test_scope_written_before_the_sql_carries_null_location_items(self):
        self.sql.unlink()
        a1 = item("A1", "Only completed stays", 1, rationale="Open stays lack a discharge date.")
        a2 = item("A2", "Calendar months", 1, rationale="Dashboard convention.")
        self.publish(self.scope(1, sql=None, assumptions=[a1, a2]))
        self.publish(self.scope(2, sql=None, assumptions=[carried(a1, 2), fresh(dict(a2, text="Calendar months (UTC)"), 2)]))
        # once the SQL exists, an unchanged null-location scope item still carries its intent (#366;
        # before #366 it was walked, so a scope-first project re-asked every item)
        self.sql = self.p.sql("q.sql", SQL_V1)
        self.publish(self.scope(3, sql=SQL_V1, assumptions=[carried(a1, 3), fresh(dict(a2, text="Calendar months (UTC)"), 3)]))


class CarryForwardHelper(Base):
    """`carryforward SLUG scope|review DRAFT` classifies exactly as publish decides."""

    def setUp(self):
        super().setUp()
        self.v1 = items_v1()
        self.publish(review_doc("q", "q.sql", revision=1, sql_sha256=sha(SQL_V1), **self.v1))
        self.assertEqual(run(["snapshot", "q", "q.sql"], self.p.root).returncode, 0)

    def candidate(self, it, **over):
        d = {k: it[k] for k in ("id", "text", "rationale", "location")}
        d["status"] = "candidate"
        d.update(over)
        return d

    def draft_doc(self, sql, by=1):
        a1, a2 = self.v1["assumptions"]
        l1, = self.v1["limitations"]
        return review_doc("q", "q.sql", revision=2, sql_sha256=sha(sql),
                          assumptions=[self.candidate(a1), self.candidate(shift(a2, by)),
                                       self.candidate(a2, id="A3", text="New assumption")],
                          limitations=[self.candidate(shift(l1, by), rationale="Reworded.")])

    def test_classification_matches_publish(self):
        # CODE_SHIFT, not LINE_SHIFT: a prepended comment is no longer an SQL change (#366).
        self.sql.write_text(CODE_SHIFT)
        draft = self.draft_doc(CODE_SHIFT)
        out = self.carryforward("review", draft)
        self.assertEqual(out["prior_revision"], 1)
        self.assertEqual(out["revision"], 2)
        self.assertFalse(out["sql_unchanged"])
        self.assertEqual([(c["kind"], c["id"], c["basis"]) for c in out["carry"]],
                         [("assumptions", "A2", "lines-unchanged")])
        self.assertEqual(out["carry"][0]["set"], {"status": "confirmed", **WHO, "confirmed_revision": 1,
                                                  "carried_from_revision": 1, "carried_basis": "lines-unchanged"})
        # A1 (unchanged wording, no location, SQL changed) is offered in one bulk question (#366)
        self.assertEqual([(b["id"], b["text"]) for b in out["bulk"]], [("A1", "Only completed stays")])
        self.assertIn("SQL changed", out["bulk"][0]["why"])
        why = {w["id"]: w["why"] for w in out["walk"]}
        self.assertEqual(set(why), {"A3", "L1"})
        self.assertIn("A3", why["A3"])
        self.assertIn("rationale", why["L1"])

        # Applying the helper's verdict publishes; carrying a walked item is refused.
        carry = {(c["kind"], c["id"]): c["set"] for c in out["carry"]}
        doc = json.loads(json.dumps(draft))
        for k in ("assumptions", "limitations"):
            for it in doc[k]:
                it.update(carry.get((k, it["id"]), {"status": "confirmed", "confirmed_by": "engineer-login",
                                                    "confirmed_at": "2026-09-23T00:00:00Z", "confirmed_revision": 2}))
        bad = json.loads(json.dumps(doc))
        bad["assumptions"][0].update(out["carry"][0]["set"])  # A1 was offered in bulk, not carried
        self.draft.write_text(json.dumps(bad))
        r = run(["publish", "q", "review", str(self.draft)], self.p.root)
        self.assertEqual(r.returncode, 4, r.stdout + r.stderr)
        self.assertIn("A1", r.stdout + r.stderr)
        self.publish(doc)

    def test_unchanged_sql_carries_all_matching_items(self):
        out = self.carryforward("review", self.draft_doc(SQL_V1, by=0))
        self.assertTrue(out["sql_unchanged"])
        self.assertEqual({(c["id"], c["basis"]) for c in out["carry"]}, {("A1", "sql-unchanged"), ("A2", "sql-unchanged")})

    def test_no_prior_document_walks_everything(self):
        out = self.carryforward("scope", scope_doc("q", "q.sql", assumptions=[self.candidate(self.v1["assumptions"][0])]))
        self.assertIsNone(out["prior_revision"])
        self.assertEqual(out["carry"], [])
        self.assertEqual([w["id"] for w in out["walk"]], ["A1"])

    def test_errors(self):
        self.assertEqual(run(["carryforward", "q", "review"], self.p.root).returncode, 1)
        self.assertEqual(run(["carryforward", "q", "lifts", str(self.draft)], self.p.root).returncode, 1)
        self.assertEqual(run(["carryforward", "q", "review", str(self.d / "nope.json")], self.p.root).returncode, 2)
        self.assertEqual(run(["carryforward", "../x", "review", str(self.draft)], self.p.root).returncode, 2)


class CriteriaCarry(Base):
    """Spec 017 (R7): `criteria_status` rows carry by `criterion` with basis criteria-unchanged.

    A row is unchanged when state, reason and flag equal the prior revision's row for the same
    criterion; anything else is walked. Publish proves a carried claim from the same definition.
    """

    BASIS = "criteria-unchanged"

    def setUp(self):
        super().setUp()
        (self.p.root / "answers.intake.json").write_text(json.dumps(sidecar()))
        self.v1 = full_status(1)
        self.publish_scope(1, self.v1)

    def scope(self, revision, status):
        return scope_doc("q", "q.sql", revision=revision, sql_sha256=sha(SQL_V1), assumptions=[], criteria_status=status)

    def publish_scope(self, revision, status, expected=0):
        doc = self.scope(revision, status)
        self.draft.write_text(json.dumps(doc))
        r = run(["publish", "q", "scope", str(self.draft)], self.p.root)
        self.assertEqual(r.returncode, expected, r.stdout + r.stderr)
        if expected == 0:
            (self.d / "scope.source.sql").write_text(SQL_V1)
        return r

    def prior(self, criterion):
        return next(r for r in self.v1 if r["criterion"] == criterion)

    def carried_row(self, criterion, revision=2, **over):
        d = dict(self.prior(criterion), carried_from_revision=revision - 1, carried_basis=self.BASIS)
        d.update(over)
        return d

    def fresh_row(self, criterion, revision=2, **over):
        d = {k: v for k, v in self.prior(criterion).items() if k not in ("carried_from_revision", "carried_basis")}
        d.update(confirmed_revision=revision, confirmed_at="2026-10-14T00:00:00Z")
        d.update(over)
        return d

    def rev2(self, **replace):
        """Revision 2 of every criterion carried, with `replace` mapping criterion -> row."""
        return [replace.get(r["criterion"], self.carried_row(r["criterion"])) for r in self.v1]

    def refused_claim(self, status, *needles):
        r = self.publish_scope(2, status, expected=4)
        for n in needles:
            self.assertIn(n, r.stdout + r.stderr)
        self.assertEqual(json.loads((self.d / "scope.json").read_text())["revision"], 1)
        return r

    def test_unchanged_rows_carry_with_their_original_confirmation(self):
        out = self.carryforward("scope", self.scope(2, [{k: v for k, v in r.items() if not k.startswith("confirmed")}
                                                          for r in self.v1]))
        self.assertEqual(out["prior_revision"], 1)
        self.assertEqual({(c["kind"], c["id"], c["basis"]) for c in out["carry"]},
                         {("criteria_status", r["criterion"], self.BASIS) for r in self.v1})
        self.assertEqual(out["walk"], [])
        by = {c["id"]: c["set"] for c in out["carry"]}
        self.assertEqual(by["D1"], {"confirmed_by": "eng-login", "confirmed_at": "2026-10-13T02:00:00Z",
                                    "confirmed_revision": 1, "carried_from_revision": 1, "carried_basis": self.BASIS})
        # upstream rides along when the prior row has it
        self.assertEqual(by["E3"]["upstream"], {"source": "recurring-decision", "id": "broad-first-pass"})
        self.assertNotIn("status", by["D1"])
        # Applying the printed set fields publishes, and the original confirmation survives.
        self.publish_scope(2, [dict(r, **by[r["criterion"]]) for r in self.v1])
        published = json.loads((self.d / "scope.json").read_text())["criteria_status"]
        self.assertEqual([r["carried_from_revision"] for r in published], [1] * len(self.v1))
        self.assertEqual({r["confirmed_revision"] for r in published}, {1})
        self.assertEqual({r["carried_basis"] for r in published}, {self.BASIS})

    def test_changed_state_reason_or_flag_is_walked_and_needs_fresh_confirmation(self):
        changes = {
            "I1": {"state": "not-applied", "reason": "Narrowed by the analyst"},                    # state
            "E3": {"reason": "Different reason"},                                                   # reason
            "E4": {"flag": {"output": "patients", "column": "excl_other"}},                         # flag
            "D2": {"reason": None},                                                                 # reason removed
        }
        draft = [{k: v for k, v in dict(r, **changes.get(r["criterion"], {})).items()
                  if v is not None and not k.startswith("confirmed")} for r in self.v1]
        out = self.carryforward("scope", self.scope(2, draft))
        walked = {w["id"]: w for w in out["walk"]}
        self.assertEqual(set(walked), set(changes))
        for w in walked.values():
            self.assertEqual(w["kind"], "criteria_status")
            self.assertIn("differs from revision 1", w["why"])
        self.assertIn("state", walked["I1"]["why"])
        self.assertIn("reason", walked["E3"]["why"])
        self.assertIn("flag", walked["E4"]["why"])
        self.assertEqual({c["id"] for c in out["carry"]}, {"N1", "D1"})
        self.assertEqual(out["bulk"], [])
        # Fresh confirmation at the new revision publishes; claiming a carry for a changed row does not.
        fresh = [self.fresh_row(r["criterion"], **changes[r["criterion"]]) if r["criterion"] in changes
                 else self.carried_row(r["criterion"]) for r in self.v1]
        fresh = [{k: v for k, v in r.items() if v is not None} for r in fresh]
        for r in fresh:
            if r["criterion"] == "D2":
                r.update(state="delivered")
                r.pop("reason", None)
        self.publish_scope(2, fresh)

    def add_sidecar_criterion(self, id_, kind):
        """An intake re-run adds a criterion after revision 1 was published."""
        path = self.p.root / "answers.intake.json"
        value = json.loads(path.read_text())
        stamp = {k: value["criteria"][0][k] for k in ("confirmed_by", "confirmed_role", "confirmed_at")}
        value["criteria"].append({"id": id_, "kind": kind, "text": "Added later", **stamp})
        path.write_text(json.dumps(value))

    def test_a_new_criterion_is_walked(self):
        self.add_sidecar_criterion("D3", "data_element")
        draft = [{k: v for k, v in r.items() if not k.startswith("confirmed")} for r in self.v1[:-1]]
        draft.append({"criterion": "D3", "state": "delivered"})
        out = self.carryforward("scope", self.scope(2, draft))
        self.assertEqual([(w["kind"], w["id"]) for w in out["walk"]], [("criteria_status", "D3")])
        self.assertIn("D3", out["walk"][0]["why"])
        self.assertEqual({c["id"] for c in out["carry"]}, {r["criterion"] for r in self.v1[:-1]})
        # D3 is new, so it needs a fresh confirmation at revision 2; the other rows carry
        self.publish_scope(2, [self.carried_row(r["criterion"]) for r in self.v1]
                           + [row("D3", "delivered", 2, confirmed_at="2026-10-14T00:00:00Z")])

    def test_absent_reason_and_flag_equal_absent(self):
        self.assertNotIn("reason", self.prior("D1"))
        self.assertNotIn("flag", self.prior("D1"))
        out = self.carryforward("scope", self.scope(2, [{"criterion": "D1", "state": "delivered"}]))
        self.assertEqual([(c["id"], c["basis"]) for c in out["carry"]], [("D1", self.BASIS)])
        # a reason or flag appearing where the prior had none is a change
        out = self.carryforward("scope", self.scope(2, [{"criterion": "D1", "state": "delivered", "reason": "Note"}]))
        self.assertEqual(out["carry"], [])
        self.assertIn("reason", out["walk"][0]["why"])

    def test_no_prior_scope_walks_every_criterion(self):
        (self.d / "scope.json").unlink()
        out = self.carryforward("scope", self.scope(1, [{"criterion": "N1", "state": "applied"}]))
        self.assertIsNone(out["prior_revision"])
        self.assertEqual(out["carry"], [])
        self.assertEqual([(w["kind"], w["id"]) for w in out["walk"]], [("criteria_status", "N1")])

    def test_publish_carries_unchanged_rows_and_chains_the_original_confirmation(self):
        self.publish_scope(2, self.rev2(I1=self.fresh_row("I1")))
        published = {r["criterion"]: r for r in json.loads((self.d / "scope.json").read_text())["criteria_status"]}
        self.assertEqual(published["N1"]["carried_basis"], self.BASIS)
        self.assertNotIn("carried_from_revision", published["I1"])
        # revision 3 carries N1 from revision 2, which itself carried revision 1's confirmation
        rev3 = [dict(r, carried_from_revision=2, carried_basis=self.BASIS) for r in published.values()]
        self.publish_scope(3, rev3)
        # claiming a confirmation at revision 2 for N1 (never confirmed there) is refused
        r = self.publish_scope(4, [dict(r, carried_from_revision=3, confirmed_revision=2) if r["criterion"] == "N1"
                                   else dict(r, carried_from_revision=3) for r in rev3], expected=4)
        self.assertIn("N1", r.stdout)

    def test_publish_refuses_a_false_carry_claim_where_the_row_changed(self):
        for field, value in (("state", "not-applied"), ("reason", "Changed reason"),
                             ("flag", {"output": "patients", "column": "excl_other"})):
            with self.subTest(field=field):
                criterion = {"state": "I1", "reason": "E3", "flag": "E4"}[field]
                over = {field: value}
                if field == "state":
                    over["reason"] = "Narrowed"
                r = self.refused_claim(self.rev2(**{criterion: self.carried_row(criterion, **over)}), criterion,
                                       "cannot carry the confirmation forward", f"{field} differs from revision 1",
                                       "re-confirm for this revision")
                self.assertNotIn("Changed reason", r.stdout + r.stderr)

    def test_publish_refuses_a_carry_claim_for_a_criterion_with_no_prior_row(self):
        self.add_sidecar_criterion("D3", "data_element")
        status = self.rev2() + [dict(row("D3", "delivered", 1), carried_from_revision=1, carried_basis=self.BASIS)]
        self.refused_claim(status, "D3", "cannot carry the confirmation forward", "no row for D3")

    def test_publish_refuses_carried_confirmation_fields_that_differ_from_the_prior_row(self):
        # (confirmed_revision cannot differ at revision 2 and still pass `check`; the chain test covers it)
        for field, value in (("confirmed_by", "someone-else"), ("confirmed_at", "2026-10-20T00:00:00Z")):
            with self.subTest(field=field):
                self.refused_claim(self.rev2(D1=self.carried_row("D1", **{field: value})), "D1",
                                   "must copy confirmed_by, confirmed_at and confirmed_revision")

    def test_publish_refuses_a_carried_row_whose_upstream_differs(self):
        self.refused_claim(self.rev2(E3=self.carried_row("E3", upstream={"source": "recurring-decision", "id": "other"})),
                           "E3", "upstream")
        dropped = {k: v for k, v in self.carried_row("E3").items() if k != "upstream"}
        self.refused_claim(self.rev2(E3=dropped), "E3", "upstream")
        self.refused_claim(self.rev2(D1=self.carried_row("D1", upstream={"source": "recurring-decision", "id": "x"})),
                           "D1", "upstream")

    def test_publish_refuses_a_basis_the_evidence_does_not_support(self):
        # "intent-unchanged" is not a criteria basis; check rejects it before publish proves anything
        r = self.publish_scope(2, self.rev2(D1=self.carried_row("D1", carried_basis="intent-unchanged")), expected=4)
        self.assertIn("D1", r.stdout)
        self.assertIn("carried_basis", r.stdout)

    def test_publish_refuses_a_carry_claim_without_a_prior_scope(self):
        (self.d / "scope.json").unlink()
        self.draft.write_text(json.dumps(self.scope(1, [dict(row("N1", "applied", 1), carried_from_revision=0)])))
        r = run(["publish", "q", "scope", str(self.draft)], self.p.root)
        self.assertEqual(r.returncode, 4, r.stdout)
        self.assertFalse((self.d / "scope.json").exists())

    def test_reconfirm_all_refuses_carried_criteria_rows(self):
        self.draft.write_text(json.dumps(self.scope(2, self.rev2())))
        r = run(["publish", "--reconfirm-all", "q", "scope", str(self.draft)], self.p.root)
        self.assertEqual(r.returncode, 4, r.stdout + r.stderr)
        self.assertIn("--reconfirm-all", r.stdout)


class Guard(unittest.TestCase):
    """A direct Write cannot prove a carried claim, so the guard routes it through publish."""

    def test_direct_write_of_carried_items_is_denied(self):
        import subprocess
        try:
            from test_sql_review_hooks import GUARD, env_for
        except ModuleNotFoundError:
            from tests.test_sql_review_hooks import GUARD, env_for
        with tempfile.TemporaryDirectory() as tmp:
            p = Project(tmp)
            doc = review_doc("q", "q.sql", revision=2, assumptions=[item("A1", "x", 1, carried_from_revision=1)])
            ev = {"tool_name": "Write", "cwd": str(p.root),
                  "tool_input": {"file_path": str(p.root / ".sqlreview/reviews/q/review.json"), "content": json.dumps(doc)}}
            r = subprocess.run(["bash", str(GUARD)], input=json.dumps(ev), capture_output=True, text=True,
                               env=env_for(), timeout=60)
            d = json.loads(r.stdout)["hookSpecificOutput"]
            self.assertEqual(d["permissionDecision"], "deny")
            self.assertIn("publish", d["permissionDecisionReason"])


if __name__ == "__main__":
    unittest.main()
