"""#436 offline facility routing contracts and real scope/helper round trips.

These test authored instructions in all target trees, not live agent behaviour or
warehouse facts. Runtime cases exercise shipped Bash/jq helpers in temp repos.
"""

import copy
import hashlib
import json
import tempfile
import unittest
from pathlib import Path

from test_data_request_recurring_decisions import run
from test_sql_review_scripts import item, review_doc, scope_doc

REPO = Path(__file__).resolve().parent.parent
TREES = {"canonical": REPO / "skills",
         "claude": REPO / "plugins/data-request/skills",
         "codex": REPO / "dist/codex/plugins/data-request/skills"}
DECISION = "tuh-facility"
SOURCE = "https://github.com/nq-rdl/agent-extensions/issues/436"


def path(tree, leaf, relative="SKILL.md"):
    return TREES[tree] / (f"data-request-{leaf}" if tree == "canonical" else leaf) / relative


def text(tree, leaf, relative="SKILL.md"):
    return " ".join(path(tree, leaf, relative).read_text().split())


def entry(tree):
    entries = json.loads(path(tree, "setup", "assets/recurring-decisions.json").read_text())["decisions"]
    found = [d for d in entries if d["id"] == DECISION]
    if len(found) != 1:
        raise AssertionError("one shared tuh-facility decision is required")
    return found[0]


class HouseDefaultContracts(unittest.TestCase):
    def test_house_default_names_tuh_and_original_confirmation(self):
        for tree in TREES:
            with self.subTest(tree=tree):
                rule = text(tree, "guardrails")
                for token in ("## House defaults", "Townsville University Hospital", "`00200`",
                              "JoshKgh", "2026-09-29", SOURCE, "references/sources.rst"):
                    self.assertIn(token, rule)

    def test_each_system_uses_its_own_verified_facility_representation(self):
        for tree in TREES:
            with self.subTest(tree=tree):
                rule = text(tree, "guardrails", "references/sources.rst")
                for token in ("HBCIS", "ePADT", "FacilityCode", "'00200'", "leading zeros",
                              "ieMR institution", "facility crosswalk", "SiteCode",
                              "not interchangeable", "Do not invent", "revision",
                              "uniqueness", "unpinned", "FacilitySpec"):
                    self.assertIn(token, rule)
                self.assertNotIn("INSTITUTION_CD = 00200", rule)

    def test_map_bootstrap_draft_apply_once_without_a_facility_question(self):
        for tree in TREES:
            for leaf in ("map", "bootstrap", "draft"):
                with self.subTest(tree=tree, leaf=leaf):
                    rule = text(tree, leaf)
                    for token in ("House defaults", "tuh-facility", "upstream", "without asking",
                                  "one standard assumption", "recurring-decisions.rst"):
                        self.assertIn(token, rule)

    def test_alternative_hhs_network_scope_gets_question_instead_of_default(self):
        for tree in TREES:
            for leaf in ("triage", "bootstrap"):
                with self.subTest(tree=tree, leaf=leaf):
                    rule = text(tree, leaf)
                    for token in ("another facility", "whole HHS", "network-wide", "Analyst question:",
                                  "instead of the TUH default", "already answered"):
                        self.assertIn(token, rule)

    def test_exception_requires_a_change_to_the_cohort_facility_set(self):
        # Authored routing contract, not an executable natural-language classifier.
        for tree in TREES:
            for leaf in ("guardrails", "triage", "map", "bootstrap", "draft"):
                with self.subTest(tree=tree, leaf=leaf):
                    self.assertIn("explicitly changes the cohort's facility set", text(tree, leaf))
            for leaf, relative in (("guardrails", "references/sources.rst"),
                                   ("setup", "references/recurring-decisions.rst")):
                with self.subTest(tree=tree, relative=relative):
                    rule = text(tree, leaf, relative)
                    for token in ("cohort's facility set", "admission-from", "discharge-to",
                                  "excludes transfers from another hospital", "keep the TUH default"):
                        self.assertIn(token, rule)

    def test_recurring_rule_is_narrow_and_keeps_formal_gates(self):
        for tree in TREES:
            with self.subTest(tree=tree):
                rule = text(tree, "setup", "references/recurring-decisions.rst")
                for token in ("Recorded house default", "tuh-facility", "without asking",
                              "confirmed_by", "confirmed_at", "confirmed_revision", "decided",
                              "date-only", "not a new engineer confirmation", "exact listed wording",
                              "changed wording", "Human confirmation is still", "upstream",
                              "Never invent", "one item", "no carried_from_revision"):
                    self.assertIn(token, rule)

    def test_shared_entry_preserves_code_and_independent_origin(self):
        for tree in TREES:
            with self.subTest(tree=tree):
                d = entry(tree)
                self.assertEqual(d["kind"], "assumption")
                self.assertEqual(d["status"], "open")
                self.assertEqual(d["evidence"], [SOURCE])
                h = d["house_default"]
                self.assertEqual(h["facility_code"], "00200")
                self.assertEqual(h["confirmed_by"], "JoshKgh")
                self.assertEqual(h["confirmed_at"], "2026-09-29")
                self.assertEqual(h["decided"], {"by": "JoshKgh", "role": "Data Engineer",
                                              "at": "2026-09-29", "source": SOURCE})
                self.assertIn("00200", d["proposal"]["text"])
                self.assertIn("house default", d["proposal"]["rationale"])


    def test_canonical_rationale_carries_origin_into_the_generated_sql_header(self):
        # record_assumption renders text+rationale, not separate decided metadata.
        # A canonical rationale must therefore carry the real decision evidence
        # without requiring a second record or mismatching scope wording.
        for tree in TREES:
            with self.subTest(tree=tree):
                d = entry(tree)
                rationale = d["proposal"]["rationale"]
                for value in ("JoshKgh", "2026-09-29", SOURCE):
                    self.assertIn(value, rationale)


class FacilityHelperRoundTrips(unittest.TestCase):
    def helper(self, tree, root, script, *args, expected=0):
        result = run(path(tree, "setup", f"scripts/{script}.sh"), list(args), root)
        self.assertEqual(result.returncode, expected, result.stdout + result.stderr)
        return result

    def test_match_returns_original_house_confirmation_and_no_numeric_false_hit(self):
        for tree in TREES:
            with self.subTest(tree=tree), tempfile.TemporaryDirectory() as tmp:
                d = entry(tree)
                draft = Path(tmp) / "scope.draft.json"
                draft.write_text(json.dumps({"assumptions": [
                    {"id": "A1", **d["proposal"], "upstream": {"decision": DECISION}},
                    {"id": "A2", "text": "FacilityCode = '200'", "rationale": "not the default"},
                    {"id": "A3", "text": "FacilityCode = '002001'", "rationale": "not the default"}
                ], "limitations": []}))
                out = json.loads(self.helper(tree, tmp, "recurring-decisions", "match", str(draft)).stdout)
                hits = [m for m in out["matches"] if m["decision"] == DECISION]
                self.assertEqual([m["id"] for m in hits], ["A1"])
                self.assertTrue(hits[0]["marked"])
                self.assertEqual(hits[0]["house_default"], d["house_default"])

    def test_malformed_house_confirmation_is_not_offered_as_a_default(self):
        mutations = {
            "numeric code": {"facility_code": 200},
            "empty confirmer": {"confirmed_by": ""},
            "email confirmer": {"confirmed_by": "engineer@example.com"},
            "missing date": {"confirmed_at": None},
            "missing origin": {"decided": None},
        }
        for tree in TREES:
            for name, fields in mutations.items():
                with self.subTest(tree=tree, case=name), tempfile.TemporaryDirectory() as tmp:
                    doc = json.loads(path(tree, "setup", "assets/recurring-decisions.json").read_text())
                    d = next(d for d in doc["decisions"] if d["id"] == DECISION)
                    d["house_default"].update(fields)
                    custom = Path(tmp) / "list.json"
                    custom.write_text(json.dumps(doc))
                    result = run(path(tree, "setup", "scripts/recurring-decisions.sh"), ["list"], tmp,
                                 {"SQLREVIEW_RECURRING_DECISIONS": str(custom)})
                    self.assertEqual(result.returncode, 4, result.stdout + result.stderr)
                    self.assertIn("house_default", result.stderr)

    def test_carried_house_provenance_mutations_cannot_publish(self):
        mutations = {
            "drop upstream": lambda a: a.pop("upstream"),
            "null upstream": lambda a: a.update(upstream=None),
            "replace source": lambda a: a["upstream"].update(source="other"),
            "drop source": lambda a: a["upstream"].pop("source"),
            "replace decision": lambda a: a["upstream"].update(decision="other"),
            "drop decided": lambda a: a.pop("decided"),
            "null decided": lambda a: a.update(decided=None),
            **{f"replace decided {field}":
               (lambda a, field=field: a["decided"].update({field: "other"}))
               for field in ("by", "role", "at", "source")},
        }
        for tree in TREES:
            for kind in ("scope", "review"):
                with self.subTest(tree=tree, kind=kind), tempfile.TemporaryDirectory() as tmp:
                    root = Path(tmp)
                    sql = "SELECT 1;\n"
                    (root / "cohort.sql").write_text(sql)
                    self.helper(tree, tmp, "sqlreview", "init")
                    slug = "cohort"
                    store = root / ".sqlreview/reviews" / slug
                    store.mkdir(parents=True, exist_ok=True)
                    d = entry(tree)
                    h = d["house_default"]
                    a = item("A1", d["proposal"]["text"], rationale=d["proposal"]["rationale"],
                             confirmed_by=h["confirmed_by"], confirmed_at=h["confirmed_at"],
                             decided=h["decided"], upstream={"decision": DECISION, "source": "house-default"})
                    factory = scope_doc if kind == "scope" else review_doc
                    doc = factory(slug, "cohort.sql", schemaVersion=2, assumptions=[a], limitations=[],
                                  sql_sha256=hashlib.sha256(sql.encode()).hexdigest(),
                                  logic=[{"step": 1, "title": "Select", "lines": [1, 1], "description": "Fixture"}])
                    draft = store / f"{kind}.draft.json"
                    draft.write_text(json.dumps(doc))
                    self.helper(tree, tmp, "sqlreview", "publish", slug, kind, str(draft))
                    # Both the first carry and a later carry must protect the prior
                    # marker/origin, even if the proposed item drops its source.
                    for revision in (2, 3):
                        doc["revision"] = revision
                        draft.write_text(json.dumps(doc))
                        carry = json.loads(self.helper(tree, tmp, "sqlreview", "carryforward",
                                                      slug, kind, str(draft)).stdout)
                        self.assertEqual(len(carry["carry"]), 1)
                        a.update(carry["carry"][0]["set"])
                        for name, mutate in mutations.items():
                            with self.subTest(revision=revision, mutation=name):
                                changed = copy.deepcopy(doc)
                                mutate(changed["assumptions"][0])
                                draft.write_text(json.dumps(changed))
                                before = (store / f"{kind}.json").read_bytes()
                                result = self.helper(tree, tmp, "sqlreview", "publish", slug, kind,
                                                     str(draft), expected=4)
                                self.assertIn("provenance", result.stdout + result.stderr)
                                self.assertEqual((store / f"{kind}.json").read_bytes(), before)
                        draft.write_text(json.dumps(doc))
                        self.helper(tree, tmp, "sqlreview", "publish", slug, kind, str(draft))
                        self.assertEqual(json.loads((store / f"{kind}.json").read_text())["assumptions"], [a])

    def test_default_publish_render_and_carry_keep_the_original_record(self):
        for tree in TREES:
            with self.subTest(tree=tree), tempfile.TemporaryDirectory() as tmp:
                root = Path(tmp)
                d = entry(tree)
                h = d["house_default"]
                self.helper(tree, tmp, "sqlreview", "init")
                slug = self.helper(tree, tmp, "sqlreview", "slug", "cohort.sql").stdout.strip()
                store = root / ".sqlreview/reviews" / slug
                store.mkdir(parents=True, exist_ok=True)
                a = {"id": "A1", **d["proposal"], "location": None, "status": "confirmed",
                     "confirmed_by": h["confirmed_by"], "confirmed_at": h["confirmed_at"],
                     "confirmed_revision": 1, "decided": h["decided"],
                     "upstream": {"decision": DECISION, "source": "house-default"}}
                doc = {"schemaVersion": 2, "kind": "scope", "slug": slug, "sql_path": "cohort.sql",
                       "title": "Cohort", "revision": 1, "recorded_by": "current-engineer",
                       "recorded_at": "2026-09-30T12:00:00Z", "git_commit": None,
                       "sql_sha256": None, "intent": "Requested admissions.", "inputs": [],
                       "outputs": [], "assumptions": [a], "limitations": [], "open_questions": []}
                draft = store / "scope.draft.json"
                draft.write_text(json.dumps(doc))
                self.helper(tree, tmp, "sqlreview", "publish", slug, "scope", str(draft))
                self.helper(tree, tmp, "sqlreview", "render", slug, "scope")
                rendered = (store / "scope.md").read_text()
                self.assertIn("00200", rendered)
                self.assertIn("JoshKgh", rendered)
                doc["revision"] = 2
                draft.write_text(json.dumps(doc))
                carry = json.loads(self.helper(tree, tmp, "sqlreview", "carryforward",
                                              slug, "scope", str(draft)).stdout)
                self.assertEqual(carry["walk"], [])
                self.assertEqual(len(carry["carry"]), 1)
                a.update(carry["carry"][0]["set"])
                draft.write_text(json.dumps(doc))
                self.helper(tree, tmp, "sqlreview", "publish", slug, "scope", str(draft))
                published = json.loads((store / "scope.json").read_text())
                self.assertEqual(published["assumptions"], [a])
                self.assertEqual(a["confirmed_at"], "2026-09-29")
                self.assertEqual(a["decided"], h["decided"])
                self.assertEqual(a["upstream"], {"decision": DECISION, "source": "house-default"})
                marked = json.loads(self.helper(tree, tmp, "recurring-decisions", "marked",
                                               str(store / "scope.json")).stdout)
                self.assertEqual(marked["decisions"][0]["decision"], DECISION)
                # A marker/default origin does not waive ordinary human confirmation.
                a.update(status="candidate", confirmed_by=None, confirmed_at=None, confirmed_revision=None)
                doc["revision"] = 3
                draft.write_text(json.dumps(doc))
                denied = self.helper(tree, tmp, "sqlreview", "publish", slug, "scope", str(draft), expected=4)
                self.assertIn("confirmed", denied.stdout + denied.stderr)


if __name__ == "__main__":
    unittest.main()
