"""Tests for scripts/check_exposure.py — the reverse bundle-reference check.

check_bundle_refs.py verifies every bundle reference resolves to something on
disk; this is the other direction: every canonical skill/agent/hook must be
referenced by at least one bundle, or explicitly allowlisted in
registry/unbundled.yaml. Closes the "authored but unshipped" gap.
"""

import io
import sys
import tempfile
import unittest
from contextlib import redirect_stderr
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))

import check_exposure  # noqa: E402


def make_repo(tmp, bundles=None, skills=(), agents=(), hooks=(), unbundled=None):
    """Build a throwaway repo skeleton with the given bundles/skills/agents/hooks."""
    repo = Path(tmp)
    (repo / "registry" / "bundles").mkdir(parents=True)
    (repo / "skills").mkdir()
    (repo / "agents").mkdir()
    (repo / "hooks").mkdir()
    for name in skills:
        (repo / "skills" / name).mkdir()
        (repo / "skills" / name / "SKILL.md").write_text(f"---\nname: {name}\n---\n")
    for name in agents:
        (repo / "agents" / name).mkdir()
        (repo / "agents" / name / "agent.md").write_text(
            f"---\nname: {name}\ndescription: x\n---\n"
        )
    for name in hooks:
        (repo / "hooks" / f"{name}.sh").write_text("#!/usr/bin/env bash\n")
    for stem, body in (bundles or {}).items():
        (repo / "registry" / "bundles" / f"{stem}.yaml").write_text(body)
    if unbundled is not None:
        (repo / "registry" / "unbundled.yaml").write_text(unbundled)
    return repo


class TestUnreferencedSkills(unittest.TestCase):
    def test_flags_orphan_skill(self):
        with tempfile.TemporaryDirectory() as tmp:
            repo = make_repo(tmp, skills=["orphan-skill"])
            orphans = check_exposure.find_unexposed(repo)
            self.assertEqual(len(orphans), 1)
            self.assertEqual(orphans[0].kind, "skill")
            self.assertEqual(orphans[0].name, "orphan-skill")
            self.assertEqual(orphans[0].path, "skills/orphan-skill/")

    def test_referenced_skill_not_flagged(self):
        with tempfile.TemporaryDirectory() as tmp:
            repo = make_repo(
                tmp,
                skills=["used"],
                bundles={"b": "id: b\nskills:\n  - used\n"},
            )
            self.assertEqual(check_exposure.find_unexposed(repo), [])

    def test_mapped_member_counts_source_as_referenced(self):
        # A {source, leaf} member exposes the SOURCE dir, not the leaf name.
        with tempfile.TemporaryDirectory() as tmp:
            repo = make_repo(
                tmp,
                skills=["go-gh"],
                bundles={"gh": "id: gh\nskills:\n  - {source: go-gh, leaf: actions-go}\n"},
            )
            self.assertEqual(check_exposure.find_unexposed(repo), [])

    def test_scans_yml_extension_bundles(self):
        with tempfile.TemporaryDirectory() as tmp:
            repo = make_repo(tmp, skills=["used"])
            (repo / "registry" / "bundles" / "legacy.yml").write_text(
                "id: legacy\nskills:\n  - used\n"
            )
            self.assertEqual(check_exposure.find_unexposed(repo), [])


class TestDisabledBundles(unittest.TestCase):
    def test_ref_from_disabled_bundle_does_not_expose(self):
        # A bundle with targets.claude.enabled: false ships nothing, so a skill
        # referenced only by it is still an orphan.
        with tempfile.TemporaryDirectory() as tmp:
            repo = make_repo(
                tmp,
                skills=["shipped-nowhere"],
                bundles={
                    "off": (
                        "id: off\nskills:\n  - shipped-nowhere\n"
                        "targets:\n  claude:\n    enabled: false\n"
                    )
                },
            )
            orphans = check_exposure.find_unexposed(repo)
            self.assertEqual([o.name for o in orphans], ["shipped-nowhere"])

    def test_ref_from_enabled_bundle_exposes(self):
        with tempfile.TemporaryDirectory() as tmp:
            repo = make_repo(
                tmp,
                skills=["shipped"],
                bundles={
                    "on": (
                        "id: on\nskills:\n  - shipped\n"
                        "targets:\n  claude:\n    enabled: true\n"
                    )
                },
            )
            self.assertEqual(check_exposure.find_unexposed(repo), [])


class TestUnreferencedAgents(unittest.TestCase):
    def test_flags_orphan_agent(self):
        with tempfile.TemporaryDirectory() as tmp:
            repo = make_repo(tmp, agents=["orphan-agent"])
            orphans = check_exposure.find_unexposed(repo)
            self.assertEqual([o.name for o in orphans], ["orphan-agent"])
            self.assertEqual(orphans[0].kind, "agent")

    def test_referenced_agent_not_flagged(self):
        with tempfile.TemporaryDirectory() as tmp:
            repo = make_repo(
                tmp,
                agents=["used-agent"],
                bundles={"b": "id: b\nagents:\n  - used-agent\n"},
            )
            self.assertEqual(check_exposure.find_unexposed(repo), [])


class TestUnreferencedHooks(unittest.TestCase):
    def test_flags_orphan_hook(self):
        with tempfile.TemporaryDirectory() as tmp:
            repo = make_repo(tmp, hooks=["orphan-hook"])
            orphans = check_exposure.find_unexposed(repo)
            self.assertEqual([o.name for o in orphans], ["orphan-hook"])
            self.assertEqual(orphans[0].kind, "hook")

    def test_referenced_hook_not_flagged(self):
        with tempfile.TemporaryDirectory() as tmp:
            repo = make_repo(
                tmp,
                hooks=["used-hook"],
                bundles={"b": "id: b\nhooks:\n  - used-hook\n"},
            )
            self.assertEqual(check_exposure.find_unexposed(repo), [])


class TestAllowlist(unittest.TestCase):
    def test_allowlist_suppresses_orphan(self):
        with tempfile.TemporaryDirectory() as tmp:
            repo = make_repo(
                tmp,
                hooks=["dev-hook"],
                unbundled=(
                    "schemaVersion: v1\nunbundled:\n"
                    "  - kind: hook\n    name: dev-hook\n    reason: repo-internal\n"
                ),
            )
            self.assertEqual(check_exposure.find_unexposed(repo), [])

    def test_stale_allowlist_entry_for_missing_item(self):
        with tempfile.TemporaryDirectory() as tmp:
            repo = make_repo(
                tmp,
                unbundled=(
                    "schemaVersion: v1\nunbundled:\n"
                    "  - kind: hook\n    name: gone\n    reason: repo-internal\n"
                ),
            )
            messages = check_exposure.find_stale_allowlist_entries(repo)
            self.assertEqual(len(messages), 1)
            self.assertIn("gone", messages[0])
            self.assertIn("no longer exists", messages[0])

    def test_stale_allowlist_entry_for_now_referenced_item(self):
        with tempfile.TemporaryDirectory() as tmp:
            repo = make_repo(
                tmp,
                hooks=["now-used"],
                bundles={"b": "id: b\nhooks:\n  - now-used\n"},
                unbundled=(
                    "schemaVersion: v1\nunbundled:\n"
                    "  - kind: hook\n    name: now-used\n    reason: repo-internal\n"
                ),
            )
            messages = check_exposure.find_stale_allowlist_entries(repo)
            self.assertEqual(len(messages), 1)
            self.assertIn("now-used", messages[0])
            self.assertIn("references it", messages[0])

    def test_missing_allowlist_file_is_empty(self):
        with tempfile.TemporaryDirectory() as tmp:
            repo = make_repo(tmp)
            allowed, entries = check_exposure.load_allowlist(repo)
            self.assertEqual(allowed, set())
            self.assertEqual(entries, [])

    def test_allowlist_entry_without_reason_is_flagged(self):
        # A bare {kind, name} exemption must not silently silence the check.
        with tempfile.TemporaryDirectory() as tmp:
            repo = make_repo(
                tmp,
                hooks=["dev-hook"],
                unbundled=(
                    "schemaVersion: v1\nunbundled:\n"
                    "  - kind: hook\n    name: dev-hook\n"
                ),
            )
            problems = check_exposure.find_allowlist_problems(repo)
            self.assertEqual(len(problems), 1)
            self.assertIn("reason", problems[0])
            # And the strict CLI must fail rather than exit 0.
            err = io.StringIO()
            with redirect_stderr(err):
                rc = check_exposure.main([str(repo)])
            self.assertEqual(rc, 1)

    def test_allowlist_entry_with_blank_reason_is_flagged(self):
        with tempfile.TemporaryDirectory() as tmp:
            repo = make_repo(
                tmp,
                hooks=["dev-hook"],
                unbundled=(
                    "schemaVersion: v1\nunbundled:\n"
                    '  - kind: hook\n    name: dev-hook\n    reason: "  "\n'
                ),
            )
            problems = check_exposure.find_allowlist_problems(repo)
            self.assertEqual(len(problems), 1)
            self.assertIn("reason", problems[0])

    def test_wellformed_allowlist_entry_has_no_problems(self):
        with tempfile.TemporaryDirectory() as tmp:
            repo = make_repo(
                tmp,
                hooks=["dev-hook"],
                unbundled=(
                    "schemaVersion: v1\nunbundled:\n"
                    "  - kind: hook\n    name: dev-hook\n    reason: repo-internal dev tool\n"
                ),
            )
            self.assertEqual(check_exposure.find_allowlist_problems(repo), [])


class TestCli(unittest.TestCase):
    def test_main_exits_1_and_reports_name_on_orphan(self):
        with tempfile.TemporaryDirectory() as tmp:
            repo = make_repo(tmp, skills=["orphan-skill"])
            err = io.StringIO()
            with redirect_stderr(err):
                rc = check_exposure.main([str(repo)])
            self.assertEqual(rc, 1)
            self.assertIn("orphan-skill", err.getvalue())

    def test_main_exits_0_when_clean(self):
        with tempfile.TemporaryDirectory() as tmp:
            repo = make_repo(
                tmp, skills=["ok"], bundles={"b": "id: b\nskills:\n  - ok\n"}
            )
            self.assertEqual(check_exposure.main([str(repo)]), 0)

    def test_warn_flag_always_exits_0_with_orphans(self):
        with tempfile.TemporaryDirectory() as tmp:
            repo = make_repo(tmp, skills=["orphan-skill"])
            err = io.StringIO()
            with redirect_stderr(err):
                rc = check_exposure.main([str(repo), "--warn"])
            self.assertEqual(rc, 0)
            self.assertIn("orphan-skill", err.getvalue())
            self.assertIn("hint:", err.getvalue())

    def test_mcp_orphan_message_uses_correct_bundle_key(self):
        # The bundle key for mcp is `mcp:`, not the naive plural `mcps:`.
        with tempfile.TemporaryDirectory() as tmp:
            repo = make_repo(tmp)
            (Path(repo) / "mcp" / "some-server").mkdir(parents=True)
            err = io.StringIO()
            with redirect_stderr(err):
                rc = check_exposure.main([str(repo)])
            self.assertEqual(rc, 1)
            out = err.getvalue()
            self.assertIn("`mcp:`", out)
            self.assertNotIn("mcps", out)


if __name__ == "__main__":
    unittest.main()
