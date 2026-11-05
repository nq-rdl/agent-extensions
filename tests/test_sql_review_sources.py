"""Committed SQL source: old SQL comes from git at the recorded commit, never from .sqlreview/."""
import json
import os
import re
import subprocess
import shutil
import tempfile
import unittest
from pathlib import Path

from test_sql_review_scripts import Project, REPO, git, run, review_doc, scope_doc, item

SCRIPTS = REPO / "skills/data-request-setup/scripts"


def committed(project):
    """Commit fixture inputs when changed; retain HEAD for repeated reads."""
    git(project.root, "add", "-A")
    pending = subprocess.run(["git", "diff", "--cached", "--quiet"], cwd=project.root, capture_output=True)
    if pending.returncode:
        git(project.root, "commit", "-q", "-m", "fixture sources")
    return git(project.root, "rev-parse", "HEAD").stdout.strip()


class Sources(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.p = Project(self.tmp.name)

    def committed(self, payload=b"SELECT 1;\n", source="builder"):
        # A scaffold child commits builder SQL. provenance.json never selects another route.
        p = self.p
        (p.root / "sql/v1").mkdir(parents=True, exist_ok=True)
        (p.root / "sql/v1/request.sql").write_bytes(payload)
        if source is not None:
            (p.root / "sql/provenance.json").write_text(json.dumps({
                "schema": 1, "requests": {"sql/v1/request.sql": {"source": source}}}))
        return p.commit()

    def fingerprint(self):
        return run(["fingerprint", "sql/v1/request.sql"], self.p.root)

    def publish_committed(self, payload=b"SELECT 1;\nSELECT 3;\n"):
        self.committed(payload)
        fp = json.loads(self.fingerprint().stdout)
        doc = review_doc("sql__v1__request", **fp,
                         assumptions=[item("A1", "Retain this range", location={"lines": [2, 2]})],
                         limitations=[], logic=[])
        draft = self.p.write_json("sql__v1__request", "review.draft.json", doc)
        r = run(["publish", "sql__v1__request", "review", str(draft)], self.p.root)
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        return draft, doc

    def change_sql(self, payload, commit=True):
        (self.p.root / "sql/v1/request.sql").write_bytes(payload)
        if commit:
            self.p.commit("SQL update")

    def evidence(self, ref):
        return subprocess.run(["bash", str(SCRIPTS / "release.sh"), "evidence", ref],
                              cwd=self.p.root, capture_output=True, text=True)

    def test_every_provenance_source_fingerprints_committed_sql(self):
        for source in ("builder", "cohort", "spec", "hand-written", None):
            with self.subTest(source=source):
                self.committed(b"SELECT 1;\n-- " + str(source).encode() + b"\n", source)
                r = self.fingerprint()
                self.assertEqual(r.returncode, 0, r.stderr)
                fp = json.loads(r.stdout)
                self.assertEqual(fp["git_commit"], git(self.p.root, "rev-parse", "HEAD").stdout.strip())
                self.assertIs(fp["git_dirty"], False)
                self.assertNotIn("sql_provenance", fp)

    def test_fingerprint_refuses_dirty_untracked_or_ignored_sql(self):
        self.committed()
        self.change_sql(b"SELECT 2;\n", commit=False)
        self.assertEqual(self.fingerprint().returncode, 2)
        git(self.p.root, "checkout", "--", "sql/v1/request.sql")
        (self.p.root / ".gitignore").write_text("sql/v1/ignored.sql\n")
        (self.p.root / "sql/v1/ignored.sql").write_text("SELECT 1;\n")
        self.p.commit("ignore")
        r = run(["fingerprint", "sql/v1/ignored.sql"], self.p.root)
        self.assertEqual(r.returncode, 2, r.stderr)
        self.assertIn("not committed", r.stderr)

    def test_status_compares_hashes_without_git(self):
        self.publish_committed()
        with tempfile.TemporaryDirectory() as bindir:
            shim = Path(bindir) / "git"
            shim.write_text("#!/bin/sh\nexit 97\n")
            shim.chmod(0o755)
            env = {"PATH": bindir + os.pathsep + os.environ["PATH"]}
            for payload, state in ((None, "current"), (b"-- header\nSELECT 1;\nSELECT 3;\n", "header-only"),
                                   (b"SELECT 2;\nSELECT 3;\n", "stale")):
                if payload is not None:
                    self.change_sql(payload, commit=False)  # uncommitted edits never block status
                r = run(["status", "--json"], self.p.root, env=env)
                self.assertEqual(r.returncode, 0, r.stderr)
                self.assertEqual(json.loads(r.stdout)["reviews"][0]["state"], state)

    def test_status_reports_records_without_clean_commit_as_no_baseline(self):
        draft, doc = self.publish_committed()
        for over in ({"git_commit": None}, {"git_dirty": True}):
            draft.with_name("review.json").write_text(json.dumps(dict(doc, **over)))
            r = run(["status", "--json"], self.p.root)
            self.assertEqual(json.loads(r.stdout)["reviews"][0]["state"], "no-baseline")
            self.assertEqual(run(["delta", "sql__v1__request"], self.p.root).returncode, 6)

    def test_materialize_exact_revision(self):
        draft, doc = self.publish_committed()
        self.change_sql(b"SELECT 2;\nSELECT 3;\n")
        doc = dict(doc, revision=2, **json.loads(self.fingerprint().stdout))
        doc["assumptions"][0]["confirmed_revision"] = 2
        draft.write_text(json.dumps(doc))
        r = run(["publish", "sql__v1__request", "review", str(draft)], self.p.root)
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        with tempfile.TemporaryDirectory() as tmp:
            output = Path(tmp) / "explained.sql"
            for revision, data in ((1, b"SELECT 1;\nSELECT 3;\n"), (2, b"SELECT 2;\nSELECT 3;\n")):
                r = run(["materialize", "sql__v1__request", "review", str(revision), str(output)], self.p.root)
                self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
                self.assertEqual(output.read_bytes(), data)
                output.unlink()
            r = run(["materialize", "sql__v1__request", "review", "3", str(output)], self.p.root)
            self.assertEqual(r.returncode, 6, r.stdout + r.stderr)
            self.assertFalse(output.exists())
        self.assertEqual(list((self.p.root / ".sqlreview").rglob("*.sql")), [])

    def explain_walk_block(self):
        """The fenced bash block of the explain skill that diffs the previous and reviewed revisions."""
        body = (REPO / "skills/data-request-explain/SKILL.md").read_text()
        blocks = [b for b in re.findall(r"```bash\n(.*?)```", body, re.S) if "git diff --no-index" in b]
        self.assertEqual(len(blocks), 1, "exactly one explain block shows the line diff")
        for command in ('materialize "$SLUG" review "$PREVIOUS" "$T/previous.sql"',
                        'materialize "$SLUG" review "$REVISION" "$T/reviewed.sql"',
                        'git diff --no-index -- "$T/previous.sql" "$T/reviewed.sql"'):
            self.assertIn(command, blocks[0])
        return blocks[0]

    def test_explain_walk_shows_a_line_diff_between_reviewed_revisions(self):
        # #505 criterion 2: the shipped explain block, run as written, prints the change as - and + lines.
        block = self.explain_walk_block()
        draft, doc = self.publish_committed()
        self.change_sql(b"SELECT 2;\nSELECT 3;\n")
        doc = dict(doc, revision=2, **json.loads(self.fingerprint().stdout))
        doc["assumptions"][0]["confirmed_revision"] = 2
        draft.write_text(json.dumps(doc))
        r = run(["publish", "sql__request", "review", str(draft)], self.p.root)
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        explain = self.p.root / ".sqlreview/reviews/sql__request/explain.json"
        explain.write_text(json.dumps({"review_revision": 1}))
        env = dict(os.environ, S=str(SCRIPTS), SLUG="sql__request")
        walk = subprocess.run(["bash", "-c", block], cwd=self.p.root, env=env, capture_output=True, text=True)
        self.assertEqual(walk.returncode, 0, walk.stdout + walk.stderr)
        lines = walk.stdout.splitlines()
        self.assertIn("-SELECT 1;", lines)
        self.assertIn("+SELECT 2;", lines)
        self.assertNotIn("-SELECT 3;", lines)
        self.assertNotIn("+SELECT 3;", lines)
        self.assertEqual(list((self.p.root / ".sqlreview").rglob("*.sql")), [])

    def test_materialize_refuses_in_repo_output(self):
        self.publish_committed()
        for output in (self.p.root / "leaked.sql", self.p.root / ".sqlreview/reviews/sql__v1__request/source.sql"):
            r = run(["materialize", "sql__v1__request", "review", "1", str(output)], self.p.root)
            self.assertEqual(r.returncode, 2, r.stdout + r.stderr)
            self.assertFalse(output.exists())

    def test_materialize_replaces_external_hardlink_without_modifying_repository(self):
        self.publish_committed()
        alias = self.p.root / ".sqlreview/reviews/sql__v1__request/alias.sql"
        original = b"preserve repository bytes\n"
        alias.write_bytes(original)
        with tempfile.TemporaryDirectory() as tmp:
            output = Path(tmp) / "explained.sql"
            os.link(alias, output)
            r = run(["materialize", "sql__v1__request", "review", "1", str(output)], self.p.root)
            self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
            self.assertEqual(output.read_bytes(), b"SELECT 1;\nSELECT 3;\n")
            self.assertEqual(alias.read_bytes(), original)
            # The helper also writes the SHA-256 marker that lets notes read this render outside the project.
            self.assertEqual(sorted(Path(tmp).iterdir()), sorted([output, output.with_name(output.name + ".sqlreview-render")]))

    def test_materialize_never_writes_through_a_linked_render_marker(self):
        # A marker that is a hard link or a symlink must not make the helper overwrite the linked file.
        self.publish_committed()
        repo_file = self.p.root / "keep.txt"
        original = b"repository bytes\n"
        repo_file.write_bytes(original)
        for kind in ("hardlink", "symlink"):
            with self.subTest(kind=kind), tempfile.TemporaryDirectory() as tmp:
                output = Path(tmp) / "explained.sql"
                marker = Path(tmp) / "explained.sql.sqlreview-render"
                if kind == "hardlink":
                    os.link(repo_file, marker)
                else:
                    os.symlink(repo_file, marker)
                r = run(["materialize", "sql__v1__request", "review", "1", str(output)], self.p.root)
                self.assertEqual(repo_file.read_bytes(), original, r.stdout + r.stderr)
                if kind == "hardlink":
                    self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
                    self.assertFalse(marker.is_symlink())
                    self.assertEqual(len(marker.read_text().strip()), 64)
                    self.assertEqual(sorted(p.name for p in Path(tmp).iterdir()),
                                     ["explained.sql", "explained.sql.sqlreview-render"])
                else:
                    self.assertEqual(r.returncode, 2, r.stdout + r.stderr)
                    self.assertTrue(marker.is_symlink())

    def test_internal_renders_get_no_marker(self):
        # sr_source_show feeds evidence, publish, delta and impact workspaces. Only materialize marks its
        # output, so a committed pipeline file cannot become something notes or intake accepts (#516).
        old = self.committed()
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp) / "out.sql"
            env = dict(os.environ, SR_ROOT=str(self.p.root), SR_SCRIPT_DIR=str(SCRIPTS))
            r = subprocess.run(["bash", "-c", '. "$SR_SCRIPT_DIR/sqlreview-lib.sh"; sr_source_show "$@"',
                                "show", old, "sql/v1/request.sql", str(target)],
                               cwd=self.p.root, env=env, capture_output=True, text=True)
            self.assertEqual(r.returncode, 0, r.stderr)
            self.assertEqual(sorted(Path(tmp).iterdir()), [target])

    def test_corrupt_hash_is_unavailable_never_current(self):
        draft, doc = self.publish_committed()
        draft.with_name("review.json").write_text(json.dumps(dict(doc, sql_sha256="0" * 64)))
        with tempfile.TemporaryDirectory() as tmp:
            output = Path(tmp) / "unproved.sql"
            r = run(["materialize", "sql__v1__request", "review", "1", str(output)], self.p.root)
            self.assertEqual(r.returncode, 6, r.stdout + r.stderr)
            self.assertFalse(output.exists())
        r = run(["carryforward", "sql__v1__request", "review", str(draft)], self.p.root)
        self.assertEqual(r.returncode, 6, r.stdout + r.stderr)
        self.assertIn("full SHA mismatch", r.stderr)

    def test_release_evidence_reads_sql_from_git(self):
        draft, doc = self.publish_committed()
        reviewed = doc["git_commit"]
        self.change_sql(b"SELECT 2;\nSELECT 3;\n")
        for ref, expected, applies in ((reviewed, 0, "current"), ("HEAD", 10, "changed")):
            r = self.evidence(ref)
            self.assertEqual(r.returncode, expected, r.stdout + r.stderr)
            row = json.loads(r.stdout)["reviews"][0]
            self.assertEqual(row["applies"], applies)
            self.assertTrue(row["reviewed_commit_in_ref"])
        git(self.p.root, "rm", "-q", "sql/v1/request.sql")
        self.p.commit("drop SQL")
        self.assertEqual(json.loads(self.evidence("HEAD").stdout)["reviews"][0]["applies"], "missing-at-ref")
        draft.with_name("review.json").write_text(json.dumps(dict(doc, sql_sha256="0" * 64)))
        r = self.evidence(reviewed)
        self.assertEqual(r.returncode, 10, r.stdout + r.stderr)
        self.assertEqual(json.loads(r.stdout)["reviews"][0]["applies"], "unavailable")
        self.assertEqual(list((self.p.root / ".sqlreview").rglob("*.sql")), [])

    def test_release_evidence_lists_non_sql_changes_since_review(self):
        _, doc = self.publish_committed()
        row = json.loads(self.evidence("HEAD").stdout)["reviews"][0]
        self.assertEqual(row["other_paths_changed_since_review"], [])
        (self.p.root / "pipeline.py").write_text("EXPORT_FORMAT = 'csv'\n")
        self.p.commit("export change")
        r = self.evidence("HEAD")
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        row = json.loads(r.stdout)["reviews"][0]
        # The SQL is unchanged, so the review applies, but the export change is visible (#521).
        self.assertEqual(row["applies"], "current")
        self.assertEqual(row["other_paths_changed_since_review"], ["pipeline.py"])

    def test_two_commit_delta_and_impact_diff_sql_from_git(self):
        self.publish_committed(b"SELECT 1; -- shared_identifier\nSELECT shared_identifier;\n")
        self.change_sql(b"SELECT 2; -- shared_identifier\nSELECT shared_identifier;\n")
        with tempfile.TemporaryDirectory() as tmp:
            for command, expected in (("delta", 10), ("impact", 0)):
                r = run([command, "sql__v1__request"], self.p.root, env={"TMPDIR": tmp})
                self.assertEqual(r.returncode, expected, r.stdout + r.stderr)
                if command == "delta":
                    self.assertIn("-SELECT 1;", r.stdout)
                    self.assertIn("+SELECT 2;", r.stdout)
                else:
                    self.assertIn("shared_identifier\tline 2\tSELECT shared_identifier;", r.stdout)
                self.assertEqual(list(Path(tmp).iterdir()), [])
        self.assertEqual(list((self.p.root / ".sqlreview").rglob("*.sql")), [])

    def test_shifted_remap_and_unchanged_range_carry_retain_confirmation(self):
        draft, prior = self.publish_committed()
        self.change_sql(b"SET NOCOUNT ON;\nSELECT 2;\nSELECT 3;\n")
        doc = dict(prior, revision=2, **json.loads(self.fingerprint().stdout))
        draft.write_text(json.dumps(doc))
        r = run(["remap", "sql__v1__request", str(draft)], self.p.root)
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        doc = json.loads(draft.read_text())
        self.assertEqual(doc["assumptions"][0]["location"]["lines"], [3, 3])
        r = run(["carryforward", "sql__v1__request", "review", str(draft)], self.p.root)
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        row = json.loads(r.stdout)["carry"][0]
        self.assertEqual(row["basis"], "lines-unchanged")
        self.assertEqual(row["set"]["carried_from_revision"], 1)
        doc["assumptions"][0].update(row["set"])
        draft.write_text(json.dumps(doc))
        r = run(["publish", "sql__v1__request", "review", str(draft)], self.p.root)
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertEqual(list((self.p.root / ".sqlreview").rglob("*.sql")), [])

    def test_missing_commit_is_not_sql_absent(self):
        draft, doc = self.publish_committed()
        doc["git_commit"] = "f" * 40
        draft.with_name("review.json").write_text(json.dumps(doc))
        for command in (["carryforward", "sql__v1__request", "review", str(draft)], ["delta", "sql__v1__request"]):
            r = run(command, self.p.root)
            self.assertEqual(r.returncode, 6, r.stdout + r.stderr)
            self.assertNotIn("sql-absent", r.stdout)

    def test_no_sql_scope_keeps_intent_carry(self):
        self.p.commit()
        doc = scope_doc("sql__v1__request", "sql/v1/request.sql", sql_sha256=None)
        self.p.write_json("sql__v1__request", "scope.json", doc)
        draft = self.p.write_json("sql__v1__request", "scope.draft.json", dict(doc, revision=2))
        r = run(["carryforward", "sql__v1__request", "scope", str(draft)], self.p.root)
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertEqual(json.loads(r.stdout)["carry"][0]["basis"], "sql-absent")

    def test_nested_project_root_reads_its_own_path(self):
        nested = self.p.root / "nested"
        nested.mkdir()
        self.p = Project(nested, git_repo=False, init=False)
        self.assertEqual(run(["init"], nested, env={"SQLREVIEW_ROOT": str(nested)}).returncode, 0)
        old = self.committed()
        self.change_sql(b"SELECT 2;\n")
        with tempfile.TemporaryDirectory() as output:
            target = Path(output) / "out.sql"
            env = dict(os.environ, SR_ROOT=str(nested), SR_SCRIPT_DIR=str(SCRIPTS))
            r = subprocess.run(["bash", "-c", '. "$SR_SCRIPT_DIR/sqlreview-lib.sh"; sr_source_show "$@"',
                                "show", old, "sql/v1/request.sql", str(target)],
                               cwd=nested, env=env, capture_output=True, text=True)
            self.assertEqual(r.returncode, 0, r.stderr)
            self.assertEqual(target.read_bytes(), b"SELECT 1;\n")

    def test_symlinked_sql_and_replacement_refs_refused(self):
        head = self.committed()
        (self.p.root / "sql/v1/linked.sql").symlink_to("request.sql")
        self.p.commit("symlink")
        self.assertEqual(run(["fingerprint", "sql/v1/linked.sql"], self.p.root).returncode, 2)
        git(self.p.root, "replace", head, head)
        self.assertEqual(self.fingerprint().returncode, 2)

    def test_init_writes_store_ignore_for_legacy_sql_copies(self):
        with tempfile.TemporaryDirectory() as tmp:
            p = Project(tmp, init=False)
            r = run(["init"], p.root)
            self.assertEqual(r.returncode, 0, r.stderr)
            self.assertIn("file\t.gitignore", r.stdout)
            self.assertEqual((p.root / ".sqlreview/.gitignore").read_text().splitlines(),
                             ["/reviews/**/source.sql", "/reviews/**/scope.source.sql", "/reviews/**/history/*.sql"])


if __name__ == "__main__":
    unittest.main()
