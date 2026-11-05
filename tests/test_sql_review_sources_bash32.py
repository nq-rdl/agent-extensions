"""Committed SQL read from git under host Bash and the strict Bash 3.2 fixture."""
import json
import os
import platform
import stat
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from test_sql_review_scripts import Project, review_doc, item, REPO
from bash32_fixture import container_runtime, static_jq, run_container

SCENARIO = r"""
set -euo pipefail
cd "$PROJECT"
S="$FIXTURE/setup/scripts"
# Builder SQL is committed; provenance.json does not select another route under the pinned shell.
newline_path="$(printf 'sql/line\nbreak.sql')"
bash "$S/sqlreview.sh" fingerprint "$newline_path" > "$FIXTURE/newline.json"
jq -e --arg p "$newline_path" '.sql_path==$p and .git_dirty==false and (has("sql_provenance") | not)' "$FIXTURE/newline.json"
bash "$S/sqlreview.sh" fingerprint sql/request.sql > "$FIXTURE/fingerprint.json"
jq -s '.[0] * .[1]' "$FIXTURE/base.json" "$FIXTURE/fingerprint.json" > .sqlreview/reviews/sql__request/review.draft.json
bash "$S/sqlreview.sh" publish sql__request review .sqlreview/reviews/sql__request/review.draft.json
bash "$S/sqlreview.sh" snapshot sql__request sql/request.sql
bash "$S/sqlreview.sh" status --json | jq -e '.reviews[0].state=="current"'
printf 'SET NOCOUNT ON;\nSELECT 2;\nSELECT 3;\n' > sql/request.sql
# An uncommitted edit is stale for status and a diff for delta, never a refusal.
bash "$S/sqlreview.sh" status --json | jq -e '.reviews[0].state=="stale"'
set +e
bash "$S/sqlreview.sh" delta sql__request > "$FIXTURE/delta.txt"
rc=$?
set -e
test "$rc" = 10
grep -q '^+SET NOCOUNT ON;' "$FIXTURE/delta.txt"
git add sql/request.sql
git -c commit.gpgsign=false commit -qm 'builder shift'
bash "$S/sqlreview.sh" fingerprint sql/request.sql > "$FIXTURE/fingerprint.json"
jq -s '.[0] * .[1] | .revision=2' .sqlreview/reviews/sql__request/review.json "$FIXTURE/fingerprint.json" > .sqlreview/reviews/sql__request/review.draft.json
bash "$S/sqlreview.sh" remap sql__request .sqlreview/reviews/sql__request/review.draft.json
bash "$S/sqlreview.sh" carryforward sql__request review .sqlreview/reviews/sql__request/review.draft.json > "$FIXTURE/carry.json"
jq -e '.carry[0].basis=="lines-unchanged" and .carry[0].set.confirmed_revision==1' "$FIXTURE/carry.json"
jq --slurpfile carry "$FIXTURE/carry.json" '.assumptions[0] += $carry[0].carry[0].set' .sqlreview/reviews/sql__request/review.draft.json > "$FIXTURE/draft.json"
cp "$FIXTURE/draft.json" .sqlreview/reviews/sql__request/review.draft.json
bash "$S/sqlreview.sh" publish sql__request review .sqlreview/reviews/sql__request/review.draft.json
jq -e '.revision==1' .sqlreview/reviews/sql__request/history/review/1.json
T="$(mktemp -d /tmp/sqlreview-fixture.XXXXXX)"
trap 'rm -rf "$T"' EXIT
bash "$S/sqlreview.sh" materialize sql__request review 1 "$T/old.sql"
printf 'SELECT 1;\nSELECT 3;\n' > "$T/expected.sql"
cmp "$T/old.sql" "$T/expected.sql"
set +e
bash "$S/sqlreview.sh" materialize sql__request review 9 "$T/missing.sql"
rc=$?
set -e
test "$rc" = 6
test ! -e "$T/missing.sql"
test -z "$(find .sqlreview -name '*.sql' -print)"
printf 'source-contract-ok\n'
"""


def fixture(directory):
    tmp = Path(directory)
    shutil.copytree(REPO / "skills/data-request-setup", tmp / "setup")
    project = tmp / "project"
    project.mkdir()
    p = Project(project)
    (project / "sql").mkdir()
    (project / "sql/request.sql").write_text("SELECT 1;\nSELECT 3;\n")
    (project / "sql/line\nbreak.sql").write_text("SELECT 7;\n")
    (project / "sql/provenance.json").write_text(json.dumps({"schema": 1, "requests": {
        "sql/request.sql": {"source": "builder"}, "sql/line\nbreak.sql": {"source": "cohort"}}}))
    p.commit()
    p.review_dir("sql__request")
    (tmp / "base.json").write_text(json.dumps(review_doc("sql__request", "sql/request.sql",
        assumptions=[item("A1", "Retain this range", location={"lines": [2, 2]})],
        limitations=[], logic=[], open_questions=[])))
    return project


def assert_private_history(case, project):
    history = project / ".sqlreview/reviews/sql__request/history"
    case.assertEqual(history.stat().st_uid, os.getuid())
    case.assertEqual(history.stat().st_gid, os.getgid())
    case.assertEqual(stat.S_IMODE(history.stat().st_mode), 0o700)


class HostSources(unittest.TestCase):
    def test_committed_publish_diff_and_carry(self):
        with tempfile.TemporaryDirectory() as tmp:
            project = fixture(tmp)
            r = subprocess.run(["bash", "-c", SCENARIO], text=True, capture_output=True,
                env={**os.environ, "PROJECT": str(project), "FIXTURE": tmp}, timeout=120)
            self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
            self.assertIn("source-contract-ok", r.stdout)
            assert_private_history(self, project)
        self.assertFalse(Path(tmp).exists())


class Bash32Sources(unittest.TestCase):
    def setUp(self):
        if not container_runtime() or not static_jq():
            self.skipTest("needs pinned Bash 3.2 image and verified jq; see docs/bash32-portability.md")

    def test_committed_publish_diff_and_carry(self):
        from bash32_fixture import copy_host_git
        with tempfile.TemporaryDirectory() as tmp:
            project = fixture(tmp)
            shutil.copyfile(static_jq(), Path(tmp) / "jq")
            (Path(tmp) / "jq").chmod(0o755)
            copy_host_git(Path(tmp), "/w")
            # Preserve private 0700 review history while keeping bind-mount output
            # owned by the host caller, who must remove the disposable fixture.
            command = 'export PATH=/w/bin:/w:$PATH PROJECT=/w/project FIXTURE=/w HOME=/w XDG_CONFIG_HOME=/w/config; ' + SCENARIO
            r = run_container(tmp, "/w", command, user=f"{os.getuid()}:{os.getgid()}")
            self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
            self.assertIn("source-contract-ok", r.stdout)
            assert_private_history(self, project)
        self.assertFalse(Path(tmp).exists())


class HostGitFixture(unittest.TestCase):
    def test_fixture_ownership_trust_is_exact_and_allows_fingerprint(self):
        if platform.system() != "Linux" or platform.machine() not in ("x86_64", "amd64"):
            self.skipTest("host Git copy ownership test requires Linux amd64")
        from bash32_fixture import copy_host_git
        with tempfile.TemporaryDirectory() as tmp:
            project = fixture(tmp)
            unrelated = Path(tmp) / "unrelated"
            unrelated.mkdir()
            subprocess.run(["git", "init", "-q", str(unrelated)], check=True)
            copy_host_git(Path(tmp), tmp)
            env = {**os.environ, "GIT_TEST_ASSUME_DIFFERENT_OWNER": "1",
                   "PATH": str(Path(tmp) / "bin") + os.pathsep + os.environ["PATH"]}
            # Real Git's test hook exercises ownership refusal without chown/root/container.
            refused = subprocess.run([str(Path(tmp) / "bin/git"), "-C", str(unrelated), "status"],
                                     env=env, text=True, capture_output=True)
            self.assertEqual(refused.returncode, 128, refused.stdout + refused.stderr)
            self.assertIn("dubious ownership", refused.stderr)
            r = subprocess.run(["bash", str(Path(tmp) / "setup/scripts/sqlreview.sh"),
                                "fingerprint", "sql/request.sql"], cwd=project,
                               env=env, text=True, capture_output=True)
            self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
            self.assertIs(json.loads(r.stdout)["git_dirty"], False)

    def test_real_git_copy_is_self_contained(self):
        if platform.system() != "Linux" or platform.machine() not in ("x86_64", "amd64"):
            self.skipTest("host Git copy smoke test requires Linux amd64")
        from bash32_fixture import copy_host_git
        with tempfile.TemporaryDirectory() as tmp:
            copy_host_git(Path(tmp), tmp)
            r = subprocess.run([str(Path(tmp) / "bin/git"), "--version"], capture_output=True, text=True)
            self.assertEqual(r.returncode, 0, r.stderr)
            self.assertTrue(r.stdout.startswith("git version "))


class SourceContainerOwnership(unittest.TestCase):
    def test_container_user_option_precedes_image_and_defaults_unchanged(self):
        from bash32_fixture import BASH32_IMAGE
        with patch("bash32_fixture.container_runtime", return_value="fixture-docker"), \
             patch("bash32_fixture.subprocess.run") as execute:
            run_container("/fixture", "/w", "true", user="1001:1001")
            args = execute.call_args.args[0]
            self.assertEqual(args[args.index("--user") + 1], "1001:1001")
            self.assertLess(args.index("--user"), args.index(BASH32_IMAGE))
            self.assertIn("--network=none", args)
            self.assertIn("--pull=never", args)
            run_container("/fixture", "/w", "true")
            self.assertNotIn("--user", execute.call_args.args[0])

    def test_source_fixture_selects_actual_caller_uid_gid(self):
        def host_scenario(directory, target, command, *, user):
            # The launcher boundary is substituted, but run the real scenario and
            # its caller-owned private-history/cleanup assertions on the host.
            return subprocess.run(["bash", "-c", SCENARIO], text=True, capture_output=True,
                                  env={**os.environ, "PROJECT": str(Path(directory) / "project"),
                                       "FIXTURE": directory}, timeout=120)

        with tempfile.TemporaryDirectory() as tmp:
            jq = Path(tmp) / "input-jq"
            jq.write_bytes(b"fixture-jq")
            with patch("test_sql_review_sources_bash32.container_runtime", return_value="fixture-docker"), \
                 patch("test_sql_review_sources_bash32.static_jq", return_value=str(jq)), \
                 patch("bash32_fixture.copy_host_git"), \
                 patch("test_sql_review_sources_bash32.run_container") as launch:
                launch.side_effect = host_scenario
                result = unittest.TestResult()
                Bash32Sources("test_committed_publish_diff_and_carry").run(result)
            self.assertTrue(result.wasSuccessful(), result.errors + result.failures)
            self.assertEqual(launch.call_args.kwargs.get("user"), f"{os.getuid()}:{os.getgid()}")


class HostGitPlatformContract(unittest.TestCase):
    def test_ordinary_smoke_skips_unsupported_hosts_before_copying(self):
        for system, machine in (("Darwin", "x86_64"), ("Darwin", "arm64"),
                                ("Linux", "aarch64"), ("Linux", "arm64")):
            with self.subTest(system=system, machine=machine):
                with patch("bash32_fixture.platform.system", return_value=system), \
                     patch("bash32_fixture.platform.machine", return_value=machine), \
                     patch("bash32_fixture.copy_host_git") as copy:
                    result = unittest.TestResult()
                    HostGitFixture("test_real_git_copy_is_self_contained").run(result)
                self.assertEqual(result.testsRun, 1)
                self.assertEqual(len(result.skipped), 1)
                self.assertEqual(result.errors, [])
                self.assertEqual(result.failures, [])
                copy.assert_not_called()

    def test_ordinary_smoke_executes_copy_on_supported_linux_aliases(self):
        for machine in ("x86_64", "amd64"):
            with self.subTest(machine=machine):
                with patch("bash32_fixture.platform.system", return_value="Linux"), \
                     patch("bash32_fixture.platform.machine", return_value=machine), \
                     patch("bash32_fixture.copy_host_git") as copy, \
                     patch("test_sql_review_sources_bash32.subprocess.run") as execute:
                    execute.return_value = subprocess.CompletedProcess([], 0, "git version fixture\n", "")
                    result = unittest.TestResult()
                    HostGitFixture("test_real_git_copy_is_self_contained").run(result)
                self.assertTrue(result.wasSuccessful(), result.errors + result.failures)
                self.assertEqual(result.skipped, [])
                copy.assert_called_once()
                self.assertEqual(execute.call_args.args[0][-1], "--version")

    def test_strict_copy_still_rejects_unsupported_hosts(self):
        from bash32_fixture import copy_host_git
        for system, machine in (("Darwin", "x86_64"), ("Linux", "aarch64")):
            with self.subTest(system=system, machine=machine):
                with patch("bash32_fixture.platform.system", return_value=system), \
                     patch("bash32_fixture.platform.machine", return_value=machine), \
                     patch("bash32_fixture.subprocess.run") as execute:
                    with self.assertRaisesRegex(RuntimeError, "requires Linux amd64 host Git"):
                        copy_host_git(Path("unused"), "/w")
                    execute.assert_not_called()


if __name__ == "__main__":
    unittest.main()
