"""No-network config/wrapper regressions for #299; real lychee tests are optional.

Run through pixi. A present lychee >=0.24.0 also exercises its actual URL filter
and cache with a loopback HTTP fixture. No external HTTP or credentials are used.
"""

import functools
import http.server
import os
from pathlib import Path
import re
import shutil
import subprocess
import tempfile
import threading
import tomllib
import unittest

import yaml

REPO = Path(__file__).resolve().parents[1]
SKILL = REPO / "skills/lychee"
FIXTURES = REPO / "tests/fixtures/lychee"
LYCHEE = shutil.which("lychee")


def config(path):
    return tomllib.loads(path.read_text())


class WrapperTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix="lychee test ")
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.skill = self.root / "installed skill"
        shutil.copytree(SKILL, self.skill)
        self.bin = self.root / "bin"
        self.bin.mkdir()
        stub = self.bin / "lychee"
        stub.write_text('#!/bin/bash\nprintf "%s\\0" "$@"\nexit "${STUB_EXIT:-0}"\n')
        stub.chmod(0o755)
        self.env = {"PATH": f"{self.bin}:/usr/bin:/bin"}

    def run_wrapper(self, args, code=0):
        result = subprocess.run(
            ["bash", str(self.skill / "scripts/check-links.sh"), *args],
            cwd=self.root, env={**self.env, "STUB_EXIT": str(code)},
            capture_output=True, timeout=10,
        )
        self.assertEqual(result.returncode, code, result.stderr)
        return result.stdout.decode().rstrip("\0").split("\0")

    def test_injects_installed_defaults_and_preserves_arguments(self):
        args = ["--format", "json", "docs with spaces/**/*.md", "--exclude", "a b|c", ""]
        # Keep the trailing empty argument in the assertion below.
        result = subprocess.run(
            ["bash", str(self.skill / "scripts/check-links.sh"), *args],
            cwd=self.root, env=self.env, capture_output=True, timeout=10,
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(result.stdout.decode().split("\0")[:-1],
                         ["--config", str(self.skill / "lychee.toml"), "--no-progress", *args])

    def test_explicit_config_spellings_replace_defaults(self):
        path = str(self.root / "project config.toml")
        Path(path).write_text("cache = false\n")
        for flags in (["--config", path], [f"--config={path}"], ["-c", path], [f"-c{path}"]):
            with self.subTest(flags=flags):
                args = [*flags, "--cache=false", "README.md"]
                self.assertEqual(self.run_wrapper(args), ["--no-progress", *args])

    def test_config_text_in_filename_is_not_an_option(self):
        args = ["docs --config notes.md"]
        self.assertEqual(self.run_wrapper(args),
                         ["--config", str(self.skill / "lychee.toml"), "--no-progress", *args])

    def test_option_terminator_preserves_positional_config_text(self):
        args = ["--", "--config", "-cnotes.md"]
        self.assertEqual(self.run_wrapper(args),
                         ["--config", str(self.skill / "lychee.toml"), "--no-progress", *args])

    def test_generated_plugins_run_from_isolated_copies(self):
        for target in ("plugins/lychee", "dist/codex/plugins/lychee"):
            with self.subTest(target=target):
                destination = self.root / target.replace("/", " ")
                shutil.copytree(REPO / target, destination)
                self.skill = destination / "skills/check"
                self.assertEqual(self.run_wrapper(["consumer README.md"]),
                                 ["--config", str(self.skill / "lychee.toml"),
                                  "--no-progress", "consumer README.md"])
                self.assertEqual(config(self.skill / "lychee.toml"), config(SKILL / "lychee.toml"))

    def test_missing_bundled_config_and_child_failure(self):
        (self.skill / "lychee.toml").unlink()
        self.assertEqual(self.run_wrapper(["README.md"], code=2), ["--no-progress", "README.md"])

    def test_ci_and_local_hook_select_repository_config(self):
        workflow = yaml.safe_load((REPO / ".github/workflows/link-check.yml").read_text())
        command = next(step["run"] for step in workflow["jobs"]["check-links"]["steps"]
                       if step.get("name") == "Check skill links")
        hook = yaml.safe_load((REPO / "lefthook.yml").read_text())
        hook_command = next(job["run"] for job in hook["pre-commit"]["jobs"]
                            if job["name"] == "lychee-links")
        # Execute the real configured commands with a recording wrapper stub.
        script = self.root / "skills/lychee/scripts/check-links.sh"
        script.parent.mkdir(parents=True)
        shutil.copy2(self.bin / "lychee", script)
        for cmd in (command, hook_command.replace("{staged_files}", "README.md")):
            with self.subTest(command=cmd):
                result = subprocess.run(["bash", "-c", cmd], cwd=self.root,
                                        env=self.env, capture_output=True, timeout=10)
                self.assertEqual(result.returncode, 0, result.stderr)
                args = result.stdout.decode().split("\0")[:-1]
                self.assertEqual(args[:3], ["--config", "lychee.toml", "--cache=false"])


class ConfigTests(unittest.TestCase):
    def test_repository_policy_is_unchanged_except_cache(self):
        old = config(FIXTURES / "legacy.toml")
        current = config(REPO / "lychee.toml")
        self.assertFalse(current["cache"])
        old["cache"] = False
        self.assertEqual(current, old)

    def test_exclusion_fixtures(self):
        cases = config(FIXTURES / "urls.toml")["cases"]
        for name, path in (("shipped", SKILL / "lychee.toml"), ("repository", REPO / "lychee.toml")):
            patterns = config(path)["exclude"]
            for case in cases:
                with self.subTest(policy=name, url=case["url"]):
                    excluded = any(re.search(pattern, case["url"]) for pattern in patterns)
                    self.assertEqual(excluded, case[name])

    def test_consumer_cache_is_bounded_and_private_addresses_excluded(self):
        shipped = config(SKILL / "lychee.toml")
        self.assertTrue(shipped["cache"])
        self.assertEqual(shipped["max_cache_age"], "1h")
        self.assertTrue(shipped["exclude_all_private"])
        self.assertNotIn("hosts", shipped)


@unittest.skipUnless(LYCHEE, "real lychee is optional; stub/config tests always run")
class LycheeRuntimeTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix="lychee runtime ")
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)

    def run_lychee(self, *args):
        return subprocess.run([LYCHEE, "--no-progress", *args], cwd=self.root,
                              env={"PATH": os.environ["PATH"]},
                              capture_output=True, text=True, timeout=20)

    def test_actual_filter_matches_url_fixtures_without_requests(self):
        cases = config(FIXTURES / "urls.toml")["cases"]
        source = self.root / "links.md"
        source.write_text("\n".join(f'<{case["url"]}>' for case in cases))
        for name, path in (("shipped", SKILL / "lychee.toml"), ("repository", REPO / "lychee.toml")):
            result = self.run_lychee("--config", str(path), "--cache=false", "--dump", str(source))
            self.assertEqual(result.returncode, 0, result.stderr)
            urls = set(result.stdout.splitlines())
            for case in cases:
                with self.subTest(policy=name, url=case["url"]):
                    # Reserved hosts are independently excluded in lychee-lib's
                    # filter/mod.rs, even with --exclude-all-private=false.
                    excluded = case[name] or case.get("builtin", False)
                    self.assertEqual(case["url"] in urls, not excluded)
            if name == "repository":
                legacy = self.run_lychee("--config", str(FIXTURES / "legacy.toml"),
                                         "--cache=false", "--dump", str(source))
                self.assertEqual(legacy.returncode, 0, legacy.stderr)
                self.assertEqual(set(legacy.stdout.splitlines()), urls)
        self.assertFalse((self.root / ".lycheecache").exists())

    def test_private_addresses_and_mail_are_excluded(self):
        source = self.root / "private.md"
        source.write_text("\n".join(f"<{url}>" for url in (
            "http://127.0.0.1/", "http://10.0.0.1/", "http://172.16.0.1/",
            "http://192.168.1.1/", "http://169.254.1.1/", "http://[::1]/",
            "mailto:person@example.com", "https://docs.example.net/")))
        result = self.run_lychee("--config", str(SKILL / "lychee.toml"),
                                 "--include-mail", "--cache=false", "--dump", str(source))
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(result.stdout.strip(), "")

    def test_cache_false_rechecks_previously_successful_url(self):
        class Handler(http.server.SimpleHTTPRequestHandler):
            def log_message(self, *args):
                pass

        page = self.root / "page.html"
        page.write_text("Healthy")
        server = http.server.ThreadingHTTPServer(
            ("127.0.0.1", 0), functools.partial(Handler, directory=str(self.root)))
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        self.addCleanup(server.server_close)
        self.addCleanup(thread.join)
        self.addCleanup(server.shutdown)
        source = self.root / "links.md"
        source.write_text(f"<http://127.0.0.1:{server.server_port}/page.html>")
        args = ["--config", str(SKILL / "lychee.toml"), "--exclude-all-private=false",
                "--include-fragments=none", "--max-retries", "0", str(source)]
        fresh = self.run_lychee(*args)
        self.assertEqual(fresh.returncode, 0, fresh.stderr)
        self.assertTrue((self.root / ".lycheecache").exists())
        page.unlink()
        cached = self.run_lychee(*args)
        self.assertEqual(cached.returncode, 0, cached.stderr)
        verified = self.run_lychee("--cache=false", *args)
        self.assertEqual(verified.returncode, 2, verified.stderr)
        self.assertIn("404", verified.stdout + verified.stderr)


if __name__ == "__main__":
    unittest.main()
