"""Behavioural tests for /redhat:setup (issue #270) – the skill text, its drift guards, the
credential scripts it drives, and the paste blocks it hands the user.

Issue #270's acceptance criteria and non-negotiables are pinned here so a later edit cannot
silently drop them:

- the skill never asks for the token in chat, never prints it, and asks the storage question
  exactly once (SetupSkillText);
- the shipped plugin copy, the guard/rh-lib hint, the fetcher agent's stop message and the
  ``${CLAUDE_PLUGIN_ROOT}`` coupling stay in lockstep with the canonical sources (DriftGuards);
- ``rh-token.sh --check`` reports source + expiry only, for every source the skill offers,
  and no path – including a caller's ``bash -x`` – leaks the offline token, the access token
  or ``BW_SESSION`` (TokenCheck);
- the skill's own store blocks round-trip through rh-lib: what they store is what the
  scripts resolve and exchange, and the token never enters any process's argv (PasteBlocks).

Everything runs offline. ``curl``, ``bw``, ``secret-tool``, ``security`` and ``uname`` are shell
shims on a private PATH; the environment is sanitised (no ``RH_*``/``BW_*``, throwaway HOME,
XDG dirs and TMPDIR) via ``clean_env`` from test_redhat_hooks. Secrets in fixtures are
obviously fake and greppable (``offline-token-FAKE-1``, ``AT-SECRET-FAKE``).
"""

import json
import os
import platform
import re
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

import yaml

sys.path.insert(0, str(Path(__file__).resolve().parent))  # sibling import also works as tests.test_redhat_setup
from test_redhat_hooks import GUARD, PLUGIN, PREFLIGHT_HOOK, REPO, SCRIPTS, clean_env, run_hook

SETUP_SKILL = REPO / "skills" / "redhat-setup" / "SKILL.md"
SETUP_COPY = PLUGIN / "skills" / "setup" / "SKILL.md"
AGENT = REPO / "agents" / "redhat-docs-fetcher" / "agent.md"
AGENT_COPY = PLUGIN / "agents" / "redhat-docs-fetcher.md"
RH_LIB = SCRIPTS / "rh-lib.sh"
RH_TOKEN = SCRIPTS / "rh-token.sh"
RH_PREFLIGHT = SCRIPTS / "rh-preflight.sh"

# Fake secrets: JWT-shaped where rh-lib's bare-JWT parser needs three base64url segments, but
# unmistakably not real. Greppable in any output they might leak into.
OFFLINE = "eyJFAKE.offline-token-FAKE-1.sigFAKE"
ACCESS = "AT-SECRET-FAKE-access-token"
SESSION = "BW-SESSION-SECRET-FAKE"
OK_BODY = '{"access_token":"' + ACCESS + '","expires_in":900}'
FENCE = re.compile(r"```bash\n(.*?)```", re.S)

# Every shim stands in for a compiled binary, so it must never trace itself – otherwise an
# exported SHELLOPTS=xtrace would make the shim (not the code under test) print its inputs.
NO_TRACE = "{ set +x +v; } 2>/dev/null\n"


def _bindir(tmp: str) -> Path:
    b = Path(tmp) / "bin"
    b.mkdir(exist_ok=True)
    return b


def _shim(bindir: Path, name: str, body: str) -> Path:
    f = bindir / name
    f.write_text("#!/usr/bin/env bash\n" + NO_TRACE + body)
    f.chmod(0o755)
    return f


def _real(tool: str) -> str:
    path = shutil.which(tool)
    if not path:
        raise unittest.SkipTest(f"{tool} not installed")
    return path


def fake_curl(tmp: str, status: str, body: str) -> str:
    """A curl stand-in: answers Red Hat SSO with the given status/body, fails on anything else.

    Appends ``ARGV: <argv>`` to ``$FAKE_LOG`` and copies a ``--data-binary @file`` body to
    ``$FAKE_BODY_COPY`` so tests can prove the token travelled by file, never by argv.
    Returns a PATH string with the shim directory first.
    """
    bindir = _bindir(tmp)
    _shim(
        bindir,
        "curl",
        'if [ "${1:-}" = "--version" ]; then echo "curl 8.0.0-fake (offline)"; exit 0; fi\n'
        'out=""; body=""; args=("$@")\n'
        'for ((i=0;i<${#args[@]};i++)); do\n'
        '  [ "${args[i]}" = "-o" ] && out="${args[i+1]}"\n'
        '  [ "${args[i]}" = "--data-binary" ] && body="${args[i+1]}"\n'
        "done\n"
        '[ -z "${FAKE_LOG:-}" ] || printf \'ARGV: %s\\n\' "$*" >> "$FAKE_LOG"\n'
        'case "$body" in @*) [ -z "${FAKE_BODY_COPY:-}" ] || cat "${body#@}" > "$FAKE_BODY_COPY" ;; esac\n'
        'case "${args[${#args[@]}-1]}" in\n'
        f"  https://sso.redhat.com/*) printf '%s' '{body}' > \"$out\"; printf '{status}'; exit 0 ;;\n"
        "  *) echo 'unexpected network call' >&2; exit 7 ;;\n"
        "esac\n",
    )
    return f"{bindir}:{os.environ['PATH']}"


def fake_bw(tmp: str, gated: bool = True, notes_fmt: str = "export RH_OFFLINE_TOKEN=%s\\n") -> None:
    """A minimal bw stand-in for the credential-resolution tests.

    ``get notes redhat-credentials`` prints ``notes_fmt`` (a printf format fed ``$FAKE_BW_TOKEN``);
    when ``gated`` it does so only if BW_SESSION is set, like the real CLI. Every call appends
    ``BW-ARGV: <argv>`` to ``$FAKE_LOG``.
    """
    gate = '[ -n "${BW_SESSION:-}" ] || { echo "Vault is locked." >&2; exit 1; }\n' if gated else ""
    _shim(
        _bindir(tmp),
        "bw",
        '[ -z "${FAKE_LOG:-}" ] || printf \'BW-ARGV: %s\\n\' "$*" >> "$FAKE_LOG"\n'
        + gate
        + 'case "$*" in\n'
        f"  'get notes redhat-credentials') printf '{notes_fmt}' \"${{FAKE_BW_TOKEN:-}}\" ;;\n"
        "  *) echo 'Not found.' >&2; exit 1 ;;\n"
        "esac\n",
    )


def fake_secret_tool(tmp: str) -> None:
    """A secret-tool stand-in.

    ``store [--label=…] attr val …`` reads one line from stdin and persists it under
    ``$FAKE_ST_STATE/<attrs joined by _>`` (label alongside); ``lookup attr val …`` prints it
    (or ``$FAKE_ST_TOKEN`` when that is set, for tests that need no store step).
    """
    _shim(
        _bindir(tmp),
        "secret-tool",
        'cmd="${1:-}"; shift || true\n'
        'if [ "$cmd" = lookup ] && [ -n "${FAKE_ST_TOKEN:-}" ]; then printf \'%s\' "$FAKE_ST_TOKEN"; exit 0; fi\n'
        'state="${FAKE_ST_STATE:?FAKE_ST_STATE unset}"; mkdir -p "$state"\n'
        'label=""\n'
        'case "$cmd" in\n'
        "  store)\n"
        '    while [ $# -gt 0 ]; do case "$1" in --label=*) label="${1#--label=}"; shift ;; *) break ;; esac; done\n'
        '    key="$(printf \'%s\' "$*" | tr \' \' \'_\')"\n'
        '    IFS= read -r s; printf \'%s\' "$s" > "$state/$key"; printf \'%s\\n\' "$label" > "$state/$key.label" ;;\n'
        "  lookup)\n"
        '    key="$(printf \'%s\' "$*" | tr \' \' \'_\')"\n'
        '    [ -s "$state/$key" ] || exit 1; cat "$state/$key" ;;\n'
        "  *) exit 1 ;;\n"
        "esac\n",
    )


def fake_security(tmp: str) -> None:
    """A macOS security(1) stand-in: ``find-generic-password … -s RH_OFFLINE_TOKEN … -w`` prints
    ``$FAKE_SEC_TOKEN``; anything else fails like an absent keychain item (exit 44)."""
    _shim(
        _bindir(tmp),
        "security",
        'case "$*" in\n'
        '  *find-generic-password*"-s RH_OFFLINE_TOKEN"*-w*) printf \'%s\\n\' "${FAKE_SEC_TOKEN:?}" ;;\n'
        "  *) exit 44 ;;\n"
        "esac\n",
    )


def fake_uname_darwin(tmp: str) -> None:
    """A uname stand-in that answers ``-s`` with Darwin and defers everything else to the real one."""
    _shim(
        _bindir(tmp),
        "uname",
        '[ "${1:-}" = -s ] && { echo Darwin; exit 0; }\n'
        f'exec "{_real("uname")}" "$@"\n',
    )


BW_TEMPLATE = (
    '{"organizationId":null,"collectionIds":null,"folderId":null,"type":1,"name":"Item name",'
    '"notes":"Some notes about this item.","favorite":false,"fields":[],"login":null,'
    '"secureNote":null,"card":null,"identity":null,"reprompt":0}'
)


def fake_bw_vault(tmp: str) -> Path:
    """A Bitwarden CLI stand-in backed by a JSON vault for the paste-block tests.

    Items persist as ``$FAKE_BW_STATE/items/<id>.json``. Supports ``unlock --raw`` (prints
    SESSION), ``sync``, ``encode`` (base64), ``get template item``, ``get item <id-or-name>``
    and ``get notes <id-or-name>`` (exact id, else case-insensitive substring match on name –
    exit 1 with ``Not found.`` / ``More than one result was found.`` on stderr like the real
    CLI), ``list items --search <q>`` (same matching), ``create item`` and ``edit item <id>``
    (base64 JSON on stdin). ``unlock --raw`` fails like a wrong master password when
    ``FAKE_BW_UNLOCK_FAIL`` is set. Vault operations require BW_SESSION. Every bw argv is appended to
    ``$FAKE_BW_STATE/calls.log``; a ``jq`` wrapper on the same bindir logs ``JQ-ARGV`` lines
    there too, so a ``--arg notes "$t"`` regression would show up. Returns the state dir.
    """
    bindir = _bindir(tmp)
    state = Path(tmp) / "bwstate"
    (state / "items").mkdir(parents=True, exist_ok=True)
    jq = _real("jq")
    _shim(
        bindir,
        "bw",
        "set -u\n"
        f"JQ='{jq}'\n"
        'state="${FAKE_BW_STATE:?FAKE_BW_STATE unset}"; items="$state/items"; mkdir -p "$items"\n'
        'printf \'bw %s\\n\' "$*" >> "$state/calls.log"\n'
        'vault() { if ls "$items"/*.json >/dev/null 2>&1; then "$JQ" -s . "$items"/*.json; else echo "[]"; fi; }\n'
        "ids_for() { # exact id first, then case-insensitive substring on name (the real CLI's lookup)\n"
        '  vault | "$JQ" -r --arg q "$1" \'([.[] | select(.id == $q)]) as $byid'
        " | (if ($byid | length) > 0 then $byid else [.[] | select(.name | ascii_downcase | contains($q | ascii_downcase))] end) | .[].id'\n"
        "}\n"
        "resolve() { # <id-or-name> -> the one item as JSON, or the CLI's own error on stderr\n"
        '  local ids n; ids="$(ids_for "$1")"; n="$(printf \'%s\\n\' "$ids" | grep -c .)"\n'
        '  if [ "$n" -eq 0 ]; then echo "Not found." >&2; return 1; fi\n'
        '  if [ "$n" -gt 1 ]; then echo "More than one result was found. Try getting a specific object by \\`id\\` instead. The following objects were found:" >&2; printf \'%s\\n\' "$ids" >&2; return 1; fi\n'
        '  cat "$items/$ids.json"\n'
        "}\n"
        'locked() { [ -n "${BW_SESSION:-}" ] || { echo "Vault is locked." >&2; exit 1; }; }\n'
        'next_id() { local n=1; while [ -e "$items/id-fake-$n.json" ]; do n=$((n + 1)); done; echo "id-fake-$n"; }\n'
        'case "${1:-} ${2:-}" in\n'
        f"  'unlock --raw') [ -z \"${{FAKE_BW_UNLOCK_FAIL:-}}\" ] || {{ echo 'Invalid master password.' >&2; exit 1; }}; printf '%s\\n' '{SESSION}' ;;\n"
        "  'sync ') locked; echo 'Syncing complete.' ;;\n"
        "  'encode ') base64 | tr -d '\\n' ;;\n"
        f"  'get template') printf '%s\\n' '{BW_TEMPLATE}' ;;\n"
        "  'get item') locked; resolve \"${3:?}\" ;;\n"
        '  \'get notes\') locked; item="$(resolve "${3:?}")" || exit 1; printf \'%s\\n\' "$item" | "$JQ" -r .notes ;;\n'
        '  \'list items\') locked; q=""; [ "${3:-}" = "--search" ] && q="${4:-}"; vault | "$JQ" -c --arg q "$q" \'[.[] | select(.name | ascii_downcase | contains($q | ascii_downcase))]\' ;;\n'
        '  \'create item\') locked; id="$(next_id)"; base64 -d | "$JQ" --arg id "$id" \'.id = $id\' > "$items/$id.json" && cat "$items/$id.json" ;;\n'
        '  \'edit item\') locked; id="${3:?}"; [ -f "$items/$id.json" ] || { echo "Not found." >&2; exit 1; }\n'
        '    base64 -d | "$JQ" --arg id "$id" \'.id = $id\' > "$items/$id.json.tmp" && mv "$items/$id.json.tmp" "$items/$id.json" && cat "$items/$id.json" ;;\n'
        '  *) echo "fake bw: unsupported: $*" >&2; exit 1 ;;\n'
        "esac\n",
    )
    _shim(
        bindir,
        "jq",
        'printf \'JQ-ARGV: %s\\n\' "$*" >> "${FAKE_BW_STATE:?}/calls.log"\n'
        f'exec "{jq}" "$@"\n',
    )
    return state


def skill_block(*needles: str) -> str:
    """Return the one ```bash fence of skills/redhat-setup/SKILL.md that contains every needle."""
    blocks = [b for b in FENCE.findall(SETUP_SKILL.read_text()) if all(n in b for n in needles)]
    if len(blocks) != 1:
        raise AssertionError(f"expected exactly one bash block matching {needles!r}, found {len(blocks)}")
    return blocks[0]


def run(args, env: dict, stdin: str | None = None):
    return subprocess.run(args, input=stdin, capture_output=True, text=True, env=env, timeout=30)


def preflight(env: dict, *args: str):
    return run(["bash", str(RH_PREFLIGHT), *args], env)


def preflight_json(env: dict) -> dict:
    r = preflight(env, "--json")
    return json.loads(r.stdout)


def token_check(env: dict, *bash_flags: str, args=("--check",)):
    return run(["bash", *bash_flags, str(RH_TOKEN), *args], env)


def cache_dir(env: dict) -> Path:
    return Path(env["XDG_RUNTIME_DIR"]) / f"rh-token-{os.getuid()}"


def mode(p: Path) -> int:
    return os.stat(p).st_mode & 0o777


class SetupSkillText(unittest.TestCase):
    """The canonical skill prose: what the model is told to do and never to do."""

    def setUp(self):
        self.text = SETUP_SKILL.read_text()
        self.fm = yaml.safe_load(self.text.split("---", 2)[1])

    def test_transcript_hygiene_instructions(self):
        prose = re.sub(r"\s+", " ", self.text)  # the sentences are hard-wrapped in the source
        for needle in (
            "Never ask the user to paste the token",
            "never run a command that would print it",
            "in their own terminal",
            "not via `!`",
            "`AskUserQuestion` exactly once",
        ):
            with self.subTest(needle=needle):
                self.assertIn(needle, prose)
        # no token-shaped sample anywhere in the skill
        self.assertIsNone(re.search(r"eyJ[A-Za-z0-9_-]{8,}\.", self.text))

    def test_storage_options_order_and_exact_commands(self):
        markers = ("**Bitwarden personal vault (Recommended)**", "**OS keychain**", "**0600 file**")
        positions = []
        for m in markers:
            pos = self.text.find(m)
            self.assertNotEqual(pos, -1, f"option marker missing: {m}")
            positions.append(pos)
        self.assertEqual(positions, sorted(positions), "storage options are out of the issue's order")
        # #270: the 0600 file is "documented as least-preferred" – on the option bullet itself
        bullet = self.text[positions[2]:self.text.index("\n\n", positions[2])]
        self.assertRegex(bullet, r"least[- ]preferred")
        for needle in (
            'security add-generic-password -a "$USER" -s RH_OFFLINE_TOKEN -U -w',  # -U: re-store updates; -w last: prompts
            "secret-tool store --label='Red Hat offline token' service redhat key RH_OFFLINE_TOKEN",
            "${XDG_CONFIG_HOME:-$HOME/.config}/redhat",
            "redhat-credentials",
            "export RH_OFFLINE_TOKEN=",
            "bwe redhat-credentials",
            "https://access.redhat.com/management/api",
            "Generate Token",
            "shown once",
            "30 days",
            "invalid_grant",
        ):
            with self.subTest(needle=needle):
                self.assertIn(needle, self.text)

    def test_flow_order_and_model_run_commands(self):
        headings = ("## 1. Check", "## 2. Generate", "## 3. Store", "## 4. Load", "## 5. Verify")
        heads = []
        for h in headings:
            pos = self.text.find(h)
            self.assertNotEqual(pos, -1, f"heading missing: {h}")
            heads.append(pos)
        self.assertEqual(heads, sorted(heads))
        self.assertLess(self.text.index('rh-preflight.sh" --json'), heads[1], "preflight must run in step 1")
        self.assertIn('rh-token.sh" --check', self.text)
        self.assertIn("${CLAUDE_PLUGIN_ROOT}/skills/fetch-docs/scripts", self.text)

    def test_frontmatter_allows_askuserquestion_and_is_user_invocable(self):
        self.assertEqual(self.fm["name"], "redhat-setup")
        self.assertTrue(self.fm["user-invocable"])
        self.assertIn("AskUserQuestion", self.fm["allowed-tools"])  # comma-separated scalar
        self.assertIn("30-day", self.fm["compatibility"])

    def test_step1_reports_bw(self):
        # The issue's check enumerates `bw` and rh-preflight.sh emits it; it decides whether the
        # Recommended option is actionable, so step 1 must surface it.
        step1 = self.text.split("## 1. Check", 1)[1].split("## 2.", 1)[0]
        self.assertIn("`bw`", step1)
        self.assertIn("`credential`", step1)

    def test_compatibility_pins_jq_rawfile(self):
        # `jq --rawfile` is a jq 1.6 addition and rh-preflight.sh checks presence only, so the
        # compatibility field is the one place the minimum is visible.
        self.assertIn("--rawfile", self.text)  # precondition: the Bitwarden block still relies on it
        self.assertRegex(self.fm["compatibility"], r"jq\s*>=\s*1\.6")

    def test_exit_3_after_source_found_has_a_next_step(self):
        # rh-token.sh exits 3 ("returned an empty token. Run /redhat:setup …") when preflight found
        # a source that yields no token; the skill must not loop the user back into itself.
        step1 = self.text.split("## 1. Check", 1)[1].split("## 2.", 1)[0]
        step5 = self.text.split("## 5. Verify", 1)[1]
        self.assertRegex(step1, r"[Ee]xit `?3`?")
        self.assertIn("RH_OFFLINE_TOKEN=", step1)  # names the missing-line cause
        self.assertIn("step 3", step1)  # re-store with the same source
        self.assertRegex(step5, r"exit(s|ed)? `?3`?|empty token")
        # rh-token.sh has two exit-3 messages; in step 5 the likely one is "No … found" (the store
        # was written in the user's own terminal, so BW_SESSION is not in Claude's environment)
        self.assertIn("No Red Hat offline token found", step5)
        self.assertIn("BW_SESSION", step5)
        self.assertIn("returned an empty token", step5)
        self.assertIn("step 3", step5)

    def test_check_only_stops_after_step_1_for_every_credential_state(self):
        self.assertIn("--check-only", self.fm["argument-hint"])
        step1 = self.text.split("## 1. Check", 1)[1].split("## 2.", 1)[0]
        self.assertIn("With `--check-only`, stop after this step whatever `credential` says.", step1)

    def test_paste_blocks_avoid_zsh_and_bash32_traps(self):
        blocks = FENCE.findall(self.text)
        self.assertGreaterEqual(len(blocks), 6)
        for i, b in enumerate(blocks):
            with self.subTest(block=i, head=b.splitlines()[0][:60]):
                self.assertNotIn("read -p", b)  # zsh reads it as a coprocess
                self.assertNotIn("mapfile", b)  # bash 4+
                self.assertNotIn("declare -A", b)  # bash 4+
                self.assertNotRegex(b, r"\becho\s+\"?\$t\b")
                self.assertNotRegex(b, r"--arg\s+\w+\s+\"\$t\"")  # token must not become a jq argv
        self.assertNotIn("wget", self.text)


class DriftGuards(unittest.TestCase):
    """The shipped copies and hand-duplicated strings stay in lockstep with the canonical sources."""

    def test_plugin_copy_is_canonical_minus_name(self):
        canon = SETUP_SKILL.read_text().splitlines()
        copy = SETUP_COPY.read_text().splitlines()
        self.assertEqual([l for l in canon if not re.match(r"^name:(\s|$)", l)], copy)
        self.assertFalse(any(l.startswith("name:") for l in copy))

    def test_guard_setup_hint_matches_rh_lib(self):
        guard = re.search(r"^SETUP='(.*)'$", GUARD.read_text(), re.M)
        lib = re.search(r"^RH_SETUP_HINT='(.*)'$", RH_LIB.read_text(), re.M)
        self.assertIsNotNone(guard, f"{GUARD}: SETUP must be a single-quoted literal on its own line")
        self.assertIsNotNone(lib, f"{RH_LIB}: RH_SETUP_HINT must be a single-quoted literal on its own line")
        self.assertEqual(guard.group(1), lib.group(1))
        self.assertIn("/redhat:setup", lib.group(1))
        self.assertEqual((PLUGIN / "skills" / "fetch-docs" / "scripts" / "rh-lib.sh").read_bytes(), RH_LIB.read_bytes())

    def test_agent_stop_message_names_setup(self):
        text = AGENT.read_text()
        for marker in ("**Credential gate**", "**Extract**"):
            self.assertIn(marker, text, f"section marker renamed in {AGENT}")
        gate = text.split("**Credential gate**", 1)[1].split("**Extract**", 1)[0]
        self.assertIn("Run `/redhat:setup` to generate and store your", gate)
        self.assertRegex(gate, r"(Do not|Never) retry")
        self.assertIn("/redhat:setup", text.split("---", 2)[1])  # description
        self.assertRegex(text, r"(do not|never) ask the user for it")
        self.assertIn("rh-token.sh --check", text)
        copy = AGENT_COPY.read_text()
        self.assertIn("Run `/redhat:setup` to generate and store your", copy)
        self.assertRegex(copy, r"(do not|never) ask the user for it")

    def test_plugin_root_references_resolve_inside_the_plugin(self):
        ref = re.compile(r"\$\{CLAUDE_PLUGIN_ROOT\}/([^\"'\s`]+)")
        scr = re.compile(r"\"\$S/(rh-[a-z]+\.sh)\"")
        files = sorted(PLUGIN.rglob("*.md"))
        self.assertTrue(ref.findall(SETUP_COPY.read_text()), "setup skill must reference the fetch-docs scripts")
        for f in files:
            text = f.read_text()
            for rel in ref.findall(text):
                with self.subTest(file=str(f.relative_to(PLUGIN)), ref=rel):
                    self.assertTrue((PLUGIN / rel).exists(), f"{rel} does not exist under plugins/redhat")
                    if (PLUGIN / rel).is_dir():
                        for s in scr.findall(text):
                            self.assertTrue((PLUGIN / rel / s).is_file(), f"{rel}/{s} is not a file")

    def test_keychain_identifiers_match_rh_lib(self):
        skill = SETUP_SKILL.read_text()
        lib = RH_LIB.read_text()
        self.assertIn('security add-generic-password -a "$USER" -s RH_OFFLINE_TOKEN -U -w', skill)
        self.assertIn('security find-generic-password -a "$USER" -s RH_OFFLINE_TOKEN -w', lib)
        self.assertIn("secret-tool store --label='Red Hat offline token' service redhat key RH_OFFLINE_TOKEN", skill)
        self.assertIn("secret-tool lookup service redhat key RH_OFFLINE_TOKEN", lib)
        self.assertIn("${XDG_CONFIG_HOME:-$HOME/.config}/redhat/offline-token", lib)


class TokenCheck(unittest.TestCase):
    """rh-token.sh --check and rh-preflight.sh as the skill drives them – offline, every source."""

    def assert_no_secret(self, *streams: str, secrets=(OFFLINE, ACCESS, SESSION)):
        blob = "".join(streams)
        for s in secrets:
            self.assertNotIn(s, blob)

    def _source_env(self, source: str, tmp: str) -> dict:
        log = os.path.join(tmp, "calls.log")
        path = fake_curl(tmp, "200", OK_BODY)
        if source == "env":
            return clean_env(tmp, RH_OFFLINE_TOKEN=OFFLINE, PATH=path, FAKE_LOG=log)
        if source == "file":
            env = clean_env(tmp, RH_CRED_SOURCES="file", PATH=path, FAKE_LOG=log)
            d = Path(env["XDG_CONFIG_HOME"]) / "redhat"
            d.mkdir(parents=True)
            (d / "offline-token").write_text(OFFLINE + "\n")
            os.chmod(d / "offline-token", 0o600)
            return env
        if source == "keychain":
            fake_secret_tool(tmp)
            return clean_env(tmp, RH_CRED_SOURCES="keychain", FAKE_ST_TOKEN=OFFLINE, PATH=path, FAKE_LOG=log)
        if source == "bitwarden":
            fake_bw(tmp)
            return clean_env(tmp, RH_CRED_SOURCES="bitwarden", BW_SESSION=SESSION, FAKE_BW_TOKEN=OFFLINE, PATH=path, FAKE_LOG=log)
        raise ValueError(source)

    def test_check_success_reports_source_and_expiry_only(self):
        for source in ("env", "file", "keychain", "bitwarden"):
            if source == "keychain" and platform.system() != "Linux":
                continue  # secret-tool is the Linux branch; Darwin is covered by the security shim test
            with self.subTest(source=source), tempfile.TemporaryDirectory() as tmp:
                env = self._source_env(source, tmp)
                r = token_check(env)
                expected = f"source={source} access_token=ok expires_in=900s"
                self.assertEqual((r.returncode, r.stdout.strip()), (0, expected), r.stderr)
                self.assert_no_secret(r.stdout, r.stderr, secrets=(OFFLINE, ACCESS, SESSION, "Bearer"))
                cache = cache_dir(env)
                self.assertEqual(mode(cache), 0o700)
                self.assertEqual(sorted(p.name for p in cache.iterdir()), ["access.env", "curl.cfg"])  # post.*/resp.* cleaned up
                for name in ("access.env", "curl.cfg"):
                    self.assertEqual(mode(cache / name), 0o600, name)
                    self.assertNotIn(OFFLINE, (cache / name).read_text())
                self.assertIn(f"Bearer {ACCESS}", (cache / "curl.cfg").read_text())
                self.assertIn(f"source={source}", (cache / "access.env").read_text())
                log = Path(env["FAKE_LOG"]).read_text()
                self.assertNotIn(OFFLINE, log)  # whole log: bw lines precede curl's
                self.assertIn("--data-binary @", log)
                self.assertNotIn("--session", log)
                if source == "env":
                    r2 = token_check(env, args=())
                    self.assertEqual((r2.returncode, r2.stdout.strip()), (0, expected), r2.stderr)

    def test_macos_keychain_branch_resolves_via_security(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = fake_curl(tmp, "200", OK_BODY)
            fake_uname_darwin(tmp)
            fake_security(tmp)
            env = clean_env(tmp, RH_CRED_SOURCES="keychain", USER="tester", FAKE_SEC_TOKEN=OFFLINE, PATH=path)
            pre = preflight(env, "--json")
            data = json.loads(pre.stdout)
            self.assertEqual((data["os"], data["credential"]), ("Darwin", "keychain"), pre.stderr)
            r = token_check(env)
            self.assertEqual((r.returncode, r.stdout.strip()), (0, "source=keychain access_token=ok expires_in=900s"), r.stderr)
            self.assert_no_secret(pre.stdout, pre.stderr, r.stdout, r.stderr)

    def test_invalid_grant_explains_regeneration_without_the_token(self):
        with self.subTest(status=400), tempfile.TemporaryDirectory() as tmp:
            body = '{"error":"invalid_grant","error_description":"Token is not active"}'
            env = clean_env(tmp, RH_OFFLINE_TOKEN=OFFLINE, PATH=fake_curl(tmp, "400", body))
            r = token_check(env)
            self.assertEqual(r.returncode, 4, r.stderr)
            for needle in ("https://access.redhat.com/management/api", "/redhat:setup", "30 days", "Token is not active", "from 'env'", "invalid_grant"):
                self.assertIn(needle, r.stderr)
            self.assertEqual(r.stdout, "")
            self.assertNotIn(OFFLINE, r.stderr)
        with self.subTest(status=503), tempfile.TemporaryDirectory() as tmp:
            env = clean_env(tmp, RH_OFFLINE_TOKEN=OFFLINE, PATH=fake_curl(tmp, "503", "{}"))
            r = token_check(env)
            self.assertEqual(r.returncode, 2, r.stderr)
            self.assertIn("HTTP 503", r.stderr)
            self.assertNotIn("/redhat:setup", r.stderr)
            self.assertNotIn(OFFLINE, r.stdout + r.stderr)

    def test_loose_file_mode_warns_but_never_prints_token(self):
        with tempfile.TemporaryDirectory() as tmp:
            alt = Path(tmp) / "elsewhere" / "tok"
            alt.parent.mkdir()
            alt.write_text(OFFLINE + "\n")
            os.chmod(alt, 0o600)
            path = fake_curl(tmp, "200", OK_BODY)
            env = clean_env(tmp, RH_CRED_SOURCES="file", RH_OFFLINE_TOKEN_FILE=str(alt), PATH=path)
            self.assertEqual(preflight_json(env)["credential"], "file")
            control = clean_env(tmp, RH_CRED_SOURCES="file", PATH=path)  # no override, no default file
            self.assertEqual(preflight_json(control)["credential"], "none")
            r = token_check(env)
            self.assertEqual((r.returncode, r.stdout.strip(), r.stderr), (0, "source=file access_token=ok expires_in=900s", ""))
            os.chmod(alt, 0o644)
            r = token_check(env)
            self.assertEqual(r.returncode, 0, r.stderr)
            self.assertIn("is not mode 0600", r.stderr)
            self.assertIn(f"chmod 600 '{alt}'", r.stderr)
            self.assertNotIn(OFFLINE, r.stdout + r.stderr)

    def test_bitwarden_source_requires_session(self):
        # The bw shim here is UNCONDITIONAL (it answers regardless of BW_SESSION), so the gate
        # under test is rh-lib's own.
        with self.subTest(case="no session"), tempfile.TemporaryDirectory() as tmp:
            fake_bw(tmp, gated=False)
            log = os.path.join(tmp, "calls.log")
            env = clean_env(tmp, RH_CRED_SOURCES="bitwarden", FAKE_BW_TOKEN=OFFLINE, PATH=fake_curl(tmp, "200", OK_BODY), FAKE_LOG=log)
            self.assertEqual(preflight_json(env)["credential"], "none")
            self.assertFalse(os.path.exists(log), "bw must not be invoked without BW_SESSION")
        with self.subTest(case="session"), tempfile.TemporaryDirectory() as tmp:
            fake_bw(tmp, gated=False)
            log = os.path.join(tmp, "calls.log")
            env = clean_env(tmp, RH_CRED_SOURCES="bitwarden", BW_SESSION=SESSION, FAKE_BW_TOKEN=OFFLINE, PATH=fake_curl(tmp, "200", OK_BODY), FAKE_LOG=log)
            pre = preflight(env, "--json")
            self.assertEqual(json.loads(pre.stdout)["credential"], "bitwarden")
            r = token_check(env)
            self.assertEqual((r.returncode, r.stdout.strip()), (0, "source=bitwarden access_token=ok expires_in=900s"), r.stderr)
            bw_lines = [l for l in Path(log).read_text().splitlines() if l.startswith("BW-ARGV: ")]
            self.assertTrue(bw_lines)
            self.assertTrue(all(l.startswith("BW-ARGV: get notes redhat-credentials") for l in bw_lines), bw_lines)
            self.assert_no_secret(pre.stdout, pre.stderr, r.stdout, r.stderr, secrets=(SESSION, OFFLINE))
        with self.subTest(case="bare JWT after a label line"), tempfile.TemporaryDirectory() as tmp:
            fake_bw(tmp, gated=False, notes_fmt="Red Hat token 2026-08\\n%s\\n")
            env = clean_env(tmp, RH_CRED_SOURCES="bitwarden", BW_SESSION=SESSION, FAKE_BW_TOKEN=OFFLINE, PATH=fake_curl(tmp, "200", OK_BODY))
            r = token_check(env)
            self.assertEqual((r.returncode, r.stdout.strip()), (0, "source=bitwarden access_token=ok expires_in=900s"), r.stderr)
            self.assertNotIn(OFFLINE, r.stdout + r.stderr)

    def test_bitwarden_note_without_token_line_exits_3(self):
        with tempfile.TemporaryDirectory() as tmp:
            fake_bw(tmp, notes_fmt="redhat-credentials\\ncreated 2026-08-01\\n")
            log = os.path.join(tmp, "calls.log")
            env = clean_env(tmp, RH_CRED_SOURCES="bitwarden", BW_SESSION="fake", PATH=fake_curl(tmp, "500", "{}"), FAKE_LOG=log)
            self.assertEqual(preflight_json(env)["credential"], "bitwarden")  # detected merely because the note exists
            r = token_check(env)
            self.assertEqual(r.returncode, 3, r.stderr)
            self.assertIn("empty token", r.stderr)
            self.assertIn("/redhat:setup", r.stderr)
            curl_lines = [l for l in Path(log).read_text().splitlines() if l.startswith("ARGV:")] if os.path.exists(log) else []
            self.assertEqual(curl_lines, [], "no exchange may be attempted without a token")

    def test_xtrace_does_not_leak_secrets(self):
        # `bash -x "$S/rh-token.sh" --check` is a form the guard sanctions; tracing must not turn
        # it into a token dump, and an exported SHELLOPTS=xtrace reaches the child shell too.
        cases = (
            ("env", ("-x",), {}),
            ("bitwarden", ("-x",), {}),
            ("env", (), {"SHELLOPTS": "xtrace"}),
        )
        for source, flags, extra in cases:
            with self.subTest(source=source, flags=flags, extra=extra), tempfile.TemporaryDirectory() as tmp:
                env = self._source_env(source, tmp)
                env.update(extra)
                r = token_check(env, *flags)
                self.assertEqual((r.returncode, r.stdout.strip()), (0, f"source={source} access_token=ok expires_in=900s"), r.stderr[-2000:])
                for s in (OFFLINE, ACCESS, SESSION):
                    self.assertNotIn(s, r.stdout + r.stderr)
                self.assertNotIn("Bearer", r.stderr)

    def test_preflight_with_credential_reports_source_without_setup_nudge(self):
        with tempfile.TemporaryDirectory() as tmp:
            env = clean_env(tmp, RH_OFFLINE_TOKEN=OFFLINE)
            data = preflight_json(env)
            self.assertEqual((data["credential"], data["setup_hint"]), ("env", ""))
            r = preflight(env)
            self.assertIn("credential=env", r.stdout)
            self.assertNotIn("/redhat:setup", r.stdout)
            self.assertNotIn(OFFLINE, r.stdout + r.stderr)
            r = preflight(env, "--require-cred")
            self.assertEqual((r.returncode, r.stdout.strip()), (0, "credential=env"), r.stderr)
            # the SessionStart hook resolves the plugin copy of rh-preflight.sh via CLAUDE_PLUGIN_ROOT
            h = run_hook(PREFLIGHT_HOOK, {"hook_event_name": "SessionStart"}, env)
            ctx = json.loads(h.stdout)["hookSpecificOutput"]["additionalContext"]
            self.assertIn("credential=env", ctx)
            self.assertNotIn("/redhat:setup", ctx)
            self.assertNotIn(OFFLINE, ctx)

    def test_preflight_without_curl_or_wget_reports_fetcher_none(self):
        with tempfile.TemporaryDirectory() as tmp:
            bindir = Path(tmp) / "bin"
            bindir.mkdir()
            for tool in ("bash", "grep", "sed", "tr", "cat", "uname", "awk", "head", "id", "mkdir", "chmod", "stat", "dirname", "jq", "date"):
                path = shutil.which(tool)  # pwd is a bash builtin in the scripts, so it needs no entry
                if path:
                    (bindir / tool).symlink_to(path)
            env = clean_env(tmp, PATH=str(bindir))
            r = preflight(env, "--json")
            self.assertEqual(r.returncode, 0, r.stderr)
            data = json.loads(r.stdout)
            self.assertEqual((data["fetcher"], data["credential"]), ("none", "none"))
            r = preflight(env)
            self.assertEqual(r.returncode, 0, r.stderr)
            self.assertIn("fetcher=none", r.stdout)


class PasteBlocks(unittest.TestCase):
    """The skill's own store blocks, executed as the user would run them, then read back by rh-lib."""

    def _file_env(self, tmp: str) -> tuple[dict, Path, Path]:
        home = Path(tmp) / "home"
        xdg = Path(tmp) / "xdg"  # deliberately not home/.config
        home.mkdir()
        xdg.mkdir()
        env = clean_env(
            str(home),
            XDG_CONFIG_HOME=str(xdg),
            RH_CRED_SOURCES="file",
            PATH=fake_curl(tmp, "200", OK_BODY),
            FAKE_LOG=os.path.join(tmp, "calls.log"),
            FAKE_BODY_COPY=os.path.join(tmp, "body.copy"),
        )
        return env, home, xdg

    def test_file_block_stores_0600_and_rh_lib_resolves_it(self):
        block = skill_block("offline-token", "umask 077")
        with tempfile.TemporaryDirectory() as tmp:
            env, home, xdg = self._file_env(tmp)
            target = xdg / "redhat" / "offline-token"
            target.parent.mkdir(parents=True)
            target.write_text("old\n")
            os.chmod(target, 0o644)  # a loose pre-existing file must be re-tightened
            r = run(["bash", "-c", block], env, stdin="tok-123\n")
            self.assertEqual(r.returncode, 0, r.stderr)
            self.assertIn("stored in", r.stdout)
            self.assertNotIn("tok-123", r.stdout + r.stderr)
            self.assertEqual(target.read_bytes(), b"tok-123\n")
            self.assertEqual(mode(target), 0o600)
            self.assertFalse((home / ".config" / "redhat" / "offline-token").exists())
            r = preflight(env, "--require-cred")
            self.assertEqual((r.returncode, r.stdout.strip()), (0, "credential=file"), r.stderr)
            r = token_check(env)
            self.assertEqual((r.returncode, r.stdout.strip()), (0, "source=file access_token=ok expires_in=900s"), r.stderr)
            self.assertTrue(Path(env["FAKE_BODY_COPY"]).read_text().endswith("&refresh_token=tok-123"))
            self.assertNotIn("tok-123", r.stdout + r.stderr)

    def test_file_block_with_empty_paste_writes_nothing(self):
        block = skill_block("offline-token", "umask 077")
        with tempfile.TemporaryDirectory() as tmp:
            env, _home, xdg = self._file_env(tmp)
            r = run(["bash", "-c", block], env, stdin="\n")
            self.assertNotEqual(r.returncode, 0)
            self.assertFalse((xdg / "redhat" / "offline-token").exists())
            self.assertEqual(preflight_json(env)["credential"], "none")

    @unittest.skipUnless(platform.system() == "Linux", "secret-tool path is Linux-only: rh_os dispatches Darwin to security")
    def test_secret_tool_block_round_trip(self):
        block = skill_block("secret-tool store")
        with tempfile.TemporaryDirectory() as tmp:
            fake_secret_tool(tmp)
            state = Path(tmp) / "st-state"
            env = clean_env(
                tmp,
                RH_CRED_SOURCES="keychain",
                FAKE_ST_STATE=str(state),
                PATH=fake_curl(tmp, "200", OK_BODY),
                FAKE_BODY_COPY=os.path.join(tmp, "body.copy"),
            )
            r = run(["bash", "-c", block], env, stdin="tok-123\n")
            self.assertEqual(r.returncode, 0, r.stderr)
            self.assertNotIn("tok-123", r.stdout + r.stderr)
            keys = [p.name for p in state.iterdir() if not p.name.endswith(".label")]
            self.assertEqual(len(keys), 1, keys)
            self.assertIn("service_redhat_key_RH_OFFLINE_TOKEN", keys[0])
            self.assertEqual((state / (keys[0] + ".label")).read_text().strip(), "Red Hat offline token")
            r = preflight(env, "--require-cred")
            self.assertEqual((r.returncode, r.stdout.strip()), (0, "credential=keychain"), r.stderr)
            r = token_check(env)
            self.assertEqual((r.returncode, r.stdout.strip()), (0, "source=keychain access_token=ok expires_in=900s"), r.stderr)
            self.assertTrue(Path(env["FAKE_BODY_COPY"]).read_text().endswith("&refresh_token=tok-123"))

    def _bw_env(self, tmp: str) -> tuple[dict, Path]:
        state = fake_bw_vault(tmp)
        env = clean_env(
            tmp,
            RH_CRED_SOURCES="bitwarden",
            FAKE_BW_STATE=str(state),
            PATH=fake_curl(tmp, "200", OK_BODY),
            FAKE_BODY_COPY=os.path.join(tmp, "body.copy"),
        )
        return env, state

    def _items(self, state: Path) -> list[Path]:
        return sorted((state / "items").glob("*.json"))

    def test_bitwarden_block_creates_note_then_edits_in_place(self):
        block = skill_block("bw create item", "bw edit item")
        with tempfile.TemporaryDirectory() as tmp:
            env, state = self._bw_env(tmp)
            r1 = run(["bash", "-c", block], env, stdin="tok-123\n")
            self.assertEqual(r1.returncode, 0, r1.stderr)
            self.assertEqual(r1.stdout.strip().splitlines()[-1], "stored")
            items = self._items(state)
            self.assertEqual(len(items), 1, items)
            note = json.loads(items[0].read_text())
            self.assertEqual(
                (note["type"], note["secureNote"], note["name"], note["notes"]),
                (2, {"type": 0}, "redhat-credentials", "export RH_OFFLINE_TOKEN=tok-123\n"),
            )
            first_id = note["id"]
            r2 = run(["bash", "-c", block], env, stdin="tok-456\n")
            self.assertEqual(r2.returncode, 0, r2.stderr)
            self.assertEqual(r2.stdout.strip().splitlines()[-1], "updated")
            items = self._items(state)
            self.assertEqual(len(items), 1, items)
            note = json.loads(items[0].read_text())
            self.assertEqual((note["id"], note["notes"]), (first_id, "export RH_OFFLINE_TOKEN=tok-456\n"))
            calls = (state / "calls.log").read_text()
            for tok in ("tok-123", "tok-456"):
                self.assertNotIn(tok, r1.stdout + r1.stderr + r2.stdout + r2.stderr)
                self.assertNotIn(tok, calls)  # neither bw nor jq ever saw the token in argv
            self.assertEqual(preflight_json(env)["credential"], "none")  # no BW_SESSION loaded
            env["BW_SESSION"] = SESSION
            self.assertEqual(preflight_json(env)["credential"], "bitwarden")
            r = token_check(env)
            self.assertEqual((r.returncode, r.stdout.strip()), (0, "source=bitwarden access_token=ok expires_in=900s"), r.stderr)
            self.assertTrue(Path(env["FAKE_BODY_COPY"]).read_text().endswith("&refresh_token=tok-456"))

    def test_bitwarden_load_step_eval_matches_stored_note_format(self):
        block = skill_block("bw create item", "bw edit item")
        with tempfile.TemporaryDirectory() as tmp:
            env, _state = self._bw_env(tmp)
            r = run(["bash", "-c", block], env, stdin="tok-123\n")
            self.assertEqual(r.returncode, 0, r.stderr)
            env.update(BW_SESSION=SESSION, EXPECTED="tok-123", PRE=str(RH_PREFLIGHT))
            load = (
                'eval "$(bw get notes redhat-credentials)"; '
                '[ "$RH_OFFLINE_TOKEN" = "$EXPECTED" ] && echo loaded; '
                'RH_CRED_SOURCES=env bash "$PRE" --require-cred'
            )
            r = run(["bash", "-c", load], env)
            self.assertEqual(r.stdout.split(), ["loaded", "credential=env"], r.stderr)
            self.assertNotIn("tok-123", r.stderr)

    def test_bitwarden_block_refuses_when_note_is_duplicated(self):
        # A vault that already holds two `redhat-credentials` notes is ambiguous for
        # `bw get notes`; the block must refuse (and sync first), not add a third and print `stored`.
        block = skill_block("bw create item", "bw edit item")
        with tempfile.TemporaryDirectory() as tmp:
            env, state = self._bw_env(tmp)
            for n in ("dup1", "dup2"):
                (state / "items" / f"id-{n}.json").write_text(json.dumps({
                    "id": f"id-{n}", "type": 2, "name": "redhat-credentials",
                    "notes": f"export RH_OFFLINE_TOKEN=old-{n}\n", "secureNote": {"type": 0},
                }))
            r = run(["bash", "-c", block], env, stdin="tok-123\n")
            self.assertEqual(len(self._items(state)), 2, "the block must not add a third note")
            self.assertNotIn("stored", r.stdout)
            self.assertNotIn("updated", r.stdout)
            self.assertIn("more than one", r.stderr)
            calls = (state / "calls.log").read_text()
            self.assertIn("bw sync", calls.splitlines())
            self.assertNotIn("tok-123", r.stdout + r.stderr + calls)
            self._assert_no_write_after_lookup(calls)

    def _assert_no_write_after_lookup(self, calls: str):
        # the guard must short-circuit, not merely print: nothing is fetched or written after the lookup
        lines = calls.splitlines()
        lookups = [i for i, l in enumerate(lines) if l.startswith("bw list items")]
        self.assertTrue(lookups, lines)
        tail = lines[lookups[-1] + 1:]
        self.assertFalse([l for l in tail if l.startswith(("bw get item", "bw edit item", "bw create item"))], tail)

    def test_bitwarden_block_refuses_when_a_near_name_note_would_shadow_the_lookup(self):
        # `bw get notes redhat-credentials` matches names as a case-insensitive substring, so a lone
        # `redhat-credentials-old` (or `Redhat-Credentials`) is what the scripts would read; creating
        # a sibling would make the lookup ambiguous and rh-token.sh exit 3. The block must refuse
        # and name the offending note, never create or edit anything.
        block = skill_block("bw create item", "bw edit item")
        for other in ("redhat-credentials-old", "Redhat-Credentials"):
            with self.subTest(other=other), tempfile.TemporaryDirectory() as tmp:
                env, state = self._bw_env(tmp)
                (state / "items" / "id-other.json").write_text(json.dumps({
                    "id": "id-other", "type": 2, "name": other,
                    "notes": "export RH_OFFLINE_TOKEN=old\n", "secureNote": {"type": 0},
                }))
                r = run(["bash", "-c", block], env, stdin="tok-123\n")
                self.assertEqual([p.name for p in self._items(state)], ["id-other.json"])
                self.assertEqual(json.loads((state / "items" / "id-other.json").read_text())["notes"], "export RH_OFFLINE_TOKEN=old\n")
                self.assertNotIn("stored", r.stdout)
                self.assertNotIn("updated", r.stdout)
                self.assertIn(other, r.stderr)
                self.assertIn("redhat-credentials", r.stderr)
                calls = (state / "calls.log").read_text()
                self.assertNotIn("tok-123", r.stdout + r.stderr + calls)
                self._assert_no_write_after_lookup(calls)
        with self.subTest(other="exact plus -old"), tempfile.TemporaryDirectory() as tmp:
            env, state = self._bw_env(tmp)
            for n in ("redhat-credentials", "redhat-credentials-old"):
                (state / "items" / f"id-{n}.json").write_text(json.dumps({
                    "id": f"id-{n}", "type": 2, "name": n, "notes": "export RH_OFFLINE_TOKEN=old\n", "secureNote": {"type": 0},
                }))
            r = run(["bash", "-c", block], env, stdin="tok-123\n")
            self.assertEqual(len(self._items(state)), 2)
            self.assertNotIn("updated", r.stdout)
            self.assertIn("more than one", r.stderr)
            self.assertIn("redhat-credentials-old", r.stderr)
            self._assert_no_write_after_lookup((state / "calls.log").read_text())

    def test_bitwarden_block_stores_when_only_unrelated_notes_match_the_search(self):
        # a note that merely mentions redhat-credentials in its body, or `aws credentials`, must not block
        block = skill_block("bw create item", "bw edit item")
        with tempfile.TemporaryDirectory() as tmp:
            env, state = self._bw_env(tmp)
            (state / "items" / "id-aws.json").write_text(json.dumps({
                "id": "id-aws", "type": 2, "name": "aws credentials", "notes": "see redhat-credentials\n", "secureNote": {"type": 0},
            }))
            r = run(["bash", "-c", block], env, stdin="tok-123\n")
            self.assertEqual(r.stdout.strip().splitlines()[-1], "stored", r.stderr)
            self.assertEqual(len(self._items(state)), 2)

    def test_bitwarden_block_stops_before_the_prompt_when_unlock_fails(self):
        # a wrong master password must not lead to a token prompt followed by `Vault is locked.`
        # from every later command, and must not clobber a pre-existing session
        block = skill_block("bw create item", "bw edit item")
        for prior in (None, SESSION):
            with self.subTest(prior_session=prior is not None), tempfile.TemporaryDirectory() as tmp:
                env, state = self._bw_env(tmp)
                env["FAKE_BW_UNLOCK_FAIL"] = "1"
                if prior:
                    env["BW_SESSION"] = prior
                r = run(["bash", "-c", block + '\nprintf %s "${BW_SESSION:-}"'], env, stdin="tok-123\n")
                calls = (state / "calls.log").read_text().splitlines()
                self.assertIn("Invalid master password.", r.stderr)
                self.assertNotIn("tok-123", r.stdout + r.stderr + "\n".join(calls))
                if prior:
                    # the old session still works, so the block carries on and stores
                    self.assertEqual(r.stdout.strip().splitlines()[-2:], ["stored", SESSION], r.stderr)
                    self.assertEqual(len(self._items(state)), 1)
                else:
                    self.assertNotIn("Paste offline token", r.stdout)
                    self.assertNotIn("Vault is locked.", r.stderr)
                    self.assertIn("unlock or sync failed", r.stderr)
                    self.assertEqual(calls, ["bw unlock --raw"])
                    self.assertEqual(self._items(state), [])
                    self.assertEqual(r.stdout.strip(), "")


if __name__ == "__main__":
    unittest.main()
