"""Supplied-cohort guidance and the Read guard (issue #516).

A researcher-supplied cohort is loaded by the runner at run time and its values never reach Git.
These tests pin:

* the data-request guard denies Read, and the path argument of Grep and Glob, under data/00_raw/ (by
  relative path, `..` detour and symlink), lets *.dvc and .gitignore there and everything else through;
* the guard still ignores tools other than Read, Write and Edit;
* hooks.json wires the guard to Read as well as Write|Edit;
* the guardrails, draft, map, analyse, explain, intake and triage skills carry the guidance, and the
  reference ships with every generated copy.

No model call is made. The values used are synthetic.
"""

import json
import os
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
GUARD = REPO / "hooks" / "data-request-guard.sh"
REFERENCE = "references/supplied-cohorts.rst"
SKILLS = ("guardrails", "draft", "map", "analyse", "explain", "intake", "triage")


def decide(event):
    env = {k: v for k, v in os.environ.items() if not k.startswith("SQLREVIEW_")}
    r = subprocess.run(["bash", str(GUARD)], input=json.dumps(event), text=True, capture_output=True,
                       env=env, timeout=60)
    if not r.stdout.strip():
        return "allow", ""
    out = json.loads(r.stdout)["hookSpecificOutput"]
    return out["permissionDecision"], out["permissionDecisionReason"]


@unittest.skipUnless(shutil.which("jq"), "the guard needs jq")
class ReadGuard(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.root = Path(self._tmp.name).resolve()
        (self.root / "data" / "00_raw").mkdir(parents=True)
        (self.root / "data" / "02_extracts").mkdir()
        (self.root / "conf" / "base" / "supplied").mkdir(parents=True)
        (self.root / "data" / "00_raw" / "sample_cohort.csv").write_text("study_id\nZZTEST-001\n")
        (self.root / "conf" / "base" / "supplied" / "sample_cohort.template.csv").write_text("study_id\n")

    def read(self, path, tool="Read"):
        key = "file_path" if tool in ("Read", "Write", "Edit") else "path"
        return decide({"tool_name": tool, "cwd": str(self.root), "tool_input": {key: str(path)}})

    def assertDenied(self, path):
        decision, reason = self.read(path)
        self.assertEqual(decision, "deny", path)
        self.assertIn("data/00_raw", reason)
        self.assertNotIn("ZZTEST-001", reason)

    def test_denies_the_supplied_file(self):
        self.assertDenied(self.root / "data" / "00_raw" / "sample_cohort.csv")

    def test_denies_a_relative_path(self):
        decision, _ = decide({"tool_name": "Read", "cwd": str(self.root),
                              "tool_input": {"file_path": "data/00_raw/sample_cohort.csv"}})
        self.assertEqual(decision, "deny")

    def test_denies_a_file_that_does_not_exist_yet(self):
        self.assertDenied(self.root / "data" / "00_raw" / "next_instalment.csv")

    def test_denies_the_directory(self):
        self.assertDenied(self.root / "data" / "00_raw")

    def test_denies_a_dotdot_detour(self):
        self.assertDenied(self.root / "data" / "02_extracts" / ".." / "00_raw" / "sample_cohort.csv")

    def test_denies_a_symlink_into_it(self):
        link = self.root / "conf" / "alias.csv"
        link.symlink_to(self.root / "data" / "00_raw" / "sample_cohort.csv")
        self.assertDenied(link)

    def test_denies_a_symlinked_directory(self):
        link = self.root / "alias_dir"
        link.symlink_to(self.root / "data" / "00_raw")
        self.assertDenied(link / "sample_cohort.csv")

    def test_denies_dotdot_after_a_symlinked_directory(self):
        (self.root / "data" / "00_raw" / "sub").mkdir()
        (self.root / "data" / "00_raw" / "a.csv").write_text("x\n")
        link = self.root / "l"
        link.symlink_to(self.root / "data" / "00_raw" / "sub")
        self.assertDenied(link / ".." / "a.csv")

    def test_denies_a_relative_symlink_chain(self):
        (self.root / "conf" / "one").symlink_to("../data/00_raw/sample_cohort.csv")
        (self.root / "two").symlink_to("conf/one")
        self.assertDenied(self.root / "two")

    def test_a_symlink_loop_is_denied_not_allowed(self):
        (self.root / "loop_a").symlink_to("loop_b")
        (self.root / "loop_b").symlink_to("loop_a")
        decision, _ = self.read(self.root / "loop_a")
        self.assertEqual(decision, "deny")

    def test_allows_other_reads(self):
        for path in (self.root / "conf" / "base" / "supplied" / "sample_cohort.template.csv",
                     self.root / "data" / "02_extracts" / "out.csv",
                     self.root / "data" / "00_raw_notes.md",
                     self.root / "README.md"):
            with self.subTest(path.name):
                self.assertEqual(self.read(path), ("allow", ""))

    def test_other_tools_are_untouched(self):
        decision, _ = decide({"tool_name": "Bash", "cwd": str(self.root),
                              "tool_input": {"command": "cat data/00_raw/sample_cohort.csv"}})
        self.assertEqual(decision, "allow")  # Bash is the scaffold child's hook, not this guard

    def test_grep_and_glob_paths_are_denied(self):
        for tool in ("Grep", "Glob"):
            for target in (self.root / "data" / "00_raw", self.root / "data" / "00_raw" / "sample_cohort.csv"):
                with self.subTest(tool=tool, target=target.name):
                    self.assertEqual(self.read(target, tool)[0], "deny")

    def test_grep_and_glob_elsewhere_or_without_a_path_pass(self):
        for tool in ("Grep", "Glob"):
            with self.subTest(tool):
                self.assertEqual(self.read(self.root / "conf", tool), ("allow", ""))
                self.assertEqual(decide({"tool_name": tool, "cwd": str(self.root), "tool_input": {"pattern": "x"}}),
                                 ("allow", ""))

    def test_dvc_pointers_and_gitignore_pass(self):
        raw = self.root / "data" / "00_raw"
        for name in ("sample_cohort.csv.dvc", ".gitignore", "sub/other.csv.dvc"):
            for tool in ("Read", "Grep"):
                with self.subTest(name=name, tool=tool):
                    self.assertEqual(self.read(raw / name, tool), ("allow", ""))

    def test_a_dvc_named_alias_of_the_csv_is_still_denied(self):
        (self.root / "data" / "00_raw" / "alias.csv.dvc").symlink_to("sample_cohort.csv")
        self.assertDenied(self.root / "data" / "00_raw" / "alias.csv.dvc")
        (self.root / "conf" / "pointer.dvc").symlink_to(self.root / "data" / "00_raw" / "sample_cohort.csv")
        self.assertDenied(self.root / "conf" / "pointer.dvc")

    def test_csv_and_lookalike_names_are_still_denied(self):
        for name in ("sample_cohort.csv", "x.dvc.csv", "dvc", "notes.gitignore"):
            with self.subTest(name):
                self.assertDenied(self.root / "data" / "00_raw" / name)

    def test_write_to_the_directory_is_not_this_guards_concern(self):
        self.assertEqual(self.read(self.root / "data" / "00_raw" / "x.csv", "Write"), ("allow", ""))


class Wiring(unittest.TestCase):
    def test_hooks_json_routes_read_to_the_guard(self):
        for root in (REPO / "hooks" / "data-request", REPO / "plugins" / "data-request" / "hooks"):  # Codex has no Read tool
            groups = json.loads((root / "hooks.json").read_text())["hooks"]["PreToolUse"]
            matchers = {g["matcher"]: [h["command"] for h in g["hooks"]] for g in groups}
            with self.subTest(str(root.relative_to(REPO))):
                guard = '"${CLAUDE_PLUGIN_ROOT}/hooks/data-request-guard.sh"'
                self.assertEqual(matchers.get("Write|Edit"), [guard])
                self.assertEqual(matchers.get("Read|Grep|Glob"), [guard])


class SkillContract(unittest.TestCase):
    def test_every_skill_names_the_rule(self):
        for leaf in SKILLS:
            body = " ".join((REPO / f"skills/data-request-{leaf}/SKILL.md").read_text().split())
            with self.subTest(leaf):
                self.assertIn("data/00_raw", body)
                self.assertRegex(body, r"(?i)(never|do not|not) (read|open)")
                if leaf != "guardrails":
                    self.assertIn("supplied-cohorts.rst", body)

    def test_guardrails_links_the_reference_and_states_the_layers(self):
        body = " ".join((REPO / "skills/data-request-guardrails/SKILL.md").read_text().split())
        self.assertIn(f"]({REFERENCE})", body)
        self.assertIn("narrower layer", body)
        self.assertIn("Read(/data/**)", body)

    def test_reference_covers_the_rules(self):
        text = " ".join((REPO / "skills/data-request-guardrails" / REFERENCE).read_text().split())
        for phrase in ("SUPPLIED_COHORTS.md", "rdl_etl_helpers.harness.literals",
                       "pypika_queries.identifier_columns", "-- @supplied:", "-- @supplied-load:",
                       "executemany", "Never inline a value", "Never read the supplied file",
                       "conf/base/supplied/<name>.template.csv", "Probe disclosure control",
                       "narrower layer", "Read(/data/**)"):
            with self.subTest(phrase):
                self.assertIn(phrase, text)

    def test_skill_pointers_ship_with_every_copy(self):
        for tree in ("plugins/data-request/skills", "dist/codex/plugins/data-request/skills"):
            for leaf in SKILLS:
                body = " ".join((REPO / tree / leaf / "SKILL.md").read_text().split())
                with self.subTest(tree=tree, leaf=leaf):
                    self.assertIn("data/00_raw", body)

    def test_reference_ships_with_every_copy(self):
        canonical = (REPO / "skills/data-request-guardrails" / REFERENCE).read_text()
        for root in (REPO / "plugins/data-request/skills/guardrails",
                     REPO / "dist/codex/plugins/data-request/skills/guardrails"):
            with self.subTest(str(root.relative_to(REPO))):
                self.assertEqual((root / REFERENCE).read_text(), canonical)


if __name__ == "__main__":
    unittest.main()
