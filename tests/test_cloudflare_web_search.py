"""Tests for skills/cloudflare-web-search/scripts/cf-websearch.sh.

A curl shim stands in for api.cloudflare.com: no network, no real credentials.
The cases pin the documented request shape (docs dated 2026-10-02), the local
limit checks that avoid paying for a 400, and that the token never reaches argv,
stdout or stderr.
"""
import json
import os
import shlex
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
SCRIPT = REPO / "skills" / "cloudflare-web-search" / "scripts" / "cf-websearch.sh"
TOKEN = "cfTok_SECRET-123"
ACCOUNT = "0123456789abcdef0123456789abcdef"

SHIM = r'''#!/usr/bin/env bash
# Fake curl: log argv and the stdin config, write the canned body to --output.
out="" data="" url=""
printf '%s\n' "$*" >> "$FAKE_DIR/argv.log"
while [ $# -gt 0 ]; do
  case "$1" in
    --output) out="$2"; shift 2 ;;
    --data) data="$2"; shift 2 ;;
    --write-out|--max-time|--request|--header) shift 2 ;;
    --config) cat > "$FAKE_DIR/config"; shift 2 ;;
    -*) shift ;;
    *) url="$1"; shift ;;
  esac
done
printf '%s' "$data" > "$FAKE_DIR/body.json"
printf '%s' "$url" > "$FAKE_DIR/url"
[ -z "${FAKE_CURL_FAIL:-}" ] || exit "$FAKE_CURL_FAIL"
cp "$FAKE_DIR/response" "$out"
printf '%s' "$FAKE_CODE"
'''

OK = {"items": [{"url": "https://example.com/a", "title": "A page", "description": "First\n  result"},
                {"url": "https://example.com/b", "title": "B page"}],
      "metadata": {"query": "q", "requestId": "r1", "latencyMs": 5}}


def fixture(tmp, response=OK, code="200"):
    bindir = Path(tmp) / "bin"
    bindir.mkdir()
    (bindir / "curl").write_text(SHIM)
    (bindir / "curl").chmod(0o755)
    (Path(tmp) / "response").write_text(json.dumps(response))
    shutil.copyfile(SCRIPT, Path(tmp) / "cf-websearch.sh")
    return {"FAKE_DIR": tmp, "FAKE_CODE": code, "TMPDIR": tmp,
            "CLOUDFLARE_API_TOKEN": TOKEN, "CLOUDFLARE_ACCOUNT_ID": ACCOUNT}


class SearchCases:
    """Shared cases; subclasses supply ``execute(tmp, env, command)``."""

    def search(self, tmp, env, *args):
        command = "bash ./cf-websearch.sh " + " ".join(shlex.quote(a) for a in args)
        r = self.execute(tmp, env, command)
        logged = (Path(tmp) / "argv.log").read_text() if (Path(tmp) / "argv.log").exists() else ""
        self.assertNotIn(TOKEN, r.stdout + r.stderr + logged)
        self.assertEqual(list(Path(tmp).glob("cf-websearch.??????")), [])
        return r

    def sent(self, tmp):
        return json.loads((Path(tmp) / "body.json").read_text())

    def test_request_shape_auth_on_stdin_and_output(self):
        with tempfile.TemporaryDirectory() as tmp:
            env = fixture(tmp)
            r = self.search(tmp, env, "--provider", "linkup", "--limit", "3", "fall in SLC")
            self.assertEqual(r.returncode, 0, r.stderr)
            self.assertEqual(json.loads(r.stdout), OK)
            self.assertEqual(self.sent(tmp), {"query": "fall in SLC", "provider": "linkup", "limit": 3,
                                              "options": {"gateway": {"id": "default"}}})
            self.assertEqual((Path(tmp) / "url").read_text(),
                             f"https://api.cloudflare.com/client/v4/accounts/{ACCOUNT}/ai/websearch/")
            self.assertEqual((Path(tmp) / "config").read_text(),
                             f'header = "Authorization: Bearer {TOKEN}"\n')

            # Defaults are left to the API; gateway env var and BYOK alias are sent.
            env["CLOUDFLARE_AI_GATEWAY_ID"] = "gw-1"
            r = self.search(tmp, env, "--byok-alias", "default", "--", "--looks-like-a-flag")
            self.assertEqual(r.returncode, 0, r.stderr)
            self.assertEqual(self.sent(tmp), {"query": "--looks-like-a-flag", "byokAlias": "default",
                                              "options": {"gateway": {"id": "gw-1"}}})

    def test_text_output_and_v4_envelope(self):
        with tempfile.TemporaryDirectory() as tmp:
            env = fixture(tmp, response={"success": True, "result": OK, "errors": []})
            r = self.search(tmp, env, "--text", "q")
            self.assertEqual(r.returncode, 0, r.stderr)
            self.assertEqual(r.stdout, "1. A page\n   https://example.com/a\n   First result\n"
                                       "2. B page\n   https://example.com/b\n")

    def test_local_validation_never_calls_the_api(self):
        with tempfile.TemporaryDirectory() as tmp:
            env = fixture(tmp)
            for args in (["--provider", "bing", "q"], ["--limit", "11", "q"], ["--limit", "0", "q"],
                         ["--byok-alias", "bad alias", "q"], ["--gateway", "a/b", "q"], [""],
                         ["x" * 1025], ["a", "b"], ["--bogus", "q"]):
                r = self.search(tmp, env, *args)
                self.assertEqual(r.returncode, 2, (args, r.stderr))
            self.search(tmp, env, "x" * 1024)  # the documented maximum is accepted
            self.assertEqual(len((Path(tmp) / "argv.log").read_text().splitlines()), 1)

    def test_missing_or_unsafe_credentials_exit_3(self):
        with tempfile.TemporaryDirectory() as tmp:
            base = fixture(tmp)
            for name, value in (("CLOUDFLARE_API_TOKEN", ""), ("CLOUDFLARE_ACCOUNT_ID", ""),
                                ("CLOUDFLARE_ACCOUNT_ID", "abc/../x"),
                                ("CLOUDFLARE_API_TOKEN", 'tok"header')):
                r = self.search(tmp, {**base, name: value}, "q")
                self.assertEqual(r.returncode, 3, (name, r.stderr))
                self.assertIn(name, r.stderr)
                if value:
                    self.assertNotIn(value, r.stderr)
            self.assertFalse((Path(tmp) / "argv.log").exists())

    def test_api_errors_report_cloudflare_message_and_hints(self):
        with tempfile.TemporaryDirectory() as tmp:
            env = fixture(tmp, response={"success": False, "errors": [{"code": 10000, "message": "Authentication error"}]},
                          code="403")
            r = self.search(tmp, env, "q")
            self.assertEqual(r.returncode, 1)
            self.assertIn("HTTP 403: 10000: Authentication error", r.stderr)
            self.assertIn("AI Gateway > Read", r.stderr)

            (Path(tmp) / "response").write_text("not json")
            env["FAKE_CODE"] = "400"
            r = self.search(tmp, env, "--byok-alias", "mine", "q")
            self.assertEqual(r.returncode, 1)
            self.assertIn("HTTP 400", r.stderr)
            self.assertIn("no fallback to credits", r.stderr)

            env["FAKE_CURL_FAIL"] = "28"
            r = self.search(tmp, env, "q")
            self.assertEqual(r.returncode, 1)
            self.assertIn("curl exit 28", r.stderr)

            del env["FAKE_CURL_FAIL"]
            env["FAKE_CODE"] = "200"
            (Path(tmp) / "response").write_text('{"unexpected": true}')
            r = self.search(tmp, env, "q")
            self.assertEqual(r.returncode, 1)
            self.assertIn("unexpected response shape", r.stderr)


class HostBash(SearchCases, unittest.TestCase):
    def setUp(self):
        if not shutil.which("jq"):
            self.skipTest("needs jq")

    def execute(self, tmp, env, command):
        path = f"{tmp}/bin:{os.environ.get('PATH', '/usr/bin:/bin')}"
        return subprocess.run(["bash", "-c", command], cwd=tmp, capture_output=True, text=True,
                              env={"PATH": path, "HOME": tmp, **env})


class Bash32(SearchCases, unittest.TestCase):
    """The same cases under the pinned Bash 3.2 / BusyBox image with static jq 1.7.1."""

    def setUp(self):
        from bash32_fixture import container_runtime, static_jq
        if not container_runtime() or not static_jq():
            self.skipTest("needs pinned Bash 3.2 image and BASH32_STATIC_JQ; see docs/bash32-portability.md")

    def execute(self, tmp, env, command):
        from bash32_fixture import run_container, static_jq
        jq = Path(tmp) / "bin" / "jq"
        if not jq.exists():
            shutil.copyfile(static_jq(), jq)
            jq.chmod(0o755)
        inner = 'cd ' + shlex.quote(tmp) + '; set +e; env -i '
        inner += ' '.join(shlex.quote(f"{k}={v}") for k, v in
                          {"PATH": f"{tmp}/bin:/usr/local/bin:/usr/bin:/bin", "HOME": tmp, **env}.items())
        inner += ' bash -c ' + shlex.quote(command)
        inner += f'; status=$?; chown -R {os.getuid()}:{os.getgid()} ' + shlex.quote(tmp) + '; exit "$status"'
        return run_container(tmp, tmp, inner)


if __name__ == "__main__":
    unittest.main()
