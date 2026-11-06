"""L1: release evidence makes no network call, even in a partial clone.

A partial clone (--filter=blob:none) fetches a missing blob from its remote when git reads it. Evidence
must not do that. Every git of the source helpers runs with GIT_NO_LAZY_FETCH=1 (git 2.44 and later read
it). Some gits ignore it, and version numbers are unreliable. So evidence, criteria and the source helpers
fail closed in every partial clone, with a fixed message. The tests count calls to the remote through a logging upload-pack, which sees every fetch,
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

MESSAGE = "this repository is a partial clone, so a read could fetch from the network"


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

    def env_logger(self, name="envlog"):
        """A git on PATH that logs GIT_NO_LAZY_FETCH, then runs the real git."""
        wrap = self.tmp / name
        wrap.mkdir()
        env_log = self.tmp / f"{name}.log"
        script = wrap / "git"
        script.write_text(
            "#!/bin/sh\n"
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
        self.assertIn(MESSAGE, r.stderr)
        self.assertIn("full clone", r.stderr)
        self.assertNotIn(SQL_PATH, r.stderr)

    def test_a_real_partial_clone_is_refused_even_with_every_blob_present(self):
        bare = self.make_source(change_sql=False)
        dest = self.clone(bare, "work")
        for args in (["evidence", "v1.0.0"], ["criteria", "v1.0.0"]):
            with self.subTest(args=args):
                r = run(RELEASE, args, dest)
                self.assertEqual(r.returncode, 2, r.stdout + r.stderr)
                self.assertIn(MESSAGE, r.stderr)
                self.assertEqual(r.stdout, "")
        self.assertFalse(self.log.exists())

    def test_each_detection_key_is_refused(self):
        # A full repository with only the key set, so the key alone decides.
        self.make_source(change_sql=False)
        for key, value in (("extensions.partialclone", "origin"), ("remote.origin.promisor", "true"),
                           ("remote.origin.partialclonefilter", "blob:none")):
            with self.subTest(key=key):
                git(self.src.root, "config", key, value)
                for args in (["evidence", "v1.0.0"], ["criteria", "v1.0.0"]):
                    r = run(RELEASE, args, self.src.root)
                    self.assertEqual(r.returncode, 2, r.stdout + r.stderr)
                    self.assertIn(MESSAGE, r.stderr)
                    self.assertEqual(r.stdout, "")
                git(self.src.root, "config", "--unset", key)

    def test_a_promisor_set_to_false_is_not_a_partial_clone(self):
        self.make_source(change_sql=False)
        git(self.src.root, "config", "remote.origin.promisor", "false")
        r = run(RELEASE, ["evidence", "v1.0.0"], self.src.root)
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)

    def test_a_full_clone_is_read_and_every_git_call_has_the_variable(self):
        self.make_source(change_sql=False)
        env, env_log = self.env_logger()
        r = run(RELEASE, ["evidence", "v1.0.0"], self.src.root, env=env)
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertNotIn(MESSAGE, r.stderr)
        self.assertEqual(set(env_log.read_text().split()), {"1"}, "every git call runs with GIT_NO_LAZY_FETCH=1")


if __name__ == "__main__":
    unittest.main()
