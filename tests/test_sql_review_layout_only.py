"""A layout-only SQL change keeps the confirmations (#586).

The normal form is query-builder's `script_fingerprint(level="normalised")`. That function is unreleased, so these
tests drive the helper through a stand-in named by SQLREVIEW_NORMALISE_CMD: a script that hashes the text with
all white space collapsed. The stand-in is a test double for the library call, not a re-implementation shipped
by the helper. The helper itself never normalises anything.
"""
import json
import os
import sys
import tempfile
import unittest
from pathlib import Path

try:
    from test_sql_review_scripts import Project, git, item, review_doc, run, scope_doc
except ModuleNotFoundError:
    from tests.test_sql_review_scripts import Project, git, item, review_doc, run, scope_doc

STAND_IN = (
    "import hashlib, re, sys\n"
    "t = re.sub(r'\\s+', ' ', sys.stdin.read()).strip()\n"
    "print(hashlib.sha256(t.encode()).hexdigest(), '0.0.1')\n"
)

TALL = "WITH stays AS (\n  SELECT * FROM adm.stays\n  WHERE discharge_date IS NOT NULL\n)\nSELECT month, COUNT(*) AS n\nFROM stays\nGROUP BY month;\n"
FLAT = "WITH stays AS ( SELECT * FROM adm.stays WHERE discharge_date IS NOT NULL )\nSELECT month, COUNT(*) AS n\nFROM stays\nGROUP BY month;\n"
MEANING = FLAT.replace("IS NOT NULL", "IS NULL")


def stand_in_env(tmp):
    script = Path(tmp) / "normalise_stand_in.py"
    script.write_text(STAND_IN)
    return {"SQLREVIEW_NORMALISE_CMD": f"{sys.executable} {script}"}


class Base(unittest.TestCase):
    path = "q.sql"
    slug = "q"

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.scratch = tempfile.TemporaryDirectory()
        self.addCleanup(self.scratch.cleanup)
        self.env = stand_in_env(self.scratch.name)
        self.p = Project(self.tmp.name)
        self.sql = self.p.sql(self.path, TALL)
        self.d = self.p.review_dir(self.slug)
        self.p.commit()

    def sr(self, *args, env="stand-in"):
        return run(list(args), self.p.root, env=self.env if env == "stand-in" else env)

    def fingerprint(self, env="stand-in"):
        r = self.sr("fingerprint", self.path, env=env)
        self.assertEqual(r.returncode, 0, r.stderr)
        return json.loads(r.stdout)

    def publish(self, doc, env="stand-in"):
        draft = self.d / "draft.json"
        draft.write_text(json.dumps(doc))
        return self.sr("publish", self.slug, doc["kind"], str(draft), env=env)

    def record(self, env="stand-in"):
        fp = self.fingerprint(env)
        for kind, make in (("scope", scope_doc), ("review", review_doc)):
            r = self.publish(make(self.slug, **fp), env)
            self.assertEqual(r.returncode, 0, r.stderr)
        self.assertEqual(self.sr("snapshot", self.slug, self.path).returncode, 0)
        return fp

    def change_layout(self, text=FLAT, message="layout"):
        self.sql.write_text(text)
        return self.p.commit(message)

    def status_row(self):
        r = self.sr("status", "--json")
        self.assertEqual(r.returncode, 0, r.stderr)
        return [x for x in json.loads(r.stdout)["reviews"] if x["slug"] == self.slug][0] if "reviews" in json.loads(r.stdout) \
            else [x for x in json.loads(r.stdout) if x["slug"] == self.slug][0]


class Fingerprint(Base):
    def test_records_the_normalised_value_and_library_version(self):
        fp = self.fingerprint()
        self.assertRegex(fp["sql_normalised_sha256"], "^[0-9a-f]{64}$")
        self.assertEqual(fp["fingerprint_library_version"], "0.0.1")

    def test_exact_value_does_not_change(self):
        fp = self.fingerprint()
        self.assertNotEqual(fp["sql_sha256"], fp["sql_normalised_sha256"])

    def test_absent_when_the_library_call_fails(self):
        for cmd in ("exit 3", "echo not-a-hash", "echo " + "g" * 64, ""):
            fp = self.fingerprint(env={"SQLREVIEW_NORMALISE_CMD": cmd})
            self.assertIsNone(fp["sql_normalised_sha256"], cmd)
            self.assertIsNone(fp["fingerprint_library_version"], cmd)
            self.assertRegex(fp["sql_sha256"], "^[0-9a-f]{64}$")

    def test_absent_when_the_default_call_finds_no_library(self):
        # No override, and no pixi or library in this throwaway project: the value is absent, never invented.
        env = {"PATH": os.pathsep.join([str(Path(sys.executable).parent), "/usr/bin", "/bin"])}
        fp = self.fingerprint(env=env)
        self.assertIsNone(fp["sql_normalised_sha256"])


class Status(Base):
    def test_layout_only_is_reported_and_distinct_from_current_and_stale(self):
        self.record()
        self.assertEqual(self.status_row()["state"], "current")
        self.change_layout()
        row = self.status_row()
        self.assertEqual(row["state"], "layout-only")
        self.assertIn("rebind", row["next"])
        self.assertNotIn("bootstrap", row["next"])
        self.change_layout(MEANING, "meaning")
        self.assertEqual(self.status_row()["state"], "stale")

    def test_scope_only_reports_scoped_layout_only(self):
        fp = self.fingerprint()
        self.assertEqual(self.publish(scope_doc(self.slug, **fp)).returncode, 0)
        self.change_layout()
        self.assertEqual(self.status_row()["state"], "scoped-layout-only")

    def test_record_without_the_normalised_value_stays_stale(self):
        self.record(env={"SQLREVIEW_NORMALISE_CMD": "exit 3"})
        self.change_layout()
        # The library is back, but the record holds no normalised value to compare: never layout-only.
        self.assertEqual(self.status_row()["state"], "stale")

    def test_library_unavailable_now_stays_stale(self):
        self.record()
        self.change_layout()
        r = self.sr("status", "--json", env={"SQLREVIEW_NORMALISE_CMD": "exit 3"})
        rows = json.loads(r.stdout)
        rows = rows["reviews"] if isinstance(rows, dict) else rows
        self.assertEqual([x for x in rows if x["slug"] == self.slug][0]["state"], "stale")

    def test_status_text_names_the_state(self):
        self.record()
        self.change_layout()
        self.assertIn("layout-only", self.sr("status").stdout)

    def test_check_refuses_a_malformed_normalised_value(self):
        fp = self.fingerprint()
        doc = review_doc(self.slug, **dict(fp, sql_normalised_sha256="xyz"))
        (self.d / "bad.json").write_text(json.dumps(doc))
        r = self.sr("check", str(self.d / "bad.json"))
        self.assertEqual(r.returncode, 4)
        self.assertIn("sql_normalised_sha256", r.stdout + r.stderr)


class Rebind(Base):
    def test_rebinds_with_one_confirmation_and_keeps_every_confirmation(self):
        fp = self.record()
        before = json.loads((self.d / "review.json").read_text())
        head = self.change_layout()
        r = self.sr("rebind", self.slug, "--confirmed-by", "engineer-login")
        self.assertEqual(r.returncode, 0, r.stderr)
        after = json.loads((self.d / "review.json").read_text())
        scope = json.loads((self.d / "scope.json").read_text())
        for kind, doc in (("review", after), ("scope", scope)):
            self.assertEqual(doc["git_commit"], head, kind)
            self.assertNotEqual(doc["sql_sha256"], fp["sql_sha256"], kind)
            self.assertEqual(doc["sql_normalised_sha256"], fp["sql_normalised_sha256"], kind)
            entry = doc["layout_rebinds"][-1]
            self.assertEqual(entry["confirmed_by"], "engineer-login")
            self.assertEqual(entry["from"]["sql_sha256"], fp["sql_sha256"])
            self.assertEqual(entry["from"]["git_commit"], fp["git_commit"])
            self.assertEqual(entry["to"]["sql_sha256"], doc["sql_sha256"])
            self.assertEqual(entry["to"]["git_commit"], head)
            self.assertEqual(entry["from"]["library_version"], "0.0.1")
            self.assertEqual(entry["to"]["library_version"], "0.0.1")
        # The helper never refreshes a human confirmation.
        for key in ("assumptions", "limitations"):
            self.assertEqual(after[key], before[key])
        self.assertEqual(after["revision"], before["revision"])
        self.assertEqual(self.status_row()["state"], "current")
        self.assertEqual(self.sr("snapshot", self.slug, self.path).returncode, 0)
        self.assertIn("Layout re-bind history", (self.d / "review.md").read_text())

    def test_a_later_publish_keeps_the_rebind_history_and_refuses_an_edit_of_it(self):
        self.record()
        self.change_layout()
        self.assertEqual(self.sr("rebind", self.slug, "--confirmed-by", "engineer-login").returncode, 0)
        doc = json.loads((self.d / "review.json").read_text())
        keep = dict(doc)
        del keep["layout_rebinds"]
        self.assertEqual(self.publish(keep).returncode, 0)  # idempotent: nothing but the history was omitted
        self.assertEqual(len(json.loads((self.d / "review.json").read_text())["layout_rebinds"]), 1)
        forged = dict(doc, layout_rebinds=[dict(doc["layout_rebinds"][0], confirmed_by="someone-else")])
        r = self.publish(forged)
        self.assertEqual(r.returncode, 4)
        self.assertIn("layout_rebinds is helper-owned", r.stderr)

    def test_requires_the_confirmation_argument(self):
        self.record()
        self.change_layout()
        for args in (("rebind", self.slug), ("rebind", self.slug, "--confirmed-by"), ("rebind", self.slug, "--confirmed-by", ""),
                     ("rebind", self.slug, "--confirmed-by", "a b"), ("rebind", self.slug, "--yes")):
            self.assertNotEqual(self.sr(*args).returncode, 0, args)
        self.assertEqual(self.status_row()["state"], "layout-only")
        self.assertNotIn("layout_rebinds", json.loads((self.d / "review.json").read_text()))

    def test_refuses_a_change_of_meaning(self):
        self.record()
        self.change_layout(MEANING, "meaning")
        r = self.sr("rebind", self.slug, "--confirmed-by", "engineer-login")
        self.assertEqual(r.returncode, 10)
        self.assertIn("not a layout-only change", r.stderr)
        self.assertNotIn("layout_rebinds", json.loads((self.d / "review.json").read_text()))

    def test_refuses_without_a_recorded_normalised_value(self):
        self.record(env={"SQLREVIEW_NORMALISE_CMD": "exit 3"})
        self.change_layout()
        r = self.sr("rebind", self.slug, "--confirmed-by", "engineer-login")
        self.assertEqual(r.returncode, 10)
        self.assertIn("no normalised fingerprint", r.stderr)

    def test_refuses_when_the_library_is_unavailable(self):
        self.record()
        self.change_layout()
        r = self.sr("rebind", self.slug, "--confirmed-by", "engineer-login", env={"SQLREVIEW_NORMALISE_CMD": "exit 3"})
        self.assertEqual(r.returncode, 10)
        self.assertIn("unavailable", r.stderr)

    def test_refuses_a_recorded_value_that_does_not_match_the_recorded_sql(self):
        self.record()
        doc = json.loads((self.d / "review.json").read_text())
        doc["sql_normalised_sha256"] = "1" * 64
        (self.d / "review.json").write_text(json.dumps(doc))
        self.change_layout()
        r = self.sr("rebind", self.slug, "--confirmed-by", "engineer-login")
        self.assertEqual(r.returncode, 6)

    def test_refuses_a_dirty_tree_and_writes_nothing(self):
        self.record()
        self.sql.write_text(FLAT)
        r = self.sr("rebind", self.slug, "--confirmed-by", "engineer-login")
        self.assertEqual(r.returncode, 2)
        self.assertNotIn("layout_rebinds", json.loads((self.d / "review.json").read_text()))

    def test_unchanged_sql_has_nothing_to_rebind(self):
        self.record()
        r = self.sr("rebind", self.slug, "--confirmed-by", "engineer-login")
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertIn("nothing to rebind", r.stdout)

    def test_a_header_only_change_is_left_to_analyse(self):
        self.record()
        self.sql.write_text("/* analysis notes: new */\n" + TALL)
        self.p.commit("header")
        r = self.sr("rebind", self.slug, "--confirmed-by", "engineer-login")
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertIn("header-only", r.stdout)
        self.assertNotIn("layout_rebinds", json.loads((self.d / "review.json").read_text()))

    def test_all_or_nothing_across_scope_and_review(self):
        self.record()
        scope = json.loads((self.d / "scope.json").read_text())
        scope["sql_normalised_sha256"] = "2" * 64
        (self.d / "scope.json").write_text(json.dumps(scope))
        self.change_layout()
        r = self.sr("rebind", self.slug, "--confirmed-by", "engineer-login")
        self.assertNotEqual(r.returncode, 0)
        self.assertNotIn("layout_rebinds", json.loads((self.d / "review.json").read_text()))
        self.assertNotIn("layout_rebinds", json.loads((self.d / "scope.json").read_text()))

    def test_publish_of_a_new_revision_after_layout_change_still_needs_a_fresh_fingerprint(self):
        fp = self.record()
        self.change_layout()
        r = self.publish(review_doc(self.slug, revision=2, **fp))
        self.assertNotEqual(r.returncode, 0)


RELEASE = Path(__file__).resolve().parent.parent / "skills" / "data-request-setup" / "scripts" / "release.sh"


class Evidence(Base):
    def evidence(self, ref="HEAD", env="stand-in"):
        import subprocess
        e = {k: v for k, v in os.environ.items() if not k.startswith("SQLREVIEW_")}
        e.update(self.env if env == "stand-in" else env)
        return subprocess.run(["bash", str(RELEASE), "evidence", "--no-amend-hold", ref], cwd=self.p.root, env=e,
                              capture_output=True, text=True, timeout=60)

    def row(self, r):
        return [x for x in json.loads(r.stdout)["reviews"] if x["kind"] == "review"][0]

    def test_exact_match_names_its_level(self):
        self.record()
        r = self.evidence()
        self.assertEqual(r.returncode, 0, r.stderr)
        row = self.row(r)
        self.assertEqual((row["applies"], row["matched_level"]), ("current", "exact"))
        self.assertEqual(row["sql_normalised_sha256_reviewed"], row["sql_normalised_sha256_at_ref"])

    def test_layout_only_is_reported_and_does_not_pass(self):
        self.record()
        self.change_layout()
        r = self.evidence()
        self.assertEqual(r.returncode, 10, r.stderr)
        row = self.row(r)
        self.assertEqual((row["applies"], row["matched_level"]), ("layout-only", "normalised"))

    def test_meaning_change_is_changed_with_no_level(self):
        self.record()
        self.change_layout(MEANING)
        row = self.row(self.evidence())
        self.assertEqual((row["applies"], row["matched_level"]), ("changed", None))

    def test_absent_normalised_value_is_never_layout_only(self):
        self.record(env={"SQLREVIEW_NORMALISE_CMD": "exit 3"})
        self.change_layout()
        row = self.row(self.evidence())
        self.assertEqual((row["applies"], row["matched_level"]), ("changed", None))
        self.assertIsNone(row["sql_normalised_sha256_reviewed"])

    def test_library_unavailable_at_evidence_time_is_never_layout_only(self):
        self.record()
        self.change_layout()
        row = self.row(self.evidence(env={"SQLREVIEW_NORMALISE_CMD": "exit 3"}))
        self.assertEqual(row["applies"], "changed")

    def test_a_rebound_record_is_current_and_lists_the_rebind(self):
        self.record()
        self.change_layout()
        self.assertEqual(self.sr("rebind", self.slug, "--confirmed-by", "engineer-login").returncode, 0)
        self.p.commit("rebound records")
        r = self.evidence()
        self.assertEqual(r.returncode, 0, r.stderr)
        row = self.row(r)
        self.assertEqual((row["applies"], row["matched_level"]), ("current", "exact"))
        self.assertEqual(row["layout_rebinds"][0]["confirmed_by"], "engineer-login")


class CrossDirectory(Base):
    """The first revision of sql/v2/<name>.sql carries from sql/v1/<name>.sql (#586)."""

    path = "sql/v1/q.sql"
    slug = "sql__v1__q"
    new_path = "sql/v2/q.sql"
    new_slug = "sql__v2__q"

    def setUp(self):
        super().setUp()
        self.old = self.record()

    def put_new(self, text):
        self.p.sql(self.new_path, text)
        self.p.commit("v2")
        r = self.sr("fingerprint", self.new_path)
        self.assertEqual(r.returncode, 0, r.stderr)
        return json.loads(r.stdout)

    def draft(self, kind, fp, items=None, **over):
        make = review_doc if kind == "review" else scope_doc
        base = json.loads((self.d / f"{kind}.json").read_text())
        doc = make(self.new_slug, **fp)
        doc["assumptions"] = items if items is not None else [dict(base["assumptions"][0])]
        doc["limitations"] = [] if kind == "scope" else [dict(base["limitations"][0])]
        doc.update(over)
        path = self.p.review_dir(self.new_slug) / f"{kind}.new.json"
        path.write_text(json.dumps(doc))
        return path, doc

    def carry(self, kind, draft, frm=None, env="stand-in"):
        args = ["carryforward", self.new_slug, kind, str(draft)] + (["--from", frm or self.slug])
        r = self.sr(*args, env=env)
        return r, (json.loads(r.stdout) if r.stdout.strip() else None)

    def carried_item(self, kind, out):
        rows = {x["id"]: x for x in out["carry"]}
        return rows

    def test_whole_script_unchanged_at_the_normalised_level_carries_every_item(self):
        fp = self.put_new(FLAT)
        path, _ = self.draft("review", fp)
        r, out = self.carry("review", path)
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertTrue(out["cross_directory"])
        self.assertEqual(out["from_slug"], self.slug)
        self.assertEqual(out["revision"], 1)
        self.assertEqual({x["id"]: x["basis"] for x in out["carry"]}, {"A1": "sql-normalised-unchanged", "L1": "sql-normalised-unchanged"})
        self.assertEqual(out["walk"] + out["bulk"], [])
        a1 = {x["id"]: x for x in out["carry"]}["A1"]["set"]
        self.assertEqual(a1["carried_from_slug"], self.slug)
        self.assertEqual(a1["confirmed_by"], "analyst-login")

    def test_identical_sql_carries_as_sql_unchanged(self):
        fp = self.put_new(TALL)
        path, _ = self.draft("review", fp)
        r, out = self.carry("review", path)
        self.assertEqual({x["basis"] for x in out["carry"]}, {"sql-unchanged"})

    def test_a_change_of_meaning_carries_nothing_and_lists_every_item(self):
        fp = self.put_new(MEANING)
        path, _ = self.draft("review", fp)
        r, out = self.carry("review", path)
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertEqual(out["carry"], [])
        self.assertEqual({x["id"] for x in out["walk"]}, {"A1", "L1"})
        self.assertIn("normalised level", out["walk"][0]["why"])

    def test_absent_normalised_value_carries_nothing(self):
        for env in ({"SQLREVIEW_NORMALISE_CMD": "exit 3"}, "stand-in"):
            fp = self.put_new(FLAT)
            path, _ = self.draft("review", fp)
            if env != "stand-in":
                doc = json.loads((self.d / "review.json").read_text())
                doc["sql_normalised_sha256"] = None
                (self.d / "review.json").write_text(json.dumps(doc))
            r, out = self.carry("review", path)
            if env != "stand-in":
                self.assertEqual(out["carry"], [])
                self.assertEqual(len(out["walk"]), 2)

    def test_library_unavailable_carries_nothing(self):
        fp = self.put_new(FLAT)
        path, _ = self.draft("review", fp)
        r, out = self.carry("review", path, env={"SQLREVIEW_NORMALISE_CMD": "exit 3"})
        self.assertEqual(out["carry"], [])

    def test_changed_text_is_walked_even_when_the_script_is_unchanged(self):
        fp = self.put_new(FLAT)
        base = json.loads((self.d / "review.json").read_text())
        reworded = dict(base["assumptions"][0], text="A reworded assumption")
        path, _ = self.draft("review", fp, items=[reworded])
        r, out = self.carry("review", path)
        self.assertEqual([x["id"] for x in out["walk"] if x["id"] == "A1"], ["A1"])

    def test_publish_accepts_the_proved_carry_and_records_provenance(self):
        fp = self.put_new(FLAT)
        path, doc = self.draft("review", fp)
        _, out = self.carry("review", path)
        rows = {x["id"]: x["set"] for x in out["carry"]}
        for key in ("assumptions", "limitations"):
            doc[key] = [dict(i, **rows[i["id"]]) for i in doc[key]]
        path.write_text(json.dumps(doc))
        r = self.sr("publish", self.new_slug, "review", str(path))
        self.assertEqual(r.returncode, 0, r.stderr)
        stored = json.loads((self.p.root / ".sqlreview/reviews" / self.new_slug / "review.json").read_text())
        self.assertEqual(stored["assumptions"][0]["carried_from_slug"], self.slug)
        self.assertEqual(stored["assumptions"][0]["carried_basis"], "sql-normalised-unchanged")
        self.assertEqual(stored["assumptions"][0]["confirmed_by"], "analyst-login")

    def test_publish_refuses_a_forged_carry_after_a_change_of_meaning(self):
        fp = self.put_new(MEANING)
        path, doc = self.draft("review", fp)
        base = json.loads((self.d / "review.json").read_text())
        for key in ("assumptions", "limitations"):
            doc[key] = [dict(i, carried_from_revision=1, carried_from_slug=self.slug, carried_basis="sql-normalised-unchanged")
                        for i in base[key]]
        path.write_text(json.dumps(doc))
        r = self.sr("publish", self.new_slug, "review", str(path))
        self.assertEqual(r.returncode, 4)
        self.assertIn("cannot carry the confirmation forward", r.stdout + r.stderr)
        self.assertFalse((self.p.root / ".sqlreview/reviews" / self.new_slug / "review.json").exists())

    def test_publish_refuses_a_carry_that_names_no_predecessor_record(self):
        fp = self.put_new(FLAT)
        path, doc = self.draft("review", fp)
        base = json.loads((self.d / "review.json").read_text())
        doc["assumptions"] = [dict(base["assumptions"][0], carried_from_revision=1, carried_from_slug="sql__v9__none")]
        doc["limitations"] = []
        path.write_text(json.dumps(doc))
        self.assertNotEqual(self.sr("publish", self.new_slug, "review", str(path)).returncode, 0)

    def test_cross_carry_applies_only_to_the_first_revision(self):
        fp = self.put_new(FLAT)
        path, doc = self.draft("review", fp)
        _, out = self.carry("review", path)
        rows = {x["id"]: x["set"] for x in out["carry"]}
        for key in ("assumptions", "limitations"):
            doc[key] = [dict(i, **rows[i["id"]]) for i in doc[key]]
        path.write_text(json.dumps(doc))
        self.assertEqual(self.sr("publish", self.new_slug, "review", str(path)).returncode, 0)
        r, _ = self.carry("review", path)
        self.assertEqual(r.returncode, 4)

    def test_scope_carry_never_carries_criteria_rows(self):
        fp = self.put_new(FLAT)
        path, doc = self.draft("scope", fp)
        doc["criteria_status"] = [{"criterion": "C1", "state": "implemented"}]
        path.write_text(json.dumps(doc))
        r, out = self.carry("scope", path)
        self.assertEqual([x["id"] for x in out["carry"]], ["A1"])
        self.assertEqual([x["id"] for x in out["walk"]], ["C1"])

    def test_plain_carryforward_is_unchanged_by_the_new_fields(self):
        r = self.sr("carryforward", self.slug, "review", str(self.d / "review.json"))
        out = json.loads(r.stdout)
        self.assertFalse(out["cross_directory"])
        self.assertEqual({x["basis"] for x in out["carry"]}, {"sql-unchanged"})


if __name__ == "__main__":
    unittest.main()
