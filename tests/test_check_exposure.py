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

# Every real bundle carries a targets block; a bundle only ships when its Claude
# target is enabled, so fixtures must say so explicitly or they test a state no
# bundle occupies. Mirrors tests/test_check_grouping.py and test_check_consistency.py.
ENABLED = "targets:\n  claude:\n    enabled: true\n    pluginName: {p}\n"
DISABLED = "targets:\n  claude:\n    enabled: false\n    pluginName: {p}\n"


def bundle(stem, body, enabled=True):
    """A bundle YAML body with the targets block real bundles always carry."""
    tmpl = ENABLED if enabled else DISABLED
    return f"id: {stem}\n{body}{tmpl.format(p=stem)}"


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
            # The path anchors a GitHub annotation, so it must name a real file.
            self.assertEqual(orphans[0].path, "skills/orphan-skill/SKILL.md")

    def test_referenced_skill_not_flagged(self):
        with tempfile.TemporaryDirectory() as tmp:
            repo = make_repo(
                tmp,
                skills=["used"],
                bundles={"b": bundle("b", "skills:\n  - used\n")},
            )
            self.assertEqual(check_exposure.find_unexposed(repo), [])

    def test_mapped_member_counts_source_as_referenced(self):
        # A {source, leaf} member exposes the SOURCE dir, not the leaf name.
        with tempfile.TemporaryDirectory() as tmp:
            repo = make_repo(
                tmp,
                skills=["go-gh"],
                bundles={"gh": bundle("gh", "skills:\n  - {source: go-gh, leaf: actions-go}\n")},
            )
            self.assertEqual(check_exposure.find_unexposed(repo), [])

    def test_scans_yml_extension_bundles(self):
        with tempfile.TemporaryDirectory() as tmp:
            repo = make_repo(tmp, skills=["used"])
            (repo / "registry" / "bundles" / "legacy.yml").write_text(
                bundle("legacy", "skills:\n  - used\n")
            )
            self.assertEqual(check_exposure.find_unexposed(repo), [])

    def test_disabled_bundle_does_not_expose_its_skill(self):
        # A disabled bundle syncs no plugin tree and generates no manifest, so
        # a skill only it references ships nowhere and is still an orphan.
        with tempfile.TemporaryDirectory() as tmp:
            repo = make_repo(
                tmp,
                skills=["parked"],
                bundles={"dead": bundle("dead", "skills:\n  - parked\n", enabled=False)},
            )
            orphans = check_exposure.find_unexposed(repo)
            self.assertEqual([(o.kind, o.name) for o in orphans], [("skill", "parked")])

    def test_bundle_without_targets_block_does_not_expose(self):
        with tempfile.TemporaryDirectory() as tmp:
            repo = make_repo(
                tmp,
                skills=["parked"],
                bundles={"b": "id: b\nskills:\n  - parked\n"},
            )
            self.assertEqual([o.name for o in check_exposure.find_unexposed(repo)], ["parked"])


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
                bundles={"b": bundle("b", "agents:\n  - used-agent\n")},
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
                bundles={"b": bundle("b", "hooks:\n  - used-hook\n")},
            )
            self.assertEqual(check_exposure.find_unexposed(repo), [])


class TestMcpAndPromptIdentity(unittest.TestCase):
    def test_mcp_dir_go_suffix_matches_bare_server_name_ref(self):
        # Canonical servers live at mcp/<name>-go/, but a bundle's `mcp:` key
        # holds the .mcp.json server name (`mcp: [lucid]`) — the -go suffix is
        # a directory convention and must not make the server read as an orphan.
        with tempfile.TemporaryDirectory() as tmp:
            repo = make_repo(tmp, bundles={"b": bundle("b", "mcp:\n  - lucid\n")})
            (repo / "mcp" / "lucid-go").mkdir(parents=True)
            self.assertEqual(check_exposure.find_unexposed(repo), [])

    def test_unreferenced_mcp_server_is_flagged_by_bare_name(self):
        with tempfile.TemporaryDirectory() as tmp:
            repo = make_repo(tmp)
            (repo / "mcp" / "lucid-go").mkdir(parents=True)
            orphans = check_exposure.find_unexposed(repo)
            self.assertEqual([(o.kind, o.name) for o in orphans], [("mcp", "lucid")])

    def test_mcp_orphan_hint_names_the_singular_mcp_key(self):
        # The bundle key is `mcp:`, not `mcps:` — the message must not send a
        # contributor to a field that does not exist.
        with tempfile.TemporaryDirectory() as tmp:
            repo = make_repo(tmp)
            (repo / "mcp" / "lucid-go").mkdir(parents=True)
            err = io.StringIO()
            with redirect_stderr(err):
                rc = check_exposure.main([str(repo)])
            self.assertEqual(rc, 1)
            self.assertIn("`mcp:` list", err.getvalue())
            self.assertNotIn("mcps", err.getvalue())

    def test_prompt_identity_strips_the_md_extension(self):
        with tempfile.TemporaryDirectory() as tmp:
            repo = make_repo(tmp, bundles={"b": bundle("b", "prompts:\n  - greet\n")})
            (repo / "prompts").mkdir()
            (repo / "prompts" / "greet.md").write_text("hi\n")
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
                bundles={"b": bundle("b", "hooks:\n  - now-used\n")},
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

    def test_entry_without_reason_does_not_suppress_its_orphan(self):
        # An incomplete exemption must not silence the very thing it exempts:
        # the orphan stays reported, so CI names what is being hidden and not
        # just the malformed entry hiding it.
        with tempfile.TemporaryDirectory() as tmp:
            repo = make_repo(
                tmp,
                hooks=["dev-hook"],
                unbundled=(
                    "schemaVersion: v1\nunbundled:\n"
                    "  - kind: hook\n    name: dev-hook\n"
                ),
            )
            orphans = check_exposure.find_unexposed(repo)
            self.assertEqual([o.name for o in orphans], ["dev-hook"])
            err = io.StringIO()
            with redirect_stderr(err):
                check_exposure.main([str(repo)])
            self.assertIn("dev-hook", err.getvalue())

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
                tmp, skills=["ok"], bundles={"b": bundle("b", "skills:\n  - ok\n")}
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

    def test_warn_flag_exits_0_on_malformed_registry_yaml(self):
        # --warn is a pre-commit reminder; a half-written bundle YAML must not
        # block the commit with a traceback.
        with tempfile.TemporaryDirectory() as tmp:
            repo = make_repo(tmp, skills=["ok"])
            (repo / "registry" / "bundles" / "broken.yaml").write_text(
                "id: b\nskills: [\n  unclosed\n"
            )
            err = io.StringIO()
            with redirect_stderr(err):
                rc = check_exposure.main([str(repo), "--warn"])
            self.assertEqual(rc, 0)
            self.assertIn("hint:", err.getvalue())

    def test_strict_mode_fails_on_malformed_registry_yaml(self):
        with tempfile.TemporaryDirectory() as tmp:
            repo = make_repo(tmp, skills=["ok"])
            (repo / "registry" / "bundles" / "broken.yaml").write_text(
                "id: b\nskills: [\n  unclosed\n"
            )
            err = io.StringIO()
            with redirect_stderr(err):
                rc = check_exposure.main([str(repo)])
            self.assertEqual(rc, 1)
            self.assertIn("::error", err.getvalue())
            self.assertIn("cannot read", err.getvalue())


class TestStructurallyInvalidRegistry(unittest.TestCase):
    """Well-formed YAML whose *values* are the wrong shape.

    Distinct from the syntax-error cases above, and the distinction is the whole
    point: ``_load_yaml`` vouches only for the top-level mapping, so a scalar
    where a mapping or list belongs parses cleanly and only blows up at the
    dereference — past ``main``'s ``except RegistryError``. Testing only syntax
    errors is what let that gap ship.
    """

    # (label, filename, content) — each puts a scalar where a shape is required.
    CASES = (
        ("targets", "registry/bundles/b.yaml", "id: b\nskills: [ok]\ntargets: invalid\n"),
        (
            "targets.claude",
            "registry/bundles/b.yaml",
            "id: b\nskills: [ok]\ntargets:\n  claude: nope\n",
        ),
        ("skills", "registry/bundles/b.yaml", bundle("b", "skills: 7\n")),
        ("agents", "registry/bundles/b.yaml", bundle("b", "agents: 5\n")),
        ("mcp", "registry/bundles/b.yaml", bundle("b", "mcp: 3\n")),
        ("unbundled", "registry/unbundled.yaml", "unbundled: 1\n"),
    )

    def _repo(self, tmp, rel, content):
        repo = make_repo(tmp, skills=["ok"], bundles={})
        target = repo / rel
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(content)
        return repo

    def test_warn_mode_never_blocks_on_a_bad_shape(self):
        for label, rel, content in self.CASES:
            with self.subTest(key=label), tempfile.TemporaryDirectory() as tmp:
                repo = self._repo(tmp, rel, content)
                err = io.StringIO()
                with redirect_stderr(err):
                    rc = check_exposure.main([str(repo), "--warn"])
                self.assertEqual(rc, 0, f"{label}: --warn must not block a commit")
                self.assertIn("hint:", err.getvalue())
                self.assertNotIn("Traceback", err.getvalue())

    def test_strict_mode_fails_cleanly_on_a_bad_shape(self):
        for label, rel, content in self.CASES:
            with self.subTest(key=label), tempfile.TemporaryDirectory() as tmp:
                repo = self._repo(tmp, rel, content)
                err = io.StringIO()
                with redirect_stderr(err):
                    rc = check_exposure.main([str(repo)])
                self.assertEqual(rc, 1, f"{label}: strict mode must fail closed")
                self.assertIn("::error", err.getvalue())
                self.assertIn(label, err.getvalue())

    def test_string_skills_list_is_rejected_not_iterated_per_character(self):
        # `skills: ok` is iterable, so an unguarded loop reads it as the members
        # 'o' and 'k' and reports the real skill as an orphan — a wrong answer
        # rather than a loud failure.
        with tempfile.TemporaryDirectory() as tmp:
            repo = self._repo(tmp, "registry/bundles/b.yaml", bundle("b", "skills: ok\n"))
            err = io.StringIO()
            with redirect_stderr(err):
                rc = check_exposure.main([str(repo)])
            self.assertEqual(rc, 1)
            self.assertIn("must be a list, got str", err.getvalue())


class TestBrokenInvocation(unittest.TestCase):
    """A gate that reads nothing must never report success."""

    def test_non_repo_root_fails_instead_of_passing_vacuously(self):
        with tempfile.TemporaryDirectory() as tmp:
            err = io.StringIO()
            with redirect_stderr(err):
                rc = check_exposure.main([tmp])
            self.assertEqual(rc, 1)
            self.assertIn("not the repo root", err.getvalue())

    def test_missing_skills_tree_fails(self):
        with tempfile.TemporaryDirectory() as tmp:
            repo = Path(tmp)
            (repo / "registry" / "bundles").mkdir(parents=True)
            err = io.StringIO()
            with redirect_stderr(err):
                rc = check_exposure.main([str(repo)])
            self.assertEqual(rc, 1)
            self.assertIn("not the repo root", err.getvalue())

    def test_warn_mode_does_not_block_on_broken_invocation(self):
        with tempfile.TemporaryDirectory() as tmp:
            err = io.StringIO()
            with redirect_stderr(err):
                rc = check_exposure.main([tmp, "--warn"])
            self.assertEqual(rc, 0)
            self.assertIn("hint:", err.getvalue())
            self.assertNotIn("::error", err.getvalue())


if __name__ == "__main__":
    unittest.main()
