"""Committed source reconstruction: generated output is never durable evidence."""
import hashlib
import json
import os
import subprocess
import tempfile
import unittest
from pathlib import Path

from test_sql_review_scripts import Project, REPO, git, run, review_doc

SCRIPTS = REPO / "skills/data-request-setup/scripts"
ADAPTER = '''#!/usr/bin/env bash
set -eu
[ "$1" = --sql-path ] && [ "$2" = 'sql/request.sql' ]
[ "$3" = --output ]
cat payload > "$4"
'''


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

    def source_call(self, function, *args):
        with tempfile.TemporaryDirectory() as output:
            target = Path(output) / "out.sql"
            env = dict(os.environ, SR_ROOT=str(self.p.root), SR_SCRIPT_DIR=str(SCRIPTS))
            r = subprocess.run(["bash", "-c", '. "$SR_SCRIPT_DIR/sqlreview-lib.sh"; '
                                + function + ' "$@"', "source", *map(str, args), str(target)],
                               cwd=self.p.root, env=env, capture_output=True, text=True)
            data = target.read_bytes() if target.is_file() else None
            return r, data

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
        self.assertEqual(r.returncode, 2)
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
            self.assertEqual(r.returncode, 2)
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
            self.assertEqual(r.returncode, 2)
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
