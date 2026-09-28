"""Issue 379: setup onboarding gaps (non-interactive flags, a trackable reviews/, the string-SQL guard).

The behavioural part drives the real `sqlreview.sh init`: a fresh `.sqlreview/` committed to git
must keep `reviews/` on the next clone, and nothing that lists reviews may count the placeholder.
The skill-contract part pins the non-inferable facts the setup skill now states, in the canonical
skill and in both packaged copies.
"""
import json
import re
import subprocess
import tempfile
import unittest
from pathlib import Path

import yaml

try:  # `unittest discover -s tests` puts tests/ on sys.path; `-m unittest tests.x` does not
    from test_sql_review_scripts import REPO, Project, git, run
except ModuleNotFoundError:
    from tests.test_sql_review_scripts import REPO, Project, git, run

CANON = REPO / "skills" / "data-request-setup" / "SKILL.md"
COPIES = [CANON,
          REPO / "plugins" / "data-request" / "skills" / "setup" / "SKILL.md",
          REPO / "dist" / "codex" / "plugins" / "data-request" / "skills" / "setup" / "SKILL.md"]


def frontmatter(path: Path) -> dict:
    return yaml.safe_load(path.read_text().split("---\n", 2)[1]) or {}


class InitReviewsPlaceholder(unittest.TestCase):
    def test_fresh_init_keeps_reviews_in_a_clone(self):
        with tempfile.TemporaryDirectory() as tmp:
            origin = Path(tmp) / "origin"
            origin.mkdir()
            p = Project(origin, init=False)
            r = run(["init"], p.root)
            self.assertEqual(r.returncode, 0, r.stderr)
            self.assertTrue((p.root / ".sqlreview/reviews/.gitkeep").is_file())
            self.assertRegex(r.stdout, r"(?m)^file\treviews/\.gitkeep$")
            git(p.root, "add", ".sqlreview")
            git(p.root, "commit", "-q", "-m", "init sqlreview")
            clone = Path(tmp) / "clone"
            subprocess.run(["git", "clone", "-q", str(p.root), str(clone)], check=True, capture_output=True)
            self.assertTrue((clone / ".sqlreview/reviews").is_dir())

    def test_init_json_lists_the_placeholder(self):
        with tempfile.TemporaryDirectory() as tmp:
            p = Project(tmp, init=False)
            j = json.loads(run(["init", "--json"], p.root).stdout)
            self.assertIn("reviews/.gitkeep", j["files"])

    def test_placeholder_is_not_a_review(self):
        with tempfile.TemporaryDirectory() as tmp:
            p = Project(tmp)
            r = run(["status", "--json"], p.root)
            self.assertEqual(r.returncode, 0, r.stderr)
            j = json.loads(r.stdout)
            self.assertEqual((j["reviews"], j["counts"]["total"]), ([], 0))
            text = run(["status"], p.root)
            self.assertEqual((text.returncode, text.stdout), (0, ""))

    def test_rerun_reports_no_difference_for_the_placeholder(self):
        with tempfile.TemporaryDirectory() as tmp:
            p = Project(tmp)
            r = run(["init", "--diff"], p.root)
            self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
            self.assertNotIn(".gitkeep", r.stdout)


class SetupSkillContract(unittest.TestCase):
    def test_non_interactive_form_is_documented(self):
        for path in COPIES[:2]:  # the Codex copy has no argument-hint
            self.assertIn("--default --yes", frontmatter(path)["argument-hint"])
        for path in COPIES:
            with self.subTest(path=path.relative_to(REPO)):
                text = path.read_text()
                self.assertRegex(text, r"(?i)take defaults.{0,80}--default --yes|--default --yes.{0,120}take defaults")

    def test_confirmation_lists_the_placeholder(self):
        for path in COPIES:
            with self.subTest(path=path.relative_to(REPO)):
                self.assertIn("reviews/.gitkeep", path.read_text())

    def test_string_sql_guard_is_pointed_to(self):
        for path in COPIES:
            with self.subTest(path=path.relative_to(REPO)):
                text = path.read_text()
                self.assertIn("guard.require_lift_for_string_sql", text)
                # the pointer is tied to the trigger: a request that forbids hand-written SQL
                self.assertRegex(text, re.compile(r"forbids hand-written SQL.{0,300}guard\.require_lift_for_string_sql", re.S))
                self.assertIn("references/lifts.rst", text)


if __name__ == "__main__":
    unittest.main()
