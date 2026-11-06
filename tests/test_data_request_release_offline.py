"""L1: release evidence makes no network call, even in a partial clone.

A partial clone (--filter=blob:none) fetches a missing blob from its remote when git reads it. Evidence
must not do that. Every git of the source helpers runs with GIT_NO_LAZY_FETCH=1 (git 2.44 and later read
it). Where git is older than 2.44 and the repository is a partial clone, evidence fails closed with a
fixed message. The tests count calls to the remote through a logging upload-pack, which sees every fetch,
whatever process starts it. Synthetic data only.
"""

import os
import shutil
import stat
import subprocess
import tempfile
import unittest
from pathlib import Path

try:  # `unittest discover -s tests` puts tests/ on sys.path; `-m unittest tests.x` does not
    from test_data_request_release import RELEASE, SQL_PATH, SQL_V2, Project, clean_env, git, run
except ModuleNotFoundError:
    from tests.test_data_request_release import RELEASE, SQL_PATH, SQL_V2, Project, clean_env, git, run

MESSAGE = "this repository is a partial clone and git is older than 2.44"


def git_version():
    out = subprocess.run(["git", "--version"], capture_output=True, text=True).stdout.split()[2]
    major, minor = out.split(".")[:2]
    return int(major), int("".join(c for c in minor if c.isdigit()))


@unittest.skipUnless(shutil.which("jq") and shutil.which("git"), "release.sh needs jq and git")
class PartialClone(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="partial-"))
        self.addCleanup(shutil.rmtree, self.tmp, True)
        (self.tmp / "src").mkdir()
        self.src = Project(str(self.tmp / "src"))
        self.log = self.tmp / "upload-pack.log"

    def make_source(self, change_sql):
        """The source repo: the review is bound to the first commit. With change_sql the tip holds
        other SQL, so the reviewed blob is not in a clone that checks out the tip."""
        if change_sql:
            self.src.write(SQL_PATH, SQL_V2)
            self.src.commit("change sql")
        self.src.tag("v1.0.0")
        bare = self.tmp / "bare.git"
        git(self.tmp, "clone", "-q", "--bare", str(self.src.root), str(bare))
        git(bare, "config", "uploadpack.allowFilter", "true")
        git(bare, "config", "uploadpack.allowAnySHA1InWant", "true")
        return bare

    def clone(self, bare, name):
        dest = self.tmp / name
        git(self.tmp, "clone", "-q", "--filter=blob:none", f"file://{bare}", str(dest))
        up = self.tmp / f"up-{name}.sh"
        up.write_text(f'#!/bin/sh\necho called >> "{self.log}"\nexec git upload-pack "$@"\n')
        up.chmod(up.stat().st_mode | stat.S_IXUSR)
        git(dest, "config", "remote.origin.uploadpack", str(up))
        git(dest, "config", "user.email", "t@example")
        git(dest, "config", "user.name", "t")
        self.assertFalse(self.log.exists(), "logging starts after the clone")
        return dest

    def old_git(self, version, name="old"):
        """A git on PATH that reports VERSION and logs GIT_NO_LAZY_FETCH, then runs the real git."""
        wrap = self.tmp / name
        wrap.mkdir()
        env_log = self.tmp / f"{name}-env.log"
        script = wrap / "git"
        script.write_text(
            "#!/bin/sh\n"
            f'[ "$1" = "--version" ] && {{ echo "git version {version}"; exit 0; }}\n'
            f'echo "${{GIT_NO_LAZY_FETCH:-unset}}" >> "{env_log}"\n'
            f'exec "{shutil.which("git")}" "$@"\n')
        script.chmod(0o755)
        return {"PATH": f"{wrap}{os.pathsep}{os.environ['PATH']}"}, env_log

    def test_the_log_sees_a_lazy_fetch_in_a_plain_partial_clone(self):
        # Control: without the helper, reading the missing blob does call the remote.
        bare = self.make_source(change_sql=True)
        dest = self.clone(bare, "control")
        old_blob = git(dest, "rev-parse", f"{self.src.review_commit}:{SQL_PATH}")
        subprocess.run(["git", "cat-file", "-p", old_blob], cwd=dest, capture_output=True, env=clean_env())
        self.assertTrue(self.log.exists(), "the control must reach the remote")

    def test_evidence_with_a_missing_blob_makes_no_fetch(self):
        bare = self.make_source(change_sql=True)
        dest = self.clone(bare, "work")
        r = run(RELEASE, ["evidence", "v1.0.0"], dest)
        self.assertFalse(self.log.exists(), "evidence reached the remote")
        self.assertEqual(r.returncode, 2, r.stdout + r.stderr)
        if git_version() < (2, 44):
            self.assertIn(MESSAGE, r.stderr)
        self.assertNotIn(SQL_PATH, r.stderr)

    def test_an_old_git_fails_closed_in_a_partial_clone_with_a_fixed_message(self):
        bare = self.make_source(change_sql=False)
        dest = self.clone(bare, "work")
        env, _ = self.old_git("2.39.5")
        r = run(RELEASE, ["evidence", "v1.0.0"], dest, env=env)
        self.assertEqual(r.returncode, 2, r.stdout + r.stderr)
        self.assertIn(MESSAGE, r.stderr)
        self.assertIn("full clone", r.stderr)
        self.assertEqual(r.stdout, "")
        self.assertFalse(self.log.exists())

    def test_criteria_also_fails_closed_with_an_old_git(self):
        bare = self.make_source(change_sql=False)
        dest = self.clone(bare, "work")
        env, _ = self.old_git("2.39.5")
        r = run(RELEASE, ["criteria", "v1.0.0"], dest, env=env)
        self.assertEqual(r.returncode, 2, r.stdout + r.stderr)
        self.assertIn(MESSAGE, r.stderr)

    def test_a_current_git_reads_a_partial_clone_when_the_blobs_are_present(self):
        bare = self.make_source(change_sql=False)
        dest = self.clone(bare, "work")
        env, env_log = self.old_git("2.44.0")
        r = run(RELEASE, ["evidence", "v1.0.0"], dest, env=env)
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertIn('"applies": "current"', r.stdout.replace('"applies":"current"', '"applies": "current"'))
        self.assertFalse(self.log.exists())
        seen = set(env_log.read_text().split())
        self.assertEqual(seen, {"1"}, "every git call runs with GIT_NO_LAZY_FETCH=1")

    def test_a_full_clone_is_read_with_an_old_git(self):
        self.make_source(change_sql=False)
        env, _ = self.old_git("2.39.5")
        r = run(RELEASE, ["evidence", "v1.0.0"], self.src.root, env=env)
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertNotIn(MESSAGE, r.stderr)


if __name__ == "__main__":
    unittest.main()
