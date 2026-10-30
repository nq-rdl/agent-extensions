"""`sqlreview.sh status` stays inside the SessionStart hook's 5-second timeout.

The preflight hook runs `status --json`, and Claude Code stops the hook after 5 seconds without
a message. Most of the cost of status is the processes that it starts for each review folder.
A PATH shim logs each command that status starts, so these tests count processes, not seconds,
and do not depend on the speed of the machine.
"""

import hashlib
import json
import os
import shutil
import stat
import subprocess
import tempfile
import unittest
from collections import Counter
from pathlib import Path

try:  # `unittest discover -s tests` puts tests/ on sys.path; `-m unittest tests.x` does not
    from test_sql_review_scripts import SCRIPT, SQL_V1, SQL_V2, Project, review_doc, run, scope_doc
    from test_sql_review_hooks import PREFLIGHT, env_for, run_hook
except ModuleNotFoundError:
    from tests.test_sql_review_scripts import SCRIPT, SQL_V1, SQL_V2, Project, review_doc, run, scope_doc
    from tests.test_sql_review_hooks import PREFLIGHT, env_for, run_hook


def sha(text):
    return hashlib.sha256(text.encode()).hexdigest()


# Commands that status or its helpers can start. Each one gets a logging shim.
SHIMMED = ("jq", "sha256sum", "shasum", "cat", "mktemp", "rm", "tail", "awk", "sed", "grep", "tr",
           "cut", "dirname", "basename", "bash", "git", "date", "sort", "head", "wc", "mkdir")
# Processes per review folder, measured over three folder shapes (scope and review, stale
# review over a scope, scope only): about 20. Before this test, status started about 136.
MAX_PER_FOLDER = 25


def build(root, units):
    """`units` groups of three folders: a current review with a scope, a stale review with a
    scope, and a bound scope without a review."""
    root.mkdir(parents=True, exist_ok=True)
    p = Project(str(root))
    for i in range(units):
        for kind in ("current", "stale", "scoped"):
            slug, sql = f"r__{kind}{i}", f"r/{kind}{i}.sql"
            p.sql(sql, SQL_V1)
            p.review_dir(slug).joinpath("scope.source.sql").write_text(SQL_V1)
            p.write_json(slug, "scope.json", scope_doc(slug, sql, revision=2, sql_sha256=sha(SQL_V1)))
            if kind == "scoped":
                continue
            p.write_json(slug, "review.json", review_doc(slug, sql))
            r = run(["snapshot", slug, sql], p.root)
            assert r.returncode == 0, r.stderr
            if kind == "stale":
                p.sql(sql, SQL_V2)
    return p


def shim_dir(where, log):
    """A directory of shims that log their own name, then run the real command."""
    where.mkdir()
    for name in SHIMMED:
        real = shutil.which(name)
        if not real:
            continue
        shim = where / name
        shim.write_text(f'#!/bin/sh\nprintf "%s\\n" {name} >> "{log}"\nexec "{real}" "$@"\n')
        shim.chmod(shim.stat().st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)
    return where


class StatusProcessCount(unittest.TestCase):
    def count(self, units):
        with tempfile.TemporaryDirectory() as tmp:
            tmp = Path(tmp)
            p = build(tmp / "project", units)
            log = tmp / "spawned.log"
            env = dict(os.environ, PATH=f"{shim_dir(tmp / 'shims', log)}{os.pathsep}{os.environ['PATH']}")
            r = subprocess.run(["bash", str(SCRIPT), "status", "--json"], cwd=p.root, env=env,
                               capture_output=True, text=True, timeout=300)
            self.assertEqual(r.returncode, 0, r.stderr)
            self.assertEqual(json.loads(r.stdout)["counts"]["total"], 3 * units)
            return Counter(log.read_text().split()) if log.exists() else Counter()

    def test_processes_per_review_folder_stay_bounded(self):
        one, three = self.count(1), self.count(3)
        per_folder = {name: (three[name] - one[name]) / 6 for name in set(one) | set(three)}
        self.assertLessEqual(sum(per_folder.values()), MAX_PER_FOLDER, per_folder)
        # The two largest costs before the limit: a child bash per review, and a dirname per
        # path component in each symlink check.
        for name in ("bash", "dirname", "basename"):
            self.assertEqual(per_folder.get(name, 0), 0, f"{name} runs once per review folder")


class PreflightBudget(unittest.TestCase):
    def test_status_past_its_budget_reports_one_line(self):
        with tempfile.TemporaryDirectory() as tmp:
            p = build(Path(tmp), 1)
            event = {"hook_event_name": "SessionStart", "cwd": str(p.root)}
            r = run_hook(PREFLIGHT, event, env_for(SQLREVIEW_PREFLIGHT_BUDGET="0"))
            self.assertEqual(r.returncode, 0, r.stderr)
            ctx = json.loads(r.stdout)["hookSpecificOutput"]["additionalContext"]
            self.assertEqual(ctx, "SQL Review: status did not finish in the 0-second session-start budget, so this "
                                  "summary is not available. Run sqlreview.sh status to see each review and its "
                                  "next command.")

    def test_status_inside_its_budget_reports_the_summary(self):
        with tempfile.TemporaryDirectory() as tmp:
            p = build(Path(tmp), 1)
            event = {"hook_event_name": "SessionStart", "cwd": str(p.root)}
            for budget in ("30", "not-a-number"):  # an unusable budget falls back to 4 seconds
                r = run_hook(PREFLIGHT, event, env_for(SQLREVIEW_PREFLIGHT_BUDGET=budget))
                ctx = json.loads(r.stdout)["hookSpecificOutput"]["additionalContext"]
                self.assertIn("3 reviews: 1 current, 1 scoped (bootstrap only), 1 stale (r__stale0)", ctx)


if __name__ == "__main__":
    unittest.main()
