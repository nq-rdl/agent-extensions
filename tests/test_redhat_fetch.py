"""#492: direct docs, fallback order and entitlement diagnostics; all HTTP is shimmed."""
import json
from pathlib import Path
import shlex
import shutil
import tempfile
import unittest

from test_redhat_hooks import clean_env, SCRIPTS
from test_redhat_setup import _bindir, _shim, run, OFFLINE, ACCESS, OK_BODY

DOCS = "https://docs.redhat.com/en/documentation/red_hat_enterprise_linux/9/html/book/page"
AAP = DOCS.replace("red_hat_enterprise_linux/9", "red_hat_ansible_automation_platform/2.5")
HTML = '''<!doctype html><html><nav>NOT ARTICLE</nav><ARTICLE class="doc">
<h2>Pacemaker &amp; pcs</h2><p>Use &lt;node&gt; &#x26; &#38; peers.</p>
<pre><code>pcs cluster setup &lt;name&gt;
  pcs status --full
</code></pre><p>Done.</p><script>DO NOT EMIT</script></ARTICLE><footer>NOT ARTICLE</footer></html>'''
SHIM = r'''
if [ "${1:-}" = --version ]; then echo "$FAKE_FETCHER 8.0.0-fake"; exit 0; fi
out=""; cfg=""; method=GET
while [ $# -gt 0 ]; do
  case "$1" in
    -o|-O) out="$2"; shift 2 ;;
    -K) cfg="$2"; shift 2 ;;
    --config=*) cfg="${1#*=}"; shift ;;
    --data-binary|--post-file=*) method=POST; shift
      [ "$FAKE_FETCHER" = wget ] || shift ;;
    -w|-H|-X|--connect-timeout|--max-time) shift 2 ;;
    https://*) url="$1"; shift ;;
    *) shift ;;
  esac
done
printf '%s %s cfg=%s\n' "$method" "$url" "$cfg" >> "$FAKE_LOG"
code=200; type=application/json; response=""
case "$url" in
  https://docs.redhat.com/*)
    [ -z "$cfg" ] || exit 91
    code="$FAKE_HTML_CODE"; type="$FAKE_HTML_TYPE"; response="$FAKE_HTML" ;;
  https://sso.redhat.com/*)
    code="$FAKE_SSO_CODE"; response="$FAKE_SSO"
    if [ -n "${FAKE_SECOND_SSO_CODE:-}" ] && [ -e "$FAKE_EXCHANGES" ]; then
      code="$FAKE_SECOND_SSO_CODE"; response="$FAKE_SECOND_SSO"
    fi
    echo exchange >> "$FAKE_EXCHANGES" ;;
  https://api.access.redhat.com/support/search/kcs*)
    [ -n "$cfg" ] && grep -q 'Authorization: Bearer' "$cfg" || exit 92
    if [ -e "$FAKE_QUERIED" ]; then response="$FAKE_KCS_RETRY"; code="$FAKE_RETRY_CODE"
    else response="$FAKE_KCS"; touch "$FAKE_QUERIED"; fi ;;
  https://api.github.com/*) response="$FAKE_TREE" ;;
  https://raw.githubusercontent.com/*) response="$FAKE_SOURCE" ;;
  *) echo 'unexpected network call' >&2; exit 93 ;;
esac
cp "$response" "$out"
if [ "$FAKE_FETCHER" = curl ]; then
  if [ "$type" = "$FAKE_HTML_TYPE" ] && [[ "$url" = https://docs.redhat.com/* ]]; then
    printf '%s\n%s\n' "$code" "$type"
  else printf '%s' "$code"; fi
else
  # A redirect followed by the final response: type/status must use the last header.
  printf '  HTTP/1.1 302 Found\n  Content-Type: text/plain\n' >&2
  printf '  HTTP/1.1 %s Status\n  Content-Type: %s\n' "$code" "$type" >&2
  [ "$code" = 200 ] || exit 8
fi
'''


class FetchCases:
    def execute(self, tmp, env, script, stdin=None):
        return run(["bash", "-c", script], env, stdin)

    def fixture(self, tmp, fetcher="curl", **extra):
        bindir = _bindir(tmp)
        _shim(bindir, fetcher, SHIM)
        # A closed PATH ensures wget-only means no host curl, and no real gh/network call.
        for tool in ("bash", "dirname", "cat", "cp", "head", "tail", "sed", "awk", "grep",
                     "tr", "date", "id", "mkdir", "chmod", "stat", "mktemp", "rm", "mv", "jq", "touch"):
            (bindir / tool).symlink_to(shutil.which(tool))
        env = clean_env(tmp, PATH=str(bindir), FAKE_FETCHER=fetcher,
                        RH_OFFLINE_TOKEN=OFFLINE, FAKE_HTML_CODE="200", FAKE_HTML_TYPE="text/html;charset=utf-8",
                        FAKE_SSO_CODE="200", FAKE_RETRY_CODE="200",
                        FAKE_LOG=str(Path(tmp) / "calls.log"), FAKE_EXCHANGES=str(Path(tmp) / "exchanges"),
                        FAKE_QUERIED=str(Path(tmp) / "queried"))
        kcs = json.dumps({"response": {"numFound": 1, "docs": [{"id": "1182463", "publishedTitle": "Solution",
                         "solution_resolution": "subscriber_only"}]}})
        for name, body in {"HTML": HTML, "SSO": OK_BODY, "KCS": kcs, "KCS_RETRY": kcs,
                           "TREE": '{"tree":[{"path":"downstream/assemblies/page.adoc"}]}',
                           "SOURCE": "= Source page\npcs status\n"}.items():
            path = Path(tmp) / name.lower()
            path.write_text(body)
            env["FAKE_" + name] = str(path)
        env.update(extra)
        return env

    def fetch(self, tmp, env, target, *args, before=""):
        script = before + "bash -x " + shlex.quote(str(SCRIPTS / "rh-fetch.sh"))
        script += " " + " ".join(shlex.quote(arg) for arg in (*args, target))
        r = self.execute(tmp, env, script)
        log = Path(env["FAKE_LOG"]).read_text() if Path(env["FAKE_LOG"]).exists() else ""
        for secret in (OFFLINE, ACCESS):
            self.assertNotIn(secret, r.stdout + r.stderr + log)
        # No fetch temporaries survive any success/fallback/credential error.
        self.assertEqual(list(Path(tmp).glob("rh-fetch.*")), [])
        return r, log

    def body(self, env, name, doc):
        Path(env["FAKE_" + name]).write_text(json.dumps({"response": {"numFound": 1, "docs": [doc]}}))

    def test_direct_html_and_html_single_without_credentials(self):
        for fetcher in ("curl", "wget"):
            for target in (DOCS + "#section", DOCS.replace("/html/book/page", "/html-single/book/index"),
                           "https://access.redhat.com/documentation/en-us/red_hat_enterprise_linux/9/html/book/page"):
                with self.subTest(fetcher=fetcher, target=target), tempfile.TemporaryDirectory() as tmp:
                    env = self.fixture(tmp, fetcher)
                    del env["RH_OFFLINE_TOKEN"]
                    output = Path(tmp) / "result.txt"
                    r, log = self.fetch(tmp, env, target, "-o", str(output))
                    self.assertEqual(r.returncode, 0, r.stderr)
                    self.assertEqual(r.stdout, "")
                    text = output.read_text()
                    self.assertIn("// source: https://docs.redhat.com/", text)
                    self.assertIn("Pacemaker & pcs", text)
                    self.assertIn("Use <node> & & peers.", text)
                    self.assertIn("pcs cluster setup <name>\n  pcs status --full", text)
                    for excluded in ("NOT ARTICLE", "DO NOT EMIT", "<code>"):
                        self.assertNotIn(excluded, text)
                    self.assertEqual(len(log.splitlines()), 1)
                    self.assertNotIn("sso", log)

    def test_block_or_invalid_html_falls_back_to_source(self):
        for fetcher in ("curl", "wget"):
            for case in ("403", "edgesuite", "denied", "no-article", "empty-article", "wrong-type"):
                with self.subTest(fetcher=fetcher, case=case), tempfile.TemporaryDirectory() as tmp:
                    env = self.fixture(tmp, fetcher)
                    del env["RH_OFFLINE_TOKEN"]
                    if case == "403": env["FAKE_HTML_CODE"] = "403"
                    if case == "wrong-type": env["FAKE_HTML_TYPE"] = "application/json"
                    if case in ("edgesuite", "denied"):
                        Path(env["FAKE_HTML"]).write_text(HTML + ("errors.edgesuite.net" if case == "edgesuite" else "Access Denied"))
                    if case == "no-article": Path(env["FAKE_HTML"]).write_text("<html>login</html>")
                    if case == "empty-article": Path(env["FAKE_HTML"]).write_text("<article> </article>")
                    r, log = self.fetch(tmp, env, AAP)
                    self.assertEqual(r.returncode, 0, r.stderr)
                    self.assertIn("// source: https://github.com/ansible/aap-docs/blob/2.5/", r.stdout)
                    self.assertIn("= Source page", r.stdout)
                    self.assertTrue(log.startswith("GET https://docs.redhat.com/"))
                    self.assertNotIn("sso", log)
                    self.assertNotIn("search/kcs", log)

    def test_closed_product_falls_back_to_index_and_missing_credential(self):
        for credential in (True, False):
            with self.subTest(credential=credential), tempfile.TemporaryDirectory() as tmp:
                env = self.fixture(tmp, FAKE_HTML_CODE="403")
                self.body(env, "KCS", {"publishedTitle": "Indexed", "docs_text_store": "pcs status"})
                if not credential: del env["RH_OFFLINE_TOKEN"]
                r, log = self.fetch(tmp, env, DOCS + "#anchor")
                self.assertEqual(r.returncode, 0 if credential else 3, r.stderr)
                if credential:
                    self.assertIn("pcs status", r.stdout)
                    self.assertLess(log.index("docs.redhat.com"), log.index("sso.redhat.com"))
                    self.assertNotIn("#anchor", log)
                else:
                    self.assertIn("/redhat:setup", r.stderr)
                    self.assertNotIn("sso", log)

    def test_source_failure_falls_back_to_index(self):
        with tempfile.TemporaryDirectory() as tmp:
            env = self.fixture(tmp, FAKE_HTML_CODE="403")
            Path(env["FAKE_TREE"]).write_text('{"tree":[{"path":"other.adoc"}]}')
            self.body(env, "KCS", {"docs_text_store": "indexed fallback"})
            r, log = self.fetch(tmp, env, AAP)
            self.assertEqual(r.returncode, 0, r.stderr)
            self.assertIn("indexed fallback", r.stdout)
            self.assertLess(log.index("api.github.com"), log.index("search/kcs"))

    def test_subscriber_only_valid_fresh_token_is_entitlement(self):
        for fetcher in ("curl", "wget"):
            for field in ("subscriber_only", ["subscriber_only"]):
                with self.subTest(fetcher=fetcher, field=field), tempfile.TemporaryDirectory() as tmp:
                    env = self.fixture(tmp, fetcher)
                    self.body(env, "KCS_RETRY", {"id": "1182463", "solution_resolution": field})
                    r, log = self.fetch(tmp, env, "kcs:1182463")
                    self.assertEqual(r.returncode, 3, r.stderr)
                    self.assertIn("account is not entitled", r.stderr)
                    self.assertIn("offline token is valid", r.stderr)
                    self.assertIn("management/subscriptions", r.stderr)
                    self.assertIn("Developer Subscription for Individuals", r.stderr)
                    self.assertNotIn("/redhat:setup", r.stderr)
                    self.assertEqual(Path(env["FAKE_EXCHANGES"]).read_text().count("exchange"), 2)
                    self.assertEqual(log.count("search/kcs"), 2)
                    self.assertEqual(r.stdout, "")

    def test_stale_cached_bearer_recovers_after_refresh(self):
        with tempfile.TemporaryDirectory() as tmp:
            env = self.fixture(tmp)
            # Seed inside the same shell: container uid differs from the host, and the
            # fixture removes its private runtime cache after each execution.
            before = 'cache="$XDG_RUNTIME_DIR/rh-token-$(id -u)"; mkdir -p "$cache"; '
            before += 'printf "source=env\\nexp=%s\\n" "$(( $(date +%s) + 800 ))" > "$cache/access.env"; '
            before += 'printf \'header = "Authorization: Bearer stale"\\n\' > "$cache/curl.cfg"; '
            self.body(env, "KCS_RETRY", {"id": "1182463", "solution_resolution": "Recovered body"})
            r, log = self.fetch(tmp, env, "kcs:1182463", before=before)
            self.assertEqual(r.returncode, 0, r.stderr)
            self.assertIn("Recovered body", r.stdout)
            self.assertNotIn("not entitled", r.stderr)
            self.assertEqual(Path(env["FAKE_EXCHANGES"]).read_text().count("exchange"), 1)
            self.assertEqual(log.count("search/kcs"), 2)

    def test_failed_fresh_exchange_or_retry_does_not_blame_entitlement(self):
        for case in ("invalid_grant", "network", "retry-http"):
            with self.subTest(case=case), tempfile.TemporaryDirectory() as tmp:
                env = self.fixture(tmp)
                # First exchange populates the cache; then make only the fresh exchange fail.
                prime = "bash " + shlex.quote(str(SCRIPTS / "rh-token.sh")) + " --check >/dev/null && "
                failure = Path(tmp) / "sso-failure"
                failure.write_text('{"error":"invalid_grant"}' if case == "invalid_grant" else '{}')
                env["FAKE_SECOND_SSO"] = str(failure)
                if case == "invalid_grant": env["FAKE_SECOND_SSO_CODE"] = "400"
                elif case == "network": env["FAKE_SECOND_SSO_CODE"] = "503"
                else: env["FAKE_RETRY_CODE"] = "503"
                r, _ = self.fetch(tmp, env, "kcs:1182463", before=prime)
                self.assertEqual(r.returncode, 3 if case == "invalid_grant" else 2, r.stderr)
                self.assertNotIn("account is not entitled", r.stderr)
                self.assertIn("/redhat:setup" if case == "invalid_grant" else "HTTP 503", r.stderr)

    def test_index_empty_or_subscriber_only_and_refresh_recovery(self):
        for case in ("empty", "empty-array", "placeholder", "recovers"):
            with self.subTest(case=case), tempfile.TemporaryDirectory() as tmp:
                env = self.fixture(tmp)
                self.body(env, "KCS", {"docs_text_store": [""] if case == "empty-array" else "", "large_text_store": []})
                self.body(env, "KCS_RETRY", {"docs_text_store": "subscriber_only" if case == "placeholder" else ""})
                if case == "recovers": self.body(env, "KCS_RETRY", {"large_text_store": ["Recovered index"]})
                r, log = self.fetch(tmp, env, "docs-text:" + DOCS + "#anchor")
                self.assertEqual(r.returncode, 0 if case == "recovers" else 3, r.stderr)
                self.assertEqual(log.count("search/kcs"), 2)
                self.assertNotIn("#anchor", log)
                if case == "recovers": self.assertIn("Recovered index", r.stdout)
                else:
                    self.assertIn("management/subscriptions", r.stderr)
                    self.assertNotIn("/redhat:setup", r.stderr)
                    if case.startswith("empty"): self.assertIn("index may not store page text", r.stderr)


class HostFetch(FetchCases, unittest.TestCase):
    pass


class Bash32Fetch(FetchCases, unittest.TestCase):
    def setUp(self):
        from bash32_fixture import container_runtime, static_jq
        if not container_runtime() or not static_jq():
            self.skipTest("needs pinned Bash 3.2 image and BASH32_STATIC_JQ; see docs/bash32-portability.md")

    def execute(self, tmp, env, script, stdin=None):
        from test_redhat_sops import Bash32Sops
        return Bash32Sops.execute(self, tmp, env, script, stdin)
