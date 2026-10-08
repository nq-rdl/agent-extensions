"""Real committed adapters under host Bash and the strict Bash 3.2 fixture."""
import json
import os
import platform
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from test_sql_review_scripts import Project, review_doc, item, REPO
from bash32_fixture import container_runtime, static_jq, run_container

# Diagnose only Git's synthetic fixture checkout, before any adapter/SQL execution.
# Mirror sr_source_isolated's environment and the clone/checkout argv exactly.
GIT_PREFLIGHT = r'''
set -euo pipefail
probe="$(mktemp -d /tmp/sqlreview-git-probe.XXXXXX)"
trap 'rm -rf "$probe"' EXIT
mkdir "$probe/home" "$probe/runtime" "$probe/config" "$probe/cache" "$probe/data" "$probe/state"
head="$(git -C "$PROJECT" rev-parse --verify HEAD)"
fixture_git_isolated() {
  env -i PATH="$PATH" HOME="$probe/home" TMPDIR="$probe/runtime" \
    XDG_CONFIG_HOME="$probe/config" XDG_CACHE_HOME="$probe/cache" \
    XDG_DATA_HOME="$probe/data" XDG_STATE_HOME="$probe/state" \
    LC_ALL=C LANG=C TZ=UTC GIT_CONFIG_NOSYSTEM=1 GIT_CONFIG_GLOBAL=/dev/null "$@"
}
if fixture_git_isolated git -c core.hooksPath=/dev/null clone --quiet --shared --no-checkout "$PROJECT" "$probe/tree" > "$probe/git.log" 2>&1; then
  :
else
  rc=$?
  printf 'fixture Git clone failed (exit %s)\n' "$rc" >&2
  cat "$probe/git.log" >&2
  exit "$rc"
fi
if fixture_git_isolated git -C "$probe/tree" -c core.hooksPath=/dev/null -c core.autocrlf=false checkout --quiet --detach "$head" >> "$probe/git.log" 2>&1; then
  :
else
  rc=$?
  printf 'fixture Git checkout failed (exit %s)\n' "$rc" >&2
  cat "$probe/git.log" >&2
  exit "$rc"
fi
rm -rf "$probe"
trap - EXIT
'''

SCENARIO = r'''
set -euo pipefail
cd "$PROJECT"
S="$FIXTURE/setup/scripts"
# Config argv contains spaces, quotes, a newline and a literal backslash.
# The adapter checks exact argv and SQL paths under the pinned shell too.
newline_path="$(printf 'sql/line\nbreak.sql')"
bash "$S/sqlreview.sh" fingerprint "$newline_path" > "$FIXTURE/newline.json"
jq -e --arg p "$newline_path" '.sql_path==$p and .sql_provenance.mode=="rendered"' "$FIXTURE/newline.json"
tracked_path="$(printf 'sql/tracked\nname.sql')"
bash "$S/sqlreview.sh" fingerprint "$tracked_path" > "$FIXTURE/tracked.json"
jq -e --arg p "$tracked_path" '.sql_path==$p and .sql_provenance.mode=="tracked"' "$FIXTURE/tracked.json"
bash "$S/sqlreview.sh" fingerprint sql/request.sql > "$FIXTURE/fingerprint.json"
jq -s '.[0] * .[1]' "$FIXTURE/base.json" "$FIXTURE/fingerprint.json" > .sqlreview/reviews/sql__request/review.draft.json
bash "$S/sqlreview.sh" publish sql__request review .sqlreview/reviews/sql__request/review.draft.json
bash "$S/sqlreview.sh" snapshot sql__request sql/request.sql
test ! -e sql/request.sql
printf 'SET NOCOUNT ON;\nSELECT 2;\nSELECT 3;\n' > payload
git add payload
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
'''


def fixture(directory):
    tmp = Path(directory)
    shutil.copytree(REPO / "skills/data-request-setup", tmp / "setup")
    project = tmp / "project"
    project.mkdir()
    p = Project(project)
    (project / "sql").mkdir()
    (project / ".gitignore").write_text("sql/request.sql\n")
    (project / "payload").write_text("SELECT 1;\nSELECT 3;\n")
    (project / "render.sh").write_text(r'''#!/usr/bin/env bash
set -eu
[ "$1" = 'literal argument
"quoted"\end' ] && [ "$2" = --sql-path ]
case "$3" in sql/request.sql|'sql/line
break.sql') ;; *) exit 2;; esac
[ "$4" = --output ]
case "$5" in /*) ;; *) exit 2;; esac
cat payload > "$5"
''')
    config = project / ".sqlreview/config.json"
    d = json.loads(config.read_text())
    d["sql_render"] = {"command": ["bash", "render.sh", 'literal argument\n"quoted"\\end']}
    config.write_text(json.dumps(d))
    (project / "sql/provenance.json").write_text(json.dumps({"schema": 1, "requests": {
        "sql/request.sql": {"source": "builder"}, "sql/line\nbreak.sql": {"source": "builder"},
        "sql/tracked\nname.sql": {"source": "hand-written"}}}))
    (project / "sql/tracked\nname.sql").write_text("SELECT 7;\n")
    p.commit()
    p.review_dir("sql__request")
    (tmp / "base.json").write_text(json.dumps(review_doc("sql__request", "sql/request.sql",
        assumptions=[item("A1", "Retain this range", location={"lines": [2, 2]})],
        limitations=[], logic=[], open_questions=[])))
    return project


class HostSources(unittest.TestCase):
    def test_adapter_historical_publish_and_carry(self):
        with tempfile.TemporaryDirectory() as tmp:
            project = fixture(tmp)
            r = subprocess.run(["bash", "-c", SCENARIO], text=True, capture_output=True,
                env={**os.environ, "PROJECT": str(project), "FIXTURE": tmp}, timeout=120)
            self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
            self.assertIn("source-contract-ok", r.stdout)


class Bash32Sources(unittest.TestCase):
    def setUp(self):
        if not container_runtime() or not static_jq():
            self.skipTest("needs pinned Bash 3.2 image and verified jq; see docs/bash32-portability.md")

    def test_adapter_historical_publish_and_carry(self):
        from bash32_fixture import copy_host_git
        with tempfile.TemporaryDirectory() as tmp:
            fixture(tmp)
            shutil.copyfile(static_jq(), Path(tmp) / "jq")
            (Path(tmp) / "jq").chmod(0o755)
            copy_host_git(Path(tmp), "/w")
            command = 'export PATH=/w/bin:/w:$PATH PROJECT=/w/project FIXTURE=/w; ' + GIT_PREFLIGHT + SCENARIO
            r = run_container(tmp, "/w", command)
            self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
            self.assertIn("source-contract-ok", r.stdout)


class HostGitFixture(unittest.TestCase):
    def test_copied_git_transport_clone_and_fetch_without_host_helpers(self):
        if platform.system() != "Linux" or platform.machine() not in ("x86_64", "amd64"):
            self.skipTest("host Git transport fixture requires Linux amd64")
        from bash32_fixture import copy_host_git
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            project = fixture(tmp)
            copy_host_git(root, tmp)
            for name in ("empty-exec-path", "home", "runtime", "config", "cache", "data", "state"):
                (root / name).mkdir()
            # A complete replacement environment and empty exec-path prevent installed
            # git-upload-pack/pack helpers from masking missing fixture dependencies.
            env = {"PATH": str(root / "bin"), "HOME": str(root / "home"),
                   "TMPDIR": str(root / "runtime"), "XDG_CONFIG_HOME": str(root / "config"),
                   "XDG_CACHE_HOME": str(root / "cache"), "XDG_DATA_HOME": str(root / "data"),
                   "XDG_STATE_HOME": str(root / "state"), "LC_ALL": "C", "LANG": "C", "TZ": "UTC",
                   "GIT_CONFIG_NOSYSTEM": "1", "GIT_CONFIG_GLOBAL": "/dev/null",
                   "GIT_EXEC_PATH": str(root / "empty-exec-path"), "GIT_TRACE": str(root / "git.trace")}
            copied_git = str(root / "bin/git")
            exec_path = subprocess.run([copied_git, "--exec-path"], env=env, text=True, capture_output=True, check=True)
            self.assertEqual(exec_path.stdout.strip(), str(root / "empty-exec-path"))
            clone = root / "clone"
            cloned = subprocess.run([copied_git, "-c", "core.hooksPath=/dev/null", "clone", "--no-local",
                                     "--no-checkout", str(project), str(clone)],
                                    env=env, text=True, capture_output=True)
            self.assertEqual(cloned.returncode, 0, cloned.stdout + cloned.stderr)
            self.assertTrue(list((clone / ".git/objects/pack").glob("*.pack")))
            checkout = subprocess.run([copied_git, "-C", str(clone), "-c", "core.hooksPath=/dev/null",
                                       "checkout", "--detach", "HEAD"], env=env, text=True, capture_output=True)
            self.assertEqual(checkout.returncode, 0, checkout.stdout + checkout.stderr)
            self.assertEqual((clone / "payload").read_bytes(), b"SELECT 1;\nSELECT 3;\n")
            (project / "payload").write_text("SELECT 99;\n")
            subprocess.run(["git", "-C", str(project), "add", "payload"], check=True)
            subprocess.run(["git", "-C", str(project), "-c", "commit.gpgsign=false", "commit", "-qm", "transport update"], check=True)
            fetched = subprocess.run([copied_git, "-C", str(clone), "fetch", "origin"],
                                     env=env, text=True, capture_output=True)
            self.assertEqual(fetched.returncode, 0, fetched.stdout + fetched.stderr)
            updated = subprocess.run([copied_git, "-C", str(clone), "checkout", "--detach", "FETCH_HEAD"],
                                     env=env, text=True, capture_output=True)
            self.assertEqual(updated.returncode, 0, updated.stdout + updated.stderr)
            self.assertEqual((clone / "payload").read_bytes(), b"SELECT 99;\n")
            trace = (root / "git.trace").read_text()
            for subprocess_name in ("upload-pack", "pack-objects", "index-pack"):
                self.assertIn(subprocess_name, trace)

    def test_isolated_git_preflight_exposes_corrupt_checkout_error_without_sql(self):
        if platform.system() != "Linux" or platform.machine() not in ("x86_64", "amd64"):
            self.skipTest("host Git preflight requires Linux amd64")
        from bash32_fixture import copy_host_git
        with tempfile.TemporaryDirectory() as tmp:
            project = fixture(tmp)
            copy_host_git(Path(tmp), tmp)
            env = {**os.environ, "PROJECT": str(project),
                   "PATH": str(Path(tmp) / "bin") + os.pathsep + os.environ["PATH"]}
            success = subprocess.run(["bash", "-c", GIT_PREFLIGHT], env=env, text=True, capture_output=True)
            self.assertEqual(success.returncode, 0, success.stdout + success.stderr)
            tree = subprocess.run(["git", "-C", str(project), "rev-parse", "HEAD^{tree}"],
                                  text=True, capture_output=True, check=True).stdout.strip()
            (project / ".git/objects" / tree[:2] / tree[2:]).unlink()
            failed = subprocess.run(["bash", "-c", GIT_PREFLIGHT], env=env, text=True, capture_output=True)
            self.assertNotEqual(failed.returncode, 0)
            self.assertIn("fixture Git checkout failed", failed.stderr)
            self.assertIn("fatal:", failed.stderr)
            self.assertNotIn("SELECT", failed.stdout + failed.stderr)

    def test_fixture_ownership_trust_resets_inherited_safe_directories(self):
        if platform.system() != "Linux" or platform.machine() not in ("x86_64", "amd64"):
            self.skipTest("host Git copy ownership test requires Linux amd64")
        with tempfile.TemporaryDirectory() as tmp:
            inherited = Path(tmp) / "gitconfig"
            inherited.write_text('[safe]\n\tdirectory = *\n')
            configurations = (
                {"GIT_CONFIG_COUNT": "1", "GIT_CONFIG_KEY_0": "safe.directory", "GIT_CONFIG_VALUE_0": "*"},
                {"GIT_CONFIG_PARAMETERS": "'safe.directory'='*'"},
                {"GIT_CONFIG_GLOBAL": str(inherited)},
                {"SUDO_UID": str(os.getuid())},
            )
            for inherited_env in configurations:
                with self.subTest(configuration=next(iter(inherited_env))), patch.dict(os.environ, inherited_env):
                    # Exercise actual copied Git, refusal, clone and fingerprint in each environment.
                    self.test_fixture_ownership_trust_is_exact_and_allows_fingerprint()

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
            cloned = subprocess.run([str(Path(tmp) / "bin/git"), "clone", "--shared", "--no-checkout",
                                     str(project), str(Path(tmp) / "clone")],
                                    env=env, text=True, capture_output=True)
            self.assertEqual(cloned.returncode, 0, cloned.stdout + cloned.stderr)
            # The hook also marks the newly created destination unowned. It stays
            # refused unless that one disposable path is explicitly trusted.
            checkout = [str(Path(tmp) / "bin/git"), "-C", str(Path(tmp) / "clone")]
            refused_clone = subprocess.run(checkout + ["checkout", "--detach", "HEAD"],
                                           env=env, text=True, capture_output=True)
            self.assertEqual(refused_clone.returncode, 128, refused_clone.stdout + refused_clone.stderr)
            trusted_clone = subprocess.run(checkout + ["-c", "safe.directory=" + str(Path(tmp) / "clone"),
                                                       "checkout", "--detach", "HEAD"],
                                           env=env, text=True, capture_output=True)
            self.assertEqual(trusted_clone.returncode, 0, trusted_clone.stdout + trusted_clone.stderr)
            r = subprocess.run(["bash", str(Path(tmp) / "setup/scripts/sqlreview.sh"),
                                "fingerprint", "sql/request.sql"], cwd=project,
                               env=env, text=True, capture_output=True)
            self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
            self.assertEqual(json.loads(r.stdout)["sql_provenance"]["mode"], "rendered")

    def test_real_git_copy_is_self_contained(self):
        if platform.system() != "Linux" or platform.machine() not in ("x86_64", "amd64"):
            self.skipTest("host Git copy smoke test requires Linux amd64")
        from bash32_fixture import copy_host_git
        with tempfile.TemporaryDirectory() as tmp:
            copy_host_git(Path(tmp), tmp)
            r = subprocess.run([str(Path(tmp) / "bin/git"), "--version"], capture_output=True, text=True)
            self.assertEqual(r.returncode, 0, r.stderr)
            self.assertTrue(r.stdout.startswith("git version "))


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
