"""Committed source reconstruction: generated output is never durable evidence."""
import hashlib
import json
import os
import subprocess
import shutil
import shlex
import tempfile
import unittest
from pathlib import Path

from test_sql_review_scripts import Project, REPO, git, run, review_doc, scope_doc, item

SCRIPTS = REPO / "skills/data-request-setup/scripts"
ADAPTER = '''#!/usr/bin/env bash
set -eu
[ "$1" = --sql-path ] && [ "$2" = 'sql/request.sql' ]
[ "$3" = --output ]
cat payload > "$4"
'''


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

    def generated(self, payload=b"SELECT 1;\n", adapter=ADAPTER, source="builder"):
        p = self.p
        (p.root / "sql").mkdir(exist_ok=True)
        (p.root / ".gitignore").write_text("sql/request.sql\n")
        (p.root / "payload").write_bytes(payload)
        (p.root / "render.sh").write_text(adapter)
        cfg = p.root / ".sqlreview/config.json"
        doc = json.loads(cfg.read_text())
        doc["sql_render"] = {"command": ["bash", "render.sh"]}
        cfg.write_text(json.dumps(doc))
        (p.root / "sql/provenance.json").write_text(json.dumps({
            "schema": 1, "requests": {"sql/request.sql": {"source": source}}}))
        return p.commit()

    def fingerprint(self):
        return run(["fingerprint", "sql/request.sql"], self.p.root)

    def source_call(self, function, *args, overrides=None):
        with tempfile.TemporaryDirectory() as output:
            target = Path(output) / "out.sql"
            env = dict(os.environ, SR_ROOT=str(self.p.root), SR_SCRIPT_DIR=str(SCRIPTS))
            env.update(overrides or {})
            r = subprocess.run(["bash", "-c", '. "$SR_SCRIPT_DIR/sqlreview-lib.sh"; '
                                + function + ' "$@"', "source", *map(str, args), str(target)],
                               cwd=self.p.root, env=env, capture_output=True, text=True)
            data = target.read_bytes() if target.is_file() else None
            return r, data

    def publish_generated(self, payload=b"SELECT 1;\nSELECT 3;\n"):
        self.generated(payload)
        fp = json.loads(self.fingerprint().stdout)
        doc = review_doc("sql__request", **fp,
                         assumptions=[item("A1", "Retain this range", location={"lines": [2, 2]})],
                         limitations=[], logic=[])
        draft = self.p.write_json("sql__request", "review.draft.json", doc)
        r = run(["publish", "sql__request", "review", str(draft)], self.p.root)
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        return draft, doc

    def change_builder(self, payload):
        (self.p.root / "payload").write_bytes(payload)
        self.p.commit("builder update")

    def test_status_without_working_sql(self):
        self.publish_generated()
        r = run(["status", "--json"], self.p.root)
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertEqual(json.loads(r.stdout)["reviews"][0]["state"], "current")
        self.change_builder(b"-- header\nSELECT 1;\nSELECT 3;\n")
        r = run(["status", "--json"], self.p.root)
        self.assertEqual(json.loads(r.stdout)["reviews"][0]["state"], "header-only")
        self.change_builder(b"SELECT 2;\nSELECT 3;\n")
        r = run(["status", "--json"], self.p.root)
        self.assertEqual(json.loads(r.stdout)["reviews"][0]["state"], "stale")
        self.assertEqual(git(self.p.root, "log", "--all", "--format=%H", "--", "sql/request.sql").stdout, "")

    def test_status_refuses_clean_commit_after_current_render(self):
        self.publish_generated()
        for header in (False, True):
            with self.subTest(header_only=header), tempfile.TemporaryDirectory() as bindir:
                self.change_builder(b"-- header\nSELECT 1;\nSELECT 3;\n" if header else b"SELECT 1;\nSELECT 3;\n")
                before = git(self.p.root, "rev-parse", "HEAD").stdout
                shim = Path(bindir) / "cp"
                shim.write_text('#!/bin/sh\n' + shlex.quote(shutil.which("cp")) + ' "$@" || exit $?\n'
                    'case "$2" in */current.sql)\n'
                    '  cd ' + shlex.quote(str(self.p.root)) + '\n'
                    "  printf 'SELECT 99;\\n' > payload\n"
                    '  git add payload && git -c commit.gpgsign=false commit -qm "concurrent source"\n'
                    'esac\n')
                shim.chmod(0o755)
                r = run(["status", "--json"], self.p.root,
                        env={"PATH": bindir + os.pathsep + os.environ["PATH"]})
                self.assertNotEqual(git(self.p.root, "rev-parse", "HEAD").stdout, before)
                self.assertEqual(git(self.p.root, "status", "--porcelain").stdout, "")
                self.assertEqual(r.returncode, 2, r.stdout + r.stderr)
                self.assertIn("source commit changed during state check", r.stderr)
                self.assertNotIn('"state": "current"', r.stdout)

    def test_status_refuses_clean_commit_after_absence_lookup(self):
        self.publish_generated()
        (self.p.root / "sql/provenance.json").unlink()
        self.p.commit("remove generated declaration")
        before = git(self.p.root, "rev-parse", "HEAD").stdout
        with tempfile.TemporaryDirectory() as bindir:
            shim = Path(bindir) / "git"
            real_git = shlex.quote(shutil.which("git"))
            shim.write_text('#!/bin/sh\n' + real_git + ' "$@" || exit $?\n'
                'case "$*" in *"ls-tree -r -t -z"*)\n'
                '  cd ' + shlex.quote(str(self.p.root)) + '\n'
                "  printf 'SELECT 99;\\n' > payload\n"
                '  ' + real_git + ' add payload && ' + real_git + ' -c commit.gpgsign=false commit -qm "concurrent source"\n'
                'esac\n')
            shim.chmod(0o755)
            r = run(["status", "--json"], self.p.root,
                    env={"PATH": bindir + os.pathsep + os.environ["PATH"]})
        self.assertNotEqual(git(self.p.root, "rev-parse", "HEAD").stdout, before)
        self.assertEqual(git(self.p.root, "status", "--porcelain").stdout, "")
        self.assertEqual(r.returncode, 2, r.stdout + r.stderr)
        self.assertIn("source commit changed during state check", r.stderr)

    def test_materialize_exact_revision(self):
        draft, doc = self.publish_generated()
        self.change_builder(b"SELECT 2;\nSELECT 3;\n")
        doc = dict(doc, revision=2, **json.loads(self.fingerprint().stdout))
        doc["assumptions"][0]["confirmed_revision"] = 2
        draft.write_text(json.dumps(doc))
        r = run(["publish", "sql__request", "review", str(draft)], self.p.root)
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        with tempfile.TemporaryDirectory() as tmp:
            output = Path(tmp) / "explained.sql"
            for revision, data in ((1, b"SELECT 1;\nSELECT 3;\n"), (2, b"SELECT 2;\nSELECT 3;\n")):
                r = run(["materialize", "sql__request", "review", str(revision), str(output)], self.p.root)
                self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
                self.assertEqual(output.read_bytes(), data)
                output.unlink()
            r = run(["materialize", "sql__request", "review", "3", str(output)], self.p.root)
            self.assertEqual(r.returncode, 6, r.stdout + r.stderr)
            self.assertFalse(output.exists())
        self.assertEqual(list((self.p.root / ".sqlreview").rglob("*.sql")), [])

    def test_materialize_refuses_in_repo_output(self):
        self.publish_generated()
        for output in (self.p.root / "leaked.sql", self.p.root / ".sqlreview/reviews/sql__request/source.sql"):
            r = run(["materialize", "sql__request", "review", "1", str(output)], self.p.root)
            self.assertEqual(r.returncode, 2, r.stdout + r.stderr)
            self.assertFalse(output.exists())

    def test_materialize_replaces_external_hardlink_without_modifying_repository(self):
        self.publish_generated()
        alias = self.p.root / ".sqlreview/reviews/sql__request/alias.sql"
        original = b"preserve repository bytes\n"
        alias.write_bytes(original)
        with tempfile.TemporaryDirectory() as tmp:
            output = Path(tmp) / "explained.sql"
            os.link(alias, output)
            self.assertEqual(alias.stat().st_ino, output.stat().st_ino)
            r = run(["materialize", "sql__request", "review", "1", str(output)], self.p.root)
            self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
            self.assertEqual(output.read_bytes(), b"SELECT 1;\nSELECT 3;\n")
            self.assertEqual(alias.read_bytes(), original)
            self.assertNotEqual(alias.stat().st_ino, output.stat().st_ino)
            self.assertEqual(list(Path(tmp).iterdir()), [output])

    def test_materialize_failed_output_publication_preserves_existing_alias(self):
        self.publish_generated()
        alias = self.p.root / ".sqlreview/reviews/sql__request/alias.sql"
        original = b"preserve repository bytes\n"
        alias.write_bytes(original)
        for operation in ("cp", "mv"):
            with self.subTest(operation=operation), tempfile.TemporaryDirectory() as bindir, tempfile.TemporaryDirectory() as tmp:
                output = Path(tmp) / "explained.sql"
                os.link(alias, output)
                shim = Path(bindir) / operation
                pattern = '*/.sqlreview-materialize.*' if operation == "cp" else str(output)
                shim.write_text(f'#!/bin/sh\ncase "$2" in {pattern}) exit 1;; esac\nexec {shutil.which(operation)} "$@"\n')
                shim.chmod(0o755)
                r = run(["materialize", "sql__request", "review", "1", str(output)], self.p.root,
                        env={"PATH": bindir + os.pathsep + os.environ["PATH"]})
                self.assertEqual(r.returncode, 2, r.stdout + r.stderr)
                self.assertEqual(alias.read_bytes(), original)
                self.assertEqual(output.read_bytes(), original)
                self.assertEqual(list(Path(tmp).iterdir()), [output])

    def test_unknown_render_cannot_complete(self):
        draft, doc = self.publish_generated()
        doc["sql_sha256"] = "0" * 64
        draft.with_name("review.json").write_text(json.dumps(doc))
        r = run(["status", "--json"], self.p.root)
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertEqual(json.loads(r.stdout)["reviews"][0]["state"], "no-baseline")
        with tempfile.TemporaryDirectory() as tmp:
            output = Path(tmp) / "unproved.sql"
            r = run(["materialize", "sql__request", "review", "1", str(output)], self.p.root)
            self.assertEqual(r.returncode, 6, r.stdout + r.stderr)
            self.assertFalse(output.exists())
        doc["sql_sha256"] = hashlib.sha256(b"SELECT 1;\nSELECT 3;\n").hexdigest()
        draft.with_name("review.json").write_text(json.dumps(doc))
        self.change_builder(b"SELECT 2;\nSELECT 3;\n")
        (self.p.root / "render.sh").write_text("#!/bin/sh\nexit 1\n")
        self.p.commit("unavailable render")
        r = run(["status", "--json"], self.p.root)
        self.assertEqual(r.returncode, 2, r.stdout + r.stderr)
        self.assertNotIn('"current"', r.stdout)

    def test_release_ref_uses_historical_builder(self):
        draft, doc = self.publish_generated()
        reviewed = doc["git_commit"]
        self.change_builder(b"SELECT 2;\nSELECT 3;\n")
        for ref, expected, applies in ((reviewed, 0, "current"), ("HEAD", 10, "changed")):
            r = subprocess.run(["bash", str(SCRIPTS / "release.sh"), "evidence", ref],
                               cwd=self.p.root, capture_output=True, text=True)
            self.assertEqual(r.returncode, expected, r.stdout + r.stderr)
            row = json.loads(r.stdout)["reviews"][0]
            self.assertEqual(row["applies"], applies)
            self.assertTrue(row["reviewed_commit_in_ref"])
        doc["sql_sha256"] = "0" * 64
        draft.with_name("review.json").write_text(json.dumps(doc))
        r = subprocess.run(["bash", str(SCRIPTS / "release.sh"), "evidence", reviewed],
                           cwd=self.p.root, capture_output=True, text=True)
        self.assertEqual(r.returncode, 10, r.stdout + r.stderr)
        self.assertEqual(json.loads(r.stdout)["reviews"][0]["applies"], "unavailable")
        self.assertEqual(list((self.p.root / ".sqlreview").rglob("*.sql")), [])

    def test_generated_header_decision_unproved(self):
        from test_sql_review_header_carry import SQL, R
        self.generated(SQL.encode())
        doc = review_doc("sql__request", **json.loads(self.fingerprint().stdout),
                         assumptions=[item("A1", "Use discharged stays", rationale=R,
                            location={"lines": [8, 8]}, status="candidate", confirmed_by=None,
                            confirmed_at=None, confirmed_revision=None)], limitations=[])
        draft = self.p.write_json("sql__request", "review.draft.json", doc)
        with tempfile.TemporaryDirectory() as tmp:
            output = Path(tmp) / "notes.sql"
            output.write_text(SQL)
            r = run(["notes", str(output), "--against", str(draft), "--confirmed-by", "engineer-login"], self.p.root)
            self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
            result = json.loads(r.stdout)
            self.assertEqual(result["header_carry_over"], [])
            self.assertEqual(result["header_walk"][0]["id"], "A1")
            self.assertIn("generated", result["header_walk"][0]["why"])

    def test_state_and_release_operational_failure_is_visible(self):
        self.publish_generated()
        with tempfile.TemporaryDirectory() as bindir, tempfile.TemporaryDirectory() as tmp:
            shim = Path(bindir) / "cp"
            shim.write_text(f'#!/bin/sh\ncase "$2" in */recorded.sql) exit 1;; esac\nexec {shutil.which("cp")} "$@"\n')
            shim.chmod(0o755)
            env = dict(os.environ, PATH=bindir + os.pathsep + os.environ["PATH"], TMPDIR=tmp)
            for script, args in ((SCRIPTS / "sqlreview.sh", ["status", "--json"]),
                                 (SCRIPTS / "release.sh", ["evidence", "HEAD"]),
                                 (SCRIPTS / "sqlreview.sh", ["materialize", "sql__request", "review", "1", str(Path(tmp) / "out.sql")])):
                r = subprocess.run(["bash", str(script), *args], cwd=self.p.root, env=env, capture_output=True, text=True)
                self.assertEqual(r.returncode, 2, r.stdout + r.stderr)
                self.assertNotIn('"current"', r.stdout)
                self.assertEqual(list(Path(tmp).iterdir()), [])

    def test_release_metadata_does_not_hide_dirty_sources(self):
        self.publish_generated()
        target = self.p.root / ".sqlreview/releases/v1/release.json"
        target.parent.mkdir(parents=True)
        target.write_text('{}')
        r = run(["status", "--json"], self.p.root)
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertEqual(json.loads(r.stdout)["reviews"][0]["state"], "current")
        (self.p.root / "payload").write_bytes(b"SELECT 4;\n")
        r = run(["status", "--json"], self.p.root)
        self.assertEqual(r.returncode, 2, r.stdout + r.stderr)
        self.assertIn("uncommitted source changes", r.stderr)

    def test_materialize_scope_and_header_revision_keep_original_bytes(self):
        self.generated(b"SELECT 1;\n")
        fp = json.loads(self.fingerprint().stdout)
        scope = scope_doc("sql__request", **fp)
        draft = self.p.write_json("sql__request", "scope.draft.json", scope)
        r = run(["publish", "sql__request", "scope", str(draft)], self.p.root)
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.change_builder(b"-- corrected header\nSELECT 1;\n")
        r = run(["publish", "sql__request", "scope", str(draft.with_name("scope.json"))], self.p.root)
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        with tempfile.TemporaryDirectory() as tmp:
            output = Path(tmp) / "scope.sql"
            r = run(["materialize", "sql__request", "scope", "1", str(output)], self.p.root)
            self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
            self.assertEqual(output.read_bytes(), b"SELECT 1;\n")
            output.unlink()
            alias = Path(tmp) / "alias"
            alias.symlink_to(self.p.root, target_is_directory=True)
            r = run(["materialize", "sql__request", "scope", "1", str(alias / "leak.sql")], self.p.root)
            self.assertEqual(r.returncode, 2, r.stdout + r.stderr)
            self.assertFalse((self.p.root / "leak.sql").exists())

    def test_two_commit_delta_and_impact_use_authenticated_renders(self):
        self.publish_generated(b"SELECT 1; -- shared_identifier\nSELECT shared_identifier;\n")
        self.change_builder(b"SELECT 2; -- shared_identifier\nSELECT shared_identifier;\n")
        with tempfile.TemporaryDirectory() as tmp:
            for command, expected in (("delta", 10), ("impact", 0)):
                r = run([command, "sql__request"], self.p.root, env={"TMPDIR": tmp})
                self.assertEqual(r.returncode, expected, r.stdout + r.stderr)
                if command == "delta":
                    self.assertIn("-SELECT 1;", r.stdout)
                    self.assertIn("+SELECT 2;", r.stdout)
                else:
                    self.assertIn("shared_identifier\tline 2\tSELECT shared_identifier;", r.stdout)
                self.assertEqual(list(Path(tmp).iterdir()), [])
        self.assertEqual(list((self.p.root / ".sqlreview").rglob("*.sql")), [])

    def test_shifted_remap_and_unchanged_range_carry_retain_confirmation(self):
        draft, prior = self.publish_generated()
        self.change_builder(b"SET NOCOUNT ON;\nSELECT 2;\nSELECT 3;\n")
        doc = dict(prior, revision=2, **json.loads(self.fingerprint().stdout))
        draft.write_text(json.dumps(doc))
        r = run(["remap", "sql__request", str(draft)], self.p.root)
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        doc = json.loads(draft.read_text())
        self.assertEqual(doc["assumptions"][0]["location"]["lines"], [3, 3])
        r = run(["carryforward", "sql__request", "review", str(draft)], self.p.root)
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        row = json.loads(r.stdout)["carry"][0]
        self.assertEqual(row["basis"], "lines-unchanged")
        for key in ("confirmed_by", "confirmed_at", "confirmed_revision"):
            self.assertEqual(row["set"][key], prior["assumptions"][0][key])
        self.assertEqual(row["set"]["carried_from_revision"], 1)
        doc["assumptions"][0].update(row["set"])
        draft.write_text(json.dumps(doc))
        r = run(["publish", "sql__request", "review", str(draft)], self.p.root)
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertEqual(list((self.p.root / ".sqlreview").rglob("*.sql")), [])

    def test_corrupt_previous_hash_cannot_carry(self):
        draft, doc = self.publish_generated()
        final = draft.with_name("review.json")
        doc["sql_sha256"] = "0" * 64
        final.write_text(json.dumps(doc))
        r = run(["carryforward", "sql__request", "review", str(draft)], self.p.root)
        self.assertEqual(r.returncode, 6, r.stdout + r.stderr)
        self.assertIn("full SHA mismatch", r.stderr)

    def test_missing_commit_is_not_sql_absent(self):
        draft, doc = self.publish_generated()
        doc["git_commit"] = "f" * 40
        doc["sql_provenance"]["commit"] = doc["git_commit"]
        draft.with_name("review.json").write_text(json.dumps(doc))
        for command in (["carryforward", "sql__request", "review", str(draft)],
                        ["carryover", "sql__request", str(draft)], ["delta", "sql__request"]):
            if command[0] == "carryover":
                scope = scope_doc("sql__request", "sql/request.sql", sql_sha256=doc["sql_sha256"],
                                  git_commit=doc["git_commit"])
                self.p.write_json("sql__request", "scope.json", scope)
            r = run(command, self.p.root)
            self.assertEqual(r.returncode, 6, r.stdout + r.stderr)
            self.assertNotIn("sql-absent", r.stdout)

    def test_no_sql_scope_keeps_intent_carry(self):
        self.p.commit()
        doc = scope_doc("sql__request", "sql/request.sql", sql_sha256=None)
        self.p.write_json("sql__request", "scope.json", doc)
        draft = self.p.write_json("sql__request", "scope.draft.json", dict(doc, revision=2))
        r = run(["carryforward", "sql__request", "scope", str(draft)], self.p.root)
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertEqual(json.loads(r.stdout)["carry"][0]["basis"], "sql-absent")
        r = run(["delta", "sql__request"], self.p.root)
        self.assertEqual(r.returncode, 6, r.stdout + r.stderr)

    def test_changed_governed_lines_refused_at_publish(self):
        draft, prior = self.publish_generated()
        self.change_builder(b"SELECT 1;\nSELECT 4;\n")
        doc = dict(prior, revision=2, **json.loads(self.fingerprint().stdout))
        doc["assumptions"][0].update(carried_from_revision=1, carried_basis="lines-unchanged")
        draft.write_text(json.dumps(doc))
        before = draft.with_name("review.json").read_bytes()
        r = run(["publish", "sql__request", "review", str(draft)], self.p.root)
        self.assertEqual(r.returncode, 4, r.stdout + r.stderr)
        self.assertIn("governed lines changed", r.stdout + r.stderr)
        self.assertEqual(draft.with_name("review.json").read_bytes(), before)

    def test_carry_historical_output_failure_stays_operational(self):
        draft, _ = self.publish_generated()
        with tempfile.TemporaryDirectory() as bindir, tempfile.TemporaryDirectory() as tmp:
            shim = Path(bindir) / "cp"
            shim.write_text(f'#!/bin/sh\ncase "$2" in */carry-base.sql) exit 1;; esac\nexec {shutil.which("cp")} "$@"\n')
            shim.chmod(0o755)
            r = run(["carryforward", "sql__request", "review", str(draft)], self.p.root,
                    env={"PATH": bindir + os.pathsep + os.environ["PATH"], "TMPDIR": tmp})
            self.assertEqual(r.returncode, 2, r.stdout + r.stderr)
            self.assertEqual(list(Path(tmp).iterdir()), [])

    def test_absence_git_failure_cannot_certify_no_sql(self):
        self.p.commit()
        doc = scope_doc("sql__request", "sql/request.sql", sql_sha256=None)
        self.p.write_json("sql__request", "scope.json", doc)
        draft = self.p.write_json("sql__request", "scope.draft.json", dict(doc, revision=2))
        with tempfile.TemporaryDirectory() as bindir:
            shim = Path(bindir) / "git"
            shim.write_text(f'#!/bin/sh\ncase "$*" in *cat-file*|*ls-tree*) exit 2;; esac\nexec {shutil.which("git")} "$@"\n')
            shim.chmod(0o755)
            r = run(["carryforward", "sql__request", "scope", str(draft)], self.p.root,
                    env={"PATH": bindir + os.pathsep + os.environ["PATH"]})
            self.assertEqual(r.returncode, 2, r.stdout + r.stderr)
            self.assertNotIn("sql-absent", r.stdout)

    def test_missing_manifest_tree_object_cannot_certify_sql_absence(self):
        self.generated()
        doc = scope_doc("sql__request", "sql/request.sql", sql_sha256=None)
        self.p.write_json("sql__request", "scope.json", doc)
        draft = self.p.write_json("sql__request", "scope.draft.json", dict(doc, revision=2))
        tree = git(self.p.root, "rev-parse", "HEAD:sql").stdout.strip()
        loose = git(self.p.root, "rev-parse", "--git-path", f"objects/{tree[:2]}/{tree[2:]}").stdout.strip()
        (self.p.root / loose).unlink()
        status = git(self.p.root, "status", "--porcelain=v1")
        self.assertEqual(status.returncode, 0)
        lookup = subprocess.run(["git", "cat-file", "-e", "HEAD:sql/provenance.json"],
                                cwd=self.p.root, capture_output=True)
        self.assertEqual(lookup.returncode, 128)
        r = run(["carryforward", "sql__request", "scope", str(draft)], self.p.root)
        self.assertEqual(r.returncode, 2, r.stdout + r.stderr)
        self.assertNotIn("sql-absent", r.stdout)

    def test_absence_tree_lookup_exit_128_is_operational(self):
        self.p.commit()
        doc = scope_doc("sql__request", "sql/request.sql", sql_sha256=None)
        self.p.write_json("sql__request", "scope.json", doc)
        draft = self.p.write_json("sql__request", "scope.draft.json", dict(doc, revision=2))
        with tempfile.TemporaryDirectory() as bindir:
            shim = Path(bindir) / "git"
            shim.write_text(f'#!/bin/sh\ncase "$*" in *cat-file*|*ls-tree*) exit 128;; esac\nexec {shutil.which("git")} "$@"\n')
            shim.chmod(0o755)
            r = run(["carryforward", "sql__request", "scope", str(draft)], self.p.root,
                    env={"PATH": bindir + os.pathsep + os.environ["PATH"]})
            self.assertEqual(r.returncode, 2, r.stdout + r.stderr)
            self.assertNotIn("sql-absent", r.stdout)

    def test_fresh_reassessment_can_replace_unavailable_prior_evidence(self):
        draft, prior = self.publish_generated()
        final = draft.with_name("review.json")
        broken = dict(prior, sql_sha256="0" * 64)
        final.write_text(json.dumps(broken))
        doc = dict(prior, revision=2)
        doc["assumptions"][0].update(confirmed_revision=2)
        draft.write_text(json.dumps(doc))
        r = run(["publish", "sql__request", "review", str(draft)], self.p.root)
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertEqual(json.loads(final.read_text())["revision"], 2)

    def test_scope_delta_selector_uses_scope_with_existing_review(self):
        self.generated(b"SELECT 1;\n")
        fp = json.loads(self.fingerprint().stdout)
        scope = scope_doc("sql__request", **fp)
        self.p.write_json("sql__request", "scope.json", scope)
        self.change_builder(b"SELECT 2;\n")
        self.p.write_json("sql__request", "review.json", review_doc("sql__request", **json.loads(self.fingerprint().stdout)))
        r = run(["delta", "sql__request"], self.p.root)
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        r = run(["delta", "sql__request", "scope"], self.p.root)
        self.assertEqual(r.returncode, 10, r.stdout + r.stderr)
        self.assertIn("-SELECT 1;", r.stdout)
        self.assertIn("+SELECT 2;", r.stdout)

    def test_moved_path_delta_refuses_binding_without_fabricated_diff(self):
        self.publish_generated()
        r = run(["move", "sql/request.sql", "sql/new.sql"], self.p.root)
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        for command in ("delta", "impact"):
            r = run([command, "sql__new"], self.p.root)
            self.assertEqual(r.returncode, 10, r.stdout + r.stderr)
            self.assertIn("requires reassessment", r.stdout)
            self.assertNotIn("sha256=", r.stdout)
            self.assertNotIn("SELECT", r.stdout)

    def test_remap_signal_cleanup_keeps_published_and_draft_inputs(self):
        draft, _ = self.publish_generated()
        before = draft.read_bytes()
        final = draft.with_name("review.json")
        published = final.read_bytes()
        with tempfile.TemporaryDirectory() as bindir, tempfile.TemporaryDirectory() as tmp:
            shim = Path(bindir) / "diff"
            shim.write_text('#!/bin/sh\nkill -TERM "$PPID"\nexit 2\n')
            shim.chmod(0o755)
            r = run(["remap", "sql__request", str(draft)], self.p.root,
                    env={"PATH": bindir + os.pathsep + os.environ["PATH"], "TMPDIR": tmp})
            self.assertNotEqual(r.returncode, 0)
            self.assertEqual(draft.read_bytes(), before)
            self.assertEqual(final.read_bytes(), published)
            self.assertEqual(list(Path(tmp).iterdir()), [])
        self.assertEqual(list((self.p.root / ".sqlreview").rglob("*.sql")), [])

    def test_remap_concurrent_input_change_refused(self):
        draft, _ = self.publish_generated()
        self.change_builder(b"-- shifted\nSELECT 1;\nSELECT 3;\n")
        with tempfile.TemporaryDirectory() as bindir, tempfile.TemporaryDirectory() as tmp:
            shim = Path(bindir) / "diff"
            shim.write_text(f'#!/bin/sh\nprintf "concurrent work" > "{draft}"\nexec {shutil.which("diff")} "$@"\n')
            shim.chmod(0o755)
            r = run(["remap", "sql__request", str(draft)], self.p.root,
                    env={"PATH": bindir + os.pathsep + os.environ["PATH"], "TMPDIR": tmp})
            self.assertEqual(r.returncode, 2, r.stdout + r.stderr)
            self.assertIn("inputs changed", r.stderr)
            self.assertEqual(draft.read_text(), "concurrent work")
            self.assertEqual(list(Path(tmp).iterdir()), [])

    def test_auth_distinguishes_missing_evidence_from_operational_output_failure(self):
        head = self.generated()
        doc = review_doc("sql__request", "sql/request.sql", git_commit=head,
                         sql_sha256=hashlib.sha256(b"SELECT 1;\n").hexdigest())
        path = self.p.write_json("sql__request", "review.json", doc)
        with tempfile.TemporaryDirectory() as binpath:
            shim = Path(binpath) / "cp"
            shim.write_text(f'#!/bin/sh\ncase "$2" in */out.sql) exit 1;; esac\nexec {shutil.which("cp")} "$@"\n')
            shim.chmod(0o755)
            r, data = self.source_call("sr_source_auth", path,
                                       overrides={"PATH": binpath + os.pathsep + os.environ["PATH"]})
            self.assertEqual(r.returncode, 2, r.stderr)
            self.assertIsNone(data)
        for commit, full in (("f" * 40, doc["sql_sha256"]), (head, "0" * 64)):
            doc.update(git_commit=commit, sql_sha256=full)
            path.write_text(json.dumps(doc))
            r, _ = self.source_call("sr_source_auth", path)
            self.assertEqual(r.returncode, 6, r.stderr)

    def test_auth_preserves_hash_and_adapter_config_tool_failures(self):
        head = self.generated()
        doc = review_doc("sql__request", "sql/request.sql", git_commit=head,
                         sql_sha256=hashlib.sha256(b"SELECT 1;\n").hexdigest())
        path = self.p.write_json("sql__request", "review.json", doc)
        for tool in ("sha256sum", "jq"):
            with self.subTest(tool=tool), tempfile.TemporaryDirectory() as binpath:
                shim = Path(binpath) / tool
                if tool == "jq":
                    shim.write_text(f'#!/bin/sh\ncase "$*" in *sql_render.command*) exit 127;; esac\nexec {shutil.which("jq")} "$@"\n')
                else:
                    shim.write_text('#!/bin/sh\nexit 1\n')
                shim.chmod(0o755)
                r, _ = self.source_call("sr_source_auth", path,
                                        overrides={"PATH": binpath + os.pathsep + os.environ["PATH"]})
                self.assertEqual(r.returncode, 2, r.stderr)

    def test_generated_sql_absent_from_git(self):
        head = self.generated()
        r = self.fingerprint()
        self.assertEqual(r.returncode, 0, r.stderr)
        d = json.loads(r.stdout)
        self.assertEqual(d["sql_sha256"], hashlib.sha256(b"SELECT 1;\n").hexdigest())
        self.assertEqual(d["git_commit"], head)
        self.assertFalse(d["git_dirty"])
        self.assertEqual(d["sql_provenance"], {"mode": "rendered", "project_root": "", "commit": head})
        self.assertFalse(list((self.p.root / ".sqlreview").rglob("*.sql")))
        self.assertFalse((self.p.root / "sql/request.sql").exists())

    def test_historical_adapter_and_nested_root(self):
        nested = self.p.root / "nested"
        nested.mkdir()
        self.p = Project(nested, git_repo=False, init=False)
        self.assertEqual(run(["init"], nested, env={"SQLREVIEW_ROOT": str(nested)}).returncode, 0)
        old = self.generated()
        (nested / "render.sh").write_text(ADAPTER.replace("cat payload", "printf 'SELECT 2;\\n'"))
        self.p.commit("new adapter")
        r, data = self.source_call("sr_source_render", old, "sql/request.sql")
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertEqual(data, b"SELECT 1;\n")
        d = json.loads(self.fingerprint().stdout)
        self.assertEqual(d["sql_provenance"]["project_root"], "nested")

    def test_argv_and_exact_bytes(self):
        payload = b"-- header\r\nSELECT '\xc3\xa9';\r\n\n"
        self.generated(payload)
        cfg = self.p.root / ".sqlreview/config.json"
        d = json.loads(cfg.read_text())
        # Additional adapter argv precedes the supplied option pair.
        d["sql_render"]["command"] = ["bash", "render.sh", "literal $(touch injection) with spaces"]
        cfg.write_text(json.dumps(d))
        (self.p.root / "render.sh").write_text(ADAPTER.replace("set -eu", "set -eu\n[ \"$1\" = 'literal $(touch injection) with spaces' ]; shift"))
        self.p.commit("argv")
        r = self.fingerprint()
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertEqual(json.loads(r.stdout)["sql_sha256"], hashlib.sha256(payload).hexdigest())
        self.assertFalse((self.p.root / "injection").exists())

    def test_fingerprint_tracked_newline_path_preserves_literal_bytes(self):
        rel = "sql/line\nbreak\\name.sql"
        path = self.p.sql(rel, "SELECT 1;\n")
        self.p.commit("newline tracked path")
        r = run(["fingerprint", "sql/./discard/../line\nbreak\\name.sql"], self.p.root)
        self.assertEqual(r.returncode, 0, r.stderr)
        fp = json.loads(r.stdout)
        self.assertEqual(fp["sql_path"], rel)
        self.assertEqual(fp["sql_sha256"], hashlib.sha256(path.read_bytes()).hexdigest())
        slug = run(["slug", rel], self.p.root)
        self.assertEqual(slug.returncode, 0, slug.stderr)
        self.assertEqual(slug.stdout.strip(), "sql__line%0Abreak%5Cname")
        doc = review_doc(slug.stdout.strip(), **fp, logic=[], assumptions=[], limitations=[], open_questions=[])
        draft = self.p.write_json(slug.stdout.strip(), "review.draft.json", doc)
        self.assertEqual(run(["check", str(draft)], self.p.root).returncode, 0)

    def test_fingerprint_generated_newline_path_and_argv(self):
        rel = "sql/line\nbreak\\name.sql"
        literal = "literal \"quoted\"\n$(touch injection)\\end"
        payload = b"SELECT 1;\r\n"
        self.generated(payload)
        (self.p.root / "sql/provenance.json").write_text(json.dumps({"schema": 1,
            "requests": {rel: {"source": "builder"}}}))
        cfg = self.p.root / ".sqlreview/config.json"
        doc = json.loads(cfg.read_text())
        doc["sql_render"]["command"] += [literal]
        cfg.write_text(json.dumps(doc))
        (self.p.root / "render.sh").write_text('#!/usr/bin/env bash\nset -eu\n'
            '[ "$1" = ' + shlex.quote(literal) + ' ]; shift\n'
            '[ "$1" = --sql-path ] && [ "$2" = ' + shlex.quote(rel) + ' ]\n'
            '[ "$3" = --output ]\ncat payload > "$4"\n')
        self.p.commit("newline generated path and argv")
        r = run(["fingerprint", rel], self.p.root)
        self.assertEqual(r.returncode, 0, r.stderr)
        fp = json.loads(r.stdout)
        self.assertEqual(fp["sql_path"], rel)
        self.assertEqual(fp["sql_sha256"], hashlib.sha256(payload).hexdigest())
        self.assertEqual(fp["sql_provenance"]["mode"], "rendered")
        self.assertFalse((self.p.root / "injection").exists())

    def test_dirty_source_refused(self):
        self.generated()
        for path in ("payload", ".sqlreview/config.json", "sql/provenance.json", "new-source"):
            with self.subTest(path=path):
                target = self.p.root / path
                old = target.read_bytes() if target.exists() else None
                target.write_text("changed")
                r = self.fingerprint()
                self.assertEqual(r.returncode, 2)
                self.assertIn("uncommitted source", r.stderr)
                if old is None:
                    target.unlink()
                else:
                    target.write_bytes(old)
        self.p.write_json("request", "review.draft.json", {"draft": True})
        (self.p.root / "sql/request.sql").write_text("ignored stale output")
        self.assertEqual(self.fingerprint().returncode, 0)

    def test_generated_path_without_adapter_refused(self):
        self.generated()
        cfg = self.p.root / ".sqlreview/config.json"
        d = json.loads(cfg.read_text()); del d["sql_render"]
        cfg.write_text(json.dumps(d)); self.p.commit("no adapter")
        r = self.fingerprint()
        self.assertEqual(r.returncode, 2)
        self.assertIn("adapter", r.stderr)

    def test_failure_output_not_leaked(self):
        self.generated(adapter="printf 'SECRET SQL'\nprintf 'SECRET SQL' >&2\nexit 1\n")
        r = self.fingerprint()
        self.assertEqual(r.returncode, 2)
        self.assertNotIn("SECRET SQL", r.stdout + r.stderr)
        self.assertIn("render failed", r.stderr)

    def test_missing_or_symlink_output_refused(self):
        for adapter in ("exit 0\n", "ln -s payload \"$4\"\n"):
            with self.subTest(adapter=adapter):
                self.generated(adapter=adapter)
                r = self.fingerprint()
                self.assertEqual(r.returncode, 2)
                self.assertIn("output", r.stderr)

    def test_manifest_classification_refuses_unknown_or_undeclared(self):
        self.generated()
        manifest = self.p.root / "sql/provenance.json"
        for d in ({"schema": 1, "requests": {}}, {"schema": 1, "requests": {"sql/request.sql": {"source": "unknown"}}},
                  {"schema": 1, "requests": []}, {"schema": 1, "requests": {"sql/request.sql": "builder"}}):
            with self.subTest(doc=d):
                manifest.write_text(json.dumps(d)); self.p.commit("invalid manifest")
                self.assertEqual(self.fingerprint().returncode, 2)

    def test_tracked_compatibility_and_explicit_hand_written(self):
        self.p.sql("sql/request.sql", "SELECT 3;\n")
        head = self.p.commit()
        r = self.fingerprint()
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertEqual(json.loads(r.stdout).get("sql_provenance", {}).get("mode"), "tracked")
        r, data = self.source_call("sr_source_render", head, "sql/request.sql")
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertEqual(data, b"SELECT 3;\n")
        (self.p.root / "sql/provenance.json").write_text(json.dumps({"schema": 1, "requests": {
            "sql/request.sql": {"source": "hand-written"}}}))
        self.p.commit("manifest")
        self.assertEqual(self.fingerprint().returncode, 0)

    def test_manifest_hash_semantics(self):
        payload = b"\xef\xbb\xbfSELECT 1;\r\n\r\n"
        self.generated(payload)
        manifest = self.p.root / "sql/provenance.json"
        d = json.loads(manifest.read_text())
        entry = d["requests"]["sql/request.sql"]
        for algorithm, sha in ((None, hashlib.sha256(b"SELECT 1;\n").hexdigest()),
                               ("sha256-raw", hashlib.sha256(payload).hexdigest())):
            entry["sha256"] = sha
            if algorithm is None:
                entry.pop("hash_algorithm", None)
            else:
                entry["hash_algorithm"] = algorithm
            manifest.write_text(json.dumps(d)); self.p.commit("hash contract")
            r = self.fingerprint()
            self.assertEqual(r.returncode, 0, r.stderr)
            self.assertEqual(json.loads(r.stdout)["sql_sha256"], hashlib.sha256(payload).hexdigest())
        entry["sha256"] = "0" * 64
        manifest.write_text(json.dumps(d)); self.p.commit("corrupt hash")
        self.assertEqual(self.fingerprint().returncode, 2)
        entry["sha256"] = hashlib.sha256(b"SELECT 1;\n").hexdigest()
        for invalid_algorithm in ("unknown", None, False, ""):
            entry["hash_algorithm"] = invalid_algorithm
            manifest.write_text(json.dumps(d)); self.p.commit("unknown algorithm")
            self.assertEqual(self.fingerprint().returncode, 2)
        entry.pop("hash_algorithm")
        for invalid_hash in (None, False, ""):
            entry["sha256"] = invalid_hash
            manifest.write_text(json.dumps(d)); self.p.commit("malformed hash")
            self.assertEqual(self.fingerprint().returncode, 2)

    def test_auth_full_hash_before_body_and_legacy_record(self):
        head = self.generated()
        doc = review_doc("sql__request", "sql/request.sql", git_commit=head,
                         sql_sha256=hashlib.sha256(b"SELECT 1;\n").hexdigest())
        path = self.p.write_json("sql__request", "review.json", doc)
        r, data = self.source_call("sr_source_auth", path)
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertEqual(data, b"SELECT 1;\n")
        doc["sql_sha256"] = "0" * 64
        doc["sql_body_sha256"] = hashlib.sha256(b"SELECT 1;\n").hexdigest()
        path.write_text(json.dumps(doc))
        r, _ = self.source_call("sr_source_auth", path)
        self.assertEqual(r.returncode, 6)
        self.assertIn("full SHA", r.stderr)

    def test_source_symlinks_and_replacement_refs_refused(self):
        head = self.generated()
        os.symlink("payload", self.p.root / "linked-source")
        self.p.commit("symlink")
        self.assertEqual(self.fingerprint().returncode, 2)
        git(self.p.root, "reset", "--hard", head)
        git(self.p.root, "replace", head, head)
        self.assertEqual(self.fingerprint().returncode, 2)

    def test_provenance_schema_binding(self):
        head = self.generated()
        doc = review_doc("sql__request", "sql/request.sql", git_commit=head,
                         sql_provenance={"mode": "rendered", "project_root": "", "commit": head})
        def check():
            return run(["check", "--stdin"], self.p.root, stdin=json.dumps(doc))
        self.assertEqual(check().returncode, 0)
        for value in ({"mode": "unknown", "project_root": "", "commit": head},
                      {"mode": "rendered", "project_root": "../outside", "commit": head},
                      {"mode": "rendered", "project_root": "", "commit": "a" * 40}):
            doc["sql_provenance"] = value
            self.assertEqual(check().returncode, 4)

    def test_manifest_canonicalization_preserves_lone_final_cr(self):
        self.generated(b"SELECT 1;\r")
        path = self.p.root / "sql/provenance.json"
        d = json.loads(path.read_text())
        d["requests"]["sql/request.sql"]["sha256"] = hashlib.sha256(b"SELECT 1;\r\n").hexdigest()
        path.write_text(json.dumps(d)); self.p.commit("lone CR")
        r = self.fingerprint()
        self.assertEqual(r.returncode, 0, r.stderr)

    def test_nondeterministic_render_refused(self):
        self.generated(adapter='head -c 32 /dev/urandom > "$4"\n')
        r = self.fingerprint()
        self.assertEqual(r.returncode, 2)
        self.assertIn("nondeterministic", r.stderr)

    def test_auth_missing_commit_and_dirty_record_refused(self):
        head = self.generated()
        doc = review_doc("sql__request", "sql/request.sql", git_commit=head,
                         sql_sha256=hashlib.sha256(b"SELECT 1;\n").hexdigest())
        path = self.p.write_json("sql__request", "review.json", doc)
        for commit, dirty in (("f" * 40, False), (head, True), (None, False),
                              (head, "false"), (head, {})):
            doc.update(git_commit=commit, git_dirty=dirty); path.write_text(json.dumps(doc))
            r, data = self.source_call("sr_source_auth", path)
            self.assertEqual(r.returncode, 6)
            self.assertIsNone(data)

    def test_tracked_source_uses_exact_git_blob_with_checkout_attributes(self):
        self.p.sql("sql/request.sql", "SELECT 3;\n")
        (self.p.root / ".gitattributes").write_text("*.sql text eol=crlf\n")
        self.p.commit()
        r = self.fingerprint()
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertEqual(json.loads(r.stdout)["sql_sha256"], hashlib.sha256(b"SELECT 3;\n").hexdigest())

    def test_adapter_does_not_inherit_shell_startup(self):
        self.generated()
        with tempfile.TemporaryDirectory() as external:
            startup = Path(external) / "startup.sh"
            startup.write_text('case "$PWD" in */sqlreview-source.*/tree) '
                               'printf "SELECT 777;\\n" > payload;; esac\n')
            r = run(["fingerprint", "sql/request.sql"], self.p.root,
                    env={"BASH_ENV": str(startup), "ENV": str(startup)})
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertEqual(json.loads(r.stdout)["sql_sha256"], hashlib.sha256(b"SELECT 1;\n").hexdigest())

    def test_adapter_private_environment_and_usable_command_path(self):
        self.generated()
        with tempfile.TemporaryDirectory() as external:
            outside = Path(external)
            (outside / "home").mkdir()
            (outside / "home/current-source-config").write_text("SELECT 777;\n")
            (outside / "bin").mkdir()
            tool = outside / "bin/fixture-renderer"
            tool.write_text('''#!/usr/bin/env bash
set -eu
for name in PYTHONPATH PYTHONHOME VIRTUAL_ENV NODE_OPTIONS AWS_ACCESS_KEY_ID PGPASSWORD CURRENT_SOURCE_CONFIG SQLREVIEW_ROOT BASH_ENV ENV; do
    ! printenv "$name" >/dev/null || exit 1
done
[ ! -e "$HOME/current-source-config" ]
[ "$LC_ALL" = C ] && [ "$TZ" = UTC ]
for directory in "$HOME" "$TMPDIR" "$XDG_CONFIG_HOME" "$XDG_CACHE_HOME" "$XDG_DATA_HOME" "$XDG_STATE_HOME"; do
    [ -d "$directory" ] && [ "$directory" != "$PWD" ]
done
cat payload > "$4"
''')
            tool.chmod(0o755)
            config = self.p.root / ".sqlreview/config.json"
            d = json.loads(config.read_text())
            d["sql_render"]["command"] = ["fixture-renderer"]
            config.write_text(json.dumps(d)); self.p.commit("explicit command runtime")
            overrides = {name: "external-override" for name in
                         ("PYTHONPATH", "PYTHONHOME", "VIRTUAL_ENV", "NODE_OPTIONS",
                          "AWS_ACCESS_KEY_ID", "PGPASSWORD", "CURRENT_SOURCE_CONFIG")}
            overrides.update(HOME=str(outside / "home"), PATH=str(outside / "bin") + os.pathsep + os.environ["PATH"])
            r = run(["fingerprint", "sql/request.sql"], self.p.root, env=overrides)
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertEqual(json.loads(r.stdout)["sql_sha256"], hashlib.sha256(b"SELECT 1;\n").hexdigest())

    def test_checkout_does_not_inherit_current_git_filters(self):
        self.generated()
        (self.p.root / ".gitattributes").write_text("payload filter=inject\n")
        self.p.commit("committed attributes")
        with tempfile.TemporaryDirectory() as external:
            smudge = Path(external) / "smudge"
            smudge.write_text("#!/bin/sh\nsed 's/SELECT 1/SELECT 888/'\n")
            smudge.chmod(0o755)
            config = Path(external) / "gitconfig"
            config.write_text('[filter "inject"]\n'
                              f'    smudge = {smudge}\n    clean = cat\n    required = true\n')
            r = run(["fingerprint", "sql/request.sql"], self.p.root,
                    env={"GIT_CONFIG_GLOBAL": str(config)})
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertEqual(json.loads(r.stdout)["sql_sha256"], hashlib.sha256(b"SELECT 1;\n").hexdigest())

    def test_auth_new_provenance_requires_false_dirty_and_legacy_null_is_supported(self):
        head = self.generated()
        doc = review_doc("sql__request", "sql/request.sql", git_commit=head,
                         sql_sha256=hashlib.sha256(b"SELECT 1;\n").hexdigest(),
                         sql_provenance={"mode": "rendered", "project_root": "", "commit": head})
        path = self.p.write_json("sql__request", "review.json", doc)
        for absent in (False, True):
            if absent:
                doc.pop("git_dirty", None)
            else:
                doc["git_dirty"] = None
            path.write_text(json.dumps(doc))
            r, data = self.source_call("sr_source_auth", path)
            self.assertEqual(r.returncode, 6)
            self.assertIsNone(data)
        doc["git_dirty"] = False; path.write_text(json.dumps(doc))
        self.assertEqual(self.source_call("sr_source_auth", path)[0].returncode, 0)
        del doc["sql_provenance"]
        for absent in (False, True):
            if absent:
                doc.pop("git_dirty", None)
            else:
                doc["git_dirty"] = None
            path.write_text(json.dumps(doc))
            r, data = self.source_call("sr_source_auth", path)
            self.assertEqual(r.returncode, 0, r.stderr)
            self.assertEqual(data, b"SELECT 1;\n")
