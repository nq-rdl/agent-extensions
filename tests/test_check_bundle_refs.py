"""Tests for scripts/check_bundle_refs.py — the bundle reference resolver.

This is the logic CI's `validate-bundles` job relies on: every skill named in a
registry bundle must resolve to skills/<name>/, and every agent to
agents/<name>/agent.md. Extracted from inline workflow YAML so it is testable.
"""

import io
import sys
import tempfile
import unittest
from contextlib import redirect_stderr
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))

import check_bundle_refs  # noqa: E402


def make_repo(tmp, bundles=None, skills=(), agents=()):
    """Build a throwaway repo skeleton with the given bundles/skills/agents."""
    repo = Path(tmp)
    (repo / "registry" / "bundles").mkdir(parents=True)
    (repo / "skills").mkdir()
    (repo / "agents").mkdir()
    for name in skills:
        (repo / "skills" / name).mkdir()
        (repo / "skills" / name / "SKILL.md").write_text(f"---\nname: {name}\n---\n")
    for name in agents:
        (repo / "agents" / name).mkdir()
        (repo / "agents" / name / "agent.md").write_text(
            f"---\nname: {name}\ndescription: x\n---\n"
        )
    for stem, body in (bundles or {}).items():
        (repo / "registry" / "bundles" / f"{stem}.yaml").write_text(body)
    return repo


class TestUnresolvedRefs(unittest.TestCase):
    def test_flags_skill_with_no_source_dir(self):
        with tempfile.TemporaryDirectory() as tmp:
            repo = make_repo(tmp, bundles={"dataops": "id: dataops\nskills:\n  - ghost\n"})
            problems = check_bundle_refs.find_unresolved_refs(repo)
            self.assertEqual(len(problems), 1)
            self.assertEqual(problems[0].kind, "skill")
            self.assertEqual(problems[0].name, "ghost")
            self.assertEqual(problems[0].bundle, "dataops")

    def test_flags_agent_with_no_source_file(self):
        with tempfile.TemporaryDirectory() as tmp:
            repo = make_repo(tmp, bundles={"swe": "id: swe\nagents:\n  - ghost-agent\n"})
            problems = check_bundle_refs.find_unresolved_refs(repo)
            self.assertEqual(len(problems), 1)
            self.assertEqual(problems[0].kind, "agent")
            self.assertEqual(problems[0].name, "ghost-agent")

    def test_returns_empty_when_all_refs_resolve(self):
        with tempfile.TemporaryDirectory() as tmp:
            repo = make_repo(
                tmp,
                skills=["real-skill"],
                agents=["real-agent"],
                bundles={"b": "id: b\nskills:\n  - real-skill\nagents:\n  - real-agent\n"},
            )
            self.assertEqual(check_bundle_refs.find_unresolved_refs(repo), [])

    def test_uses_filename_stem_when_no_id_field(self):
        with tempfile.TemporaryDirectory() as tmp:
            repo = make_repo(tmp, bundles={"named-by-file": "skills:\n  - ghost\n"})
            problems = check_bundle_refs.find_unresolved_refs(repo)
            self.assertEqual(problems[0].bundle, "named-by-file")


class TestCli(unittest.TestCase):
    def test_main_exits_1_and_reports_name_on_drift(self):
        with tempfile.TemporaryDirectory() as tmp:
            repo = make_repo(tmp, bundles={"dataops": "id: dataops\nskills:\n  - csv\n"})
            err = io.StringIO()
            with redirect_stderr(err):
                rc = check_bundle_refs.main([str(repo)])
            self.assertEqual(rc, 1)
            self.assertIn("csv", err.getvalue())

    def test_main_exits_0_when_clean(self):
        with tempfile.TemporaryDirectory() as tmp:
            repo = make_repo(
                tmp, skills=["ok"], bundles={"b": "id: b\nskills:\n  - ok\n"}
            )
            self.assertEqual(check_bundle_refs.main([str(repo)]), 0)


if __name__ == "__main__":
    unittest.main()
