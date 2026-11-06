"""`sqlreview.sh status` stays inside the SessionStart hook's 5-second timeout.

The preflight hook runs `status --json`, and Claude Code stops the hook after 5 seconds without
a message. Most of the cost of status is the processes that it starts for each review folder.
A PATH shim logs each command that status starts, so these tests count processes, not seconds,
and do not depend on the speed of the machine.
"""

import json
import os
import shutil
import stat
import subprocess
import tempfile
import time
import unittest
from collections import Counter
from pathlib import Path

try:  # `unittest discover -s tests` puts tests/ on sys.path; `-m unittest tests.x` does not
    from test_sql_review_scripts import SCRIPT, SQL_V1, SQL_V2, Project, review_doc, run, scope_doc
    from test_sql_review_hooks import PREFLIGHT, env_for, run_hook
except ModuleNotFoundError:
    from tests.test_sql_review_scripts import SCRIPT, SQL_V1, SQL_V2, Project, review_doc, run, scope_doc
    from tests.test_sql_review_hooks import PREFLIGHT, env_for, run_hook


# Commands that status or its helpers can start. Each one gets a logging shim.
SHIMMED = ("jq", "sha256sum", "shasum", "cat", "mktemp", "rm", "tail", "awk", "sed", "grep", "tr",
           "cut", "dirname", "basename", "bash", "git", "date", "sort", "head", "wc", "mkdir")
# Processes per review folder, measured over three folder shapes (scope and review, stale
# review over a scope, scope only): about 20. Before this test, status started about 136.
MAX_PER_FOLDER = 25


def build(root, units):
    """`units` groups of three folders: a current review with a scope, a stale review with a
    scope, and a bound scope without a review. The SQL is committed and fingerprinted (#505)."""
    root.mkdir(parents=True, exist_ok=True)
    p = Project(str(root))
    folders = [(f"r__{kind}{i}", f"r/{kind}{i}.sql", kind) for i in range(units)
               for kind in ("current", "stale", "scoped")]
    for _, sql, _ in folders:
        p.sql(sql, SQL_V1)
    p.commit("reviewed maintained SQL")
    for slug, sql, kind in folders:
        r = run(["fingerprint", sql], p.root)
        assert r.returncode == 0, r.stderr
        fp = json.loads(r.stdout)
        fp.pop("sql_path")
        p.write_json(slug, "scope.json", scope_doc(slug, sql, revision=2, sql_sha256=fp["sql_sha256"],
                                                   sql_body_sha256=fp["sql_body_sha256"]))
        if kind == "scoped":
            continue
        p.write_json(slug, "review.json", review_doc(slug, sql, **fp))
        r = run(["snapshot", slug, sql], p.root)
        assert r.returncode == 0, r.stderr
    for _, sql, kind in folders:
        if kind == "stale":
            p.sql(sql, SQL_V2)
    p.commit("changed maintained SQL")
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
    def count(self, units, amendments=0):
        with tempfile.TemporaryDirectory() as tmp:
            tmp = Path(tmp)
            p = build(tmp / "project", units)
            for i in range(amendments):  # each record has one handed-off part
                rec = p.root / ".sqlreview" / "amendments" / f"enq{9100 + i}.json"
                rec.parent.mkdir(exist_ok=True)
                rec.write_text(json.dumps({"schemaVersion": 1, "kind": "amendment", "parts": [
                    {"id": "P1", "status": "done", "commit": "a" * 40}, {"id": "P2", "status": "handed off"}]}))
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

    def test_each_amendment_record_costs_one_jq_read(self):
        none, four = self.count(1), self.count(1, amendments=4)
        extra = {name: four[name] - none[name] for name in set(none) | set(four) if four[name] != none[name]}
        self.assertEqual(extra, {"jq": 4}, "one jq read per amendment record and no other process")


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

    def run_stub(self, body, budget="1"):
        """Run the hook against a stub status helper; return the result and the seconds it took."""
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            helper = root / "plugin" / "skills" / "setup" / "scripts" / "sqlreview.sh"
            helper.parent.mkdir(parents=True)
            helper.write_text("#!/usr/bin/env bash\n" + body)
            (root / "project").mkdir()
            event = {"hook_event_name": "SessionStart", "cwd": str(root / "project")}
            start = time.monotonic()
            r = run_hook(PREFLIGHT, event, env_for(root / "plugin", SQLREVIEW_PREFLIGHT_BUDGET=budget))
            return r, time.monotonic() - start

    def test_status_blocked_in_a_child_is_stopped_at_the_budget(self):
        # Bash defers its TERM trap until the child returns, so signalling only the status shell
        # waited the full 6 seconds; signalling its process group does not.
        for body in ('trap "exit 143" TERM\nsleep 6\n',
                     'bash -c \'trap "" TERM; sleep 6\'\n'):  # a child that ignores TERM gets KILL
            r, took = self.run_stub(body)
            self.assertEqual(r.returncode, 0, r.stderr)
            self.assertIn("did not finish in the 1-second", json.loads(r.stdout)["hookSpecificOutput"]["additionalContext"])
            self.assertLess(took, 4, body)

    @unittest.skipUnless(os.path.exists("/proc/self/fd"), "the stub finds its output file through /proc")
    def test_a_status_that_finished_as_the_budget_expired_is_not_reported_as_a_timeout(self):
        # Review finding 10: the watchdog can create its marker just after status exits. The stub makes that
        # outcome certain: it creates the marker itself, then prints a valid summary and exits 0.
        body = ('out="$(readlink "/proc/$$/fd/1")"\n: > "$out.timeout"\n'
                'printf \'%s\\n\' \'{"schemaVersion":2,"reviews":[],"counts":{"total":0},"amendments":[]}\'\nexit 0\n')
        r, _ = self.run_stub(body, budget="30")
        self.assertEqual(r.returncode, 0, r.stderr)
        ctx = json.loads(r.stdout)["hookSpecificOutput"]["additionalContext"]
        self.assertIn("is initialised (schema 2) with no reviews yet", ctx)
        self.assertNotIn("did not finish", ctx)

    def test_a_status_stopped_by_the_watchdog_is_still_a_timeout(self):
        r, _ = self.run_stub('trap "exit 2" TERM\nsleep 6\n')
        self.assertIn("did not finish in the 1-second", json.loads(r.stdout)["hookSpecificOutput"]["additionalContext"])

    def test_a_descendant_holding_stdout_does_not_hold_the_hook(self):
        # Status has exited, but a background child still has its stdout. Before, the capture
        # pipe stayed open until that child ended.
        r, took = self.run_stub("(sleep 6) &\nexit 0\n", budget="30")
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertLess(took, 4)


if __name__ == "__main__":
    unittest.main()
