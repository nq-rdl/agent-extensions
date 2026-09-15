"""Behavioural tests for the sql-review plugin's shared helper, sqlreview.sh.

The helper lives at skills/sql-review-setup/scripts/sqlreview.sh (shared by all four
/sql-review:* skills via ${CLAUDE_PLUGIN_ROOT}/skills/setup/scripts/). Every test runs it
against a throwaway project directory; git is used only where the subcommand's contract
mentions it. Exit codes are part of the contract (docs/specs/2026-09-15-sql-review-plugin-design.md §4).
"""

import hashlib
import json
import os
import subprocess
import tempfile
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
SCRIPT = REPO / "skills" / "sql-review-setup" / "scripts" / "sqlreview.sh"
ASSETS = REPO / "skills" / "sql-review-setup" / "assets" / "sqlreview"


def run(args, cwd, env=None, stdin=None):
    e = {k: v for k, v in os.environ.items() if not k.startswith("SQLREVIEW_")}
    e.update(env or {})
    return subprocess.run(
        ["bash", str(SCRIPT), *args], cwd=cwd, env=e, input=stdin,
        capture_output=True, text=True, timeout=60,
    )


def git(cwd, *args):
    return subprocess.run(["git", *args], cwd=cwd, capture_output=True, text=True, check=True)


def item(id_, text, revision=1, **over):
    d = {
        "id": id_, "text": text, "rationale": "because", "location": None,
        "status": "confirmed", "confirmed_by": "analyst@example", "confirmed_at": "2026-09-15T00:00:00Z",
        "confirmed_revision": revision,
    }
    d.update(over)
    return d


def review_doc(slug="reports__monthly", sql_path="reports/monthly.sql", revision=1, **over):
    d = {
        "schemaVersion": 1, "kind": "review", "slug": slug, "sql_path": sql_path,
        "title": "Monthly report", "revision": revision, "recorded_at": "2026-09-15T00:00:00Z",
        "recorded_by": "engineer@example", "sql_sha256": "0" * 64, "git_commit": None, "git_dirty": False,
        "purpose": "Counts admissions per month.",
        "inputs": [{"name": "adm.stays", "description": "one row per stay"}],
        "outputs": [{"name": "month", "description": "calendar month"}, {"name": "n", "description": "count"}],
        "grain": "one row per month",
        "logic": [{"step": 1, "title": "Filter", "lines": [3, 5], "description": "keeps discharged stays"}],
        "assumptions": [item("A1", "Discharge date is populated", revision)],
        "limitations": [item("L1", "Excludes transfers", revision)],
        "open_questions": ["Should transfers count?"],
        "changes": [{"revision": revision, "at": "2026-09-15T00:00:00Z", "by": "engineer@example", "summary": "initial"}],
    }
    d.update(over)
    return d


def scope_doc(slug="reports__monthly", sql_path="reports/monthly.sql", revision=1, **over):
    d = {
        "schemaVersion": 1, "kind": "scope", "slug": slug, "sql_path": sql_path,
        "title": "Monthly report", "revision": revision, "recorded_at": "2026-09-15T00:00:00Z",
        "recorded_by": "engineer@example", "git_commit": None,
        "intent": "Monthly admission counts for the ward dashboard.",
        "inputs": [{"name": "adm.stays", "description": "one row per stay"}],
        "outputs": [{"name": "month", "description": "calendar month"}],
        "assumptions": [item("A1", "Only completed stays are in scope", revision)],
        "limitations": [],
        "open_questions": ["Which wards?"],
    }
    d.update(over)
    return d


class Project:
    """A temp project: optional git repo, initialised .sqlreview/, SQL files."""

    def __init__(self, tmp, git_repo=True, init=True):
        self.root = Path(tmp)
        if git_repo:
            git(self.root, "init", "-q")
            git(self.root, "config", "user.email", "t@example")
            git(self.root, "config", "user.name", "t")
        if init:
            r = run(["init"], self.root)
            assert r.returncode == 0, r.stderr

    def sql(self, rel, text):
        p = self.root / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(text)
        return p

    def review_dir(self, slug):
        d = self.root / ".sqlreview" / "reviews" / slug
        d.mkdir(parents=True, exist_ok=True)
        return d

    def write_json(self, slug, name, doc):
        d = self.review_dir(slug)
        sql = self.root / doc.get("sql_path", "missing")
        if name == "review.json" and sql.is_file():
            doc = dict(doc, sql_sha256=hashlib.sha256(sql.read_bytes()).hexdigest())
        (d / name).write_text(json.dumps(doc, indent=2))
        return d / name


SQL_V1 = "WITH stays AS (\n  SELECT * FROM adm.stays\n  WHERE discharge_date IS NOT NULL\n)\nSELECT month, COUNT(*) AS n\nFROM stays\nGROUP BY month;\n"
SQL_V2 = SQL_V1.replace("WITH stays AS", "WITH completed AS").replace("FROM stays", "FROM completed")


class Init(unittest.TestCase):
    def test_creates_tree_from_bundled_default(self):
        with tempfile.TemporaryDirectory() as tmp:
            p = Project(tmp, init=False)
            r = run(["init"], p.root)
            self.assertEqual(r.returncode, 0, r.stderr)
            for rel in ("config.json", "templates/scope.md", "templates/review.md"):
                self.assertTrue((p.root / ".sqlreview" / rel).is_file(), rel)
                self.assertEqual((p.root / ".sqlreview" / rel).read_bytes(), (ASSETS / rel).read_bytes())
            cfg = json.loads((p.root / ".sqlreview" / "config.json").read_text())
            self.assertEqual(cfg["schemaVersion"], 1)
            self.assertIn("Decision points made by the RDL", cfg["definitions"]["assumption"])
            self.assertTrue(cfg["definitions"]["limitation"])

    def test_rerun_never_overwrites_and_reports_delta(self):
        with tempfile.TemporaryDirectory() as tmp:
            p = Project(tmp)
            cfg = p.root / ".sqlreview" / "config.json"
            cfg.write_text(cfg.read_text().replace('"schemaVersion": 1', '"schemaVersion": 1, "custom": true'))
            r = run(["init"], p.root)
            self.assertEqual(r.returncode, 10, r.stdout + r.stderr)
            self.assertIn('"custom": true', cfg.read_text())     # untouched
            self.assertRegex(r.stdout, r"(?m)^differs\tconfig.json$")
            self.assertRegex(r.stdout, r"(?m)^same\ttemplates/scope.md$")
            self.assertIn("+", r.stdout)                          # a unified diff follows
            j = json.loads(run(["init", "--diff", "--json"], p.root).stdout)
            self.assertEqual({f["path"]: f["state"] for f in j["files"]}["config.json"], "differs")

    def test_diff_reports_new_without_creating_and_apply_replaces_only_named(self):
        with tempfile.TemporaryDirectory() as tmp:
            p = Project(tmp, init=False)
            r = run(["init", "--diff"], p.root)
            self.assertEqual(r.returncode, 10)
            self.assertRegex(r.stdout, r"(?m)^new\tconfig.json$")
            self.assertFalse((p.root / ".sqlreview").exists())
            run(["init"], p.root)
            cfg = p.root / ".sqlreview" / "config.json"
            tpl = p.root / ".sqlreview" / "templates" / "scope.md"
            cfg.write_text("{}")
            tpl.write_text("mine")
            r = run(["init", "--apply", "config.json"], p.root)
            self.assertEqual(r.returncode, 0, r.stderr)
            self.assertEqual(cfg.read_bytes(), (ASSETS / "config.json").read_bytes())
            self.assertEqual(tpl.read_text(), "mine")

    def test_root_resolution_from_nested_cwd_and_env(self):
        with tempfile.TemporaryDirectory() as tmp:
            p = Project(tmp)
            nested = p.root / "a" / "b"
            nested.mkdir(parents=True)
            r = run(["status", "--json"], nested)
            self.assertEqual(r.returncode, 0, r.stderr)
            self.assertEqual(Path(json.loads(r.stdout)["root"]).resolve(), p.root.resolve())
            with tempfile.TemporaryDirectory() as other:
                r = run(["status"], other, env={"SQLREVIEW_ROOT": str(p.root)})
                self.assertEqual(r.returncode, 0, r.stderr)


class Status(unittest.TestCase):
    def test_not_initialised_exits_3_with_setup_hint(self):
        with tempfile.TemporaryDirectory() as tmp:
            r = run(["status"], Project(tmp, init=False).root)
            self.assertEqual(r.returncode, 3)
            self.assertIn("/sql-review:setup", r.stderr)

    def test_states(self):
        with tempfile.TemporaryDirectory() as tmp:
            p = Project(tmp)
            p.sql("reports/monthly.sql", SQL_V1)
            p.sql("reports/weekly.sql", SQL_V1)
            p.sql("audits/gone.sql", SQL_V1)
            for slug, path in (("reports__monthly", "reports/monthly.sql"), ("reports__weekly", "reports/weekly.sql"),
                               ("audits__gone", "audits/gone.sql"), ("reports__nobase", "reports/nobase.sql")):
                p.write_json(slug, "review.json", review_doc(slug, path))
            run(["snapshot", "reports__monthly", "reports/monthly.sql"], p.root)
            run(["snapshot", "reports__weekly", "reports/weekly.sql"], p.root)
            run(["snapshot", "audits__gone", "audits/gone.sql"], p.root)
            (p.root / "reports" / "weekly.sql").write_text(SQL_V2)
            (p.root / "audits" / "gone.sql").unlink()
            p.sql("reports/nobase.sql", SQL_V1)
            p.write_json("reports__planned", "scope.json", scope_doc("reports__planned", "reports/planned.sql"))
            j = json.loads(run(["status", "--json"], p.root).stdout)
            states = {r["slug"]: r["state"] for r in j["reviews"]}
            self.assertEqual(states, {
                "reports__monthly": "current", "reports__weekly": "stale", "audits__gone": "missing",
                "reports__nobase": "no-baseline", "reports__planned": "scoped",
            })
            self.assertEqual(j["schemaVersion"], 1)
            text = run(["status"], p.root).stdout
            self.assertRegex(text, r"(?m)^reports__weekly\tstale\treports/weekly.sql\t1$")


class Slug(unittest.TestCase):
    def test_same_basename_different_dirs_do_not_collide(self):
        with tempfile.TemporaryDirectory() as tmp:
            p = Project(tmp)
            a = run(["slug", "reports/monthly.sql"], p.root).stdout.strip()
            b = run(["slug", "audits/monthly.sql"], p.root).stdout.strip()
            self.assertEqual(a, "reports__monthly")
            self.assertEqual(b, "audits__monthly")
            self.assertEqual(run(["slug", str(p.root / "reports" / "monthly.sql")], p.root).stdout.strip(), a)
            self.assertEqual(run(["slug", "monthly.sql"], p.root).stdout.strip(), "monthly")
            self.assertEqual(run(["slug", "odd name (1).sql"], p.root).stdout.strip(), "odd%20name%20%281%29")

    def test_conflicting_binding_exits_5(self):
        with tempfile.TemporaryDirectory() as tmp:
            p = Project(tmp)
            p.write_json("reports__monthly", "review.json", review_doc("reports__monthly", "other/thing.sql"))
            r = run(["slug", "reports/monthly.sql"], p.root)
            self.assertEqual(r.returncode, 5)
            self.assertIn("other/thing.sql", r.stderr)


class Check(unittest.TestCase):
    def check(self, doc, cwd):
        return run(["check", "--stdin"], cwd, stdin=json.dumps(doc))

    def test_confirmed_review_and_scope_are_valid(self):
        with tempfile.TemporaryDirectory() as tmp:
            self.assertEqual(self.check(review_doc(), tmp).returncode, 0)
            self.assertEqual(self.check(scope_doc(), tmp).returncode, 0)
            self.assertEqual(self.check(review_doc(assumptions=[], limitations=[]), tmp).returncode, 0)

    def test_file_argument(self):
        with tempfile.TemporaryDirectory() as tmp:
            f = Path(tmp) / "r.json"
            f.write_text(json.dumps(review_doc()))
            self.assertEqual(run(["check", str(f)], tmp).returncode, 0)

    def test_violations_name_the_item(self):
        cases = {
            "unconfirmed": review_doc(assumptions=[item("A1", "x", status="pending")]),
            "no_by": review_doc(limitations=[item("L1", "x", confirmed_by="")]),
            "no_at": review_doc(limitations=[item("L1", "x", confirmed_at=None)]),
            "stale_revision": review_doc(revision=2, assumptions=[item("A1", "x", revision=1)]),
            "empty_text": review_doc(assumptions=[item("A1", "")]),
            "dup_id": review_doc(assumptions=[item("A1", "x"), item("A1", "y")]),
        }
        with tempfile.TemporaryDirectory() as tmp:
            for name, doc in cases.items():
                with self.subTest(name):
                    r = self.check(doc, tmp)
                    self.assertEqual(r.returncode, 4, r.stdout)
                    self.assertRegex(r.stdout, r"\b[AL]1\b")

    def test_missing_keys_and_bad_json(self):
        with tempfile.TemporaryDirectory() as tmp:
            for key in ("kind", "slug", "sql_path", "revision", "assumptions", "limitations", "purpose", "logic"):
                doc = review_doc()
                del doc[key]
                with self.subTest(key):
                    r = self.check(doc, tmp)
                    self.assertEqual(r.returncode, 4)
                    self.assertIn(key, r.stdout)
            r = self.check(review_doc(kind="report"), tmp)
            self.assertEqual(r.returncode, 4)
            r = run(["check", "--stdin"], tmp, stdin="{not json")
            self.assertEqual(r.returncode, 4)
            self.assertIn("JSON", r.stdout + r.stderr)


class Fingerprint(unittest.TestCase):
    def test_sha_and_git_provenance(self):
        with tempfile.TemporaryDirectory() as tmp:
            p = Project(tmp)
            f = p.sql("reports/monthly.sql", SQL_V1)
            git(p.root, "add", "-A")
            git(p.root, "commit", "-q", "-m", "init")
            head = git(p.root, "rev-parse", "HEAD").stdout.strip()
            j = json.loads(run(["fingerprint", "reports/monthly.sql"], p.root).stdout)
            self.assertEqual(j["sql_sha256"], hashlib.sha256(f.read_bytes()).hexdigest())
            self.assertEqual(j["sql_path"], "reports/monthly.sql")
            self.assertEqual(j["git_commit"], head)
            self.assertFalse(j["git_dirty"])
            f.write_text(SQL_V2)
            self.assertTrue(json.loads(run(["fingerprint", "reports/monthly.sql"], p.root).stdout)["git_dirty"])
            self.assertEqual(run(["fingerprint", "nope.sql"], p.root).returncode, 2)

    def test_without_git(self):
        with tempfile.TemporaryDirectory() as tmp:
            p = Project(tmp, git_repo=False)
            p.sql("q.sql", SQL_V1)
            j = json.loads(run(["fingerprint", "q.sql"], p.root).stdout)
            self.assertIsNone(j["git_commit"])


class SnapshotDelta(unittest.TestCase):
    def _reviewed(self, p, path="reports/monthly.sql", slug="reports__monthly"):
        p.sql(path, SQL_V1)
        p.write_json(slug, "review.json", review_doc(slug, path))
        r = run(["snapshot", slug, path], p.root)
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertEqual((p.root / ".sqlreview" / "reviews" / slug / "source.sql").read_text(), SQL_V1)

    def test_unchanged_exits_0_changed_exits_10(self):
        with tempfile.TemporaryDirectory() as tmp:
            p = Project(tmp)
            self._reviewed(p)
            r = run(["delta", "reports__monthly"], p.root)
            self.assertEqual(r.returncode, 0, r.stderr)
            (p.root / "reports" / "monthly.sql").write_text(SQL_V2)
            r = run(["delta", "reports__monthly"], p.root)
            self.assertEqual(r.returncode, 10)
            self.assertIn("-WITH stays AS", r.stdout)
            self.assertIn("+WITH completed AS", r.stdout)
            self.assertIn("baseline_sha256=", r.stdout)

    def test_baseline_is_bytes_not_git(self):
        # dirty, untracked, reverted-to-HEAD and no-git all behave the same: bytes vs bytes.
        with tempfile.TemporaryDirectory() as tmp:
            p = Project(tmp)
            f = p.sql("reports/monthly.sql", SQL_V2)          # HEAD will hold V2
            git(p.root, "add", "-A")
            git(p.root, "commit", "-q", "-m", "v2")
            f.write_text(SQL_V1)                               # reviewed content is the dirty V1
            p.write_json("reports__monthly", "review.json", review_doc())
            run(["snapshot", "reports__monthly", "reports/monthly.sql"], p.root)
            self.assertEqual(run(["delta", "reports__monthly"], p.root).returncode, 0)
            git(p.root, "checkout", "--", "reports/monthly.sql")   # revert to HEAD → differs from baseline
            self.assertEqual(run(["delta", "reports__monthly"], p.root).returncode, 10)
        with tempfile.TemporaryDirectory() as tmp:
            p = Project(tmp, git_repo=False)
            self._reviewed(p, "untracked.sql", "untracked")
            self.assertEqual(run(["delta", "untracked"], p.root).returncode, 0)

    def test_no_baseline_exits_6_missing_sql_exits_2(self):
        with tempfile.TemporaryDirectory() as tmp:
            p = Project(tmp)
            p.sql("reports/monthly.sql", SQL_V1)
            p.write_json("reports__monthly", "review.json", review_doc())
            r = run(["delta", "reports__monthly"], p.root)
            self.assertEqual(r.returncode, 6)
            self.assertIn("baseline", r.stderr)
            self._reviewed(p)
            (p.root / "reports" / "monthly.sql").unlink()
            self.assertEqual(run(["delta", "reports__monthly"], p.root).returncode, 2)
            self.assertEqual(run(["delta", "unknown"], p.root).returncode, 2)


class Impact(unittest.TestCase):
    SQL = ("WITH stays AS (\n  SELECT * FROM adm.stays\n),\nwards AS (\n  SELECT * FROM ref.wards\n)\n"
           "SELECT s.month, w.name, COUNT(*) AS n\nFROM stays s\nJOIN wards w ON w.id = s.ward_id\nGROUP BY s.month, w.name;\n")

    def test_identifiers_in_hunks_are_traced_to_unchanged_lines_with_banner(self):
        with tempfile.TemporaryDirectory() as tmp:
            p = Project(tmp)
            p.sql("q.sql", self.SQL)
            p.write_json("q", "review.json", review_doc("q", "q.sql"))
            run(["snapshot", "q", "q.sql"], p.root)
            # Line 2 changes: the projected columns now name month and ward_id, which unchanged
            # lines 7, 9 and 10 depend on. `wards` is untouched and must not be traced.
            (p.root / "q.sql").write_text(self.SQL.replace("SELECT * FROM adm.stays", "SELECT id, ward_id, month FROM adm.stays"))
            r = run(["impact", "q"], p.root)
            self.assertEqual(r.returncode, 0, r.stderr)
            self.assertIn("heuristic", r.stdout.lower())
            self.assertRegex(r.stdout, r"(?m)^month\tline 7\t")
            self.assertRegex(r.stdout, r"(?m)^month\tline 10\t")
            self.assertRegex(r.stdout, r"(?m)^ward_id\tline 9\t")
            self.assertNotRegex(r.stdout, r"(?m)^wards\t")
            self.assertNotRegex(r.stdout, r"(?m)^month\tline 2\t")   # the hunk line itself is not a consequence

    def test_no_change_and_no_baseline(self):
        with tempfile.TemporaryDirectory() as tmp:
            p = Project(tmp)
            p.sql("q.sql", SQL_V1)
            p.write_json("q", "review.json", review_doc("q", "q.sql"))
            self.assertEqual(run(["impact", "q"], p.root).returncode, 6)
            run(["snapshot", "q", "q.sql"], p.root)
            r = run(["impact", "q"], p.root)
            self.assertEqual(r.returncode, 0)
            self.assertIn("no change", r.stdout.lower())


class Move(unittest.TestCase):
    def test_move_rebinds_path_and_slug(self):
        with tempfile.TemporaryDirectory() as tmp:
            p = Project(tmp)
            p.sql("reports/monthly.sql", SQL_V1)
            p.write_json("reports__monthly", "review.json", review_doc())
            p.write_json("reports__monthly", "scope.json", scope_doc())
            run(["snapshot", "reports__monthly", "reports/monthly.sql"], p.root)
            (p.root / "archive").mkdir()
            (p.root / "reports" / "monthly.sql").rename(p.root / "archive" / "monthly.sql")
            r = run(["move", "reports/monthly.sql", "archive/monthly.sql"], p.root)
            self.assertEqual(r.returncode, 0, r.stderr)
            d = p.root / ".sqlreview" / "reviews" / "archive__monthly"
            self.assertTrue(d.is_dir())
            self.assertFalse((p.root / ".sqlreview" / "reviews" / "reports__monthly").exists())
            for name in ("review.json", "scope.json"):
                j = json.loads((d / name).read_text())
                self.assertEqual((j["sql_path"], j["slug"]), ("archive/monthly.sql", "archive__monthly"))
            self.assertEqual(run(["delta", "archive__monthly"], p.root).returncode, 10)
            self.assertEqual(run(["move", "nope.sql", "x.sql"], p.root).returncode, 2)


class Render(unittest.TestCase):
    def test_review_render_is_deterministic_and_uses_template(self):
        with tempfile.TemporaryDirectory() as tmp:
            p = Project(tmp)
            p.sql("reports/monthly.sql", SQL_V1)
            p.write_json("reports__monthly", "review.json", review_doc())
            r = run(["render", "reports__monthly", "review"], p.root)
            self.assertEqual(r.returncode, 0, r.stderr)
            out = p.root / ".sqlreview" / "reviews" / "reports__monthly" / "review.md"
            md = out.read_text()
            for needle in ("Monthly report", "reports/monthly.sql", "| A1 |", "Discharge date is populated",
                           "| L1 |", "Excludes transfers", "Counts admissions per month.", "adm.stays",
                           "Should transfers count?", "Decision points made by the RDL", "3-5"):
                self.assertIn(needle, md, needle)
            self.assertNotIn("{{", md)
            first = out.read_bytes()
            run(["render", "reports__monthly", "review"], p.root)
            self.assertEqual(out.read_bytes(), first)

    def test_scope_render_and_unknown_placeholder_reported(self):
        with tempfile.TemporaryDirectory() as tmp:
            p = Project(tmp)
            p.write_json("reports__monthly", "scope.json", scope_doc())
            tpl = p.root / ".sqlreview" / "templates" / "scope.md"
            tpl.write_text(tpl.read_text() + "\n{{not_a_thing}}\n")
            r = run(["render", "reports__monthly", "scope"], p.root)
            self.assertEqual(r.returncode, 0, r.stderr)
            self.assertIn("not_a_thing", r.stderr)
            md = (p.root / ".sqlreview" / "reviews" / "reports__monthly" / "scope.md").read_text()
            self.assertIn("Only completed stays are in scope", md)
            self.assertIn("{{not_a_thing}}", md)
            self.assertIn("Which wards?", md)

    def test_render_errors(self):
        with tempfile.TemporaryDirectory() as tmp:
            p = Project(tmp)
            self.assertEqual(run(["render", "nothing", "review"], p.root).returncode, 2)
            p.write_json("x", "review.json", review_doc("x", "x.sql"))
            self.assertEqual(run(["render", "x", "bogus"], p.root).returncode, 2)


class Usage(unittest.TestCase):
    def test_no_args_and_unknown_command(self):
        with tempfile.TemporaryDirectory() as tmp:
            self.assertEqual(run([], tmp).returncode, 1)
            r = run(["frobnicate"], tmp)
            self.assertEqual(r.returncode, 1)
            self.assertIn("usage", (r.stdout + r.stderr).lower())


if __name__ == "__main__":
    unittest.main()
