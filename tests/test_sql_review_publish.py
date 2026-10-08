"""Exercise the sanctioned final-write path from an installed native package."""

import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest

from tests.test_sql_review_scripts import REPO, Project, review_doc, scope_doc, git


class Publish(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        root = Path(self.temp.name)
        self.workspace = root / "unrelated workspace"
        self.workspace.mkdir()
        self.project = Project(self.workspace)
        self.cache = root / "plugin cache"
        shutil.copytree(REPO / "dist/codex/plugins/data-request", self.cache)
        # Exercise the canonical helper while installed-tree refresh is a later task.
        shutil.copytree(REPO / "skills/data-request-setup/scripts",
                        self.cache / "skills/setup/scripts", dirs_exist_ok=True)
        self.script = self.cache / "skills/setup/scripts/sqlreview.sh"
        self.draft = root / "confirmed draft.json"
        self.final = self.workspace / ".sqlreview/reviews/q"

    def run_helper(self, *args):
        env = {k: v for k, v in os.environ.items() if not k.startswith("SQLREVIEW_")}
        return subprocess.run(["bash", str(self.script), *args], cwd=self.workspace,
                              env=env, capture_output=True, text=True)

    def publish(self, doc, slug="q", kind=None):
        self.draft.write_text(json.dumps(doc))
        return self.run_helper("publish", slug, kind or doc["kind"], str(self.draft))

    def generated(self, payload="SELECT 1;\n"):
        (self.workspace / "sql").mkdir(exist_ok=True)
        (self.workspace / ".gitignore").write_text("sql/request.sql\n")
        (self.workspace / "payload").write_text(payload)
        (self.workspace / "render.sh").write_text('set -eu\ncat payload > "$4"\n')
        config = self.workspace / ".sqlreview/config.json"
        cfg = json.loads(config.read_text())
        cfg["sql_render"] = {"command": ["bash", "render.sh"]}
        config.write_text(json.dumps(cfg))
        (self.workspace / "sql/provenance.json").write_text(json.dumps({
            "schema": 1, "requests": {"sql/request.sql": {"source": "builder"}}}))
        self.project.commit()
        self.final = self.workspace / ".sqlreview/reviews/sql__request"
        result = self.run_helper("fingerprint", "sql/request.sql")
        self.assertEqual(result.returncode, 0, result.stderr)
        return json.loads(result.stdout)

    def generated_doc(self, fp, kind="review", revision=1):
        return (review_doc if kind == "review" else scope_doc)(
            "sql__request", revision=revision, **fp)

    def assert_no_sql_records(self):
        self.assertFalse(list((self.workspace / ".sqlreview").rglob("*.sql")))
        git(self.workspace, "add", ".sqlreview")
        added = git(self.workspace, "diff", "--cached", "--name-only", "--", ".sqlreview").stdout
        self.assertFalse(any(path.endswith(".sql") for path in added.splitlines()), added)

    def test_rendered_publication_without_snapshots(self):
        fp = self.generated()
        for kind in ("scope", "review"):
            result = self.publish(self.generated_doc(fp, kind), "sql__request")
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            saved = json.loads((self.final / f"{kind}.json").read_text())
            self.assertEqual(saved["sql_provenance"], fp["sql_provenance"])
        self.assertFalse((self.workspace / "sql/request.sql").exists())
        self.assert_no_sql_records()

    def test_revision_history_retains_hash_and_commit(self):
        fp = self.generated()
        for kind in ("scope", "review"):
            self.assertEqual(self.publish(self.generated_doc(fp, kind), "sql__request").returncode, 0)
            before = (self.final / f"{kind}.json").read_bytes()
            result = self.publish(self.generated_doc(fp, kind, 2), "sql__request")
            self.assertEqual(result.returncode, 0, result.stderr)
            history = self.final / f"history/{kind}/1.json"
            self.assertEqual(history.read_bytes(), before)
            old = json.loads(history.read_text())
            self.assertEqual(old["git_commit"], fp["git_commit"])
            self.assertEqual(old["sql_sha256"], fp["sql_sha256"])
        self.assert_no_sql_records()

    def test_history_conflict_preserves_final(self):
        fp = self.generated()
        self.assertEqual(self.publish(self.generated_doc(fp), "sql__request").returncode, 0)
        before = (self.final / "review.json").read_bytes()
        history = self.final / "history/review/1.json"
        history.parent.mkdir(parents=True)
        history.write_text("conflict")
        result = self.publish(self.generated_doc(fp, revision=2), "sql__request")
        self.assertEqual(result.returncode, 2, result.stderr)
        self.assertEqual((self.final / "review.json").read_bytes(), before)
        self.assertEqual(history.read_text(), "conflict")

    def test_failed_publication_preserves_history(self):
        fp = self.generated()
        self.assertEqual(self.publish(self.generated_doc(fp), "sql__request").returncode, 0)
        before = (self.final / "review.json").read_bytes()
        doc = self.generated_doc(fp, revision=2)
        doc["assumptions"][0]["status"] = "pending"
        self.assertNotEqual(self.publish(doc, "sql__request").returncode, 0)
        self.assertEqual((self.final / "review.json").read_bytes(), before)
        self.assertFalse((self.final / "history/review/1.json").exists())

    def test_snapshot_is_idempotent_verification(self):
        fp = self.generated()
        self.assertEqual(self.publish(self.generated_doc(fp), "sql__request").returncode, 0)
        before = {p: p.read_bytes() for p in self.final.rglob("*") if p.is_file()}
        for _ in range(2):
            result = self.run_helper("snapshot", "sql__request", "sql/request.sql")
            self.assertEqual(result.returncode, 0, result.stderr)
        after = {p: p.read_bytes() for p in self.final.rglob("*") if p.is_file()}
        self.assertEqual(before, after)
        self.assert_no_sql_records()

    def test_recorded_full_hash_authenticates_even_when_current_hash_matches(self):
        fp = self.generated()
        # Claim an unavailable commit while retaining the correct current full/body hashes.
        doc = self.generated_doc(dict(fp, git_commit="f" * 40,
                                      sql_provenance={**fp["sql_provenance"], "commit": "f" * 40}))
        result = self.publish(doc, "sql__request")
        self.assertEqual(result.returncode, 6, result.stderr)
        self.assertFalse((self.final / "review.json").exists())

    def test_header_revision_preserves_original_and_records_current_commit(self):
        fp = self.generated("-- old header\nSELECT 1;\n")
        doc = self.generated_doc(fp)
        self.assertEqual(self.publish(doc, "sql__request").returncode, 0)
        (self.workspace / "payload").write_text("-- new header\nSELECT 1;\n")
        current = self.project.commit("header")
        result = self.publish(doc, "sql__request")
        self.assertEqual(result.returncode, 0, result.stderr)
        saved = json.loads((self.final / "review.json").read_text())
        self.assertEqual(saved["sql_sha256"], fp["sql_sha256"])
        self.assertEqual(saved["git_commit"], fp["git_commit"])
        self.assertEqual(saved["assumptions"], doc["assumptions"])
        self.assertEqual(saved["header_revisions"][-1]["git_commit"], current)
        self.assertEqual(saved["header_revisions"][-1]["sql_provenance"]["commit"], current)
        self.assert_no_sql_records()

    def test_corrupt_original_hash_cannot_use_matching_body(self):
        fp = self.generated("-- header\nSELECT 1;\n")
        doc = self.generated_doc(dict(fp, sql_sha256="0" * 64))
        result = self.publish(doc, "sql__request")
        self.assertEqual(result.returncode, 6, result.stderr)
        self.assertFalse((self.final / "review.json").exists())

    def test_source_changes_between_fingerprint_and_publish_are_refused(self):
        fp = self.generated()
        (self.workspace / "payload").write_text("SELECT 2;\n")
        doc = self.generated_doc(fp)
        self.assertEqual(self.publish(doc, "sql__request").returncode, 2)
        self.project.commit("body change")
        result = self.publish(doc, "sql__request")
        self.assertEqual(result.returncode, 2, result.stderr)
        self.assertFalse((self.final / "review.json").exists())

    def test_legacy_records_require_clean_reproducible_commit(self):
        fp = self.generated()
        doc = self.generated_doc(fp)
        del doc["sql_provenance"]
        for dirty in (None, False):
            doc["git_dirty"] = dirty
            result = self.publish(doc, "sql__request")
            self.assertEqual(result.returncode, 0, result.stderr)
            (self.final / "review.json").unlink()
        del doc["git_dirty"]
        self.assertEqual(self.publish(doc, "sql__request").returncode, 0)
        (self.final / "review.json").unlink()
        for commit, dirty in ((None, False), (fp["git_commit"], True),
                              (fp["git_commit"], "false")):
            doc.update(git_commit=commit, git_dirty=dirty)
            result = self.publish(doc, "sql__request")
            self.assertEqual(result.returncode, 6, result.stderr)
            self.assertFalse((self.final / "review.json").exists())

    def test_failed_final_replace_rolls_back_new_history(self):
        fp = self.generated()
        self.assertEqual(self.publish(self.generated_doc(fp), "sql__request").returncode, 0)
        before = (self.final / "review.json").read_bytes()
        with tempfile.TemporaryDirectory() as binpath:
            shim = Path(binpath) / "mv"
            shim.write_text(f'#!/bin/sh\ncase "$2" in */review.json) exit 1;; esac\nexec {shutil.which("mv")} "$@"\n')
            shim.chmod(0o755)
            self.draft.write_text(json.dumps(self.generated_doc(fp, revision=2)))
            env = dict(os.environ, PATH=binpath + os.pathsep + os.environ["PATH"])
            result = subprocess.run(["bash", str(self.script), "publish", "sql__request", "review", str(self.draft)],
                                    cwd=self.workspace, env=env, capture_output=True, text=True)
        self.assertEqual(result.returncode, 2, result.stderr)
        self.assertEqual((self.final / "review.json").read_bytes(), before)
        self.assertFalse((self.final / "history/review/1.json").exists())
        self.assertEqual(list(self.final.glob(".publish.*")), [])
        self.assert_no_sql_records()

    def test_publication_interrupted_before_replace_preserves_final_and_history(self):
        fp = self.generated()
        self.assertEqual(self.publish(self.generated_doc(fp), "sql__request").returncode, 0)
        before = (self.final / "review.json").read_bytes()
        with tempfile.TemporaryDirectory() as binpath:
            shim = Path(binpath) / "mv"
            shim.write_text(f'#!/bin/sh\ncase "$2" in */review.json) kill -TERM "$PPID"; exit 1;; esac\nexec {shutil.which("mv")} "$@"\n')
            shim.chmod(0o755)
            self.draft.write_text(json.dumps(self.generated_doc(fp, revision=2)))
            env = dict(os.environ, PATH=binpath + os.pathsep + os.environ["PATH"])
            result = subprocess.run(["bash", str(self.script), "publish", "sql__request", "review", str(self.draft)],
                                    cwd=self.workspace, env=env, capture_output=True, text=True)
        self.assertNotEqual(result.returncode, 0, result.stderr)
        self.assertEqual((self.final / "review.json").read_bytes(), before)
        self.assertFalse((self.final / "history/review/1.json").exists())
        self.assertEqual(list(self.final.glob(".publish.*")), [])
        self.assert_no_sql_records()

    def test_signal_after_final_replace_keeps_matching_revision_history(self):
        fp = self.generated()
        self.assertEqual(self.publish(self.generated_doc(fp), "sql__request").returncode, 0)
        before = (self.final / "review.json").read_bytes()
        with tempfile.TemporaryDirectory() as binpath:
            shim = Path(binpath) / "mv"
            shim.write_text(f'#!/bin/sh\n{shutil.which("mv")} "$@" || exit 1\ncase "$2" in */review.json) kill -TERM "$PPID";; esac\n')
            shim.chmod(0o755)
            self.draft.write_text(json.dumps(self.generated_doc(fp, revision=2)))
            env = dict(os.environ, PATH=binpath + os.pathsep + os.environ["PATH"])
            subprocess.run(["bash", str(self.script), "publish", "sql__request", "review", str(self.draft)],
                           cwd=self.workspace, env=env, capture_output=True, text=True)
        self.assertEqual(json.loads((self.final / "review.json").read_text())["revision"], 2)
        history = self.final / "history/review/1.json"
        self.assertTrue(history.is_file())
        self.assertEqual(history.read_bytes(), before)
        self.assert_no_sql_records()

    def test_helper_owned_header_provenance_schema_refuses_inconsistent_commit(self):
        fp = self.generated()
        doc = self.generated_doc(fp)
        doc["header_revisions"] = [{"sql_sha256": fp["sql_sha256"], "at": "2026-10-08",
                                   "git_commit": fp["git_commit"], "git_dirty": False,
                                   "sql_provenance": {**fp["sql_provenance"], "commit": "a" * 40}}]
        self.draft.write_text(json.dumps(doc))
        result = self.run_helper("check", str(self.draft))
        self.assertEqual(result.returncode, 4, result.stderr)

    def test_snapshot_refuses_source_mutation_during_render(self):
        self.generated()
        control = Path(self.temp.name) / "source mutation enabled"
        adapter = self.workspace / "render.sh"
        adapter.write_text('set -eu\ncat payload > "$4"\n' +
                           f'if [ -f "{control}" ]; then printf "SELECT 2;\\n" > "{self.workspace / "payload"}"; fi\n')
        self.project.commit("adapter")
        result = self.run_helper("fingerprint", "sql/request.sql")
        self.assertEqual(result.returncode, 0, result.stderr)
        fp = json.loads(result.stdout)
        self.assertEqual(self.publish(self.generated_doc(fp), "sql__request").returncode, 0)
        before = (self.final / "review.json").read_bytes()
        control.touch()
        result = self.run_helper("snapshot", "sql__request", "sql/request.sql")
        self.assertEqual(result.returncode, 2, result.stderr)
        self.assertEqual((self.final / "review.json").read_bytes(), before)
        self.assert_no_sql_records()

    def test_scope_then_review_publish_snapshot_and_render(self):
        scope = scope_doc("q", "q.sql")
        result = self.publish(scope)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertEqual(json.loads((self.final / "scope.json").read_text()), scope)
        self.assertEqual(self.run_helper("render", "q", "scope").returncode, 0)
        self.project.sql("q.sql", "select 1;\n")
        self.project.commit()
        fp = json.loads(self.run_helper("fingerprint", "q.sql").stdout)
        review = review_doc("q", **fp)
        self.assertEqual(self.publish(review).returncode, 0)
        self.assertEqual(self.publish(review).returncode, 0)  # interrupted workflow retry
        self.assertEqual(self.run_helper("snapshot", "q", "q.sql").returncode, 0)
        self.assertEqual(self.run_helper("render", "q", "review").returncode, 0)
        self.assert_no_sql_records()
        self.assertTrue((self.final / "review.md").is_file())
        review = review_doc("q", revision=2, **fp)
        self.assertEqual(self.publish(review).returncode, 0)
        self.assertEqual(self.run_helper("snapshot", "q", "q.sql").returncode, 0)
        self.assertTrue((self.final / "history/review/1.json").is_file())
        self.assert_no_sql_records()

    def test_installed_header_only_publish_retains_original_provenance(self):
        original = "-- notes: Male or Female\nSELECT 1;\n"
        self.project.sql("q.sql", original)
        self.project.commit()
        fingerprint = json.loads(self.run_helper("fingerprint", "q.sql").stdout)
        doc = review_doc("q", **fingerprint)
        self.assertEqual(self.publish(doc).returncode, 0)
        self.assertEqual(self.run_helper("snapshot", "q", "q.sql").returncode, 0)
        self.project.sql("q.sql", original.replace("Male or Female", "MALE or FEMALE"))
        self.project.commit("header")
        self.assertEqual(self.publish(doc).returncode, 0)
        self.assertEqual(self.run_helper("delta", "q").returncode, 0)
        self.assertIn("header-only", self.run_helper("status").stdout)
        saved = json.loads((self.final / "review.json").read_text())
        self.assertEqual(saved["sql_sha256"], fingerprint["sql_sha256"])
        self.assertEqual(saved["git_commit"], fingerprint["git_commit"])
        self.assert_no_sql_records()
        self.assertEqual(self.run_helper("render", "q", "review").returncode, 0)
        self.assertIn("Header revision", (self.final / "review.md").read_text())

    def test_invalid_publish_preserves_final_and_draft(self):
        original = scope_doc("q", "q.sql")
        self.assertEqual(self.publish(original).returncode, 0)
        final_bytes = (self.final / "scope.json").read_bytes()
        pending = scope_doc("q", "q.sql", revision=2)
        pending["assumptions"][0]["status"] = "pending"
        stale_confirmation = scope_doc("q", "q.sql", revision=2)
        stale_confirmation["assumptions"][0]["confirmed_revision"] = 1
        for doc, slug, kind in [
            (pending, "q", "scope"), (stale_confirmation, "q", "scope"),
            (scope_doc("q", "q.sql", revision=3), "q", "scope"),
            (scope_doc("q", "q.sql", intent="Changed without revision"), "q", "scope"),
            (scope_doc("other", "other.sql"), "q", "scope"),
            (original, "q", "review"), (original, "../escape", "scope"),
        ]:
            with self.subTest(doc=doc, slug=slug, kind=kind):
                self.assertNotEqual(self.publish(doc, slug, kind).returncode, 0)
                self.assertEqual((self.final / "scope.json").read_bytes(), final_bytes)
                self.assertTrue(self.draft.is_file())
                self.assertEqual(list(self.final.glob(".publish.*")), [])

    def test_changed_sql_and_symlink_destinations_are_refused(self):
        self.project.sql("q.sql", "select 1;")
        result = self.publish(review_doc("q", "q.sql"))
        self.assertNotEqual(result.returncode, 0)
        self.assertFalse((self.final / "review.json").exists())
        outside = Path(self.temp.name) / "outside.json"
        outside.write_text("keep")
        (self.final / "scope.json").symlink_to(outside)
        self.assertNotEqual(self.publish(scope_doc("q", "q.sql")).returncode, 0)
        self.assertEqual(outside.read_text(), "keep")

    def test_custom_roles_preserve_configuration_and_quote_user_answers(self):
        config = self.workspace / ".sqlreview/config.json"
        original = json.loads(config.read_text())
        original["custom"] = {"keep": True}
        original["roles"]["other"] = "Reviewer"
        config.write_text(json.dumps(original))
        names = ["Engineer's \"team\"", "Analyst $(touch unexpected)"]
        result = self.run_helper("roles", *names)
        self.assertEqual(result.returncode, 0, result.stderr)
        expected = json.loads(json.dumps(original))
        expected["roles"].update(engineer=names[0], analyst=names[1])
        self.assertEqual(json.loads(config.read_text()), expected)
        self.assertFalse((self.workspace / "unexpected").exists())
        self.assertNotEqual(self.run_helper("roles", "", names[1]).returncode, 0)
        self.assertEqual(json.loads(config.read_text()), expected)
        for invalid in ("{}", "not JSON", "{}\n{}"):
            config.write_text(invalid)
            self.assertNotEqual(self.run_helper("roles", *names).returncode, 0)
            self.assertEqual(config.read_text(), invalid)
        self.assertEqual(list(config.parent.glob(".roles.*")), [])
