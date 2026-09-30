"""Issue 438: compute draft ranges, never confirmations or published evidence."""
import copy
import hashlib
import json
import os
import shutil
import tempfile
import unittest

try:
    from test_sql_review_scripts import Project, SQL_V1, item, review_doc, run, scope_doc
except ModuleNotFoundError:
    from tests.test_sql_review_scripts import Project, SQL_V1, item, review_doc, run, scope_doc


def sha(text):
    return hashlib.sha256(text.encode()).hexdigest()


class Remap(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.p = Project(self.tmp.name)
        self.sql = self.p.sql("q.sql", SQL_V1)
        self.d = self.p.review_dir("q")
        self.draft = self.d / "review.draft.json"
        self.prior = review_doc("q", "q.sql", sql_sha256=sha(SQL_V1),
            assumptions=[item("A1", "Discharge date marks completion", location={"lines": [3, 3]}),
                         item("A2", "Whole query", location=None)],
            limitations=[item("L1", "Monthly grain", location={"lines": [5, 7]})],
            logic=[{"step": 1, "title": "Filter", "lines": [1, 4], "description": "Filter stays"},
                   {"step": 2, "title": "Count", "lines": [5, 7], "description": "Count by month"}])
        self.seed(self.prior, SQL_V1)

    def seed(self, doc, sql):
        self.prior = doc
        self.kind = doc["kind"]
        self.published = self.d / (self.kind + ".json")
        self.baseline = self.d / ("source.sql" if self.kind == "review" else "scope.source.sql")
        self.published.write_text(json.dumps(doc))
        self.baseline.write_text(sql)
        self.before = {p: p.read_bytes() for p in (self.published, self.baseline)}

    def stage(self):
        draft = copy.deepcopy(self.prior)
        draft["revision"] = 2
        draft["sql_sha256"] = sha(self.sql.read_text())
        self.draft.write_text(json.dumps(draft))
        return draft

    def remap(self, explicit=True, expected=0):
        args = ["remap", "q"] + ([str(self.draft)] if explicit else [])
        r = run(args, self.p.root)
        self.assertEqual(r.returncode, expected, r.stdout + r.stderr)
        if expected == 0:
            for path, before in self.before.items():
                self.assertEqual(path.read_bytes(), before)
            return json.loads(r.stdout)
        return r

    def read(self):
        return json.loads(self.draft.read_text())

    def test_two_line_header_growth_every_range_and_real_carryforward(self):
        self.sql.write_text("-- new assumption\n-- its rationale\n" + SQL_V1)
        original = self.stage()
        out = self.remap()
        doc = self.read()
        expected = copy.deepcopy(original)
        expected["assumptions"][0]["location"]["lines"] = [5, 5]
        expected["limitations"][0]["location"]["lines"] = [7, 9]
        expected["logic"][0]["lines"] = [3, 6]
        expected["logic"][1]["lines"] = [7, 9]
        self.assertEqual(doc, expected)  # no fingerprint/revision/confirmation edits
        self.assertEqual(len(out["remapped"]), 4)
        self.assertEqual(out["walk"], [])
        r = run(["carryforward", "q", "review", str(self.draft)], self.p.root)
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        verdict = json.loads(r.stdout)
        self.assertEqual({row["id"] for row in verdict["carry"]}, {"A1", "A2", "L1"})
        self.assertEqual(verdict["walk"], [])
        for k in ("assumptions", "limitations"):
            for it in doc[k]:
                it.update(next(row["set"] for row in verdict["carry"] if row["id"] == it["id"]))
        self.draft.write_text(json.dumps(doc))
        r = run(["publish", "q", "review", str(self.draft)], self.p.root)
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)

    def test_body_only_and_mixed_changes_leave_changed_ranges_untouched(self):
        for header in ("", "-- new header\n-- more header\n"):
            with self.subTest(header=header):
                self.sql.write_text(header + SQL_V1.replace("IS NOT NULL", "IS NOT NULL AND ward <> 'X'"))
                original = self.stage()
                out = self.remap()
                doc = self.read()
                shift = 2 if header else 0
                self.assertEqual(doc["assumptions"], original["assumptions"])
                self.assertEqual(doc["logic"][0], original["logic"][0])
                self.assertEqual(doc["limitations"][0]["location"]["lines"], [5 + shift, 7 + shift])
                self.assertEqual(doc["logic"][1]["lines"], [5 + shift, 7 + shift])
                self.assertEqual({(r["kind"], r["id"]) for r in out["walk"]},
                                 {("assumptions", "A1"), ("logic", 1)})

    def test_insertion_inside_range_does_not_expand_it(self):
        self.sql.write_text(SQL_V1.replace("FROM stays\n", "-- explain count\nFROM stays\n"))
        original = self.stage()
        out = self.remap()
        self.assertEqual(self.read()["limitations"], original["limitations"])
        self.assertIn("L1", [r["id"] for r in out["walk"]])

    def test_repeated_edited_lines_are_ambiguous_not_arbitrarily_aligned(self):
        text = "SELECT 1;\nSELECT 1;\nSELECT 2;\n"
        doc = review_doc("q", "q.sql", sql_sha256=sha(text),
                         assumptions=[item("A1", "First select", location={"lines": [1, 1]})],
                         limitations=[], logic=[])
        self.seed(doc, text)
        self.sql.write_text("SELECT 1;\n" + text)
        original = self.stage()
        out = self.remap()
        self.assertEqual(self.read(), original)
        self.assertIn("ambiguous", out["walk"][0]["why"])

    def test_retry_is_byte_idempotent(self):
        self.sql.write_text("-- header\n-- rationale\n" + SQL_V1)
        self.stage()
        self.remap()
        once = self.draft.read_bytes()
        self.remap()
        self.assertEqual(self.draft.read_bytes(), once)

    def test_default_creates_draft_only_and_never_overwrites_existing_work(self):
        self.sql.write_text("-- header\n-- rationale\n" + SQL_V1)
        self.remap(explicit=False)
        self.assertEqual(self.read()["revision"], 1)
        doc = self.read()
        doc["purpose"] = "Unpublished work"
        self.draft.write_text(json.dumps(doc))
        self.remap(explicit=False)
        self.assertEqual(self.read()["purpose"], "Unpublished work")

    def test_scope_uses_its_own_authenticated_baseline(self):
        (self.d / "review.json").unlink()
        doc = scope_doc("q", "q.sql", sql_sha256=sha(SQL_V1),
                        assumptions=self.prior["assumptions"], limitations=self.prior["limitations"])
        self.seed(doc, SQL_V1)
        self.draft = self.d / "scope.draft.json"
        self.sql.write_text("-- header\n-- rationale\n" + SQL_V1)
        self.stage()
        out = self.remap()
        self.assertEqual(out["document"], "scope")
        self.assertEqual(self.read()["assumptions"][0]["location"]["lines"], [5, 5])

    def test_missing_corrupt_baseline_and_invalid_range_fail_atomically(self):
        self.sql.write_text("-- header\n" + SQL_V1)
        self.stage()
        before = self.draft.read_bytes()
        self.baseline.unlink()
        self.remap(expected=6)
        self.assertEqual(self.draft.read_bytes(), before)
        self.baseline.write_text("corrupt\n")
        self.remap(expected=2)
        self.assertEqual(self.draft.read_bytes(), before)
        self.baseline.write_text(SQL_V1)
        doc = self.read()
        doc["logic"][1]["lines"] = [0, 2]
        self.draft.write_text(json.dumps(doc))
        before = self.draft.read_bytes()
        self.remap(expected=4)
        self.assertEqual(self.draft.read_bytes(), before)

    def test_unsafe_destinations_and_bindings_are_refused(self):
        self.stage()
        for name in ("review.json", "scope.json", "source.sql", "../elsewhere.json"):
            r = run(["remap", "q", str(self.d / name)], self.p.root)
            self.assertEqual(r.returncode, 2, r.stdout + r.stderr)
        target = self.d / "link.json"
        target.symlink_to(self.draft)
        r = run(["remap", "q", str(target)], self.p.root)
        self.assertEqual(r.returncode, 2, r.stdout + r.stderr)
        doc = self.read()
        doc["sql_path"] = "another.sql"
        self.draft.write_text(json.dumps(doc))
        self.remap(expected=4)

    def test_unchanged_sql_and_crlf_without_final_newline(self):
        text = SQL_V1.replace("\n", "\r\n").removesuffix("\r\n")
        doc = copy.deepcopy(self.prior)
        doc["sql_sha256"] = sha(text)
        self.seed(doc, text)
        self.sql.write_bytes(text.encode())
        self.stage()
        out = self.remap()
        self.assertEqual(out["walk"], [])
        self.assertTrue(all(row["from"] == row["to"] for row in out["remapped"]))
        self.sql.write_bytes(("-- header\r\n-- rationale\r\n" + text).encode())
        self.stage()
        out = self.remap()
        self.assertEqual(out["walk"], [])
        self.assertEqual(self.read()["assumptions"][0]["location"]["lines"], [5, 5])

    def test_binary_diff_is_refused_without_writing(self):
        text = SQL_V1 + "-- binary " + chr(0) + "\n"
        doc = copy.deepcopy(self.prior)
        doc["sql_sha256"] = sha(text)
        self.seed(doc, text)
        self.sql.write_text(text.replace("binary", "changed"))
        self.stage()
        before = self.draft.read_bytes()
        r = self.remap(expected=2)
        self.assertIn("binary SQL", r.stderr)
        self.assertEqual(self.draft.read_bytes(), before)

    def test_reported_95_ranges_after_internal_header_growth(self):
        header = "".join(f"-- header {n}\n" for n in range(1, 127))
        body = "".join(f"SELECT {n};\n" for n in range(1, 96))
        text = header + body
        doc = review_doc("q", "q.sql", sql_sha256=sha(text),
            assumptions=[item(f"A{n}", f"Assumption {n}", location={"lines": [126 + n, 126 + n]})
                         for n in range(1, 68)], limitations=[],
            logic=[{"step": n, "title": f"Step {n}", "description": "Select",
                    "lines": [193 + n, 193 + n]} for n in range(1, 29)])
        self.seed(doc, text)
        self.sql.write_text(text.replace("-- header 73\n", "-- assumption\n-- rationale\n-- header 73\n"))
        self.stage()
        out = self.remap()
        self.assertEqual(len(out["remapped"]), 95)
        self.assertEqual(out["walk"], [])
        for row in out["remapped"]:
            self.assertEqual(row["to"], [n + 2 for n in row["from"]])

    def test_deletion_and_multiple_hunks_shift_only_unchanged_ranges(self):
        self.sql.write_text(SQL_V1.replace("WITH stays AS (\n", "").replace("SELECT month, COUNT(*) AS n\n", "-- count\nSELECT month, COUNT(*) AS n\n"))
        self.stage()
        out = self.remap()
        self.assertEqual(self.read()["assumptions"][0]["location"]["lines"], [2, 2])
        self.assertEqual(self.read()["limitations"][0]["location"]["lines"], [5, 7])
        self.assertEqual({r["id"] for r in out["walk"]}, {1})

    def test_duplicate_draft_ids_and_steps_fail_before_any_write(self):
        for key in ("assumptions", "logic"):
            with self.subTest(key=key):
                self.sql.write_text("-- header\n" + SQL_V1)
                doc = self.stage()
                doc[key].append(copy.deepcopy(doc[key][0]))
                self.draft.write_text(json.dumps(doc))
                before = self.draft.read_bytes()
                self.remap(expected=4)
                self.assertEqual(self.draft.read_bytes(), before)

    def test_diff_failure_is_atomic_and_cleans_temporary_files(self):
        self.stage()
        before = self.draft.read_bytes()
        tools = self.p.root / "tools"
        tools.mkdir()
        stub = tools / "diff"
        stub.write_text("#!/bin/sh\nexit 2\n")
        stub.chmod(0o755)
        r = run(["remap", "q", str(self.draft)], self.p.root,
                env={"PATH": str(tools) + os.pathsep + os.environ["PATH"]})
        self.assertEqual(r.returncode, 2, r.stdout + r.stderr)
        self.assertEqual(self.draft.read_bytes(), before)
        self.assertEqual(list(self.d.glob(".remap.*")), [])

    def test_concurrent_draft_edit_is_preserved(self):
        self.sql.write_text("-- header\n" + SQL_V1)
        self.stage()
        tools = self.p.root / "tools"
        tools.mkdir()
        stub = tools / "diff"
        stub.write_text(f'#!/bin/sh\nprintf "concurrent work" > "{self.draft}"\nexec "{shutil.which("diff")}" "$@"\n')
        stub.chmod(0o755)
        r = run(["remap", "q", str(self.draft)], self.p.root,
                env={"PATH": str(tools) + os.pathsep + os.environ["PATH"]})
        self.assertEqual(r.returncode, 2, r.stdout + r.stderr)
        self.assertEqual(self.draft.read_text(), "concurrent work")
        self.assertIn("inputs changed", r.stderr)

    def test_concurrent_default_draft_creation_is_preserved(self):
        self.sql.write_text("-- header\n" + SQL_V1)
        tools = self.p.root / "tools"
        tools.mkdir()
        stub = tools / "diff"
        stub.write_text(f'#!/bin/sh\nprintf "concurrent work" > "{self.draft}"\nexec "{shutil.which("diff")}" "$@"\n')
        stub.chmod(0o755)
        r = run(["remap", "q"], self.p.root,
                env={"PATH": str(tools) + os.pathsep + os.environ["PATH"]})
        self.assertEqual(r.returncode, 2, r.stdout + r.stderr)
        self.assertEqual(self.draft.read_text(), "concurrent work")

    def test_baseline_and_current_sql_symlinks_are_not_evidence(self):
        self.stage()
        saved = self.p.root / "saved.sql"
        saved.write_text(SQL_V1)
        for path in (self.baseline, self.sql):
            path.unlink()
            path.symlink_to(saved)
            self.remap(expected=2)
            path.unlink()
            path.write_text(SQL_V1)

    def test_manual_ranges_and_new_items_are_not_reinterpreted_as_baseline_coordinates(self):
        self.sql.write_text("-- header\n-- rationale\n" + SQL_V1)
        doc = self.stage()
        doc["assumptions"][0]["location"]["lines"] = [1, 2]
        doc["assumptions"].append(item("A3", "New", location={"lines": [4, 4]}))
        self.draft.write_text(json.dumps(doc))
        out = self.remap()
        self.assertEqual(self.read()["assumptions"], doc["assumptions"])
        self.assertEqual({r["id"] for r in out["walk"]}, {"A1", "A3"})


if __name__ == "__main__":
    unittest.main()
