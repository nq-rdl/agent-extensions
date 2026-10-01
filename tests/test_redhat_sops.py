"""#478: offline sops source/store/guard cases shared by host Bash and Bash 3.2."""
import json
import os
from pathlib import Path
import shlex
import shutil
import tempfile
import unittest

from test_redhat_setup import (ACCESS, OFFLINE, SESSION, OK_BODY, SCRIPTS, GUARD,
                               _bindir, _shim, fake_bw, fake_curl, mode, run)
from test_redhat_hooks import clean_env


def fake_sops(tmp):
    _shim(_bindir(tmp), "sops", r'''
printf 'SOPS-ARGV: %s\n' "$*" >> "$FAKE_LOG"
case "$1" in
  -d)
    [ "$2" = --extract ] && [ "$3" = '["RH_OFFLINE_TOKEN"]' ] && [ -f "$4" ] || exit 9
    if [ "${FAKE_DECRYPT_FAIL:-}" = 1 ]; then
      printf '%s' "$FAKE_SOPS_TOKEN"; printf '%s' "$FAKE_SOPS_TOKEN" >&2; exit 1
    fi
    printf '%s' "${FAKE_SOPS_TOKEN:-}" ;;
  encrypt)
    [ "$#" = 11 ] && [ "$2" = --age ] && [ "$4" = --input-type ] && [ "$5" = dotenv ] \
      && [ "$6" = --output-type ] && [ "$7" = yaml ] && [ "$8" = --filename-override ] \
      && [ "$10" = --encrypted-regex ] || exit 9
    IFS= read -r line
    printf '%s\n' "$line" > "$FAKE_STDIN_COPY"
    # Inspect the real redirected temp file's permissions, before writing ciphertext.
    stat -Lc %a /proc/$$/fd/1 > "$FAKE_TEMP_MODE" 2>/dev/null || true
    if [ "${FAKE_ENCRYPT_FAIL:-}" = 1 ]; then
      printf '%s' "$line" >&2; echo partial; exit 1
    fi
    echo 'RH_OFFLINE_TOKEN: ENC[FAKE-ciphertext]' ;;
  *) exit 9 ;;
esac
'''.replace('"$10"', '"${10}"'))


class SopsCases:
    def execute(self, tmp, env, script, stdin=None):
        return run(["bash", "-c", script], env, stdin)

    def fixture(self, tmp):
        fake_sops(tmp)
        _shim(_bindir(tmp), "secret-tool", "exit 1\n")
        _shim(_bindir(tmp), "security", "exit 44\n")
        env = clean_env(tmp, RH_CRED_SOURCES="sops", PATH=fake_curl(tmp, "200", OK_BODY),
                        FAKE_LOG=str(Path(tmp) / "calls.log"), FAKE_SOPS_TOKEN=OFFLINE,
                        FAKE_STDIN_COPY=str(Path(tmp) / "stdin.copy"),
                        FAKE_TEMP_MODE=str(Path(tmp) / "temp.mode"))
        target = Path(env["XDG_CONFIG_HOME"]) / "redhat/offline-token.sops.yaml"
        return env, target

    def assert_safe(self, tmp, result):
        blob = result.stdout + result.stderr
        log = Path(tmp) / "calls.log"
        if log.exists():
            blob += log.read_text()
        for secret in (OFFLINE, ACCESS, SESSION):
            self.assertNotIn(secret, blob)

    def token_cmd(self):
        return 'bash -x ' + shlex.quote(str(SCRIPTS / "rh-token.sh")) + ' --check'

    def store_cmd(self, seed=False):
        return 'bash -x ' + shlex.quote(str(SCRIPTS / "rh-store-sops.sh")) + ' age1FAKErecipient' + (' --from-bitwarden' if seed else '')

    def test_source_found_empty_failure_missing(self):
        for case in ("found", "empty", "failure", "missing-file", "missing-cli"):
            with self.subTest(case=case), tempfile.TemporaryDirectory() as tmp:
                env, target = self.fixture(tmp)
                target.parent.mkdir(parents=True)
                if case != "missing-file":
                    target.write_text("dummy encrypted fixture\n")
                if case == "empty":
                    env["FAKE_SOPS_TOKEN"] = ""
                if case == "failure":
                    env["FAKE_DECRYPT_FAIL"] = "1"
                if case == "missing-cli":
                    (Path(tmp) / "bin/sops").unlink()
                    # No dependence on whether host sops is installed.
                    for tool in ("bash", "dirname", "uname", "grep", "id", "mkdir", "chmod", "stat", "date"):
                        (Path(tmp) / "bin" / tool).symlink_to(shutil.which(tool))
                    env["PATH"] = str(Path(tmp) / "bin")
                if case == "found":
                    del env["XDG_CONFIG_HOME"]  # HOME/.config fallback
                r = self.execute(tmp, env, self.token_cmd())
                self.assert_safe(tmp, r)
                self.assertEqual(r.returncode, 0 if case == "found" else 3, r.stderr)
                if case == "found":
                    self.assertEqual(r.stdout.strip(), "source=sops access_token=ok expires_in=900s")
                else:
                    self.assertEqual(r.stdout, "")
                    self.assertIn("/redhat:setup", r.stderr)
                    if case in ("empty", "failure"):
                        for hint in ("sops", "age identity", "encrypted file"):
                            self.assertIn(hint, r.stderr)

    def test_started_before_file_exists_store_without_bw_and_check(self):
        with tempfile.TemporaryDirectory() as tmp:
            env, target = self.fixture(tmp)
            # One running shell, unchanged environment: preflight before file, hidden store,
            # then check. Neither bw nor a launch-time token/session is needed.
            script = 'bash ' + shlex.quote(str(SCRIPTS / "rh-preflight.sh")) + ' --json; '
            script += self.store_cmd() + ' && ' + self.token_cmd()
            r = self.execute(tmp, env, script, OFFLINE + "\n")
            self.assertEqual(r.returncode, 0, r.stderr)
            self.assertEqual(json.loads(r.stdout.splitlines()[0])["credential"], "none")
            self.assertIn("source=sops access_token=ok", r.stdout)
            self.assert_safe(tmp, r)
            self.assertNotIn(OFFLINE, target.read_text())
            self.assertEqual(mode(target), 0o600)
            temp_mode = Path(env["FAKE_TEMP_MODE"]).read_text().strip()
            # /proc is Linux-only; final file mode is asserted everywhere.
            if temp_mode:
                self.assertEqual(temp_mode, "600")
            self.assertEqual(list(target.parent.glob(target.name + ".*")), [])
            self.assertEqual(Path(env["FAKE_STDIN_COPY"]).read_text(), "RH_OFFLINE_TOKEN=" + OFFLINE + "\n")

    def test_store_empty_failure_and_symlink_replacement(self):
        for case in ("empty", "failure", "symlink", "invalid"):
            with self.subTest(case=case), tempfile.TemporaryDirectory() as tmp:
                env, target = self.fixture(tmp)
                target.parent.mkdir(parents=True)
                victim = Path(tmp) / "victim"
                victim.write_text("old ciphertext")
                if case == "symlink":
                    target.symlink_to(victim)
                else:
                    target.write_text("old ciphertext")
                if case == "failure":
                    env["FAKE_ENCRYPT_FAIL"] = "1"
                paste = "\n" if case == "empty" else ("bad value\n" if case == "invalid" else OFFLINE + "\n")
                r = self.execute(tmp, env, self.store_cmd(), paste)
                self.assert_safe(tmp, r)
                self.assertEqual(r.returncode, 0 if case == "symlink" else (2 if case == "failure" else 3), r.stderr)
                self.assertEqual(victim.read_text(), "old ciphertext")
                if case == "symlink":
                    self.assertFalse(target.is_symlink())
                    self.assertEqual(mode(target), 0o600)
                else:
                    self.assertEqual(target.read_text(), "old ciphertext")
                self.assertEqual(list(target.parent.glob(target.name + ".*")), [])

    def test_bitwarden_seed_notes_and_custom_field(self):
        for case in ("notes", "field", "empty", "locked"):
            with self.subTest(case=case), tempfile.TemporaryDirectory() as tmp:
                env, target = self.fixture(tmp)
                fake_bw(tmp, notes_fmt="export RH_OFFLINE_TOKEN=%s\\n" if case == "notes" else "")
                env.update(BW_SESSION=SESSION, FAKE_BW_TOKEN=OFFLINE)
                if case == "field":
                    env["FAKE_BW_ITEM_JSON"] = json.dumps({"fields": [{"name": "RH_OFFLINE_TOKEN", "type": 1, "value": OFFLINE}]})
                if case == "locked":
                    del env["BW_SESSION"]
                r = self.execute(tmp, env, self.store_cmd(seed=True))
                self.assert_safe(tmp, r)
                self.assertEqual(r.returncode, 0 if case in ("notes", "field") else 3, r.stderr)
                self.assertEqual(target.exists(), case in ("notes", "field"))
                if target.exists():
                    self.assertNotIn(OFFLINE, target.read_text())
                    self.assertEqual(Path(env["FAKE_STDIN_COPY"]).read_text(), "RH_OFFLINE_TOKEN=" + OFFLINE + "\n")
                self.assertNotIn("--session", Path(env["FAKE_LOG"]).read_text() if Path(env["FAKE_LOG"]).exists() else "")

    def test_path_override_order_filter_and_preflight_tools(self):
        with tempfile.TemporaryDirectory() as tmp:
            env, default = self.fixture(tmp)
            target = Path(tmp) / "custom.yaml"
            target.write_text("dummy encrypted fixture")
            env["RH_OFFLINE_TOKEN_SOPS_FILE"] = str(target)
            for tool in ("age", "age-plugin-tpm"):
                _shim(_bindir(tmp), tool, "exit 0\n")
            plain = default.with_name("offline-token")
            plain.parent.mkdir(parents=True)
            plain.write_text("fallback-file-token")
            fake_bw(tmp)
            env.update(BW_SESSION=SESSION, FAKE_BW_TOKEN=OFFLINE)
            pre = 'bash ' + shlex.quote(str(SCRIPTS / "rh-preflight.sh")) + ' --json'
            stored = self.execute(tmp, env, self.store_cmd(), OFFLINE + "\n")
            self.assertEqual(stored.returncode, 0, stored.stderr)
            self.assert_safe(tmp, stored)
            self.assertEqual(mode(target), 0o600)
            self.assertFalse(default.exists())
            for sources, expected in ((None, "sops"),
                                      ("file,bitwarden", "file"), ("bitwarden", "bitwarden")):
                if sources is None:
                    del env["RH_CRED_SOURCES"]  # test the actual default, not a duplicated list
                else:
                    env["RH_CRED_SOURCES"] = sources
                r = self.execute(tmp, env, pre)
                self.assertEqual(r.returncode, 0, r.stderr)
                data = json.loads(r.stdout)
                self.assertEqual(data["credential"], expected)
                self.assertEqual([data[k] for k in ("sops", "age", "age-plugin-tpm")], ["yes"] * 3)
                self.assert_safe(tmp, r)
            env["RH_CRED_SOURCES"] = "env,keychain,sops,file,bitwarden"
            env["RH_OFFLINE_TOKEN"] = OFFLINE
            r = self.execute(tmp, env, pre)
            self.assertEqual(json.loads(r.stdout)["credential"], "env")
            del env["RH_OFFLINE_TOKEN"]
            for tool in ("secret-tool", "security"):
                _shim(_bindir(tmp), tool, "printf '%s' '" + OFFLINE + "'\n")
            r = self.execute(tmp, env, pre)
            self.assertEqual(json.loads(r.stdout)["credential"], "keychain")
            self.assert_safe(tmp, r)

    def test_guard_direct_decrypt_denied_only_for_token_file(self):
        with tempfile.TemporaryDirectory() as tmp:
            env, target = self.fixture(tmp)
            env["RH_OFFLINE_TOKEN_SOPS_FILE"] = str(Path(tmp) / "custom secret.yaml")
            deny = [
                'sops -d ~/.config/redhat/offline-token.sops.yaml',
                'sops decrypt "$RH_OFFLINE_TOKEN_SOPS_FILE"',
                'sops --decrypt "${RH_OFFLINE_TOKEN_SOPS_FILE}"',
                'sops -d --extract \'["RH_OFFLINE_TOKEN"]\' "' + env["RH_OFFLINE_TOKEN_SOPS_FILE"] + '"',
                'true && /usr/local/bin/sops -d ' + str(target),
                'sops -d ' + str(target) + '; bash "$S/rh-token.sh" --check',
                'bash "$S/rh-token.sh" --check; sops decrypt ' + str(target),
                # Relative paths after cd, and commands that hand plaintext to a child.
                'cd ~/.config/redhat && sops -d offline-token.sops.yaml',
                'cd "$(dirname "$RH_OFFLINE_TOKEN_SOPS_FILE")" && sops -d "custom secret.yaml"',
                'sops exec-env ~/.config/redhat/offline-token.sops.yaml env',
                'sops exec-file "$RH_OFFLINE_TOKEN_SOPS_FILE" "cat {}"',
            ]
            allow = [
                'sops -d other.sops.yaml', 'sops decrypt project/secrets.yaml',
                'sops exec-env project/secrets.yaml make',
                'git commit -m "deny sops -d ~/.config/redhat/offline-token.sops.yaml"',
                'grep -rn "sops decrypt" skills/',
                'echo "sops -d ~/.config/redhat/offline-token.sops.yaml"',
                'bash "$S/rh-token.sh" --check',
                '[ -n "${RH_OFFLINE_TOKEN:-}" ] && echo present',
            ]
            for command in deny + allow:
                with self.subTest(command=command):
                    payload = json.dumps({"tool_name": "Bash", "tool_input": {"command": command}})
                    r = self.execute(tmp, env, 'bash ' + shlex.quote(str(GUARD)), payload)
                    self.assertEqual(r.returncode, 0, r.stderr)
                    if command in deny:
                        data = json.loads(r.stdout)["hookSpecificOutput"]
                        self.assertEqual(data["permissionDecision"], "deny")
                        self.assertIn("rh-token.sh", data["permissionDecisionReason"])
                    else:
                        self.assertEqual(r.stdout, "", r.stderr)


class HostSops(SopsCases, unittest.TestCase):
    pass


class Bash32Sops(SopsCases, unittest.TestCase):
    def setUp(self):
        from bash32_fixture import container_runtime, static_jq
        if not container_runtime() or not static_jq():
            self.skipTest("needs pinned Bash 3.2 image and BASH32_STATIC_JQ; see docs/bash32-portability.md")

    def execute(self, tmp, env, script, stdin=None):
        from bash32_fixture import run_container, static_jq
        scripts = Path(tmp) / "scripts"
        if not scripts.exists():
            shutil.copytree(SCRIPTS, scripts)
        guard = Path(tmp) / "guard.sh"
        shutil.copyfile(GUARD, guard)
        bindir = Path(tmp) / "bin"
        # Replace host executable links with the fixture's BusyBox commands/Bash.
        for path in bindir.iterdir():
            if path.is_symlink():
                path.unlink()
        shutil.copyfile(static_jq(), bindir / "jq")
        (bindir / "jq").chmod(0o755)
        selected = {k: v for k, v in env.items() if k.startswith(("FAKE_", "RH_", "BW_")) or
                    k in ("HOME", "XDG_CONFIG_HOME", "XDG_RUNTIME_DIR", "TMPDIR", "SOPS_AGE_KEY_FILE")}
        selected["PATH"] = f"{bindir}:/usr/local/bin:/usr/bin:/bin"
        script = script.replace(str(SCRIPTS), str(scripts)).replace(str(GUARD), str(guard))
        command = 'set +e; env -i ' + ' '.join(shlex.quote(k + '=' + v) for k, v in selected.items())
        command += ' bash -c ' + shlex.quote(script)
        command += '; status=$?; rm -rf ' + shlex.quote(env["XDG_RUNTIME_DIR"])
        # Restore ownership of private 0600 outputs/directories, not their modes.
        command += f'; chown -R {os.getuid()}:{os.getgid()} ' + shlex.quote(tmp) + '; exit "$status"'
        return run_container(tmp, tmp, command, payload=stdin)
