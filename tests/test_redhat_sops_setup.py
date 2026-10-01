"""#491 install/identity behavior: disposable homes and offline command shims only."""
import hashlib
import json
from pathlib import Path
import shlex
import shutil
import tempfile
import unittest

from test_redhat_setup import SCRIPTS, OFFLINE, _bindir, _shim, mode, run
from test_redhat_hooks import clean_env
import test_redhat_sops as sops_tests
from test_redhat_sops import fake_sops

BINARY = '#!/usr/bin/env bash\necho "sops ${FAKE_VERSION:-3.13.3}"\n'
DIGEST = hashlib.sha256(BINARY.encode()).hexdigest()


class SetupCases:
    def execute(self, tmp, env, script, stdin=None):
        return run(['bash', '-c', script], env, stdin)

    def command(self, name, args=''):
        return 'bash ' + shlex.quote(str(SCRIPTS / name)) + ' ' + args

    def fixture(self, tmp, os_name='Linux', arch='x86_64', manager='dnf'):
        b = _bindir(tmp)
        # Isolated PATH prevents accidental invocation of host package/download tools.
        for tool in ('bash', 'dirname', 'mkdir', 'mktemp', 'rm', 'chmod', 'ln', 'grep',
                     'awk', 'sha256sum', 'install', 'mv', 'cat', 'id', 'date', 'stat'):
            (b / tool).symlink_to(shutil.which(tool))
        _shim(b, 'uname', f'[ "$1" = -s ] && echo {os_name} || echo {arch}\n')
        _shim(b, 'age', 'exit 0\n')
        _shim(b, 'age-keygen', '''
if [ "${1:-}" = -y ]; then
  [ -s "$2" ] || exit 1
  printf '%s\\n' "${FAKE_RECIPIENT:-age1fakerecipient}"
else
  echo AGE-SECRET-KEY-FAKE
fi
''')
        _shim(b, 'sudo', 'exec "$@"\n')
        _shim(b, manager, '''
printf '%s\\n' "$*" >> "$FAKE_LOG"
[ "${FAKE_PACKAGE_FAIL:-}" != 1 ] || exit 1
printf '#!/usr/bin/env bash\\nexit 0\\n' > "$FAKE_BIN/age"
printf '#!/usr/bin/env bash\\necho AGE-SECRET-KEY-FAKE\\n' > "$FAKE_BIN/age-keygen"
chmod 755 "$FAKE_BIN/age" "$FAKE_BIN/age-keygen"
''')
        _shim(b, 'curl', '''
out=''
while [ "$#" -gt 1 ]; do
  if [ "$1" = -o ]; then out="$2"; shift; fi
  shift
done
printf '%s\\n' "$1" >> "$FAKE_LOG"
[ "${FAKE_DOWNLOAD_FAIL:-}" != 1 ] || exit 7
case "$1" in
  */sops-v3.13.3.checksums.txt)
    asset="sops-v3.13.3.$FAKE_OS.$FAKE_ARCH"
    [ "${FAKE_CHECKSUM:-}" != missing ] || exit 0
    printf '%s  %s\\n' "$FAKE_DIGEST" "$asset" > "$out"
    [ "${FAKE_CHECKSUM:-}" != duplicate ] || printf '%s  %s\\n' "$FAKE_DIGEST" "$asset" >> "$out" ;;
  */sops-v3.13.3.*)
    printf '%s' "$FAKE_BINARY" > "$out"
    [ "${FAKE_CHECKSUM:-}" != tamper ] || echo tampered >> "$out" ;;
  *) exit 9 ;;
esac
exit 0
''')
        return clean_env(tmp, PATH=str(b), FAKE_BIN=str(b), FAKE_LOG=str(Path(tmp) / 'calls'),
                         FAKE_BINARY=BINARY, FAKE_DIGEST=DIGEST,
                         FAKE_OS=os_name.lower(), FAKE_ARCH={'x86_64': 'amd64', 'arm64': 'arm64',
                                                           'aarch64': 'arm64'}.get(arch, arch))

    def test_install_preview_platform_packages_and_binary(self):
        for os_name, arch, manager in [('Linux', 'x86_64', 'dnf'), ('Linux', 'aarch64', 'apt-get'),
                                       ('Darwin', 'arm64', 'brew'), ('Darwin', 'x86_64', 'brew')]:
            with self.subTest(os=os_name, arch=arch), tempfile.TemporaryDirectory() as tmp:
                env = self.fixture(tmp, os_name, arch, manager)
                for tool in ('age', 'age-keygen'):
                    (Path(tmp) / 'bin' / tool).unlink()
                cmd = self.command('rh-install-sops-age.sh')
                r = self.execute(tmp, env, cmd)
                self.assertEqual(r.returncode, 0, r.stderr)
                self.assertIn(manager, r.stdout)
                self.assertFalse(Path(env['FAKE_LOG']).exists())
                r = self.execute(tmp, env, cmd + '--yes')
                self.assertEqual(r.returncode, 0, r.stderr)
                target = Path(env['HOME']) / '.local/bin/sops'
                self.assertEqual(target.read_text(), BINARY)
                self.assertEqual(mode(target), 0o755)
                log = Path(env['FAKE_LOG']).read_text()
                self.assertIn('sops-v3.13.3.' + env['FAKE_OS'] + '.' + env['FAKE_ARCH'], log)
                self.assertNotIn('.rpm', log)
                self.assertNotIn('.deb', log)

    def test_install_failures_preserve_existing_binary(self):
        for case in ('missing', 'duplicate', 'tamper', 'download', 'version', 'dnf'):
            with self.subTest(case=case), tempfile.TemporaryDirectory() as tmp:
                env = self.fixture(tmp)
                target = Path(env['HOME']) / '.local/bin/sops'
                target.parent.mkdir(parents=True)
                target.write_text('old binary')
                env['FAKE_CHECKSUM'] = case
                if case == 'download':
                    env['FAKE_DOWNLOAD_FAIL'] = '1'
                if case == 'version':
                    env['FAKE_VERSION'] = '3.9.0'
                if case == 'dnf':
                    (Path(tmp) / 'bin/age').unlink()
                    env['FAKE_PACKAGE_FAIL'] = '1'
                r = self.execute(tmp, env, self.command('rh-install-sops-age.sh', '--yes'))
                self.assertNotEqual(r.returncode, 0)
                self.assertEqual(target.read_text(), 'old binary')
                self.assertFalse(list(target.parent.glob('.sops.*')))
                if case == 'dnf':
                    self.assertIn('--disablerepo=', r.stderr)
                    self.assertIn('GPG', r.stderr)

    def test_install_unsupported_arch_fails_before_actions(self):
        with tempfile.TemporaryDirectory() as tmp:
            env = self.fixture(tmp, arch='riscv64')
            r = self.execute(tmp, env, self.command('rh-install-sops-age.sh', '--yes'))
            self.assertEqual(r.returncode, 2)
            self.assertFalse(Path(env['FAKE_LOG']).exists())

    def test_identity_paths_reuse_and_private_output(self):
        for os_name, path_kind in [('Linux', 'xdg'), ('Linux', 'home'),
                                   ('Darwin', 'home'), ('Darwin', 'xdg'), ('Linux', 'custom')]:
            with self.subTest(os=os_name, path=path_kind), tempfile.TemporaryDirectory() as tmp:
                env = self.fixture(tmp, os_name)
                if path_kind == 'home':
                    del env['XDG_CONFIG_HOME']
                    root = Path(env['HOME']) / ('.config' if os_name == 'Linux' else 'Library/Application Support')
                else:
                    root = Path(env['XDG_CONFIG_HOME'])
                key = root / 'sops/age/keys.txt'
                if path_kind == 'custom':
                    key = Path(tmp) / 'custom/key.txt'
                    env['SOPS_AGE_KEY_FILE'] = str(key)
                for _ in range(2):
                    r = self.execute(tmp, env, self.command('rh-age-identity.sh'))
                    self.assertEqual((r.returncode, r.stdout), (0, 'age1fakerecipient\n'), r.stderr)
                    self.assertNotIn('AGE-SECRET', r.stdout + r.stderr)
                    self.assertEqual(key.read_text(), 'AGE-SECRET-KEY-FAKE\n')
                    self.assertEqual(mode(key), 0o600)
                    self.assertFalse(list(key.parent.glob('keys.txt.*')))
                # Reuse must never run generation, even if generation would now fail.
                _shim(_bindir(tmp), 'age-keygen', '[ "$1" = -y ] && echo age1existing || exit 9\n')
                r = self.execute(tmp, env, self.command('rh-age-identity.sh'))
                self.assertEqual(r.stdout, 'age1existing\n')
                self.assertEqual(key.read_text(), 'AGE-SECRET-KEY-FAKE\n')

    def test_identity_symlink_failure_and_ambiguous_recipient(self):
        for case in ('symlink', 'generation', 'ambiguous', 'race'):
            with self.subTest(case=case), tempfile.TemporaryDirectory() as tmp:
                env = self.fixture(tmp)
                key = Path(env['XDG_CONFIG_HOME']) / 'sops/age/keys.txt'
                key.parent.mkdir(parents=True)
                if case == 'symlink':
                    key.symlink_to(Path(tmp) / 'absent')
                elif case == 'generation':
                    _shim(_bindir(tmp), 'age-keygen', 'echo AGE-SECRET-LEAK >&2; echo partial; exit 1\n')
                elif case == 'race':
                    env['FAKE_RACE_KEY'] = str(key)
                    _shim(_bindir(tmp), 'age-keygen', 'echo concurrent > "$FAKE_RACE_KEY"; echo AGE-SECRET-KEY-FAKE\n')
                else:
                    key.write_text('existing key')
                    env['FAKE_RECIPIENT'] = 'age1one\nage1two'
                r = self.execute(tmp, env, self.command('rh-age-identity.sh'))
                self.assertEqual(r.returncode, 2, r.stderr)
                self.assertEqual(r.stdout, '')
                self.assertNotIn('AGE-SECRET', r.stderr)
                if case == 'generation':
                    self.assertFalse(key.exists())
                    self.assertEqual(list(key.parent.iterdir()), [])
                if case == 'ambiguous':
                    self.assertEqual(key.read_text(), 'existing key')
                if case == 'race':
                    self.assertEqual(key.read_text(), 'concurrent\n')
                    self.assertEqual(list(key.parent.iterdir()), [key])

    def test_store_without_recipient_initializes_before_hidden_paste(self):
        with tempfile.TemporaryDirectory() as tmp:
            env = self.fixture(tmp)
            fake_sops(tmp)
            env.update(FAKE_STDIN_COPY=str(Path(tmp) / 'stdin'), FAKE_TEMP_MODE=str(Path(tmp) / 'mode'))
            r = self.execute(tmp, env, self.command('rh-store-sops.sh'), OFFLINE + '\n')
            self.assertEqual(r.returncode, 0, r.stderr)
            self.assertIn('--age age1fakerecipient', Path(env['FAKE_LOG']).read_text())
            self.assertNotIn(OFFLINE, r.stdout + r.stderr)

    def test_tpm_detection_and_generation_with_offline_device(self):
        with tempfile.TemporaryDirectory() as tmp:
            env = self.fixture(tmp)
            device = Path(tmp) / 'device'
            script = '. ' + shlex.quote(str(SCRIPTS / 'rh-age-lib.sh')) + '; rh_tpm_status ' + shlex.quote(str(device))
            r = self.execute(tmp, env, script)
            self.assertEqual(r.stdout, 'none\n')
            device.write_text('fake device')
            r = self.execute(tmp, env, script)
            self.assertEqual(r.stdout, 'accessible\n')
            # Simulate inaccessible device even when a container runs the test as root.
            denied = 'function [() { if builtin [ "$1" = -w ]; then return 1; fi; builtin [ "$@"; }; '
            r = self.execute(tmp, env, denied + script)
            self.assertEqual(r.stdout, 'present\n')
            # Override only the detector function in a disposable script copy, never /dev.
            copied = Path(tmp) / 'tpm-scripts'
            shutil.copytree(SCRIPTS, copied)
            with (copied / 'rh-age-lib.sh').open('a') as f:
                f.write('\nrh_tpm_status() { echo "${FAKE_TPM:-accessible}"; }\n')
            _shim(_bindir(tmp), 'age-plugin-tpm', 'if [ "$1" = --generate ]; then echo AGE-PLUGIN-TPM-FAKE; else echo age1tpmfake; fi\n')
            command = 'bash ' + shlex.quote(str(copied / 'rh-age-identity.sh'))
            r = self.execute(tmp, env, command)
            self.assertEqual((r.returncode, r.stdout), (0, 'age1tpmfake\n'), r.stderr)
            key = Path(env['XDG_CONFIG_HOME']) / 'sops/age/keys.txt'
            self.assertEqual(key.read_text(), 'AGE-PLUGIN-TPM-FAKE\n')
            key.unlink()
            env['FAKE_TPM'] = 'present'
            r = self.execute(tmp, env, command)
            self.assertEqual(r.stdout, 'age1fakerecipient\n')
            r = self.execute(tmp, env, 'bash ' + shlex.quote(str(copied / 'rh-preflight.sh')) + ' --json')
            self.assertEqual(json.loads(r.stdout)['tpm'], 'present')
            self.assertIn('tss group', json.loads(r.stdout)['tpm_hint'])


class HostSetup(SetupCases, unittest.TestCase):
    pass


class Bash32Setup(SetupCases, unittest.TestCase):
    setUp = sops_tests.Bash32Sops.setUp
    execute = sops_tests.Bash32Sops.execute
