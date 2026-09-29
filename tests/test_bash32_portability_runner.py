"""The dedicated portability gate must prove that selected tests actually ran."""
import importlib.util
import io
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import bash32_fixture


class PortabilityGate(unittest.TestCase):
    def runner(self):
        path = Path(__file__).resolve().parents[1] / 'scripts/run_bash32_portability.py'
        spec = importlib.util.spec_from_file_location('portability_runner', path)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        return module

    def test_zero_selected_cases_fail(self):
        self.assertFalse(self.runner().run_suite(unittest.TestSuite(), stream=io.StringIO()))

    def test_incomplete_selection_fails(self):
        suite = unittest.TestSuite([unittest.FunctionTestCase(lambda: None)])
        self.assertFalse(self.runner().run_suite(suite, stream=io.StringIO(), expected_count=3))

    def test_cli_fails_when_required_runtime_is_unavailable(self):
        env = dict(os.environ, BASH32_CONTAINER_RUNTIME="unavailable")
        path = Path(__file__).resolve().parents[1] / 'scripts/run_bash32_portability.py'
        result = subprocess.run([sys.executable, str(path)], env=env, capture_output=True,
                                text=True, timeout=60)
        self.assertEqual(result.returncode, 1, result.stderr)
        self.assertIn('skipped 3', result.stderr)

    def test_skipped_subtest_fails(self):
        class MissingFixture(unittest.TestCase):
            def test_required(self):
                with self.subTest(fixture='unavailable'):
                    self.skipTest('fixture unavailable')
        self.assertFalse(self.runner().run_suite(unittest.defaultTestLoader.loadTestsFromTestCase(MissingFixture), stream=io.StringIO()))

    def test_expected_failure_does_not_count_as_coverage(self):
        class Broken(unittest.TestCase):
            @unittest.expectedFailure
            def test_required(self):
                self.fail('regression')
        self.assertFalse(self.runner().run_suite(unittest.defaultTestLoader.loadTestsFromTestCase(Broken), stream=io.StringIO()))

    def test_skipped_case_fails_even_when_unittest_succeeds(self):
        class MissingFixture(unittest.TestCase):
            @unittest.skip('fixture unavailable')
            def test_required(self):
                pass
        output = io.StringIO()
        self.assertFalse(self.runner().run_suite(unittest.defaultTestLoader.loadTestsFromTestCase(MissingFixture), stream=output))
        self.assertIn('skipped', output.getvalue())

    def test_failure_fails(self):
        class Broken(unittest.TestCase):
            def test_required(self):
                self.fail('regression')
        self.assertFalse(self.runner().run_suite(unittest.defaultTestLoader.loadTestsFromTestCase(Broken), stream=io.StringIO()))

    def test_success_reports_executed_count(self):
        class Covered(unittest.TestCase):
            def test_required(self):
                pass
        output = io.StringIO()
        self.assertTrue(self.runner().run_suite(unittest.defaultTestLoader.loadTestsFromTestCase(Covered), stream=output))
        self.assertIn('Executed 1 portability cases; skipped 0', output.getvalue())


class FixtureIntegrity(unittest.TestCase):
    def test_unverified_jq_is_not_accepted(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / 'jq'
            path.write_bytes(b'wrong binary')
            with patch.dict(os.environ, BASH32_STATIC_JQ=str(path)):
                self.assertIsNone(bash32_fixture.static_jq())

    def test_corrupt_download_fails_before_install_or_pull(self):
        with tempfile.TemporaryDirectory() as tmp:
            with patch.object(bash32_fixture.urllib.request, 'urlopen') as download:
                download.return_value.__enter__.return_value.read.return_value = b'corrupt'
                with patch.object(bash32_fixture.subprocess, 'run') as runtime:
                    with self.assertRaisesRegex(RuntimeError, 'checksum mismatch'):
                        bash32_fixture.prepare('docker', Path(tmp))
                    runtime.assert_not_called()
                    self.assertFalse((Path(tmp) / 'jq').exists())
