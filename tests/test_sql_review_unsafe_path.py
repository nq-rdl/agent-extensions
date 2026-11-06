"""M2: a stored sql_path never reaches a paste-ready hint or the session-start context unless it is safe.

The sql_path of a record is free text. Status and the SessionStart hook print it inside next-command
hints, so a hostile branch could plant a command there. Two layers hold: check refuses any sql_path
beyond letters, digits and _ . / - (message without the value), and the hints print a path only when
it holds those characters only. Otherwise they print the fixed text "(unsafe sql_path)".
Synthetic data only: ZZTEST markers stand in for hostile text.
"""

import json
import subprocess
import tempfile
import unittest
from pathlib import Path

try:  # `unittest discover -s tests` puts tests/ on sys.path; `-m unittest tests.x` does not
    from test_sql_review_scripts import REPO, SCRIPT, SQL_V1, Project, review_doc, run, scope_doc
    from test_sql_review_hooks import PREFLIGHT, decision, env_for, run_hook
except ModuleNotFoundError:
    from tests.test_sql_review_scripts import REPO, SCRIPT, SQL_V1, Project, review_doc, run, scope_doc
    from tests.test_sql_review_hooks import PREFLIGHT, decision, env_for, run_hook

SCRIPTS = SCRIPT.parent
EVIL = "sql/v1/a' ; touch ZZTEST-PWNED ; echo '.sql"
FIXED = "(unsafe sql_path)"
RULE = "sql_path must not contain quotes, backtick, $, ;, |, &, <, >, backslash or control characters"


def slug_of(path):
    r = subprocess.run(["jq", "-nr", "-L", str(SCRIPTS), "--arg", "p", path, 'include "sqlreview-slug"; $p | path_slug'],
                       capture_output=True, text=True, check=True)
    return r.stdout.strip()


class UnsafeSqlPath(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.p = Project(self.tmp.name)

    def plant(self, path):
        slug = slug_of(path)
        return slug, self.p.write_json(slug, "scope.json", scope_doc(slug, path))

    def assertNoHostileText(self, text):
        # The slug is percent-encoded, so only the raw text of the path counts as a leak.
        for needle in ("touch ZZTEST", "' ;", "; echo", "echo '", "a'"):
            self.assertNotIn(needle, text)

    def test_check_refuses_the_record_without_echoing_it(self):
        _, doc = self.plant(EVIL)
        r = run(["check", str(doc)], self.p.root)
        self.assertEqual(r.returncode, 4, r.stdout + r.stderr)
        self.assertIn(RULE, r.stdout)
        self.assertNoHostileText(r.stdout + r.stderr)

    def test_check_refuses_each_unsafe_character(self):
        for ch in ("'", '"', "`", "$", ";", "|", "&", "<", ">", "\\", "\n", "\t", "\r", "\x00", "\x1f", "\x7f"):
            with self.subTest(ch=repr(ch)):
                path = f"sql/v1/a{ch}b.sql"
                doc = self.p.write_json("x", "scope.json", scope_doc("x", path))
                r = run(["check", str(doc)], self.p.root)
                self.assertEqual(r.returncode, 4, r.stdout)
                self.assertIn(RULE, r.stdout)

    def test_check_accepts_a_space_and_other_harmless_characters(self):
        for path in ("reports/monthly report.sql", "sql/v1/odd name (1).sql", "sql/v1/a%20b~c.sql", "sql/v1/déjà.sql"):
            with self.subTest(path=path):
                slug = slug_of(path)
                doc = self.p.write_json(slug, "scope.json", scope_doc(slug, path))
                r = run(["check", str(doc)], self.p.root)
                self.assertEqual((r.returncode, r.stdout.strip()), (0, "ok"), r.stdout)

    def test_a_valid_path_with_a_space_shows_the_fixed_text_in_status_and_preflight(self):
        self.plant("reports/monthly report.sql")
        for args in (["status"], ["status", "--json"], ["status", "--verbose"]):
            with self.subTest(args=args):
                r = run(args, self.p.root)
                self.assertEqual(r.returncode, 0, r.stderr)
                self.assertIn(FIXED, r.stdout)
                self.assertNotIn("monthly report", r.stdout.replace("monthly%20report", ""))
        ctx = decision(run_hook(PREFLIGHT, {"cwd": str(self.p.root)}, env_for()))["additionalContext"]
        self.assertIn(FIXED, ctx)
        self.assertNotIn("monthly report", ctx)

    def test_check_accepts_the_reviewed_directory_forms(self):
        for path in ("sql/v1/a.sql", "sql/v2.1/a-b_c.sql", "sql/v3-1/deep/dir/q.sql", "reports/monthly.sql"):
            with self.subTest(path=path):
                slug = slug_of(path)
                doc = self.p.write_json(slug, "scope.json", scope_doc(slug, path))
                r = run(["check", str(doc)], self.p.root)
                self.assertEqual((r.returncode, r.stdout.strip()), (0, "ok"), r.stderr)

    def test_status_prints_the_fixed_text_not_the_path(self):
        self.plant(EVIL)
        for args in (["status"], ["status", "--json"], ["status", "--verbose"], ["status", "--json", "--verbose"]):
            with self.subTest(args=args):
                r = run(args, self.p.root)
                self.assertEqual(r.returncode, 0, r.stderr)
                self.assertIn(FIXED, r.stdout)
                self.assertNoHostileText(r.stdout + r.stderr)

    def test_preflight_context_prints_the_fixed_text_not_the_path(self):
        self.plant(EVIL)
        ctx = decision(run_hook(PREFLIGHT, {"cwd": str(self.p.root)}, env_for()))["additionalContext"]
        self.assertIn(FIXED, ctx)
        self.assertNoHostileText(ctx)

    def test_a_normal_path_still_prints_in_the_hints(self):
        self.plant("sql/v1.2/a-b_c.sql")
        ctx = decision(run_hook(PREFLIGHT, {"cwd": str(self.p.root)}, env_for()))["additionalContext"]
        self.assertIn("/data-request:draft to write sql/v1.2/a-b_c.sql, then /data-request:analyse sql/v1.2/a-b_c.sql", ctx)
        self.assertNotIn(FIXED, ctx)

    def hint(self, state, path):
        """The next-command hint and the reason for a record that check never lets through."""
        script = (f'SR_SCRIPT_DIR="{SCRIPTS}"; SR_ROOT="{self.p.root}"; SR_REVIEWS="$SR_ROOT/.sqlreview/reviews"; '
                  f'. "{SCRIPTS}/sqlreview-lib.sh"; sr_next s "$1" "$2"; sr_state_reason s missing')
        r = subprocess.run(["bash", "-c", script, "bash", state, path], capture_output=True, text=True)
        self.assertEqual(r.returncode, 0, r.stderr)
        return r.stdout

    def test_the_hint_functions_guard_themselves_when_check_is_bypassed(self):
        for state in ("missing", "scoped", "stale", "no-baseline", "header-only", "scoped-header-only", "current"):
            with self.subTest(state=state):
                out = self.hint(state, EVIL)
                self.assertIn(FIXED, out)
                self.assertNoHostileText(out)

    def test_the_hint_functions_print_a_safe_path(self):
        out = self.hint("missing", "sql/v1/ok.sql")
        self.assertIn("sqlreview.sh move 'sql/v1/ok.sql' <new path>", out)
        self.assertNotIn(FIXED, out.splitlines()[0])


if __name__ == "__main__":
    unittest.main()
