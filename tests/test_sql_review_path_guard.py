"""Issue 516: sqlreview.sh refuses to read researcher-value paths into the committed .sqlreview/.

Files under data/ and pipeline SQL under sql/<name>/ can hold cohort values, so only a reviewed
sql/v<N>/ tree (the scaffold's rule: v[0-9]+([.-][0-9]+)*) may be fingerprinted, snapshotted,
slugged, moved or parsed for notes. The path is canonicalised first (".." and symlinks resolved),
an unresolvable path fails closed, and the message names the rule, never file content.
"""
import hashlib
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

    def test_move_archives_the_refused_binding_and_status_still_lists_it(self):
        # A record bound to a refused path moves into a reviewed directory. The history entry that
        # move keeps still names the old path, and materialize must rebuild that revision from Git.
        with tempfile.TemporaryDirectory() as proj, tempfile.TemporaryDirectory() as tmp:
            p = Project(proj)
            p.sql("sql/v1/q.sql", SQL_V1)
            p.sql("sql/pipeline_a/q.sql", SQL_V1)
            p.commit("sources")
            fp = json.loads(run(["fingerprint", "sql/v1/q.sql"], p.root).stdout)
            slug, old, new = "sql__pipeline_a__q", "sql/pipeline_a/q.sql", "sql/v2/q.sql"
            doc = review_doc(slug, **fp)
            # The guard now refuses to publish the old path, so the fixture writes the record under a
            # reviewed path and then rebinds it, as an older helper would have left it.
            fixed = dict(doc, sql_path="sql/v1/q.sql", slug="sql__v1__q")
            draft = p.write_json("sql__v1__q", "review.draft.json", fixed)
            r = run(["publish", "sql__v1__q", "review", str(draft)], p.root)
            self.assertEqual(r.returncode, 0, r.stderr)
            (p.root / ".sqlreview/reviews/sql__v1__q/review.draft.json").unlink()
            (p.root / ".sqlreview/reviews/sql__v1__q").rename(p.root / ".sqlreview/reviews" / slug)
            rec = p.root / ".sqlreview/reviews" / slug / "review.json"
            rec.write_text(json.dumps(dict(json.loads(rec.read_text()), sql_path=old, slug=slug), indent=2))
            p.commit("record")
            status = run(["status", "--json"], p.root)
            self.assertEqual(status.returncode, 0, status.stderr)
            self.assertIn(slug, status.stdout)
            r = run(["move", old, new], p.root)
            self.assertEqual(r.returncode, 0, r.stderr)
            archived = p.root / ".sqlreview/reviews/sql__v2__q/history/review/1.json"
            self.assertEqual(json.loads(archived.read_text())["sql_path"], old)
            out = Path(tmp) / "old.sql"
            r = run(["materialize", "sql__v2__q", "review", "1", str(out)], p.root)
            self.assertEqual(r.returncode, 0, r.stderr)
            self.assertEqual(out.read_text(), SQL_V1)
            # The render of a record bound to a refused path carries no marker, so notes refuses it (#516).
            self.assertFalse(Path(str(out) + ".sqlreview-render").exists())
            r = run(["notes", str(out)], p.root)
            self.assertEqual(r.returncode, 2, r.stdout + r.stderr)
            self.assertIn("refused", r.stderr)

    def test_no_initialised_root_fails_closed_for_notes_and_the_other_file_arguments(self):
        # From a directory with no .sqlreview/ above it, the cwd must not become the project root:
        # `notes proj/data/cohort.sql` used to be accepted from $HOME.
        with tempfile.TemporaryDirectory() as home:
            home = Path(home)
            (home / "proj/data").mkdir(parents=True)
            (home / "proj/data/cohort.sql").write_text(f"SELECT '{MARKER}';\n")
            (home / "proj/sql/v1").mkdir(parents=True)
            (home / "proj/sql/v1/q.sql").write_text(SQL_V1)
            env = {k: v for k, v in os.environ.items() if not k.startswith("SQLREVIEW_")}
            for args in (["notes", "proj/data/cohort.sql"], ["notes", "proj/sql/v1/q.sql"],
                         ["check", "proj/data/cohort.sql"], ["lint", "proj/data/cohort.sql"]):
                r = subprocess.run(["bash", str(SCRIPT), *args], cwd=home, env=env, capture_output=True, text=True)
                self.assertEqual(r.returncode, 2, (args, r.stdout, r.stderr))
                self.assertIn("no initialised", r.stderr)
                self.assertNotIn(MARKER, r.stdout + r.stderr)
                self.assertNotIn("cohort.sql", r.stderr)
                self.assertEqual(r.stdout, "")
            # init still works there, since it takes no file argument.
            r = subprocess.run(["bash", str(SCRIPT), "init"], cwd=home, env=env, capture_output=True, text=True)
            self.assertEqual(r.returncode, 0, r.stderr)

    def test_dotdot_after_a_symlink_that_folds_to_forbidden_sql_is_refused(self):
        # sql/pipeline_a/link -> ../v1/sub: the kernel opens link/../q.sql as sql/v1/q.sql (reviewed), but the
        # lexical fold is sql/pipeline_a/q.sql (pipeline SQL). Callers use the folded form, so the pair is refused.
        (self.root / "sql/v1/sub").mkdir()
        os.symlink("../v1/sub", self.root / "sql/pipeline_a/link")
        path = "sql/pipeline_a/link/../q.sql"
        rule = "no .. after a symlink"
        self.refused(["fingerprint", path], rule)
        self.refused(["slug", path], rule)
        self.refused(["snapshot", "any", path], rule)
        self.refused(["notes", path], rule)
        self.refused(["move", "sql/v1/q.sql", path], rule)
        self.refused(["lint", path], rule)
        self.refused(["criteria", "sql/pipeline_a/link/../draft.json"], rule)
        # The same link used without a following .. is judged by where it leads, as before.
        self.assertEqual(run(["fingerprint", "sql/pipeline_a/link/../../v1/q.sql"], self.root).returncode, 2)

    def test_status_keeps_the_state_of_a_record_bound_to_a_refused_path(self):
        # A scope that passes check but names pipeline SQL must not turn `invalid` in status: the real state
        # stays visible so the engineer can move the record into sql/v<N>/. Writes keep the policy.
        slug, old = "sql__pipeline_a__q", "sql/pipeline_a/q.sql"
        self.p.write_json(slug, "scope.json", scope_doc(slug, old))
        self.assertEqual(run(["check", str(self.root / ".sqlreview/reviews" / slug / "scope.json")], self.root).returncode, 0)
        status = run(["status", "--json"], self.root)
        self.assertEqual(status.returncode, 0, status.stderr)
        rows = [r for r in json.loads(status.stdout)["reviews"] if r["slug"] == slug]
        self.assertEqual(len(rows), 1, status.stdout)
        self.assertEqual(rows[0]["state"], "scoped", rows[0])
        self.assertEqual(rows[0]["sql_path"], old)
        self.assertNotIn(MARKER, status.stdout + status.stderr)
        # The read command and the write commands still refuse the path.
        self.refused(["questions", slug], RULE_SQL)
        self.refused(["migrate-questions", slug], RULE_SQL)

    def test_status_path_adds_no_canonicalisation(self):
        # The SessionStart hook has a 5 second limit, so status must not run the canonical check per folder.
        # status reads stored paths through sr_state, which must use only the structural check.
        lib = (SCRIPTS / "sqlreview-lib.sh").read_text()
        body = lib[lib.index("sr_state() {"):lib.index("# Why a review is invalid or missing")]
        self.assertIn("sr_safe_path", body)
        for name in ("sr_safe_sql", "sr_refuse_unreviewed", "sr_guard_input", "sr_realpath_m"):
            self.assertNotIn(name, body)

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

    def test_control_characters_in_a_path_are_refused(self):
        # Command substitution strips a trailing newline, so "alias.sql<LF>" would be checked as
        # "alias.sql" while the shell opens the other file. Refuse the character, not just the leak.
        os.symlink("../../data/secret.json", self.root / "sql/v1/alias.sql\n")
        self.p.sql("data/secret.json", json.dumps({"x": MARKER}))
        self.p.write_json("sql__v1__q", "scope.json", scope_doc("sql__v1__q", "sql/v1/q.sql"))
        names = {"trailing newline": "sql/v1/alias.sql\n", "embedded newline": "sql/v1/al\nias.sql",
                 "carriage return": "sql/v1/alias.sql\r", "tab": "sql/v1/al\tias.sql"}
        for label, name in names.items():
            self.p.sql(name, SQL_V1) if "alias.sql\n" != name else None
            for command, args in (("notes", [name]), ("publish-questions", ["sql__v1__q", name]),
                                  ("fingerprint", [name]), ("check", [name])):
                with self.subTest(label=label, command=command):
                    before = tree(self.root)
                    r = run([command, *args], self.root)
                    self.assertEqual(r.returncode, 2, (r.stdout, r.stderr))
                    self.assertIn("control character", r.stderr)
                    self.assertNotIn(MARKER, r.stdout + r.stderr)
                    self.assertEqual(r.stdout, "")
                    self.assertEqual(tree(self.root), before)

    def test_symlink_target_with_a_newline_fails_closed(self):
        os.symlink("../../data/secret.json\n", self.root / "sql/v1/tgt.sql")
        self.p.sql("data/secret.json", json.dumps({"x": MARKER}))
        r = run(["notes", "sql/v1/tgt.sql"], self.root)
        self.assertEqual(r.returncode, 2, r.stderr)
        self.assertNotIn(MARKER, r.stdout + r.stderr)

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


SCRIPTS = SCRIPT.parent
D = "data/secret.json"
SLUG = "sql__v1__q"
# Every subcommand and the arguments that hand it a refused data/ file. NOINPUT marks commands
# whose only inputs are slugs and project SQL paths, or that only write a path; the walk below
# fails when a dispatch entry is in neither table, so a new subcommand needs a decision here.
SQLREVIEW_INPUTS = {
    "check": [[D]],
    "lint": [[D], ["--ste", D]],
    "carryover": [[SLUG, D]],
    "carryforward": [[SLUG, "scope", D]],
    "remap": [[SLUG, D]],
    "publish": [[SLUG, "review", D]],
    "publish-questions": [[SLUG, D]],
    "intake": [["sql/v1/missing.json", "1", D], [D, "1"]],
    "notes": [[D], ["sql/v1/q.sql", "--against", D], ["sql/v1/q.sql", "--questions", D]],
    "ledger": [["check", D], ["set", "nq-rdl/x#1", D], ["get", "nq-rdl/x#1", "--against", D],
               ["--session", "check", D]],
    "slug": [[D]],
    "fingerprint": [[D]],
    "snapshot": [[SLUG, D]],
    "move": [["sql/v1/q.sql", D]],
    "criteria": [[D]],
}
SQLREVIEW_NOINPUT = {"init", "status", "roles", "guard", "lifts-stale", "materialize", "delta", "impact",
                     "questions", "migrate-questions", "render", "discard-draft"}
RELEASE_INPUTS = {"check": [[D]], "render": [[D]], "amend-check": [[D], ["--name", "r", D]]}
# criteria reads a --fingerprints file of four sha256 strings that it validates strictly, so no value can pass through.
# fetch-command takes no argument and reads only the remotes.
RELEASE_NOINPUT = {"evidence", "criteria", "fetch-command"}
RECURRING_INPUTS = {"match": [[D], ["--any-kind", D]], "marked": [[D], ["sql/v1/q.sql", D]]}
RECURRING_NOINPUT = {"list"}


def dispatched(script, pattern):
    """Command names in a script's final dispatch `case`."""
    import re
    text = (SCRIPTS / script).read_text()
    tail = text[text.rindex('case "$cmd" in'):]
    return {m.group(1) for m in re.finditer(pattern, tail, re.M)}


class RootDiscovery(unittest.TestCase):
    """The project that governs a file is found from the file, not from the cwd (Codex round 2 on #552)."""

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.parent = Path(os.path.realpath(self._tmp.name))
        self.env = {k: v for k, v in os.environ.items() if not k.startswith("SQLREVIEW_")}

    def sh(self, script, args, cwd):
        return subprocess.run(["bash", str(SCRIPTS / script), *args], cwd=cwd, env=self.env,
                              capture_output=True, text=True, timeout=60)

    def project(self, name="proj"):
        (self.parent / name).mkdir(parents=True, exist_ok=True)
        p = Project(self.parent / name)
        p.sql("data/cohort.sql", f"-- {MARKER}\n{SQL_V1}")
        p.sql("sql/pipeline_a/q.sql", f"-- {MARKER}\n{SQL_V1}")
        p.sql("sql/v1/q.sql", SQL_V1)
        p.commit()
        os.symlink("data", p.root / "inputs")
        os.symlink("sql/pipeline_a", p.root / "pipe")
        return p

    def refused(self, script, args, cwd, rule):
        r = self.sh(script, args, cwd)
        self.assertEqual(r.returncode, 2, (script, args, r.stdout, r.stderr))
        self.assertIn(rule, r.stderr)
        self.assertNotIn(MARKER, r.stdout + r.stderr)
        self.assertEqual(r.stdout, "")

    def test_alias_to_data_is_refused_from_the_parent_of_the_project(self):
        self.project()
        for args in (["notes", "proj/inputs/cohort.sql"], ["check", "proj/inputs/cohort.sql"],
                     ["lint", "proj/inputs/cohort.sql"], ["notes", "proj/data/cohort.sql"]):
            with self.subTest(args=args):
                self.refused("sqlreview.sh", args, self.parent, RULE_DATA)
        self.refused("release.sh", ["check", "proj/inputs/cohort.sql"], self.parent, RULE_DATA)
        self.refused("recurring-decisions.sh", ["match", "proj/inputs/cohort.sql"], self.parent, RULE_DATA)

    def test_alias_to_pipeline_sql_is_refused_from_the_parent_of_the_project(self):
        self.project()
        self.refused("sqlreview.sh", ["notes", "proj/pipe/q.sql"], self.parent, RULE_SQL)
        self.refused("sqlreview.sh", ["notes", "proj/sql/pipeline_a/q.sql"], self.parent, RULE_SQL)
        # A reviewed directory in the same project is not refused by the data or sql rules.
        r = self.sh("sqlreview.sh", ["notes", "proj/sql/v1/q.sql"], self.parent)
        self.assertEqual(r.returncode, 0, r.stderr)

    def test_alias_into_data_with_no_project_anywhere_is_refused(self):
        (self.parent / "bare/data").mkdir(parents=True)
        (self.parent / "bare/data/cohort.sql").write_text(f"-- {MARKER}\n{SQL_V1}")
        os.symlink("data", self.parent / "bare/inputs")
        self.refused("sqlreview.sh", ["notes", "bare/inputs/cohort.sql"], self.parent,
                     "no initialised .sqlreview/ project is found")

    def test_a_plain_scratch_file_with_no_project_still_works(self):
        (self.parent / "scratch").mkdir()
        (self.parent / "scratch/q.sql").write_text(SQL_V1)
        for cwd, arg in ((self.parent / "scratch", "q.sql"), (self.parent, "scratch/q.sql")):
            r = self.sh("sqlreview.sh", ["notes", arg], cwd)
            self.assertEqual(r.returncode, 0, r.stderr)

    def test_a_nested_project_does_not_hide_the_outer_projects_data(self):
        # cwd is in an inner initialised project: the outer project's data/ is still data/.
        outer = self.project("outer")
        (outer.root / "inner").mkdir()
        inner = Project(outer.root / "inner", git_repo=False, init=False)
        (inner.root / ".sqlreview/reviews").mkdir(parents=True)  # init would find the outer project instead
        inner.sql("q.sql", SQL_V1)
        self.refused("sqlreview.sh", ["notes", "../data/cohort.sql"], inner.root, RULE_DATA)
        self.refused("release.sh", ["check", "../data/cohort.sql"], inner.root, RULE_DATA)
        self.refused("recurring-decisions.sh", ["match", "../data/cohort.sql"], inner.root, RULE_DATA)

    def test_another_projects_data_is_refused_in_outside_ok_modes(self):
        a, b = self.project("a"), self.project("b")
        self.refused("release.sh", ["check", "../a/data/cohort.sql"], b.root, RULE_DATA)
        self.refused("release.sh", ["amend-check", "../a/inputs/cohort.sql"], b.root, RULE_DATA)
        # SQLREVIEW_ROOT may name a different project than the file's own: the file's project still governs it.
        self.env["SQLREVIEW_ROOT"] = str(b.root)
        self.refused("release.sh", ["check", str(a.root / "inputs/cohort.sql")], self.parent, RULE_DATA)
        self.refused("sqlreview.sh", ["notes", str(a.root / "inputs/cohort.sql")], self.parent, RULE_DATA)

    def test_a_planted_inner_root_does_not_launder_data(self):
        # `init` inside data/ makes data/ look like a project root; the outer project's rule still applies.
        p = self.project()
        (p.root / "data/.sqlreview").mkdir()
        self.refused("sqlreview.sh", ["notes", "data/cohort.sql"], p.root, RULE_DATA)
        self.refused("sqlreview.sh", ["notes", "proj/data/cohort.sql"], self.parent, RULE_DATA)


class EveryEntryPoint(unittest.TestCase):
    """Issue 516 root cause: one unguarded entry point at a time kept being found, so walk them all."""

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.p = Project(self._tmp.name)
        self.root = self.p.root
        self.p.sql("data/secret.json", json.dumps({"x": MARKER}))
        self.p.sql("sql/v1/q.sql", SQL_V1)
        self.p.review_dir(SLUG)
        self.p.commit()

    def assert_refused(self, script, command, args):
        before = tree(self.root)
        r = subprocess.run(["bash", str(SCRIPTS / script), command, *args], cwd=self.root,
                           capture_output=True, text=True, timeout=60,
                           env={k: v for k, v in os.environ.items() if not k.startswith("SQLREVIEW_")})
        label = (script, command, args)
        self.assertEqual(r.returncode, 2, (label, r.stdout, r.stderr))
        self.assertIn("refused", r.stderr, label)
        self.assertIn(RULE_DATA, r.stderr, label)
        self.assertNotIn(MARKER, r.stdout + r.stderr, label)
        self.assertEqual(r.stdout, "", label)
        self.assertEqual(tree(self.root), before, label)

    def walk(self, script, pattern, inputs, noinput):
        commands = dispatched(script, pattern) - {"help"}
        self.assertEqual(commands - set(inputs) - noinput, set(),
                         f"{script}: new subcommand without a guard decision in this test")
        self.assertEqual((set(inputs) | noinput) - commands, set(), f"{script}: stale entry")
        self.assertEqual(set(inputs) & noinput, set())
        for command, variants in inputs.items():
            for args in variants:
                with self.subTest(script=script, command=command, args=args):
                    self.assert_refused(script, command, args)

    def test_sqlreview(self):
        self.walk("sqlreview.sh", r"^  ([a-z][a-z-]*)\) .*cmd_", SQLREVIEW_INPUTS, SQLREVIEW_NOINPUT)

    def test_release(self):
        self.walk("release.sh", r"^  ([a-z][a-z-]*)\) cmd_", RELEASE_INPUTS, RELEASE_NOINPUT)

    def test_recurring_decisions(self):
        self.walk("recurring-decisions.sh", r"^  ([a-z][a-z-]*)\) cmd_", RECURRING_INPUTS, RECURRING_NOINPUT)

    def test_publish_questions_copies_nothing_from_data(self):
        self.p.write_json(SLUG, "scope.json", scope_doc(SLUG, "sql/v1/q.sql"))
        self.assert_refused("sqlreview.sh", "publish-questions", [SLUG, D])
        self.assertFalse((self.root / ".sqlreview/reviews" / SLUG / "questions.json").exists())


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

    def test_notes_accepts_only_a_render_with_a_matching_marker(self):
        with tempfile.TemporaryDirectory() as proj, tempfile.TemporaryDirectory() as tmp:
            p = Project(proj)
            p.sql("sql/v1/q.sql", SQL_V1)
            p.commit("v1")
            out = Path(tmp) / "current.sql"
            out.write_text(SQL_V1)
            self.assertEqual(run(["notes", str(out)], p.root).returncode, 2)  # no marker
            marker = Path(str(out) + ".sqlreview-render")
            marker.write_text(hashlib.sha256(out.read_bytes()).hexdigest() + "\n")
            self.assertEqual(run(["notes", str(out)], p.root).returncode, 0)
            out.write_text(SQL_V1 + "-- edited\n")  # changed after marking
            self.assertEqual(run(["notes", str(out)], p.root).returncode, 2)

    def test_paths_outside_data_and_sql_are_unaffected(self):
        with tempfile.TemporaryDirectory() as tmp:
            p = Project(tmp)
            p.sql("reports/monthly.sql", SQL_V1)
            p.commit()
            self.assertEqual(run(["fingerprint", "reports/monthly.sql"], p.root).returncode, 0)


if __name__ == "__main__":
    unittest.main()
