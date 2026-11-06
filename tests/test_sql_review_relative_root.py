"""L3: a relative SQLREVIEW_ROOT names the same directory the existence check used.

The check ran against the current directory, but the value was normalised as if it were absolute, so
SQLREVIEW_ROOT=relroot became /relroot. The root is now made absolute against the current directory.
Synthetic data only.
"""

import json
import shutil
import tempfile
import unittest
from pathlib import Path

try:  # `unittest discover -s tests` puts tests/ on sys.path; `-m unittest tests.x` does not
    from test_sql_review_scripts import Project, git, run
    from test_data_request_release import RELEASE
    from test_data_request_release import run as release_run
except ModuleNotFoundError:
    from tests.test_sql_review_scripts import Project, git, run
    from tests.test_data_request_release import RELEASE
    from tests.test_data_request_release import run as release_run


@unittest.skipUnless(shutil.which("jq") and shutil.which("git"), "the scripts need jq and git")
class RelativeRoot(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.parent = Path(self.tmp.name).resolve()
        (self.parent / "relroot").mkdir()
        self.p = Project(str(self.parent / "relroot"))
        git(self.p.root, "remote", "add", "origin", "https://example.org/zztest.git")

    def test_status_reports_the_real_directory(self):
        for value in ("relroot", "./relroot", "relroot/", "relroot/../relroot"):
            with self.subTest(value=value):
                r = run(["status", "--json"], self.parent, env={"SQLREVIEW_ROOT": value})
                self.assertEqual(r.returncode, 0, r.stderr)
                self.assertEqual(json.loads(r.stdout)["root"], str(self.parent / "relroot"))

    def test_an_absolute_root_is_unchanged(self):
        r = run(["status", "--json"], self.parent, env={"SQLREVIEW_ROOT": str(self.parent / "relroot")})
        self.assertEqual(json.loads(r.stdout)["root"], str(self.parent / "relroot"))

    def test_a_relative_root_without_a_store_is_not_found(self):
        r = run(["status", "--json"], self.parent, env={"SQLREVIEW_ROOT": "nowhere"})
        self.assertEqual(r.returncode, 3, r.stdout + r.stderr)

    def test_fetch_command_sees_the_remote(self):
        r = release_run(RELEASE, ["fetch-command"], self.parent, env={"SQLREVIEW_ROOT": "relroot"})
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertEqual(r.stdout.strip(), f"git -C '{self.parent / 'relroot'}' fetch --tags origin")


if __name__ == "__main__":
    unittest.main()
