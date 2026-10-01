"""Run required Bash 3.2 cases, failing on skips and empty/incomplete selection."""
import argparse
import os
import sys
import unittest
from pathlib import Path

CASES = (
    "test_installed_hooks.Bash32BusyBoxFallback.test_prompt_fallbacks_gate_without_jq_or_python",
    "test_installed_hooks.Bash32BusyBoxFallback.test_escaped_input",
    "test_cc_agent_teams_check_config.Bash32BusyBox.test_enable_disable_check_under_bash32",
    "test_redhat_setup.Bash32Bitwarden.test_bitwarden_text_field",
    "test_redhat_setup.Bash32Bitwarden.test_bitwarden_hidden_field",
    "test_redhat_setup.Bash32Bitwarden.test_bitwarden_notes_win_over_field",
    "test_redhat_setup.Bash32Bitwarden.test_bitwarden_empty_field_exits_3",
    "test_redhat_setup.Bash32Bitwarden.test_bitwarden_missing_or_wrong_field_exits_3",
    "test_redhat_sops.Bash32Sops.test_source_found_empty_failure_missing",
    "test_redhat_sops.Bash32Sops.test_started_before_file_exists_store_without_bw_and_check",
    "test_redhat_sops.Bash32Sops.test_store_empty_failure_and_symlink_replacement",
    "test_redhat_sops.Bash32Sops.test_bitwarden_seed_notes_and_custom_field",
    "test_redhat_sops.Bash32Sops.test_path_override_order_filter_and_preflight_tools",
    "test_redhat_sops.Bash32Sops.test_guard_direct_decrypt_denied_only_for_token_file",
)


def run_suite(suite, *, stream=sys.stderr, expected_count=None):
    selected = suite.countTestCases()
    if selected == 0 or (expected_count is not None and selected != expected_count):
        print(f"Invalid portability selection: {selected} cases", file=stream)
        return False
    result = unittest.TextTestRunner(stream=stream, verbosity=2).run(suite)
    print(f"Executed {result.testsRun} portability cases; skipped {len(result.skipped)}", file=stream)
    return (result.wasSuccessful() and not result.skipped and
            result.testsRun == selected and not result.expectedFailures)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--prepare", metavar="DIRECTORY", help="download verified jq and pull the pinned image")
    parser.add_argument("--runtime", choices=("docker", "podman"))
    args = parser.parse_args()
    if args.runtime:
        os.environ["BASH32_CONTAINER_RUNTIME"] = args.runtime
    sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tests"))
    if args.prepare:
        from bash32_fixture import prepare
        prepare(args.runtime or "docker", Path(args.prepare))
        return 0
    suite = unittest.defaultTestLoader.loadTestsFromNames(CASES)
    return 0 if run_suite(suite, expected_count=len(CASES)) else 1


if __name__ == "__main__":
    sys.exit(main())
