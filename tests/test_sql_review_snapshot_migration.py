"""Maintainer cleanup against real temporary child repositories."""
import hashlib
import json
import os
import subprocess
import tempfile
import unittest
from pathlib import Path
from test_sql_review_scripts import review_doc, scope_doc

REPO = Path(__file__).resolve().parent.parent
UTILITY = REPO / "scripts/migrate_sqlreview_snapshots.sh"
AUDIT = "docs/maintenance/sqlreview-snapshot-hashes.json"
RULES = ("/reviews/**/source.sql", "/reviews/**/scope.source.sql", "/reviews/**/history/*.sql")


class SnapshotMigration(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name) / "child with spaces"
        self.root.mkdir()
        self.git("init", "-q")
        self.git("config", "user.email", "test@example.invalid")
        self.git("config", "user.name", "Fixture")
        self.store = self.root / ".sqlreview"
        self.review = self.store / "reviews/request"
        (self.review / "history/review").mkdir(parents=True)
        self.snapshots = {
            ".sqlreview/reviews/request/source.sql": b"SELECT 1;\n",
            ".sqlreview/reviews/request/scope.source.sql": b"-- scope\nSELECT 1;\n",
            ".sqlreview/reviews/request/history/7.sql": b"-- orphan\nSELECT 7;\n",
        }
        for name, content in self.snapshots.items():
            (self.root / name).write_bytes(content)
        self.write_json(self.store / "config.json", {"schema": 1})
        self.write_json(self.review / "review.json", review_doc("request", git_commit=None))
        self.write_json(self.review / "scope.json", scope_doc("request", git_commit="a" * 40,
                        git_dirty=True, sql_sha256="0" * 64))
        self.write_json(self.review / "history/review/1.json", review_doc("request", git_commit="b" * 40))
        self.write_json(self.review / "questions.json", {"open_questions": ["Leave this question"]})
        self.write_json(self.review / "lift.json", {"lifts": [{"from": 1, "to": 2}]})
        (self.review / "review.md").write_bytes(b"# Report\nHuman confirmation retained.\n")
        (self.review / "scope.md").write_bytes(b"# Scope\n")
        (self.review / "keep.sql").write_bytes(b"SELECT 'unrelated';\n")
        (self.review / "history/review/keep.sql").write_bytes(b"SELECT 'nested';\n")
        (self.store / ".gitignore").write_bytes(b"# custom ignore\n/custom-private\n")
        self.git("add", ".")
        self.git("commit", "-qm", "fixture")
        self.head = self.git("rev-parse", "HEAD").stdout
        self.original = self.bytes_tree()

    def git(self, *args):
        return subprocess.run(["git", *args], cwd=self.root, capture_output=True, text=True, check=True)

    def write_json(self, path, value):
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(value, indent=2) + "\n")

    def bytes_tree(self):
        return {str(p.relative_to(self.root)): p.read_bytes() for p in self.root.rglob("*")
                if p.is_file() and ".git" not in p.relative_to(self.root).parts and not p.is_symlink()}

    def run_cleanup(self, check=False, env=None):
        args = ["bash", str(UTILITY), "--root", str(self.root)]
        if check:
            args.append("--check")
        return subprocess.run(args, capture_output=True, text=True, env=env, timeout=15)

    def assert_preserved(self):
        for name, content in self.original.items():
            if name not in self.snapshots and name != ".sqlreview/.gitignore":
                self.assertEqual((self.root / name).read_bytes(), content, name)
        self.assertEqual(self.git("rev-parse", "HEAD").stdout, self.head)
        self.assertEqual(self.git("diff", "--cached").stdout, "")

    def expected_index(self):
        return {"schemaVersion": 1, "snapshots": {name: {"sql_sha256": hashlib.sha256(data).hexdigest()}
                for name, data in self.snapshots.items()}}

    def test_check_lists_all_removals_and_changes_no_bytes(self):
        result = self.run_cleanup(check=True)
        self.assertEqual(result.returncode, 0, result.stderr)
        for name in self.snapshots:
            self.assertIn(name, result.stdout)
        self.assertEqual(self.bytes_tree(), self.original)
        self.assert_preserved()

    def test_apply_preserves_records_orphan_hashes_custom_ignores_and_is_idempotent(self):
        result = self.run_cleanup()
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(json.loads((self.root / AUDIT).read_text()), self.expected_index())
        for name in self.snapshots:
            self.assertFalse((self.root / name).exists(), name)
        ignore = (self.store / ".gitignore").read_text()
        self.assertTrue(ignore.startswith("# custom ignore\n/custom-private\n"))
        for rule in RULES:
            self.assertIn(rule, ignore.splitlines())
        self.assert_preserved()
        after = self.bytes_tree()
        result = self.run_cleanup()
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(self.bytes_tree(), after)
        self.assert_preserved()

    def test_all_preflight_failures_leave_every_byte_unchanged(self):
        for unsafe in ("malformed", "empty-json", "multiple-json", "symlink-sql", "symlink-record", "directory-sql", "fifo-sql", "symlink-history", "symlink-docs", "symlink-ignore"):
            with self.subTest(unsafe=unsafe):
                target = self.review / "source.sql"
                cleanup = []
                if unsafe in ("malformed", "empty-json", "multiple-json"):
                    target = self.review / "late.json"
                    target.write_text({"malformed": "{", "empty-json": "", "multiple-json": '{}\n{}\n'}[unsafe])
                    cleanup.append(target)
                elif unsafe == "symlink-docs":
                    target = self.root / "docs"
                    target.symlink_to(self.root, target_is_directory=True)
                    cleanup.append(target)
                elif unsafe == "symlink-history":
                    target = self.store / "reviews/unsafe"
                    target.mkdir()
                    (target / "history").symlink_to(self.review / "history", target_is_directory=True)
                    cleanup.extend([target / "history", target])
                else:
                    if unsafe == "symlink-record":
                        target = self.review / "review.json"
                    elif unsafe == "symlink-ignore":
                        target = self.store / ".gitignore"
                    content = target.read_bytes()
                    target.unlink()
                    if unsafe.startswith("symlink"):
                        target.symlink_to(self.review / "keep.sql")
                    elif unsafe == "fifo-sql":
                        os.mkfifo(target)
                    else:
                        target.mkdir()
                    cleanup.append(target)
                before = self.bytes_tree()
                for check in (True, False):
                    result = self.run_cleanup(check=check)
                    self.assertNotEqual(result.returncode, 0, result.stdout)
                    self.assertEqual(self.bytes_tree(), before)
                    self.assertFalse((self.root / AUDIT).exists())
                for path in cleanup:
                    if path.is_dir() and not path.is_symlink():
                        path.rmdir()
                    else:
                        path.unlink()
                if unsafe not in ("malformed", "empty-json", "multiple-json", "symlink-docs", "symlink-history"):
                    target.write_bytes(content)

    def test_unsafe_audit_file_refuses_deletion_and_ignore_changes(self):
        audit = self.root / AUDIT
        audit.parent.mkdir(parents=True)
        for unsafe in ("malformed", "symlink", "directory", "fifo"):
            with self.subTest(unsafe=unsafe):
                if unsafe == "malformed":
                    audit.write_text("{")
                elif unsafe == "symlink":
                    audit.symlink_to(self.review / "review.json")
                elif unsafe == "directory":
                    audit.mkdir()
                else:
                    os.mkfifo(audit)
                before = self.bytes_tree()
                for check in (True, False):
                    result = self.run_cleanup(check=check)
                    self.assertNotEqual(result.returncode, 0)
                    self.assertEqual(self.bytes_tree(), before)
                if unsafe == "directory":
                    audit.rmdir()
                else:
                    audit.unlink()

    def test_line_break_paths_refuse_mutation(self):
        (self.review / "history/bad\nname.sql").write_bytes(b"SELECT 9;\n")
        before = self.bytes_tree()
        result = self.run_cleanup()
        self.assertNotEqual(result.returncode, 0)
        self.assertEqual(self.bytes_tree(), before)

    def test_conflicting_index_and_unsafe_index_keys_refuse_all_mutation(self):
        for index in ({"schemaVersion": 1, "snapshots": {
                next(iter(self.snapshots)): {"sql_sha256": "f" * 64}}},
                {"schemaVersion": 1, "snapshots": {"../escape.sql": {"sql_sha256": "f" * 64}}},
                {"schemaVersion": 1, "snapshots": {".sqlreview/reviews/request/history/bad\u0000.sql": {
                    "sql_sha256": "f" * 64}}},
                {"schemaVersion": 1, "snapshots": {".sqlreview/reviews/request/source.sql": {
                    "sql_sha256": "f" * 64, "sql_commit": "invented"}}}):
            self.write_json(self.root / AUDIT, index)
            before = self.bytes_tree()
            for check in (True, False):
                result = self.run_cleanup(check=check)
                self.assertNotEqual(result.returncode, 0, result.stdout)
                self.assertEqual(self.bytes_tree(), before)

    def test_interruption_after_hash_persistence_is_recoverable_without_sql_loss(self):
        shims = Path(self.temp.name) / "shims"
        shims.mkdir()
        shim = shims / "rm"
        shim.write_text('#!/bin/sh\nfor arg do\n case "$arg" in *.sql) exit 75 ;; esac\ndone\nexec /bin/rm "$@"\n')
        shim.chmod(0o755)
        env = dict(os.environ, PATH=str(shims) + os.pathsep + os.environ["PATH"])
        result = self.run_cleanup(env=env)
        self.assertNotEqual(result.returncode, 0)
        self.assertEqual(json.loads((self.root / AUDIT).read_text()), self.expected_index())
        for name, content in self.snapshots.items():
            self.assertEqual((self.root / name).read_bytes(), content)
        self.assert_preserved()
        result = self.run_cleanup()
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(json.loads((self.root / AUDIT).read_text()), self.expected_index())
        self.assert_preserved()

    def test_rerun_refuses_changed_sql_after_hash_persistence(self):
        self.write_json(self.root / AUDIT, self.expected_index())
        (self.review / "source.sql").write_bytes(b"SELECT 'changed';\n")
        before = self.bytes_tree()
        result = self.run_cleanup()
        self.assertNotEqual(result.returncode, 0)
        self.assertEqual(self.bytes_tree(), before)

    def test_existing_audit_bytes_survive_when_all_hashes_already_match(self):
        self.write_json(self.root / AUDIT, self.expected_index())
        before = (self.root / AUDIT).read_bytes()
        result = self.run_cleanup()
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual((self.root / AUDIT).read_bytes(), before)
        self.assert_preserved()

    def test_ignore_without_final_newline_is_preserved_as_a_prefix(self):
        (self.store / ".gitignore").write_bytes(b"# custom\n/custom-private")
        result = self.run_cleanup()
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertTrue((self.store / ".gitignore").read_bytes().startswith(b"# custom\n/custom-private\n"))
        self.assert_preserved()

    def test_missing_store_is_a_noop_and_missing_ignore_is_created_for_existing_store(self):
        import shutil
        shutil.rmtree(self.store)
        for check in (True, False):
            result = self.run_cleanup(check=check)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual(self.bytes_tree(), {})
        self.store.mkdir()
        result = self.run_cleanup()
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual((self.store / ".gitignore").read_text().splitlines(), list(RULES))
        self.assertFalse((self.root / AUDIT).exists())


if __name__ == "__main__":
    unittest.main()
