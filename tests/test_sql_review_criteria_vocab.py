"""Tests for the shared research-criteria jq vocabulary (spec 017, unit D).

skills/data-request-setup/scripts/sqlreview-criteria.jq is a def-only jq module included by the
intake, check, coverage, scope-renderer and release scripts via `jq -L <scripts dir>` and
`include "sqlreview-criteria";` (the same way sqlreview-slug.jq is). Each test drives real jq.
"""

import json
import re
import subprocess
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
SCRIPTS = REPO / "skills" / "data-request-setup" / "scripts"
MODULE = SCRIPTS / "sqlreview-criteria.jq"

KINDS = ["entry_event", "inclusion", "exclusion", "data_element"]


def jq(program, stdin="null"):
    """Run `program` with the vocabulary included; return the parsed single JSON output."""
    r = subprocess.run(
        ["jq", "-c", "-L", str(SCRIPTS), 'include "sqlreview-criteria"; ' + program],
        input=stdin, capture_output=True, text=True, timeout=30,
    )
    if r.returncode != 0:
        raise AssertionError("jq failed (%d): %s" % (r.returncode, r.stderr))
    lines = r.stdout.strip().splitlines()
    if len(lines) != 1:
        raise AssertionError("expected one output, got %r" % r.stdout)
    return json.loads(lines[0])


def crit(id_, kind, **over):
    d = {"id": id_, "kind": kind, "text": "t"}
    d.update(over)
    return d


class ModuleShape(unittest.TestCase):
    def test_module_exists_and_documents_the_include_line(self):
        self.assertTrue(MODULE.is_file())
        text = MODULE.read_text()
        self.assertIn('include "sqlreview-criteria";', text)
        self.assertIn("-L", text)

    def test_module_is_def_only(self):
        # A module with a top-level program cannot be included; non-comment lines must all be
        # part of `def ...;` forms, so the last non-comment, non-blank line ends a def.
        body = [ln for ln in MODULE.read_text().splitlines() if ln.strip() and not ln.lstrip().startswith("#")]
        self.assertTrue(body)
        self.assertTrue(all(ln.startswith("def ") or ln.startswith(" ") for ln in body), body)
        self.assertTrue(body[-1].rstrip().endswith(";"))


class Kinds(unittest.TestCase):
    def test_crit_kinds_in_canonical_order(self):
        self.assertEqual(jq("crit_kinds"), KINDS)

    def test_crit_prefix_maps_each_kind(self):
        got = {k: jq('"%s" | crit_prefix' % k) for k in KINDS}
        self.assertEqual(got, {"entry_event": "N", "inclusion": "I", "exclusion": "E", "data_element": "D"})

    def test_crit_prefix_unknown_kind_is_null(self):
        self.assertIsNone(jq('"bogus" | crit_prefix'))


class IdOk(unittest.TestCase):
    def ok(self, id_, kind):
        return jq("crit_id_ok", json.dumps({"id": id_, "kind": kind}))

    def test_valid_id_for_each_kind(self):
        for id_, kind in [("N1", "entry_event"), ("I2", "inclusion"), ("E10", "exclusion"), ("D999", "data_element")]:
            with self.subTest(id=id_):
                self.assertIs(self.ok(id_, kind), True)

    def test_prefix_kind_mismatch_is_rejected(self):
        for id_, kind in [("I1", "exclusion"), ("E1", "inclusion"), ("D1", "entry_event"), ("N1", "data_element")]:
            with self.subTest(id=id_, kind=kind):
                self.assertIs(self.ok(id_, kind), False)

    def test_malformed_ids_are_rejected(self):
        for bad in ["", "I", "I0", "I01", "i1", "X1", "I-1", "I1 ", " I1", "I1\n", "II1", "I1a", "1", "I1.5"]:
            with self.subTest(id=bad):
                self.assertIs(self.ok(bad, "inclusion"), False)

    def test_unknown_kind_is_rejected(self):
        self.assertIs(self.ok("I1", "bogus"), False)

    def test_non_string_or_missing_fields_are_rejected_not_errors(self):
        self.assertIs(jq("crit_id_ok", '{"id": 1, "kind": "inclusion"}'), False)
        self.assertIs(jq("crit_id_ok", '{"id": null, "kind": "inclusion"}'), False)
        self.assertIs(jq("crit_id_ok", '{"kind": "inclusion"}'), False)
        self.assertIs(jq("crit_id_ok", '{"id": "I1"}'), False)
        self.assertIs(jq("crit_id_ok", '{"id": "I1", "kind": 3}'), False)


class States(unittest.TestCase):
    def test_states_per_kind(self):
        both = ["applied", "partially-applied", "flagged", "not-applied", "researcher-applies", "not-doable"]
        self.assertEqual(jq('crit_states("entry_event")'), ["applied", "not-doable"])
        self.assertEqual(jq('crit_states("inclusion")'), both)
        self.assertEqual(jq('crit_states("exclusion")'), both)
        self.assertEqual(jq('crit_states("data_element")'), ["delivered", "not-delivered", "not-doable"])

    def test_unknown_kind_has_no_states(self):
        self.assertEqual(jq('crit_states("bogus")'), [])

    def test_all_states_is_the_duplicate_free_union(self):
        allstates = jq("crit_all_states")
        self.assertEqual(len(allstates), len(set(allstates)))
        expected = set()
        for k in KINDS:
            expected |= set(jq('crit_states("%s")' % k))
        self.assertEqual(set(allstates), expected)
        self.assertEqual(len(allstates), 8)

    def test_reason_required_set(self):
        self.assertEqual(
            jq("crit_reason_required"), ["partially-applied", "not-applied", "not-delivered", "not-doable"]
        )

    def test_reason_required_states_are_all_known_states(self):
        self.assertTrue(set(jq("crit_reason_required")) <= set(jq("crit_all_states")))


class Ordering(unittest.TestCase):
    def test_sort_by_kind_then_numeric_id(self):
        shuffled = [
            crit("D1", "data_element"), crit("E10", "exclusion"), crit("I2", "inclusion"), crit("N1", "entry_event"),
            crit("E2", "exclusion"), crit("I10", "inclusion"), crit("D12", "data_element"), crit("I1", "inclusion"),
            crit("D2", "data_element"), crit("E1", "exclusion"), crit("N2", "entry_event"),
        ]
        got = [c["id"] for c in jq("sort_by(crit_order)", json.dumps(shuffled))]
        self.assertEqual(got, ["N1", "N2", "I1", "I2", "I10", "E1", "E2", "E10", "D1", "D2", "D12"])

    def test_numeric_not_lexical_within_a_kind(self):
        got = [c["id"] for c in jq("sort_by(crit_order)", json.dumps([crit("E10", "exclusion"), crit("E2", "exclusion")]))]
        self.assertEqual(got, ["E2", "E10"])

    def test_kind_dominates_id_number(self):
        got = [c["id"] for c in jq("sort_by(crit_order)", json.dumps([crit("I1", "inclusion"), crit("N99", "entry_event")]))]
        self.assertEqual(got, ["N99", "I1"])

    def test_sort_is_stable_for_equal_keys_and_ignores_withdrawn(self):
        items = [crit("I2", "inclusion", withdrawn={"reason": "x", "at": "2026-01-01"}), crit("I1", "inclusion")]
        got = [c["id"] for c in jq("sort_by(crit_order)", json.dumps(items))]
        self.assertEqual(got, ["I1", "I2"])


class Live(unittest.TestCase):
    def test_live_drops_withdrawn_and_keeps_order(self):
        items = [
            crit("I1", "inclusion"),
            crit("I2", "inclusion", withdrawn={"reason": "merged", "at": "2026-09-01", "replaced_by": "I3"}),
            crit("I3", "inclusion"),
            crit("E1", "exclusion", withdrawn={"reason": "dropped", "at": "2026-09-01T00:00:00Z"}),
        ]
        got = [c["id"] for c in jq("crit_live", json.dumps(items))]
        self.assertEqual(got, ["I1", "I3"])

    def test_live_of_empty_and_all_withdrawn(self):
        self.assertEqual(jq("crit_live", "[]"), [])
        items = [crit("I1", "inclusion", withdrawn={"reason": "r", "at": "2026-09-01"})]
        self.assertEqual(jq("crit_live", json.dumps(items)), [])

    def test_live_returns_whole_objects_unchanged(self):
        items = [crit("I1", "inclusion", applied_by="rdl")]
        self.assertEqual(jq("crit_live", json.dumps(items)), items)


class Includes(unittest.TestCase):
    def test_include_works_without_a_program_of_its_own(self):
        # Guards against the module growing a top-level program, which would break `include`.
        self.assertEqual(jq("1"), 1)
        self.assertIsNotNone(re.search(r"^def crit_kinds\b", MODULE.read_text(), re.M))


if __name__ == "__main__":
    unittest.main()
