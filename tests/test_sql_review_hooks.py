"""Behavioural tests for the sql-review plugin's hooks.

hooks/sql-review-guard.sh    PreToolUse (Write|Edit): the assumption/limitation confirmation
                             invariant on review/scope JSON, rendered-markdown protection, config ask.
hooks/sql-review-preflight.sh SessionStart: one factual context line about the project's state.

Both are hand-copied to plugins/sql-review/scripts/ (a test asserts byte-identical copies). Each
test pipes a Claude Code event through the hook with CLAUDE_PLUGIN_ROOT pointing at the plugin
copy, the way an installed plugin runs, and asserts the permissionDecision / additionalContext.
"""

import json
import os
import subprocess
import tempfile
import unittest
from pathlib import Path

try:  # `unittest discover -s tests` puts tests/ on sys.path; `-m unittest tests.x` does not
    from test_sql_review_scripts import SQL_V1, SQL_V2, Project, item, review_doc, run as run_helper, scope_doc
except ModuleNotFoundError:
    from tests.test_sql_review_scripts import SQL_V1, SQL_V2, Project, item, review_doc, run as run_helper, scope_doc

REPO = Path(__file__).resolve().parent.parent
PLUGIN = REPO / "plugins" / "sql-review"
GUARD = REPO / "hooks" / "sql-review-guard.sh"
PREFLIGHT = REPO / "hooks" / "sql-review-preflight.sh"


def env_for(plugin_root=PLUGIN, **extra):
    env = {k: v for k, v in os.environ.items() if not k.startswith("SQLREVIEW_")}
    if plugin_root is None:
        env.pop("CLAUDE_PLUGIN_ROOT", None)
    else:
        env["CLAUDE_PLUGIN_ROOT"] = str(plugin_root)
    env.update(extra)
    return env


def run_hook(script, event, env, cwd=None):
    stdin = event if isinstance(event, str) else json.dumps(event)
    return subprocess.run(["bash", str(script)], input=stdin, capture_output=True, text=True, env=env, timeout=60, cwd=cwd)


def write_event(path, content, cwd):
    return {"tool_name": "Write", "tool_input": {"file_path": str(path), "content": content}, "cwd": str(cwd)}


def edit_event(path, cwd):
    return {"tool_name": "Edit", "tool_input": {"file_path": str(path), "old_string": "a", "new_string": "b"}, "cwd": str(cwd)}


def decision(result):
    return json.loads(result.stdout)["hookSpecificOutput"]


class GuardHook(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.p = Project(self.tmp.name)
        self.root = self.p.root
        self.reviews = self.root / ".sqlreview" / "reviews"
        self.env = env_for()

    def tearDown(self):
        self.tmp.cleanup()

    def assert_passthrough(self, r):
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertEqual(r.stdout.strip(), "")

    def test_paths_outside_sqlreview_pass_silently(self):
        for ev in (
            write_event(self.root / "reports" / "monthly.sql", "select 1", self.root),
            edit_event(self.root / "README.md", self.root),
            write_event(self.root / "notes" / ".sqlreview.bak" / "x.json", "{}", self.root),
        ):
            with self.subTest(ev["tool_input"]["file_path"]):
                self.assert_passthrough(run_hook(GUARD, ev, self.env))

    def test_other_tools_and_malformed_stdin_are_noops(self):
        self.assert_passthrough(run_hook(GUARD, {"tool_name": "Bash", "tool_input": {"command": "echo x > .sqlreview/reviews/a/review.json"}}, self.env))
        self.assert_passthrough(run_hook(GUARD, "not json", self.env))
        self.assert_passthrough(run_hook(GUARD, "", self.env))

    def test_confirmed_review_write_is_allowed(self):
        f = self.reviews / "reports__monthly" / "review.json"
        self.assert_passthrough(run_hook(GUARD, write_event(f, json.dumps(review_doc()), self.root), self.env))
        s = self.reviews / "reports__monthly" / "scope.json"
        self.assert_passthrough(run_hook(GUARD, write_event(s, json.dumps(scope_doc()), self.root), self.env))

    def test_relative_path_from_nested_cwd_is_still_guarded(self):
        nested = self.root / "a" / "b"
        nested.mkdir(parents=True)
        ev = {"tool_name": "Write", "tool_input": {"file_path": "../../.sqlreview/reviews/x/review.json",
                                                    "content": json.dumps(review_doc(assumptions=[item("A1", "x", status="pending")]))},
              "cwd": str(nested)}
        self.assertEqual(decision(run_hook(GUARD, ev, self.env, cwd=nested))["permissionDecision"], "deny")

    def test_unconfirmed_items_are_denied_naming_ids_and_the_step(self):
        cases = {
            "pending": review_doc(assumptions=[item("A1", "x", status="pending")]),
            "no_by": review_doc(limitations=[item("L2", "x", confirmed_by="")]),
            "stale_revision": review_doc(revision=3, assumptions=[item("A1", "x", revision=2)]),
            "scope_pending": scope_doc(assumptions=[item("A1", "x", status="draft")]),
        }
        for name, doc in cases.items():
            with self.subTest(name):
                kind = "scope.json" if doc["kind"] == "scope" else "review.json"
                r = run_hook(GUARD, write_event(self.reviews / "s" / kind, json.dumps(doc), self.root), self.env)
                d = decision(r)
                self.assertEqual(d["permissionDecision"], "deny")
                self.assertRegex(d["permissionDecisionReason"], r"\b[AL][12]\b")
                self.assertIn("AskUserQuestion", d["permissionDecisionReason"])

    def test_missing_keys_and_invalid_json_are_denied(self):
        doc = review_doc()
        del doc["assumptions"]
        d = decision(run_hook(GUARD, write_event(self.reviews / "s" / "review.json", json.dumps(doc), self.root), self.env))
        self.assertEqual(d["permissionDecision"], "deny")
        self.assertIn("assumptions", d["permissionDecisionReason"])
        d = decision(run_hook(GUARD, write_event(self.reviews / "s" / "review.json", "{oops", self.root), self.env))
        self.assertEqual(d["permissionDecision"], "deny")

    def test_edit_of_authoritative_json_is_denied(self):
        for name in ("review.json", "scope.json"):
            with self.subTest(name):
                d = decision(run_hook(GUARD, edit_event(self.reviews / "s" / name, self.root), self.env))
                self.assertEqual(d["permissionDecision"], "deny")
                self.assertIn("Write", d["permissionDecisionReason"])

    def test_drafts_state_and_snapshot_are_exempt(self):
        for name, content in (("review.draft.json", json.dumps(review_doc(assumptions=[item("A1", "x", status="pending")]))),
                              ("explain.json", "{}"), ("source.sql", SQL_V1)):
            with self.subTest(name):
                self.assert_passthrough(run_hook(GUARD, write_event(self.reviews / "s" / name, content, self.root), self.env))
                self.assert_passthrough(run_hook(GUARD, edit_event(self.reviews / "s" / name, self.root), self.env))

    def test_rendered_markdown_is_denied(self):
        for name in ("review.md", "scope.md"):
            for ev in (write_event(self.reviews / "s" / name, "# x", self.root), edit_event(self.reviews / "s" / name, self.root)):
                with self.subTest(name=name, tool=ev["tool_name"]):
                    d = decision(run_hook(GUARD, ev, self.env))
                    self.assertEqual(d["permissionDecision"], "deny")
                    self.assertIn("render", d["permissionDecisionReason"])

    def test_config_asks_and_templates_pass(self):
        cfg = self.root / ".sqlreview" / "config.json"
        for ev in (write_event(cfg, "{}", self.root), edit_event(cfg, self.root)):
            with self.subTest(ev["tool_name"]):
                d = decision(run_hook(GUARD, ev, self.env))
                self.assertEqual(d["permissionDecision"], "ask")
                self.assertIn("/sql-review:setup", d["permissionDecisionReason"])
        tpl = self.root / ".sqlreview" / "templates" / "review.md"
        self.assert_passthrough(run_hook(GUARD, write_event(tpl, "# t", self.root), self.env))
        self.assert_passthrough(run_hook(GUARD, edit_event(tpl, self.root), self.env))

    def test_missing_checker_denies_rather_than_passes(self):
        # The guard resolves sqlreview.sh via CLAUDE_PLUGIN_ROOT, then relative to its own plugin
        # copy, then the canonical skills/ tree. Run a copy of the hook from a bare directory with a
        # bogus plugin root so none resolve: a missing guardrail must fail closed.
        bare = Path(self.tmp.name) / "bare"
        bare.mkdir()
        hook = bare / "sql-review-guard.sh"
        hook.write_bytes(GUARD.read_bytes())
        env = env_for(plugin_root=bare / "nowhere")
        r = run_hook(hook, write_event(self.reviews / "reports__monthly" / "review.json", json.dumps(review_doc()), self.root), env)
        d = decision(r)
        self.assertEqual(d["permissionDecision"], "deny")
        self.assertIn("sqlreview.sh", d["permissionDecisionReason"])

    def test_plugin_copy_resolves_checker_without_plugin_root(self):
        env = env_for(plugin_root=None)
        r = run_hook(PLUGIN / "scripts" / "sql-review-guard.sh",
                     write_event(self.reviews / "s" / "review.json", json.dumps(review_doc(assumptions=[item("A1", "x", status="pending")])), self.root), env)
        self.assertEqual(decision(r)["permissionDecision"], "deny")
        r = run_hook(PLUGIN / "scripts" / "sql-review-guard.sh",
                     write_event(self.reviews / "reports__monthly" / "review.json", json.dumps(review_doc()), self.root), env)
        self.assert_passthrough(r)

    def test_without_jq_the_guard_falls_back_to_python3(self):
        bindir = Path(self.tmp.name) / "bin"
        bindir.mkdir()
        for tool in ("bash", "grep", "sed", "tr", "cat", "python3", "dirname", "basename", "pwd", "diff", "mktemp", "rm", "cp", "mkdir", "wc", "sort", "uniq", "awk", "head", "cut", "date", "git", "sha256sum", "shasum", "readlink"):
            path = subprocess.run(["bash", "-c", f"command -v {tool}"], capture_output=True, text=True).stdout.strip()
            if path:
                (bindir / tool).symlink_to(path)
        env = env_for(PATH=str(bindir))
        d = decision(run_hook(GUARD, write_event(self.reviews / "s" / "review.json", json.dumps(review_doc(assumptions=[item("A1", "x", status="pending")])), self.root), env))
        self.assertEqual(d["permissionDecision"], "deny")
        self.assert_passthrough(run_hook(GUARD, write_event(self.root / "x.sql", "select 1", self.root), env))


class PreflightHook(unittest.TestCase):
    def test_initialised_project_reports_counts_and_stale_slugs(self):
        with tempfile.TemporaryDirectory() as tmp:
            p = Project(tmp)
            p.sql("reports/monthly.sql", SQL_V1)
            p.sql("reports/weekly.sql", SQL_V1)
            p.write_json("reports__monthly", "review.json", review_doc())
            p.write_json("reports__weekly", "review.json", review_doc("reports__weekly", "reports/weekly.sql"))
            run_helper(["snapshot", "reports__monthly", "reports/monthly.sql"], p.root)
            run_helper(["snapshot", "reports__weekly", "reports/weekly.sql"], p.root)
            (p.root / "reports" / "weekly.sql").write_text(SQL_V2)
            r = run_hook(PREFLIGHT, {"hook_event_name": "SessionStart", "cwd": str(p.root)}, env_for())
            self.assertEqual(r.returncode, 0, r.stderr)
            out = json.loads(r.stdout)["hookSpecificOutput"]
            self.assertEqual(out["hookEventName"], "SessionStart")
            ctx = out["additionalContext"]
            self.assertIn("2 review", ctx)
            self.assertIn("reports__weekly", ctx)
            self.assertNotIn("reports__monthly", ctx)
            self.assertIn("/sql-review:analyse", ctx)

    def test_uninitialised_project_with_sql_files_hints_setup(self):
        with tempfile.TemporaryDirectory() as tmp:
            p = Project(tmp, init=False)
            p.sql("q.sql", SQL_V1)
            r = run_hook(PREFLIGHT, {"cwd": str(p.root)}, env_for())
            ctx = json.loads(r.stdout)["hookSpecificOutput"]["additionalContext"]
            self.assertIn("/sql-review:setup", ctx)

    def test_uninitialised_project_without_sql_is_silent(self):
        with tempfile.TemporaryDirectory() as tmp:
            p = Project(tmp, init=False)
            r = run_hook(PREFLIGHT, {"cwd": str(p.root)}, env_for())
            self.assertEqual((r.returncode, r.stdout.strip()), (0, ""))

    def test_missing_helper_or_cwd_is_a_noop(self):
        with tempfile.TemporaryDirectory() as tmp:
            bare = Path(tmp) / "bare"
            bare.mkdir()
            hook = bare / "sql-review-preflight.sh"
            hook.write_bytes(PREFLIGHT.read_bytes())
            r = run_hook(hook, {"cwd": tmp}, env_for(plugin_root=bare / "nowhere"))
            self.assertEqual((r.returncode, r.stdout.strip()), (0, ""))
            r = run_hook(PREFLIGHT, {"cwd": str(Path(tmp) / "does-not-exist")}, env_for())
            self.assertEqual((r.returncode, r.stdout.strip()), (0, ""))


class PluginCopies(unittest.TestCase):
    def test_hook_copies_match_canonical(self):
        for name in ("sql-review-guard.sh", "sql-review-preflight.sh"):
            with self.subTest(name):
                self.assertEqual((REPO / "hooks" / name).read_bytes(), (PLUGIN / "scripts" / name).read_bytes())


if __name__ == "__main__":
    unittest.main()
