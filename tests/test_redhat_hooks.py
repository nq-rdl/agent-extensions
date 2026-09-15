"""Behavioural tests for the redhat plugin's guardrail hooks and credential scripts.

The hooks are shell (hooks/redhat-docs-*.sh, hand-copied to plugins/redhat/scripts/ — a test
asserts the copies are byte-identical).
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
        self.assert_passthrough(run_hook(GUARD, bash_event("export RH_OFFLINE_TOKEN=`bw get notes redhat-credentials`"), self.env))
        self.assert_passthrough(run_hook(GUARD, bash_event('RH_OFFLINE_TOKEN=$TOKEN_FROM_ELSEWHERE bash "$S/rh-token.sh" --check'), self.env))

    def test_quoted_literal_token_assignment_is_denied(self):
        # Quoting is the conventional form — the guard must not be bypassable by it.
        for cmd in (
            "export RH_OFFLINE_TOKEN='eyJhbGciOiJIUzI1NiJ9.literal'",
            'RH_OFFLINE_TOKEN="eyJhbGciOiJIUzI1NiJ9.literal" bash "$S/rh-token.sh" --check',
        ):
            with self.subTest(cmd=cmd):
                d = decision(run_hook(GUARD, bash_event(cmd), self.env))
                self.assertEqual(d["permissionDecision"], "deny")
                self.assertIn("literal", d["permissionDecisionReason"])

    def test_empty_or_unset_assignment_passes(self):
        self.assert_passthrough(run_hook(GUARD, bash_event('RH_OFFLINE_TOKEN="" bash "$S/rh-preflight.sh"'), self.env))

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

    def test_plugin_script_invocation_forms_pass(self):
        # Command-position variants that must stay exempt: env prefix, quoted path, after && / ;,
        # inside a loop body, inside $(…), and piped into a post-processor.
        for cmd in (
            'RH_CRED_SOURCES=env,file bash "$S/rh-token.sh" --check',
            '"$S/rh-fetch.sh" https://access.redhat.com/solutions/7137578',
            'cd /tmp && bash -x "$S/rh-fetch.sh" https://access.redhat.com/solutions/7137578',
            'S=x; bash "$S/rh-fetch.sh" https://access.redhat.com/solutions/7137578',
            'for u in https://access.redhat.com/solutions/1; do bash "$S/rh-fetch.sh" "$u"; done',
            'python3 render.py "$(bash "$S/rh-fetch.sh" https://docs.redhat.com/en/documentation/x/1/html/b/p)"',
            'bash "$S/rh-fetch.sh" https://docs.redhat.com/en/documentation/x/1/html/b/p | python3 render.py',
        ):
            with self.subTest(cmd=cmd):
                self.assert_passthrough(run_hook(GUARD, bash_event(cmd), self.env))

    def test_lookalike_script_in_cwd_is_not_exempt(self):
        # Only the plugin's own scripts (variable-prefixed or under …/scripts/) are sanctioned; a
        # same-named file the model scaffolds in the working directory still hits the credential gate.
        gated = "'https://api.access.redhat.com/support/search/kcs?q=*&fq=id:7137578'"
        for cmd in ("bash ./rh-fetch.sh " + gated, "bash ./my-rh-fetch.sh " + gated, "rh-fetch.sh " + gated):
            with self.subTest(cmd=cmd):
                d = decision(run_hook(GUARD, bash_event(cmd), self.env))
                self.assertEqual(d["permissionDecision"], "deny")
                self.assertIn("/redhat:setup", d["permissionDecisionReason"])
        for cmd in (
            'bash "${CLAUDE_PLUGIN_ROOT}/skills/fetch-docs/scripts/rh-fetch.sh" ' + gated,
            'bash "$S"/rh-fetch.sh ' + gated,
            "bash skills/redhat-docs-fetch/scripts/rh-fetch.sh " + gated,
        ):
            with self.subTest(cmd=cmd):
                self.assert_passthrough(run_hook(GUARD, bash_event(cmd), self.env))

    def test_script_name_in_comment_does_not_exempt(self):
        # A mention is not an invocation: the fetcher policy still applies.
        for cmd in (
            "python3 -c \"import requests; requests.get('https://api.access.redhat.com/support/search/kcs')\" # rh-fetch.sh",
            "node -e \"fetch('https://api.access.redhat.com/support/search/kcs')\" # see rh-fetch.sh",
            "python3 -c \"import requests; requests.get('https://api.access.redhat.com/support/search/kcs')\"; bash $S/rh-fetch.sh --help",
        ):
            with self.subTest(cmd=cmd):
                d = decision(run_hook(GUARD, bash_event(cmd), self.env))
                self.assertEqual(d["permissionDecision"], "deny")
                self.assertIn("curl", d["permissionDecisionReason"])

    def test_direct_sso_call_asks_even_next_to_plugin_script(self):
        sso = "curl -X POST https://sso.redhat.com/auth/realms/redhat-external/protocol/openid-connect/token -d @body"
        for cmd in (sso + "; : rh-token.sh", sso + ' && bash "$S/rh-token.sh" --check'):
            with self.subTest(cmd=cmd):
                self.assertEqual(decision(run_hook(GUARD, bash_event(cmd), self.env))["permissionDecision"], "ask")

    def test_non_redhat_commands_that_mention_the_plugin_are_not_blocked(self):
        # Reviewing, grepping or committing this plugin's own sources must not trip the guard.
        for cmd in (
            'git commit -m "guard: deny echo of RH_OFFLINE_TOKEN"',
            "grep -rn RH_OFFLINE_TOKEN hooks/ | cat",
            "set -e; grep -rn RH_OFFLINE_TOKEN skills/",
            "oc get node -o wide # https://docs.redhat.com/en/x",
            "echo 'see https://docs.redhat.com/en/x for details'",
        ):
            with self.subTest(cmd=cmd):
                self.assert_passthrough(run_hook(GUARD, bash_event(cmd), self.env))
        self.assert_passthrough(run_hook(GUARD, {"tool_name": "WebFetch", "tool_input": {"url": "https://example.com/?ref=docs.redhat.com"}}, self.env))

    def test_dumping_or_reading_the_token_is_denied(self):
        for cmd in (
            "env | grep RH_OFFLINE_TOKEN",
            "printenv RH_OFFLINE_TOKEN",
            'printf "%s" "$RH_OFFLINE_TOKEN" | wc -c',
            "cat ~/.config/redhat/offline-token",
            'curl -H "Authorization: Bearer $RH_OFFLINE_TOKEN" https://api.access.redhat.com/support/search/kcs?q=x',
        ):
            with self.subTest(cmd=cmd):
                self.assertEqual(decision(run_hook(GUARD, bash_event(cmd), self.env))["permissionDecision"], "deny")

    def test_curl_in_comment_does_not_satisfy_fetcher_policy(self):
        d = decision(run_hook(GUARD, bash_event("python3 fetch.py https://docs.redhat.com/en/x # curl"), self.env))
        self.assertEqual(d["permissionDecision"], "deny")
        self.assertIn("curl", d["permissionDecisionReason"])

    def test_without_jq_the_guard_falls_back_to_python3(self):
        bindir = Path(self.tmp.name) / "bin"
        bindir.mkdir()
        for tool in ("bash", "grep", "sed", "tr", "cat", "python3", "dirname", "pwd"):
            path = subprocess.run(["bash", "-c", f"command -v {tool}"], capture_output=True, text=True).stdout.strip()
            if path:
                (bindir / tool).symlink_to(path)
        env = clean_env(self.tmp.name, PATH=str(bindir))
        d = decision(run_hook(GUARD, bash_event("export RH_OFFLINE_TOKEN=eyJhbGciOiJIUzI1NiJ9.literal"), env))
        self.assertEqual(d["permissionDecision"], "deny")
        self.assert_passthrough(run_hook(GUARD, bash_event("curl -sS https://example.com/"), env))

    def test_credential_gate_finds_preflight_without_plugin_root(self):
        # The plugin copy resolves rh-preflight.sh relative to itself; the canonical copy falls back
        # to checking the env var and the 0600 file directly. Either way a file-stored token passes.
        cfg = Path(self.tmp.name) / ".config" / "redhat"
        cfg.mkdir(parents=True)
        (cfg / "offline-token").write_text("file-token-value\n")
        os.chmod(cfg / "offline-token", 0o600)
        env = clean_env(self.tmp.name, RH_CRED_SOURCES="file")
        del env["CLAUDE_PLUGIN_ROOT"]
        gated = bash_event("curl -sS 'https://api.access.redhat.com/support/search/kcs?q=*&fq=id:7137578'")
        self.assert_passthrough(run_hook(PLUGIN / "scripts" / "redhat-docs-guard.sh", gated, env))
        self.assert_passthrough(run_hook(GUARD, gated, env))

    def test_plain_curl_to_docs_host_passes_to_curl_policy(self):
        # docs.redhat.com is not a gated host and curl is the sanctioned fetcher: no verdict.
        self.assert_passthrough(run_hook(GUARD, bash_event("curl -I https://docs.redhat.com/robots.txt"), self.env))


class PluginCopies(unittest.TestCase):
    def test_hook_copies_match_canonical(self):
        # hooks.json points at plugins/redhat/scripts/; those are hand-copied from hooks/.
        for name in ("redhat-docs-guard.sh", "redhat-docs-preflight.sh"):
            with self.subTest(name=name):
                self.assertEqual((REPO / "hooks" / name).read_bytes(), (PLUGIN / "scripts" / name).read_bytes())


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

    def _fake_curl(self, tmp: str, sso_status: str, sso_body: str) -> str:
        """A curl stand-in: answers Red Hat SSO with the given status/body, fails on anything else."""
        bindir = Path(tmp) / "bin"
        bindir.mkdir(exist_ok=True)
        fake = bindir / "curl"
        fake.write_text(
            "#!/usr/bin/env bash\n"
            'out=""; args=("$@")\n'
            'for ((i=0;i<${#args[@]};i++)); do [ "${args[i]}" = "-o" ] && out="${args[i+1]}"; done\n'
            'case "${args[${#args[@]}-1]}" in\n'
            f"  https://sso.redhat.com/*) printf '%s' '{sso_body}' > \"$out\"; printf '{sso_status}'; exit 0 ;;\n"
            "  *) echo 'unexpected network call' >&2; exit 7 ;;\n"
            "esac\n"
        )
        fake.chmod(0o755)
        return f"{bindir}:{os.environ['PATH']}"

    def _cache_dir(self, env: dict) -> Path:
        return Path(env["XDG_RUNTIME_DIR"]) / f"rh-token-{os.getuid()}"

    def test_check_ignores_cache_and_invalid_grant_clears_it(self):
        with tempfile.TemporaryDirectory() as tmp:
            env = clean_env(tmp, RH_OFFLINE_TOKEN="dummy-offline-token", PATH=self._fake_curl(tmp, "400", '{"error":"invalid_grant"}'))
            cache = self._cache_dir(env)
            cache.mkdir(parents=True, mode=0o700)
            (cache / "access.env").write_text(f"source=env\nexp={int(__import__('time').time()) + 800}\n")
            (cache / "curl.cfg").write_text('header = "Authorization: Bearer stale"\n')
            r = subprocess.run(["bash", str(SCRIPTS / "rh-token.sh"), "--check"], capture_output=True, text=True, env=env)
            self.assertEqual(r.returncode, 4, r.stderr)   # a stale cache must not mask a rejected token
            self.assertIn("invalid_grant", r.stderr)
            self.assertFalse((cache / "access.env").exists())
            self.assertFalse((cache / "curl.cfg").exists())

    def test_curl_config_uses_a_valid_cache_without_network(self):
        with tempfile.TemporaryDirectory() as tmp:
            env = clean_env(tmp, RH_OFFLINE_TOKEN="dummy-offline-token", PATH=self._fake_curl(tmp, "500", "{}"))
            cache = self._cache_dir(env)
            cache.mkdir(parents=True, mode=0o700)
            (cache / "access.env").write_text(f"source=env\nexp={int(__import__('time').time()) + 800}\n")
            (cache / "curl.cfg").write_text('header = "Authorization: Bearer cached"\n')
            r = subprocess.run(["bash", str(SCRIPTS / "rh-token.sh"), "--curl-config"], capture_output=True, text=True, env=env)
            self.assertEqual((r.returncode, r.stdout.strip()), (0, str(cache / "curl.cfg")), r.stderr)

    def test_cache_dir_refuses_a_planted_symlink(self):
        with tempfile.TemporaryDirectory() as tmp:
            env = clean_env(tmp, RH_OFFLINE_TOKEN="dummy-offline-token")
            Path(env["XDG_RUNTIME_DIR"]).mkdir(parents=True)
            self._cache_dir(env).symlink_to(tmp)
            r = subprocess.run(["bash", str(SCRIPTS / "rh-token.sh"), "--check"], capture_output=True, text=True, env=env)
            self.assertEqual(r.returncode, 2)
            self.assertIn("refusing cache dir", r.stderr)

    def test_fetch_argument_validation(self):
        with tempfile.TemporaryDirectory() as tmp:
            env = clean_env(tmp)
            for args, needle in (
                (["kcs:*"], "numeric"),
                (["kcs:1 OR id:2"], "numeric"),
                (["--rows", "abc", "search:x"], "integer"),
                (["-o"], "needs a value"),
                (["https://docs.redhat.com/en/documentation/openshift_container_platform/4.18/html/nodes/index"], "landing page"),
            ):
                with self.subTest(args=args):
                    r = subprocess.run(["bash", str(SCRIPTS / "rh-fetch.sh"), *args], capture_output=True, text=True, env=env)
                    self.assertNotEqual(r.returncode, 0)
                    self.assertIn(needle, r.stderr)

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
            r = subprocess.run(["bash", str(SCRIPTS / "rh-fetch.sh"), "https://docs.redhat.com/en/documentation/red_hat_enterprise_linux/9/html/book/page#anchor"], capture_output=True, text=True, env=env)
            self.assertEqual(r.returncode, 4)
            # the docs-text: advice must name the page URL — the KCS index is keyed without the anchor
            self.assertIn("docs-text:https://docs.redhat.com/en/documentation/red_hat_enterprise_linux/9/html/book/page'", r.stderr)
            self.assertNotIn("page#anchor", r.stderr.split("docs-text:")[1])

    def test_legacy_access_documentation_url_routes_like_docs(self):
        # access.redhat.com/documentation/<locale>/… 301s to docs.redhat.com; same product routing applies.
        with tempfile.TemporaryDirectory() as tmp:
            r = subprocess.run(["bash", str(SCRIPTS / "rh-fetch.sh"), "https://access.redhat.com/documentation/en-us/red_hat_enterprise_linux/9/html/book/page"], capture_output=True, text=True, env=clean_env(tmp))
            self.assertEqual(r.returncode, 4)
            self.assertIn("No known public source repo for product 'red_hat_enterprise_linux'", r.stderr)
            self.assertNotIn("solution/article id", r.stderr)


if __name__ == "__main__":
    unittest.main()
