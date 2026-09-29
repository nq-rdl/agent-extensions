"""Deterministic tests for scripts/link_rot.py (weekly link-rot tracker, #301).

No network, no GitHub: lychee reports are built in memory or replayed from
tests/fixtures/link_rot/, DNS answers come from a fake resolver, lychee itself
is a recording stub, and the tracker issue lives in the MockIssues store.
"""

import json
import os
import re
import socket
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

import yaml

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "scripts"))

import link_rot as lr  # noqa: E402

FIXTURE = REPO / "tests/fixtures/link_rot/basic"
SCRIPT = REPO / "scripts/link_rot.py"
MAPS = ("success_map", "error_map", "timeout_map", "excluded_map")
T1, T2, T3, T4 = ("2026-10-05T04:23:00Z", "2026-10-12T04:23:00Z",
                  "2026-10-19T04:23:00Z", "2026-10-26T04:23:00Z")


def entry(url, text="200 OK", code=None, line=None, details=None):
    status = {"text": text}
    if code is not None:
        status["code"] = code
    if details:
        status["details"] = details
    data = {"url": url, "status": status}
    if line is not None:
        data["span"] = {"line": line, "column": 1}
    return data


def report(**maps):
    """report(success_map={"a.md": [entry(...)]}, ...) with a consistent total."""
    data = {m: maps.get(m, {}) for m in MAPS}
    data["total"] = sum(len(v) for m in MAPS for v in data[m].values())
    return data


OK = lr.Raw("ok", 200)
R404, R410 = lr.Raw("http", 404), lr.Raw("http", 410)
R403, R429, R500, R503 = (lr.Raw("http", c) for c in (403, 429, 500, 503))
TIMEOUT, NET = lr.Raw("timeout"), lr.Raw("network")


def obs(states, observed_at=T1, report_only=()):
    """Observation document: {url: state} canonical, plus report-only URLs."""
    urls = [{"url": u, "state": s, "reason": {"broken": "http-404", "unknown": "timeout"}.get(s, "ok"),
             "canonical": True, "sources": [{"path": "skills/demo/SKILL.md", "line": 3}], "passes": []}
            for u, s in states.items()]
    urls += [{"url": u, "state": "broken", "reason": "http-404", "canonical": False,
              "sources": [{"path": "hooks/demo.sh"}], "passes": []} for u in report_only]
    return {"schema": lr.OBSERVATIONS_SCHEMA, "scan_ok": True, "errors": [],
            "observed_at": observed_at, "urls": urls, "summary": lr.summarize(urls)}


A, B, C = "https://a.example.com/page", "https://b.example.com/", "https://c.example.com/x"


class NormalizeTests(unittest.TestCase):
    def test_identity_rules(self):
        cases = {
            "HTTPS://Docs.Example.COM/Path": "https://docs.example.com/Path",
            "https://docs.example.com": "https://docs.example.com/",
            "https://docs.example.com:443/a": "https://docs.example.com/a",
            "http://docs.example.com:80/a": "http://docs.example.com/a",
            "https://docs.example.com:8443/a": "https://docs.example.com:8443/a",
            "https://user:secret@docs.example.com/a": "https://docs.example.com/a",
            "https://docs.example.com./a": "https://docs.example.com/a",
            "https://docs.example.com/a%2fb?q=%7e": "https://docs.example.com/a%2Fb?q=%7E",
            "https://docs.example.com/a?#": "https://docs.example.com/a",
            "https://docs.example.com/a#Section": "https://docs.example.com/a#Section",
            "  https://docs.example.com/a  ": "https://docs.example.com/a",
            "mailto:someone@example.com": "mailto:someone@example.com",
            "https://docs.example.com:bad/": "https://docs.example.com:bad/",
        }
        for raw, expected in cases.items():
            with self.subTest(raw=raw):
                self.assertEqual(lr.normalize_url(raw), expected)
                self.assertEqual(lr.normalize_url(expected), expected)

    def test_fragments_are_distinct_findings(self):
        self.assertNotEqual(lr.normalize_url(A + "#one"), lr.normalize_url(A + "#two"))


class SelectInputTests(unittest.TestCase):
    BASE = ["README.md", "CONTRIBUTING.md", "AGENTS.md", "docs/a.md", "skills/s/SKILL.md",
            "skills/s/references/r.rst"]

    def test_scope(self):
        got = lr.select_inputs(self.BASE + [
            "docs/specs/deep/b.md", "agents/x.md", "hooks/h.sh", "hooks/codex/nested.sh",
            "skills/s/scripts/run.sh", "skills/s/assets/c.json", "skills/s/assets/c.yml",
            "skills/s/assets/c.yaml", "skills/s/scripts/t.py", "skills/s/lychee.toml",
            "plugins/p/skills/s/SKILL.md", "dist/codex/plugins/p/skills/s/SKILL.md",
            "docs/image.png", "tests/test_x.py"])
        self.assertEqual(got["errors"], [])
        self.assertEqual(got["canonical"], sorted(self.BASE + ["docs/specs/deep/b.md", "agents/x.md"]))
        self.assertEqual(got["report_only"], sorted([
            "hooks/h.sh", "skills/s/scripts/run.sh", "skills/s/assets/c.json",
            "skills/s/assets/c.yml", "skills/s/assets/c.yaml", "skills/s/scripts/t.py"]))

    def test_unexpected_zero_inputs(self):
        self.assertEqual(len(lr.select_inputs([])["errors"]), len(lr.REQUIRED_PATTERNS))
        got = lr.select_inputs([p for p in self.BASE if not p.startswith("docs/")])
        self.assertEqual(got["errors"], ["unexpected zero inputs for required pattern 'docs/**/*.md'"])

    def test_agents_are_optional_and_generated_copies_never_count(self):
        got = lr.select_inputs(self.BASE)
        self.assertEqual(got["errors"], [])
        only_plugins = lr.select_inputs(["plugins/p/" + p for p in self.BASE])
        self.assertEqual(only_plugins["canonical"], [])
        self.assertTrue(only_plugins["errors"])


class ClassifyTests(unittest.TestCase):
    def test_entry_kinds(self):
        cases = [
            ("success_map", entry(A, "200 OK", 200), ("ok", 200, False)),
            ("success_map", entry(A, "OK (cached)", 200), ("ok", 200, True)),
            ("excluded_map", entry(A, "Excluded", details="exclude"), ("excluded", None, False)),
            ("timeout_map", entry(A, "Timeout", details="Request timed out"), ("timeout", None, False)),
            ("error_map", entry(A, "Rejected status code: 404 Not Found", 404), ("http", 404, False)),
            ("error_map", entry(A, "Error (cached)", 404), ("http", 404, True)),
            ("error_map", entry(A, "Cannot find fragment", details="Cannot find fragment"),
             ("fragment", None, False)),
            ("error_map", entry(A, "Network error: Connection failed.", details="Connection failed"),
             ("network", None, False)),
            ("error_map", entry(A, "Network error: Connection refused", details="Connection refused"),
             ("network", None, False)),
            ("error_map", entry(A, "Unsupported: weird"), ("other", None, False)),
        ]
        for map_name, data, (kind, code, dup) in cases:
            with self.subTest(data=data["status"]):
                raw = lr.classify_entry(map_name, data)
                self.assertEqual((raw.kind, raw.code, raw.duplicate), (kind, code, dup))

    def test_state_table(self):
        cases = [
            ([OK], None, ("healthy", "ok")),
            ([lr.Raw("excluded")], None, ("excluded", "excluded by lychee.toml")),
            ([R404, R404], None, ("broken", "http-404")),
            ([R410, R410], None, ("broken", "http-410")),
            ([R404, R410], None, ("broken", "http-410")),
            ([R404], None, ("unknown", "unconfirmed http-404")),
            ([R404, R429], None, ("unknown", "http-429")),
            ([R404, TIMEOUT], None, ("unknown", "timeout")),
            ([R404, OK], None, ("unknown", "inconsistent: http-404 then ok")),
            ([R429, OK], None, ("healthy", "ok-on-retry")),
            ([TIMEOUT, OK], None, ("healthy", "ok-on-retry")),
            ([R403, R403], None, ("unknown", "http-403")),
            ([R429, R429], None, ("unknown", "http-429")),
            ([R500, R500], None, ("unknown", "http-500")),
            ([R503, R503], None, ("unknown", "http-503")),
            ([lr.Raw("http", 301), lr.Raw("http", 301)], None, ("unknown", "http-301")),
            ([lr.Raw("http", 401), lr.Raw("http", 401)], None, ("unknown", "http-401")),
            ([TIMEOUT, TIMEOUT], None, ("unknown", "timeout")),
            ([NET, NET], "nxdomain", ("broken", "nxdomain")),
            ([NET, NET], "resolves", ("unknown", "connection-failure")),
            ([NET, NET], "resolver-error", ("unknown", "resolver-failure")),
            ([NET, NET], None, ("unknown", "connection-failure")),
            ([NET], "nxdomain", ("unknown", "unconfirmed-nxdomain")),
            ([NET, R404], "nxdomain", ("unknown", "http-404")),
            ([lr.Raw("fragment"), lr.Raw("fragment")], None, ("unknown", "fragment-not-found")),
            ([], None, ("unknown", "not-observed")),
        ]
        for passes, dns, expected in cases:
            with self.subTest(passes=[p.label() for p in passes], dns=dns):
                self.assertEqual(lr.classify(passes, dns), expected)

    def test_reduce_pass(self):
        dup_ok = lr.Raw("ok", 200, duplicate=True)
        dup_net = lr.Raw("other", None, "Error (cached)", duplicate=True)
        self.assertEqual(lr.reduce_pass([NET, dup_net]), NET)       # dedupe copy ignored
        self.assertEqual(lr.reduce_pass([dup_ok]).kind, "ok")       # only copies: use them
        self.assertEqual(lr.reduce_pass([OK, lr.Raw("fragment")]).kind, "fragment")
        self.assertEqual(lr.reduce_pass([R404, R404]), R404)
        self.assertEqual(lr.reduce_pass([R404, R429]).kind, "other")

    def test_thresholds_are_pinned(self):
        self.assertEqual(lr.BROKEN_STATUSES, {404, 410})
        self.assertEqual(lr.CONFIRMATION_PASSES, 2)
        self.assertEqual((lr.DNS_LOOKUPS, lr.RECOVERY_OBSERVATIONS), (3, 1))


class ParseReportTests(unittest.TestCase):
    def test_groups_sources_and_keeps_only_real_spans(self):
        data = report(success_map={"a.md": [entry(A, line=3)], "b.md": [entry("HTTPS://A.Example.com/page", "OK (cached)", 200)]},
                      excluded_map={"a.md": [entry("file:///repo/x.md", "Excluded")]})
        got = lr.parse_report(data, "t")
        self.assertEqual(list(got), [A])
        self.assertEqual(got[A]["sources"], [{"path": "a.md", "line": 3, "column": 1}, {"path": "b.md"}])

    def test_malformed_and_incomplete_reports_are_operational(self):
        good = report(success_map={"a.md": [entry(A)]})
        bad = [
            [],
            {k: v for k, v in good.items() if k != "success_map"},
            {**good, "total": 2},
            {**good, "error_map": []},
            {**good, "error_map": {"a.md": {"url": A}}},
            {**good, "error_map": {"a.md": [{"status": {}}]}},
        ]
        for data in bad:
            with self.subTest(data=data), self.assertRaises(lr.OperationalError):
                lr.parse_report(data, "t")


class DnsProbeTests(unittest.TestCase):
    def resolver(self, answers):
        calls = []

        def resolve(name, _port):
            calls.append(name)
            answer = answers[name].pop(0) if isinstance(answers[name], list) else answers[name]
            if answer != "ok":
                raise socket.gaierror(answer, "fake")
        return resolve, calls

    def probe(self, answers):
        resolve, calls = self.resolver(answers)
        sleeps = []
        result = lr.dns_probe("gone.example.com", resolver=resolve, sleep=sleeps.append)
        return result, calls, sleeps

    def test_confirmed_nxdomain(self):
        result, calls, sleeps = self.probe({"github.com": "ok", "gone.example.com": socket.EAI_NONAME})
        self.assertEqual(result, "nxdomain")
        self.assertEqual(calls.count("gone.example.com"), lr.DNS_LOOKUPS)
        self.assertEqual(sleeps, [lr.DNS_INTERVAL_SECONDS] * (lr.DNS_LOOKUPS - 1))

    def test_resolver_failures_are_not_nxdomain(self):
        cases = [
            ({"github.com": socket.EAI_AGAIN, "gone.example.com": socket.EAI_NONAME}, "resolver-error"),
            ({"github.com": ["ok", socket.EAI_AGAIN], "gone.example.com": socket.EAI_NONAME}, "resolver-error"),
            ({"github.com": "ok", "gone.example.com": socket.EAI_AGAIN}, "resolver-error"),
            ({"github.com": "ok", "gone.example.com": [socket.EAI_NONAME, "ok"]}, "resolves"),
            ({"github.com": "ok", "gone.example.com": [socket.EAI_NONAME, socket.EAI_NONAME, socket.EAI_AGAIN]},
             "resolver-error"),
        ]
        for answers, expected in cases:
            with self.subTest(answers=answers):
                self.assertEqual(self.probe(answers)[0], expected)


class ScanFixtureTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.fixture = self.root / "fixture"
        self.fixture.mkdir()
        for name in ("inputs", "main", "confirm", "dns"):
            (self.fixture / f"{name}.json").write_text((FIXTURE / f"{name}.json").read_text())

    def scan(self):
        return lr.scan(self.root, self.root / "out", fixture=self.fixture, now=T1)

    def edit(self, name, change):
        path = self.fixture / f"{name}.json"
        data = json.loads(path.read_text())
        change(data)
        path.write_text(json.dumps(data))

    def test_replayed_fixture(self):
        doc = self.scan()
        self.assertTrue(doc["scan_ok"], doc["errors"])
        got = {o["url"]: (o["state"], o["reason"], o["canonical"]) for o in doc["urls"]}
        self.assertEqual(got, {
            "https://docs.example.com/ok": ("healthy", "ok", True),
            "https://docs.example.com/flaky": ("healthy", "ok-on-retry", True),
            "https://docs.example.com/gone": ("broken", "http-404", True),
            "https://nxdomain.invalid/page": ("broken", "nxdomain", True),
            "https://api.example.net/forbidden": ("unknown", "http-403", True),
            "https://slow.example.org/": ("unknown", "timeout", True),
            "https://docs.example.com/excluded": ("excluded", "excluded by lychee.toml", True),
            "https://github.com/$repo/raw": ("broken", "http-404", False),
        })
        self.assertEqual(doc["summary"]["canonical"], {"healthy": 2, "broken": 2, "unknown": 2, "excluded": 1})
        ok = next(o for o in doc["urls"] if o["url"] == "https://docs.example.com/ok")
        self.assertEqual(ok["sources"], [{"path": "README.md", "line": 3, "column": 1},
                                         {"path": "docs/guide.md", "line": 9, "column": 4}])

    def test_incomplete_or_empty_scans_are_operational_failures(self):
        mutations = [
            ("inputs", lambda d: d.update(canonical=[], report_only=[])),
            ("inputs", lambda d: d["canonical"].remove("docs/guide.md")),
            ("main", lambda d: d.update(total=d["total"] + 1)),
            ("main", lambda d: d.pop("timeout_map")),
            ("confirm", lambda d: d["error_map"].clear() or d.update(total=2)),
            ("main", lambda d: d["success_map"].update({"elsewhere.md": [entry(A)]}) or d.update(total=d["total"] + 1)),
        ]
        for name, change in mutations:
            with self.subTest(name=name):
                self.setUp()
                self.edit(name, change)
                doc = self.scan()
                self.assertFalse(doc["scan_ok"])
                self.assertTrue(doc["errors"])
                with self.assertRaises(lr.OperationalError):
                    lr.plan_tracker(doc, None, [], T1)

    def test_malformed_json_is_operational(self):
        (self.fixture / "main.json").write_text("{not json")
        doc = self.scan()
        self.assertFalse(doc["scan_ok"])
        self.assertIn("JSONDecodeError", doc["errors"][0])


STUB = r'''#!{python}
import json, os, sys
args = sys.argv[1:]
with open(os.environ["STUB_LOG"], "a") as fh:
    fh.write(json.dumps(args) + "\n")
if args == ["--version"]:
    print("lychee " + os.environ.get("STUB_VERSION", "0.24.2")); sys.exit(0)
files = open(args[args.index("--files-from") + 1]).read().split()
if "--dump-inputs" in args:
    skip = os.environ.get("STUB_SKIP_INPUT")
    print("\n".join(f for f in files if f != skip)); sys.exit(0)
confirm = files[0].endswith("confirm-inputs.md")
data = open(os.environ["STUB_CONFIRM" if confirm else "STUB_MAIN"]).read()
open(args[args.index("--output") + 1], "w").write(data)
sys.exit(int(os.environ.get("STUB_EXIT", "2")))
'''


class ScanStubLycheeTests(unittest.TestCase):
    """The live path: git enumeration, config verification and lychee invocation."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name) / "repo"
        env = {k: v for k, v in os.environ.items() if not k.startswith("GIT_")}
        inputs = json.loads((FIXTURE / "inputs.json").read_text())
        for path in inputs["canonical"] + inputs["report_only"] + ["plugins/p/skills/demo/SKILL.md"]:
            (self.root / path).parent.mkdir(parents=True, exist_ok=True)
            (self.root / path).write_text("x\n")
        (self.root / "lychee.toml").write_text((REPO / "lychee.toml").read_text())
        subprocess.run(["git", "init", "-q", str(self.root)], check=True, env=env)
        subprocess.run(["git", "-C", str(self.root), "add", "-A"], check=True, env=env)
        self.stub = Path(self.tmp.name) / "lychee"
        self.stub.write_text(STUB.replace("{python}", sys.executable))
        self.stub.chmod(0o755)
        self.log = Path(self.tmp.name) / "log.jsonl"
        self.env = {"STUB_LOG": str(self.log), "STUB_MAIN": str(FIXTURE / "main.json"),
                    "STUB_CONFIRM": str(FIXTURE / "confirm.json")}

    def scan(self, **env):
        saved = dict(os.environ)
        os.environ.update(self.env, **env)
        try:
            return lr.scan(self.root, Path(self.tmp.name) / "out", lychee=str(self.stub),
                           confirm_delay=0, now=T1, sleep=lambda _s: None,
                           prober=lambda host: "nxdomain")
        finally:
            os.environ.clear()
            os.environ.update(saved)

    def calls(self):
        return [json.loads(line) for line in self.log.read_text().splitlines()]

    def test_single_config_fresh_requests_and_enumerated_inputs(self):
        doc = self.scan()
        self.assertTrue(doc["scan_ok"], doc["errors"])
        self.assertEqual(doc["lychee_version"], lr.LYCHEE_VERSION)
        self.assertNotIn("plugins/p/skills/demo/SKILL.md", doc["inputs"]["canonical"])
        checks = [c for c in self.calls() if "--output" in c]
        self.assertEqual(len(checks), 2)  # main + confirmation pass
        for call in [c for c in self.calls() if c != ["--version"]]:
            self.assertEqual(call.count("--config"), 1)
            self.assertEqual(call[call.index("--config") + 1], "lychee.toml")
            self.assertIn("--cache=false", call)
        for call in checks:
            self.assertEqual(call[2:2 + len(lr.LYCHEE_OVERRIDES)], list(lr.LYCHEE_OVERRIDES))
        inputs = (Path(self.tmp.name) / "out/inputs.txt").read_text().split()
        self.assertEqual(inputs, doc["inputs"]["canonical"] + doc["inputs"]["report_only"])
        confirm = (Path(self.tmp.name) / "out/confirm-inputs.md").read_text().split()
        self.assertEqual(len(confirm), 6)  # every non-healthy, non-excluded URL is re-checked

    def test_tool_failures_are_operational(self):
        cases = [
            {"STUB_VERSION": "0.23.0"},
            {"STUB_EXIT": "1"},
            {"STUB_EXIT": "3"},
            {"STUB_SKIP_INPUT": "docs/guide.md"},
            {"STUB_MAIN": str(Path(self.tmp.name) / "missing.json")},
        ]
        for env in cases:
            with self.subTest(env=env):
                doc = self.scan(**env)
                self.assertFalse(doc["scan_ok"])
                self.assertTrue(doc["errors"])

    def test_config_must_disable_cache(self):
        (self.root / "lychee.toml").write_text("cache = true\n")
        doc = self.scan()
        self.assertFalse(doc["scan_ok"])
        self.assertIn("cache = false", doc["errors"][0])


class LifecycleTests(unittest.TestCase):
    """Tracker lifecycle through the MockIssues store."""

    def setUp(self):
        self.store = lr.MockIssues({})

    def run_track(self, doc, now=None):
        before = len(self.store.writes)
        plan, applied = lr.track(doc, self.store, now or doc["observed_at"])
        return plan, self.store.writes[before:]

    def tracker(self):
        (issue,) = self.store.trackers()
        return issue, lr.parse_state(issue["body"])

    def human_comment(self, body, association="MEMBER", login="maintainer"):
        issue, _ = self.tracker()
        next_id = 1000 + len(issue["comments"])
        issue["comments"].append({"id": next_id, "body": body, "user": {"login": login},
                                  "author_association": association, "created_at": T1})

    def human_close(self, login="maintainer", at="2026-10-06T09:00:00Z"):
        issue, _ = self.tracker()
        issue.update(state="closed", closed_by={"login": login}, closed_at=at)

    def ops(self, writes):
        return [w["op"] for w in writes]

    def test_healthy_unknown_and_report_only_never_open_a_tracker(self):
        _, writes = self.run_track(obs({A: "healthy", B: "unknown", C: "excluded"}, report_only=[C + "2"]))
        self.assertEqual(writes, [])
        self.assertEqual(self.store.trackers(), [])

    def test_new_broken_opens_one_tracker_and_same_set_rerun_is_idempotent(self):
        _, writes = self.run_track(obs({A: "broken", B: "healthy"}))
        self.assertEqual(self.ops(writes), ["create_label", "create"])
        issue, state = self.tracker()
        self.assertEqual(issue["labels"], [lr.LABEL])
        self.assertEqual(state["findings"][A]["status"], "active")
        for _ in range(2):
            _, writes = self.run_track(obs({A: "broken", B: "healthy"}))
            self.assertEqual(writes, [])
        self.assertEqual(len(self.store.data["issues"]), 1)

    def test_broken_then_timeout_stays_unresolved(self):
        self.run_track(obs({A: "broken"}, T1))
        _, writes = self.run_track(obs({A: "unknown"}, T2))
        self.assertEqual(self.ops(writes), ["edit_body"])
        issue, state = self.tracker()
        self.assertEqual(issue["state"], "open")
        finding = state["findings"][A]
        self.assertEqual((finding["status"], finding["last_observed_state"]), ("active", "unknown"))
        self.assertEqual(finding["last_confirmed_broken"], T1)

    def test_operational_failure_preserves_tracker(self):
        self.run_track(obs({A: "broken"}, T1))
        snapshot = json.dumps(self.store.data, sort_keys=True)
        failed = {**obs({}, T2), "scan_ok": False, "errors": ["lychee exited 3"]}
        with self.assertRaises(lr.OperationalError):
            self.run_track(failed)
        self.human_close()
        closed = json.dumps(self.store.data, sort_keys=True)
        with self.assertRaises(lr.OperationalError):
            self.run_track(failed)
        self.assertEqual(json.dumps(self.store.data, sort_keys=True), closed)
        self.assertNotEqual(snapshot, closed)  # only the human's close changed anything

    def test_clean_recovery_closes_and_rerun_is_quiet(self):
        self.run_track(obs({A: "broken", B: "broken"}, T1))
        _, writes = self.run_track(obs({A: "healthy", B: "unknown"}, T2))
        self.assertNotIn("close", self.ops(writes))  # B is unknown: not recovered
        _, writes = self.run_track(obs({A: "healthy", B: "healthy"}, T3))
        self.assertEqual(self.ops(writes), ["comment", "close", "edit_body"])
        issue, state = self.tracker()
        self.assertEqual(issue["closed_by"], {"login": self.store.actor})
        self.assertEqual({f["resolution"] for f in state["findings"].values()}, {"healthy"})
        _, writes = self.run_track(obs({A: "healthy", B: "healthy"}, T3))
        self.assertEqual(writes, [])

    def test_confirmed_removal_and_exclusion_resolve(self):
        self.run_track(obs({A: "broken", B: "broken"}, T1))
        _, writes = self.run_track(obs({B: "excluded", C: "healthy"}, T2))
        self.assertEqual(self.ops(writes), ["comment", "close", "edit_body"])
        _, state = self.tracker()
        self.assertEqual(state["findings"][A]["resolution"], "removed from canonical inputs")
        self.assertEqual(state["findings"][B]["resolution"], "excluded by lychee.toml")
        comment = self.store.data["issues"][0]["comments"][-1]["body"]
        self.assertIn(A, comment)

    def test_url_moved_to_report_only_counts_as_removed(self):
        self.run_track(obs({A: "broken"}, T1))
        self.run_track(obs({}, T2, report_only=[A]))
        _, state = self.tracker()
        self.assertEqual(state["findings"][A]["resolution"], "removed from canonical inputs")

    def test_recurrence_after_recovery_reopens(self):
        self.run_track(obs({A: "broken"}, T1))
        self.run_track(obs({A: "healthy"}, T2))
        _, writes = self.run_track(obs({A: "broken"}, T3))
        self.assertEqual(self.ops(writes), ["reopen", "comment", "edit_body"])
        issue, state = self.tracker()
        self.assertEqual(issue["state"], "open")
        self.assertEqual(state["findings"][A]["recurrences"], 1)
        self.assertEqual(state["findings"][A]["first_seen"], T1)
        self.assertIn("recurred", issue["comments"][-1]["body"])

    def test_human_closure_new_url_alongside_dismissed_url(self):
        self.run_track(obs({A: "broken"}, T1))
        self.human_close()
        _, writes = self.run_track(obs({A: "broken"}, T2))
        self.assertEqual(self.ops(writes), ["edit_body"])  # stays closed, no comment
        issue, state = self.tracker()
        self.assertEqual(issue["state"], "closed")
        self.assertEqual(state["suppressions"][A]["source"], "closure")
        self.assertIn("@maintainer", state["suppressions"][A]["reason"])
        _, writes = self.run_track(obs({A: "broken"}, T2))  # same-set rerun
        self.assertEqual(writes, [])
        _, writes = self.run_track(obs({A: "broken", B: "broken"}, T3))
        self.assertEqual(self.ops(writes), ["reopen", "comment", "edit_body"])
        issue, state = self.tracker()
        comment = issue["comments"][-1]["body"]
        self.assertIn(B, comment)
        self.assertNotIn(A, comment)
        self.assertIn(A, state["suppressions"])
        self.assertEqual(lr._reportable(state), {B})

    def test_suppression_commands_and_mixed_findings(self):
        self.run_track(obs({A: "broken"}, T1))
        self.human_comment(f"/link-rot suppress {A} vendor page behind login")
        self.human_comment(f"/link-rot suppress {B}", login="noreason")
        self.human_comment(f"/link-rot suppress {C} spam", association="NONE", login="drive-by")
        plan, writes = self.run_track(obs({A: "broken", C: "broken"}, T2))
        issue, state = self.tracker()
        self.assertEqual(set(state["suppressions"]), {A})
        self.assertEqual(state["suppressions"][A]["reason"], "vendor page behind login")
        self.assertEqual(self.ops(writes), ["comment", "edit_body"])  # only C is new
        self.assertIn(C, issue["comments"][-1]["body"])
        self.assertNotIn(A, issue["comments"][-1]["body"].split("stay suppressed")[0].replace(C, ""))
        self.assertTrue(any("reason is required" in n for n in plan.notes))
        self.assertTrue(any("ignored command from @drive-by" in n for n in plan.notes))
        # Commands are processed once; the suppressed URL resets on recovery.
        _, writes = self.run_track(obs({A: "broken", C: "broken"}, T2))
        self.assertEqual(writes, [])
        self.run_track(obs({A: "healthy", C: "broken"}, T3))
        _, state = self.tracker()
        self.assertNotIn(A, state["suppressions"])
        _, writes = self.run_track(obs({A: "broken", C: "broken"}, T4))
        self.assertIn("comment", self.ops(writes))  # recurrence after recovery is reported

    def test_unsuppress_all_restores_reporting(self):
        self.run_track(obs({A: "broken"}, T1))
        self.human_close()
        self.run_track(obs({A: "broken"}, T2))
        self.human_comment("/link-rot unsuppress all")
        _, writes = self.run_track(obs({A: "broken"}, T3))
        self.assertEqual(self.ops(writes), ["reopen", "comment", "edit_body"])

    def test_partial_failure_rerun_does_not_duplicate_comments(self):
        self.run_track(obs({A: "broken"}, T1))
        issue, _ = self.tracker()
        plan = lr.plan_tracker(obs({A: "broken", B: "broken"}, T2), issue,
                               self.store.comments(issue["number"]), T2)
        comment = next(a for a in plan.actions if a["op"] == "comment")
        self.store.comment(issue["number"], comment["body"])  # then the run died
        _, writes = self.run_track(obs({A: "broken", B: "broken"}, T2))
        self.assertEqual(self.ops(writes), ["edit_body"])
        self.assertEqual(sum(comment["key"] in c["body"] for c in issue["comments"]), 1)

    def test_rerun_after_reopen_without_saved_state(self):
        self.run_track(obs({A: "broken"}, T1))
        self.run_track(obs({A: "healthy"}, T2))
        issue, _ = self.tracker()
        plan = lr.plan_tracker(obs({A: "broken"}, T3), issue, self.store.comments(issue["number"]), T3)
        self.assertEqual([a["op"] for a in plan.actions], ["reopen", "comment", "edit_body"])
        self.store.set_state(issue["number"], "open", T3)  # then the run died
        _, writes = self.run_track(obs({A: "broken"}, T3))
        self.assertEqual(self.ops(writes), ["comment", "edit_body"])
        _, writes = self.run_track(obs({A: "broken"}, T3))
        self.assertEqual(writes, [])
        self.assertEqual(sum("link-rot-event" in c["body"] and A in c["body"]
                             for c in issue["comments"]), 2)  # close + one findings comment

    def test_healthy_streak_restarts_after_non_healthy(self):
        self.run_track(obs({A: "broken"}, T1))
        self.run_track(obs({A: "unknown"}, T2))
        _, state = self.tracker()
        self.assertEqual(state["findings"][A]["healthy_streak"], 0)

    def test_duplicate_trackers_are_closed(self):
        self.run_track(obs({A: "broken"}, T1))
        issue, _ = self.tracker()
        self.store.data["issues"].append({**json.loads(json.dumps(issue)), "number": 7, "comments": []})
        _, writes = self.run_track(obs({A: "broken"}, T1))
        self.assertEqual(self.ops(writes), ["comment", "close"])
        self.assertEqual(self.store.data["issues"][1]["state"], "closed")
        _, writes = self.run_track(obs({A: "broken"}, T1))
        self.assertEqual(writes, [])

    def test_malformed_state_is_operational(self):
        self.run_track(obs({A: "broken"}, T1))
        issue, _ = self.tracker()
        issue["body"] = issue["body"].replace('"findings"', '"findings" oops')
        with self.assertRaises(lr.OperationalError):
            self.run_track(obs({A: "healthy"}, T2))
        self.assertEqual(issue["state"], "open")

    def test_state_block_survives_hostile_text(self):
        url = "https://a.example.com/x?q=--><!--"
        self.run_track(obs({url: "broken"}, T1))
        self.human_comment(f"/link-rot suppress {url} bad --> `reason` <b>")
        self.run_track(obs({url: "broken"}, T2))
        _, state = self.tracker()
        self.assertEqual(state["suppressions"][url]["reason"], "bad --> 'reason' <b>")
        self.assertIn(url, state["findings"])

    def test_resolved_history_is_pruned(self):
        self.run_track(obs({A: "broken", B: "broken"}, T1))
        self.run_track(obs({A: "healthy", B: "broken"}, T2))
        self.run_track(obs({A: "healthy", B: "broken"}, "2027-02-01T04:23:00Z"))
        _, state = self.tracker()
        self.assertNotIn(A, state["findings"])
        self.assertIn(B, state["findings"])


class CliTests(unittest.TestCase):
    def run_cli(self, *args):
        env = {k: v for k, v in os.environ.items() if k not in ("GITHUB_STEP_SUMMARY", "GITHUB_RUN_ID")}
        return subprocess.run([sys.executable, str(SCRIPT), *args], capture_output=True,
                              text=True, env=env, timeout=60)

    def test_fixture_dry_run_and_repeat_runs(self):
        with tempfile.TemporaryDirectory() as tmp:
            out, issues = Path(tmp) / "out", Path(tmp) / "issues.json"
            result = self.run_cli("scan", "--fixture", str(FIXTURE), "--out-dir", str(out), "--now", T1)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertTrue((out / "scan-report.md").exists())
            issues.write_text("{}\n")
            observations = str(out / "observations.json")
            dry = self.run_cli("track", "--observations", observations, "--issues-fixture", str(issues),
                               "--dry-run", "--save-fixture", "--now", T1)
            self.assertEqual(dry.returncode, 0, dry.stderr)
            self.assertIn("Planned (dry run, nothing written)", dry.stdout)
            self.assertIn("- create", dry.stdout)
            self.assertEqual(issues.read_text(), "{}\n")  # dry run never saves
            for expected in ("- create", "- no changes"):
                real = self.run_cli("track", "--observations", observations, "--issues-fixture",
                                    str(issues), "--save-fixture", "--now", T1)
                self.assertEqual(real.returncode, 0, real.stderr)
                self.assertIn(expected, real.stdout)
            self.assertEqual(len(json.loads(issues.read_text())["issues"]), 1)

    def test_failed_scan_blocks_tracking(self):
        with tempfile.TemporaryDirectory() as tmp:
            fixture = Path(tmp) / "fixture"
            fixture.mkdir()
            (fixture / "inputs.json").write_text('{"canonical": [], "report_only": []}')
            out = Path(tmp) / "out"
            result = self.run_cli("scan", "--fixture", str(fixture), "--out-dir", str(out))
            self.assertEqual(result.returncode, 1)
            self.assertIn("unexpected zero inputs", result.stderr)
            self.assertIn("Operational failure", (out / "scan-report.md").read_text())
            issues = Path(tmp) / "issues.json"
            issues.write_text("{}\n")
            track = self.run_cli("track", "--observations", str(out / "observations.json"),
                                 "--issues-fixture", str(issues), "--save-fixture")
            self.assertEqual(track.returncode, 1)
            self.assertIn("tracker left untouched", track.stderr)
            self.assertEqual(issues.read_text(), "{}\n")


class WorkflowTests(unittest.TestCase):
    def setUp(self):
        self.path = REPO / ".github/workflows/link-rot-check.yml"
        self.wf = yaml.safe_load(self.path.read_text())
        self.on = self.wf.get("on", self.wf.get(True))

    def test_triggers_permissions_and_concurrency(self):
        self.assertEqual(self.on["schedule"], [{"cron": "23 4 * * 1"}])
        dry = self.on["workflow_dispatch"]["inputs"]["dry_run"]
        self.assertEqual((dry["type"], dry["default"]), ("boolean", False))
        self.assertEqual(self.wf["permissions"], {})
        self.assertEqual(self.wf["concurrency"], {"group": "link-rot-check", "cancel-in-progress": False})
        jobs = self.wf["jobs"]
        self.assertEqual(jobs["scan"]["permissions"], {"contents": "read", "issues": "read"})
        self.assertEqual(jobs["track"]["permissions"], {"contents": "read", "issues": "write"})
        self.assertEqual(jobs["track"]["needs"], "scan")
        self.assertIn("inputs.dry_run", jobs["track"]["if"])

    def test_actions_and_lychee_are_pinned(self):
        text = self.path.read_text()
        for uses in re.findall(r"uses:\s*(\S+)", text):
            self.assertRegex(uses, r"^[\w.-]+/[\w./-]+@[0-9a-f]{40}$")
        self.assertIn(f"lycheeVersion: v{lr.LYCHEE_VERSION}", text)
        self.assertIn(f"lycheeVersion: v{lr.LYCHEE_VERSION}",
                      (REPO / ".github/workflows/link-check.yml").read_text())
        for job in self.wf["jobs"].values():
            for step in job["steps"]:
                if "actions/checkout" in step.get("uses", ""):
                    self.assertFalse(step["with"]["persist-credentials"])

    def test_scan_uses_the_script_and_leaves_the_checkout_clean(self):
        runs = "\n".join(step.get("run", "") for job in self.wf["jobs"].values() for step in job["steps"])
        self.assertIn("scripts/link_rot.py scan", runs)
        self.assertIn("scripts/link_rot.py track", runs)
        self.assertIn("--dry-run", runs)
        self.assertNotIn("--config", runs)  # the script passes exactly one config
        self.assertIn("runner.temp", self.path.read_text())


if __name__ == "__main__":
    unittest.main()
