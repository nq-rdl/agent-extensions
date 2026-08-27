"""Behavioural tests for the redhat plugin's guardrail hooks and credential scripts.

The hooks are shell (hooks/redhat-docs-*.sh, hand-copied to plugins/redhat/scripts/).
Each test pipes a Claude Code event JSON through the hook with a sanitised environment
(no RH_* variables, a throwaway HOME, credential sources restricted to `env`) and asserts
the permissionDecision / additionalContext. No network: every path exercised here stops
before any HTTP call.
"""

import json
import os
import subprocess
import tempfile
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
PLUGIN = REPO / "plugins" / "redhat"
GUARD = REPO / "hooks" / "redhat-docs-guard.sh"
PREFLIGHT_HOOK = REPO / "hooks" / "redhat-docs-preflight.sh"
SCRIPTS = REPO / "skills" / "redhat-docs-fetch" / "scripts"


def clean_env(home: str, **extra) -> dict:
    env = {k: v for k, v in os.environ.items() if not k.startswith(("RH_", "BW_"))}
    env.update(
        HOME=home,
        XDG_CONFIG_HOME=os.path.join(home, ".config"),
        XDG_RUNTIME_DIR=os.path.join(home, "run"),
        TMPDIR=home,
        CLAUDE_PLUGIN_ROOT=str(PLUGIN),
        RH_CRED_SOURCES="env",
    )
    env.update(extra)
    return env


def run_hook(script: Path, event: dict | str, env: dict):
    stdin = event if isinstance(event, str) else json.dumps(event)
    return subprocess.run(
        ["bash", str(script)], input=stdin, capture_output=True, text=True, env=env, timeout=30
    )


def bash_event(command: str) -> dict:
    return {"tool_name": "Bash", "tool_input": {"command": command}}


def decision(result) -> dict:
    return json.loads(result.stdout)["hookSpecificOutput"]


class GuardHook(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.env = clean_env(self.tmp.name)

    def tearDown(self):
        self.tmp.cleanup()

    def assert_passthrough(self, result):
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(result.stdout.strip(), "")

    def test_non_redhat_command_passes_silently(self):
        self.assert_passthrough(run_hook(GUARD, bash_event("curl -sS https://example.com/"), self.env))

    def test_malformed_stdin_is_a_noop(self):
        self.assert_passthrough(run_hook(GUARD, "not json at all", self.env))

    def test_webfetch_to_redhat_host_is_denied(self):
        r = run_hook(GUARD, {"tool_name": "WebFetch", "tool_input": {"url": "https://docs.redhat.com/en/x"}}, self.env)
        d = decision(r)
        self.assertEqual(d["permissionDecision"], "deny")
        self.assertIn("/redhat:fetch-docs", d["permissionDecisionReason"])

    def test_webfetch_elsewhere_passes(self):
        self.assert_passthrough(run_hook(GUARD, {"tool_name": "WebFetch", "tool_input": {"url": "https://github.com/x"}}, self.env))

    def test_python_requests_against_redhat_is_denied(self):
        r = run_hook(GUARD, bash_event("python3 -c \"import requests; requests.get('https://api.access.redhat.com/support/search/kcs')\""), self.env)
        d = decision(r)
        self.assertEqual(d["permissionDecision"], "deny")
        self.assertIn("curl", d["permissionDecisionReason"])

    def test_literal_bearer_token_is_denied(self):
        r = run_hook(GUARD, bash_event("curl -H 'Authorization: Bearer eyJhbGciOiJSUzI1NiJ9.abcdefghijklmnopqrstuvwxyz' https://api.access.redhat.com/support/search/kcs?q=x"), self.env)
        self.assertEqual(decision(r)["permissionDecision"], "deny")

    def test_literal_token_assignment_is_denied_even_without_host(self):
        r = run_hook(GUARD, bash_event("export RH_OFFLINE_TOKEN=eyJhbGciOiJIUzI1NiJ9.literal"), self.env)
        d = decision(r)
        self.assertEqual(d["permissionDecision"], "deny")
        self.assertIn("/redhat:setup", d["permissionDecisionReason"])

    def test_assignment_from_secret_store_is_allowed(self):
        self.assert_passthrough(run_hook(GUARD, bash_event('export RH_OFFLINE_TOKEN="$(bw get notes redhat-credentials)"'), self.env))

    def test_echoing_the_token_is_denied(self):
        r = run_hook(GUARD, bash_event("echo $RH_OFFLINE_TOKEN"), self.env)
        self.assertEqual(decision(r)["permissionDecision"], "deny")

    def test_direct_sso_call_asks(self):
        r = run_hook(GUARD, bash_event("curl -X POST https://sso.redhat.com/auth/realms/redhat-external/protocol/openid-connect/token -d @body"), self.env)
        d = decision(r)
        self.assertEqual(d["permissionDecision"], "ask")
        self.assertIn("rh-token.sh", d["permissionDecisionReason"])

    def test_gated_host_without_credential_is_denied_with_setup_hint(self):
        r = run_hook(GUARD, bash_event("curl -sS 'https://api.access.redhat.com/support/search/kcs?q=*&fq=id:7137578'"), self.env)
        d = decision(r)
        self.assertEqual(d["permissionDecision"], "deny")
        self.assertIn("/redhat:setup", d["permissionDecisionReason"])

    def test_gated_host_with_credential_passes(self):
        env = clean_env(self.tmp.name, RH_OFFLINE_TOKEN="dummy-value-for-presence-only")
        self.assert_passthrough(run_hook(GUARD, bash_event("curl -sS 'https://api.access.redhat.com/support/search/kcs?q=*&fq=id:7137578'"), env))

    def test_public_search_without_credential_passes(self):
        self.assert_passthrough(run_hook(GUARD, bash_event("curl -sS 'https://api.access.redhat.com/support/search/kcs?q=proxy&rows=3'"), self.env))

    def test_plugin_scripts_pass(self):
        self.assert_passthrough(run_hook(GUARD, bash_event("bash $S/rh-fetch.sh kcs:7137578 # https://access.redhat.com/solutions/7137578"), self.env))

    def test_plain_curl_to_docs_host_passes_to_curl_policy(self):
        # docs.redhat.com is not a gated host and curl is the sanctioned fetcher: no verdict.
        self.assert_passthrough(run_hook(GUARD, bash_event("curl -I https://docs.redhat.com/robots.txt"), self.env))


class PreflightHook(unittest.TestCase):
    def test_without_credential_context_points_at_setup(self):
        with tempfile.TemporaryDirectory() as tmp:
            r = run_hook(PREFLIGHT_HOOK, {"hook_event_name": "SessionStart"}, clean_env(tmp))
            self.assertEqual(r.returncode, 0, r.stderr)
            ctx = json.loads(r.stdout)["hookSpecificOutput"]
            self.assertEqual(ctx["hookEventName"], "SessionStart")
            self.assertIn("credential=none", ctx["additionalContext"])
            self.assertIn("/redhat:setup", ctx["additionalContext"])

    def test_with_credential_reports_source_not_value(self):
        with tempfile.TemporaryDirectory() as tmp:
            r = run_hook(PREFLIGHT_HOOK, {}, clean_env(tmp, RH_OFFLINE_TOKEN="s3cr3t-token-value"))
            ctx = json.loads(r.stdout)["hookSpecificOutput"]["additionalContext"]
            self.assertIn("credential=env", ctx)
            self.assertNotIn("s3cr3t", ctx)

    def test_missing_plugin_root_is_a_noop(self):
        with tempfile.TemporaryDirectory() as tmp:
            env = clean_env(tmp, CLAUDE_PLUGIN_ROOT=os.path.join(tmp, "nowhere"))
            r = run_hook(PREFLIGHT_HOOK, {}, env)
            self.assertEqual((r.returncode, r.stdout.strip()), (0, ""))


class CredentialScripts(unittest.TestCase):
    def test_preflight_json_shape(self):
        with tempfile.TemporaryDirectory() as tmp:
            r = subprocess.run(["bash", str(SCRIPTS / "rh-preflight.sh"), "--json"], capture_output=True, text=True, env=clean_env(tmp))
            data = json.loads(r.stdout)
            self.assertEqual(data["credential"], "none")
            self.assertIn("/redhat:setup", data["setup_hint"])
            for key in ("os", "arch", "fetcher", "jq", "gh", "bw"):
                self.assertIn(key, data)

    def test_preflight_require_cred_exits_3(self):
        with tempfile.TemporaryDirectory() as tmp:
            r = subprocess.run(["bash", str(SCRIPTS / "rh-preflight.sh"), "--require-cred"], capture_output=True, text=True, env=clean_env(tmp))
            self.assertEqual(r.returncode, 3)
            self.assertIn("/redhat:setup", r.stderr)

    def test_file_source_is_detected_but_value_never_printed(self):
        with tempfile.TemporaryDirectory() as tmp:
            cfg = Path(tmp) / ".config" / "redhat"
            cfg.mkdir(parents=True)
            (cfg / "offline-token").write_text("file-token-value\n")
            os.chmod(cfg / "offline-token", 0o600)
            env = clean_env(tmp, RH_CRED_SOURCES="env,file")
            r = subprocess.run(["bash", str(SCRIPTS / "rh-preflight.sh")], capture_output=True, text=True, env=env)
            self.assertIn("credential=file", r.stdout)
            self.assertNotIn("file-token-value", r.stdout + r.stderr)

    def test_token_check_without_credential_exits_3_no_network(self):
        with tempfile.TemporaryDirectory() as tmp:
            r = subprocess.run(["bash", str(SCRIPTS / "rh-token.sh"), "--check"], capture_output=True, text=True, env=clean_env(tmp))
            self.assertEqual(r.returncode, 3)
            self.assertIn("/redhat:setup", r.stderr)

    def test_fetch_usage_and_unknown_product(self):
        with tempfile.TemporaryDirectory() as tmp:
            env = clean_env(tmp)
            r = subprocess.run(["bash", str(SCRIPTS / "rh-fetch.sh")], capture_output=True, text=True, env=env)
            self.assertEqual(r.returncode, 1)
            r = subprocess.run(["bash", str(SCRIPTS / "rh-fetch.sh"), "https://docs.redhat.com/en/documentation/red_hat_enterprise_linux/9/html/book/page"], capture_output=True, text=True, env=env)
            self.assertEqual(r.returncode, 4)
            self.assertIn("docs-text:", r.stderr)


if __name__ == "__main__":
    unittest.main()
