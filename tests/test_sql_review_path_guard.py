"""Issue 516: sqlreview.sh refuses to read researcher-value paths into the committed .sqlreview/.

Files under data/ and pipeline SQL under sql/<name>/ can hold cohort values, so only a reviewed
sql/v<N>/ tree (the scaffold's rule: v[0-9]+([.-][0-9]+)*) may be fingerprinted, snapshotted,
slugged, moved or parsed for notes. The path is canonicalised first (".." and symlinks resolved),
an unresolvable path fails closed, and the message names the rule, never file content.
"""
import json
import os
import subprocess
import tempfile
import unittest
from pathlib import Path

try:  # `unittest discover -s tests` puts tests/ on sys.path; `-m unittest tests.x` does not
    from test_sql_review_scripts import SCRIPT, SQL_V1, Project, item, review_doc, run, scope_doc
except ModuleNotFoundError:
    from tests.test_sql_review_scripts import SCRIPT, SQL_V1, Project, item, review_doc, run, scope_doc

MARKER = "ZZTEST-90210-ROW"  # stands in for a researcher-supplied value; must never be echoed
RULE_DATA = "no data/ paths"
RULE_SQL = "sql/v[0-9]+([.-][0-9]+)*"


def tree(root):
    """Every path and file body under .sqlreview/, to prove a refusal writes nothing."""
    out = {}
    base = Path(root) / ".sqlreview"
    for p in sorted(base.rglob("*")):
        out[str(p.relative_to(base))] = p.read_bytes() if p.is_file() and not p.is_symlink() else None
    return out


class PathGuard(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.p = Project(self._tmp.name)
        self.root = self.p.root
        self.p.sql("data/00_raw/x.csv", f"id,value\n1,{MARKER}\n")
        self.p.sql("sql/pipeline_a/q.sql", f"-- {MARKER}\n{SQL_V1}")
        self.p.sql("sql/v1/q.sql", SQL_V1)
        self.p.sql("sql/v2.1/q.sql", SQL_V1)
        self.p.sql("sql/v3-1/q.sql", SQL_V1)
        self.p.sql("sql/v1x/q.sql", SQL_V1)
        self.p.sql("sql/loose.sql", SQL_V1)
        self.p.commit()
        # Links stay uncommitted: fingerprint's own clean-source rule would refuse the repo first,
        # and the guard must hold for every command, including ones that never look at git.
        os.symlink("../../data/00_raw/x.csv", self.root / "sql/v1/link.csv")
        os.symlink("../../data", self.root / "sql/v1/datadir")
        os.symlink("loop", self.root / "sql/v1/loop")
        os.symlink("../../data/00_raw", self.root / "sql/v1/rawdir")
        self.p.sql("data/secret.csv", f"id,value\n1,{MARKER}\n")

    def refused(self, args, rule):
        before = tree(self.root)
        r = run(args, self.root)
        self.assertEqual(r.returncode, 2, (args, r.stdout, r.stderr))
        self.assertIn("refused", r.stderr)
        self.assertIn(rule, r.stderr)
        self.assertNotIn(MARKER, r.stdout + r.stderr)
        self.assertEqual(r.stdout, "")
        self.assertEqual(tree(self.root), before, "a refusal must not write under .sqlreview/")

    def each_command(self, path, rule):
        self.refused(["fingerprint", path], rule)
        self.refused(["snapshot", "any", path], rule)
        self.refused(["slug", path], rule)
        self.refused(["notes", path], rule)
        self.refused(["move", "sql/v1/q.sql", path], rule)

    def test_data_path_refused(self):
        self.each_command("data/00_raw/x.csv", RULE_DATA)

    def test_data_path_refused_when_absent_or_cased(self):
        self.each_command("data/nope.csv", RULE_DATA)
        self.each_command("Data/00_raw/x.csv", RULE_DATA)

    def test_absolute_data_path_refused(self):
        self.each_command(str(self.root / "data/00_raw/x.csv"), RULE_DATA)

    def test_pipeline_sql_refused(self):
        self.each_command("sql/pipeline_a/q.sql", RULE_SQL)

    def test_sql_outside_a_version_directory_refused(self):
        self.each_command("sql/loose.sql", RULE_SQL)
        self.each_command("sql/v1x/q.sql", RULE_SQL)

    def test_dotdot_out_of_version_directory_refused(self):
        self.each_command("sql/v1/../pipeline_a/q.sql", RULE_SQL)

    def test_dotdot_into_data_refused(self):
        self.each_command("sql/v1/../../data/00_raw/x.csv", RULE_DATA)

    def test_symlinked_file_into_data_refused(self):
        self.each_command("sql/v1/link.csv", RULE_DATA)

    def test_symlinked_directory_into_data_refused(self):
        self.each_command("sql/v1/datadir/00_raw/x.csv", RULE_DATA)

    def test_dotdot_after_a_symlink_is_resolved_by_the_filesystem(self):
        # The kernel opens data/secret.csv; folding ".." first would have read it as sql/v1/secret.csv.
        self.each_command("sql/v1/rawdir/../secret.csv", RULE_DATA)

    def test_record_bound_to_a_refused_path_can_move_into_a_reviewed_directory(self):
        old, slug = "sql/pipeline_a/q.sql", "sql__pipeline_a__q"
        self.p.write_json(slug, "review.json", review_doc(slug, old))
        self.refused(["move", "sql/v1/q.sql", "sql/pipeline_a/q.sql"], RULE_SQL)
        r = run(["move", old, "sql/v2.1/q.sql"], self.root)
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertEqual(r.stdout.strip().split("\t"), ["moved", slug, "sql__v2.1__q", "sql/v2.1/q.sql"])
        self.assertNotIn(MARKER, r.stdout + r.stderr)

    def test_paths_outside_the_project_root_refused(self):
        other = Path(self._tmp.name).parent / (Path(self._tmp.name).name + "-other")
        (other / "data/00_raw").mkdir(parents=True)
        (other / "data/00_raw/x.csv").write_text(f"id,value\n1,{MARKER}\n")
        self.addCleanup(lambda: __import__("shutil").rmtree(other, ignore_errors=True))
        os.symlink(other / "data/00_raw/x.csv", self.root / "sql/v1/out.csv")
        rule = "outside the project root"
        rel = f"../{other.name}/data/00_raw/x.csv"
        self.each_command(rel, rule)
        self.each_command(str(other / "data/00_raw/x.csv"), rule)
        self.each_command("sql/v1/out.csv", rule)

    def test_notes_accepts_only_a_helper_marked_render(self):
        import hashlib
        with tempfile.TemporaryDirectory(prefix="sqlreview-notes.") as tmp:
            f = Path(tmp) / "current.sql"
            f.write_text(SQL_V1)
            # A forged directory with the helper's name and mode, but no marker: refused.
            self.assertEqual(run(["notes", str(f)], self.root).returncode, 2)
            marker = Path(str(f) + ".sqlreview-render")
            marker.write_text("0" * 64 + "\n")
            self.assertEqual(run(["notes", str(f)], self.root).returncode, 2)
            marker.write_text(hashlib.sha256(SQL_V1.encode()).hexdigest() + "\n")
            self.assertEqual(run(["notes", str(f)], self.root).returncode, 0)
            self.assertEqual(run(["slug", str(f)], self.root).returncode, 2)
            f.write_text(SQL_V1 + "-- edited after marking\n")
            self.assertEqual(run(["notes", str(f)], self.root).returncode, 2)

    def test_hard_link_from_data_is_refused(self):
        os.link(self.root / "data/00_raw/x.csv", self.root / "sql/v1/hl.csv")
        self.each_command("sql/v1/hl.csv", "hard links")

    def test_intake_drafts_argument_is_guarded(self):
        self.p.sql("data/secret.sql", f"-- {MARKER}\n")
        for drafts in ("data/secret.sql", "sql/pipeline_a/q.sql", "../outside.json"):
            r = run(["intake", "sql/v1/missing.json", "1", drafts], self.root)
            self.assertEqual(r.returncode, 2, (drafts, r.stderr))
            self.assertIn("refused", r.stderr)
            self.assertNotIn(MARKER, r.stdout + r.stderr)
            self.assertEqual(r.stdout, "")
        os.symlink("../../data/secret.sql", self.root / "sql/v1/drafts.json")
        r = run(["intake", "sql/v1/missing.json", "1", "sql/v1/drafts.json"], self.root)
        self.assertEqual(r.returncode, 2, r.stderr)
        self.assertNotIn(MARKER, r.stdout + r.stderr)

    def test_publish_refuses_a_draft_file_under_data(self):
        slug = "sql__v1__q"
        self.p.sql("data/scope.json", json.dumps(scope_doc(slug, "sql/v1/q.sql")))
        self.p.review_dir(slug)
        before = tree(self.root)
        r = run(["publish", slug, "scope", "data/scope.json"], self.root)
        self.assertEqual(r.returncode, 2, r.stderr)
        self.assertIn(RULE_DATA, r.stderr)
        self.assertNotIn(MARKER, r.stdout + r.stderr)
        self.assertEqual(tree(self.root), before)

    def test_unresolvable_path_fails_closed(self):
        self.each_command("sql/v1/loop/q.sql", "cannot be resolved")

    def test_notes_from_a_subdirectory_is_checked_against_the_project_root(self):
        before = tree(self.root)
        r = run(["notes", "../../data/00_raw/x.csv"], self.root / "sql" / "v1")
        self.assertEqual(r.returncode, 2, r.stderr)
        self.assertIn(RULE_DATA, r.stderr)
        self.assertNotIn(MARKER, r.stdout + r.stderr)
        self.assertEqual(tree(self.root), before)

    def test_intake_sidecar_under_data_refused(self):
        self.p.sql("data/answers.intake.json", f'{{"x": "{MARKER}"}}')
        r = run(["intake", "data/answers.intake.json", "1"], self.root)
        self.assertEqual(r.returncode, 2, r.stderr)
        self.assertIn(RULE_DATA, r.stderr)
        self.assertNotIn(MARKER, r.stdout + r.stderr)

    def test_sql_path_in_a_draft_is_checked_on_publish(self):
        draft = self.root / ".sqlreview" / "reviews" / "sql__pipeline_a__q" / "review.draft.json"
        draft.parent.mkdir(parents=True)
        draft.write_text(json.dumps(review_doc("sql__pipeline_a__q", "sql/pipeline_a/q.sql", assumptions=[item("A1", "x")])))
        r = run(["publish", "sql__pipeline_a__q", "review", str(draft)], self.root)
        self.assertEqual(r.returncode, 2, r.stderr)
        self.assertIn(RULE_SQL, r.stderr)
        self.assertNotIn(MARKER, r.stdout + r.stderr)
        self.assertFalse((draft.parent / "review.json").exists())


class ReviewedTreePasses(unittest.TestCase):
    def test_reviewed_version_directories_pass(self):
        with tempfile.TemporaryDirectory() as tmp:
            p = Project(tmp)
            rels = ("sql/v1/q.sql", "sql/v2.1/q.sql", "sql/v3-1/q.sql", "sql/v10.2-3/q.sql")
            for rel in rels:
                p.sql(rel, SQL_V1)
            p.commit()
            for rel in rels:
                with self.subTest(rel=rel):
                    r = run(["fingerprint", rel], p.root)
                    self.assertEqual(r.returncode, 0, r.stderr)
                    self.assertIn(f'"sql_path": "{rel}"', r.stdout)
                    r = run(["notes", rel], p.root)
                    self.assertEqual(r.returncode, 0, r.stderr)
                    self.assertIn('"present": false', r.stdout)
                    r = run(["slug", rel], p.root)
                    self.assertEqual(r.returncode, 0, r.stderr)

    def test_helper_render_writes_the_marker_notes_accepts(self):
        with tempfile.TemporaryDirectory() as proj, tempfile.TemporaryDirectory() as tmp:
            p = Project(proj)
            p.sql("sql/v1/q.sql", SQL_V1)
            p.commit("v1")
            out = Path(tmp) / "current.sql"
            script = (f'. "{SCRIPT.parent}/sqlreview-lib.sh"; SR_ROOT="{p.root}"; sr_source_clean || exit $?; '
                      f'sr_source_render HEAD sql/v1/q.sql "{out}" || exit $?')
            r = subprocess.run(["bash", "-c", script], cwd=p.root, capture_output=True, text=True)
            self.assertEqual(r.returncode, 0, r.stderr)
            self.assertTrue(Path(str(out) + ".sqlreview-render").is_file())
            self.assertEqual(run(["notes", str(out)], p.root).returncode, 0)

    def test_paths_outside_data_and_sql_are_unaffected(self):
        with tempfile.TemporaryDirectory() as tmp:
            p = Project(tmp)
            p.sql("reports/monthly.sql", SQL_V1)
            p.commit()
            self.assertEqual(run(["fingerprint", "reports/monthly.sql"], p.root).returncode, 0)


if __name__ == "__main__":
    unittest.main()
