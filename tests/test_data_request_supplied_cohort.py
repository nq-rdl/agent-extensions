"""Supplied-cohort guidance and the Read guard (issue #516).

A researcher-supplied cohort is loaded by the runner at run time and its values never reach Git.
These tests pin:

* the data-request guard denies Read, Grep and Glob under data/00_raw/ (Grep and Glob also by root at or above it and by glob text) (by
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
import time
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
BASH = shutil.which("bash") or "bash"
GUARD = REPO / "hooks" / "data-request-guard.sh"
REFERENCE = "references/supplied-cohorts.rst"
SKILLS = ("guardrails", "draft", "map", "analyse", "explain", "intake", "triage")


def decide(event, extra_env=None):
    env = {k: v for k, v in os.environ.items() if not k.startswith("SQLREVIEW_")}
    env.update(extra_env or {})
    r = subprocess.run([BASH, str(GUARD)], input=json.dumps(event), text=True, capture_output=True,
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

    def test_grep_and_glob_elsewhere_pass(self):
        (self.root / "skills").mkdir()
        (self.root / "src").mkdir()
        for tool in ("Grep", "Glob"):
            for sub in ("conf", "skills", "src", "data/02_extracts"):
                with self.subTest(tool=tool, path=sub):
                    self.assertEqual(self.read(self.root / sub, tool), ("allow", ""))
            filtered = {"pattern": "x", "glob": "*.py"} if tool == "Grep" else {"pattern": "**/*.py"}
            self.assertEqual(self.search(tool, path="skills", **filtered), ("allow", ""))

    def search(self, tool, **tool_input):
        return decide({"tool_name": tool, "cwd": str(self.root), "tool_input": tool_input})

    def test_grep_path_data_with_a_glob_naming_00_raw_is_denied(self):
        self.assertEqual(self.search("Grep", pattern="x", path="data", glob="00_raw/**")[0], "deny")

    def test_grep_without_a_path_and_a_glob_naming_the_directory_is_denied(self):
        self.assertEqual(self.search("Grep", pattern="x", glob="data/00_raw/*")[0], "deny")

    def test_glob_without_a_path_and_a_pattern_naming_the_directory_is_denied(self):
        self.assertEqual(self.search("Glob", pattern="data/00_raw/**")[0], "deny")

    def test_glob_path_data_with_a_pattern_naming_00_raw_is_denied(self):
        self.assertEqual(self.search("Glob", path="data", pattern="00_raw/*")[0], "deny")

    def test_a_case_variant_of_the_directory_is_denied(self):
        self.assertEqual(self.read(self.root / "data" / "00_RAW" / "x", "Grep")[0], "deny")
        self.assertEqual(self.read(self.root / "data" / "00_RAW" / "sample_cohort.csv")[0], "deny")
        self.assertEqual(self.search("Glob", pattern="data/00_RAW/x")[0], "deny")
        self.assertEqual(self.search("Grep", pattern="x", glob="Data/00_Raw/*")[0], "deny")

    def test_a_search_rooted_above_the_directory_is_denied(self):
        # The project root, data/ and a parent of the project reach data/00_raw/, so each is denied (M1).
        for tool in ("Grep", "Glob"):
            for root in (".", "data", str(self.root), str(self.root / "data"), str(self.root.parent), "..", "data/../conf/.."):
                with self.subTest(tool=tool, root=root):
                    decision, reason = self.search(tool, pattern="x", path=root)
                    self.assertEqual(decision, "deny")
                    self.assertIn("data/00_raw", reason)
                    self.assertIn("excludes data/", reason)

    def test_a_search_rooted_levels_above_a_project_off_the_cwd_chain_is_denied(self):
        # Review finding 1: the root is an ancestor of other projects, not of the cwd's own project.
        with tempfile.TemporaryDirectory() as tmp:
            top = Path(tmp).resolve()
            (top / "notes").mkdir()
            for levels in (1, 2, 3):
                parts = [f"d{i}" for i in range(levels - 1)] + ["projB"]
                raw = top.joinpath(*parts, "data", "00_raw")
                raw.mkdir(parents=True)
                (raw / "c.csv").write_text("study_id\nZZTEST-002\n")
                for tool in ("Grep", "Glob"):
                    with self.subTest(tool=tool, levels=levels):
                        decision, reason = decide({"tool_name": tool, "cwd": str(top / "notes"),
                                                   "tool_input": {"pattern": "x", "path": str(top)}})
                        self.assertEqual(decision, "deny")
                        self.assertIn("data/00_raw", reason)
                        self.assertNotIn("ZZTEST-002", reason)
                shutil.rmtree(top / parts[0])

    def test_a_search_outside_any_project_with_no_raw_directory_beneath_passes(self):
        with tempfile.TemporaryDirectory() as tmp:
            top = Path(tmp).resolve()
            (top / "notes").mkdir()
            (top / "projC" / "data" / "02_extracts").mkdir(parents=True)
            for tool in ("Grep", "Glob"):
                with self.subTest(tool=tool):
                    self.assertEqual(decide({"tool_name": tool, "cwd": str(top / "notes"),
                                             "tool_input": {"pattern": "x", "path": str(top)}}), ("allow", ""))
                    self.assertEqual(decide({"tool_name": tool, "cwd": str(top / "notes"),
                                             "tool_input": {"pattern": "x", "path": str(top / "projC" / "data")}}),
                                     ("allow", ""))

    def test_a_search_with_no_path_is_denied_when_the_project_has_the_directory(self):
        for tool in ("Grep", "Glob"):
            with self.subTest(tool):
                decision, reason = self.search(tool, pattern="x")
                self.assertEqual(decision, "deny")
                self.assertIn("excludes data/", reason)

    def test_a_search_with_no_path_passes_when_the_project_has_no_raw_directory(self):
        shutil.rmtree(self.root / "data" / "00_raw")
        for tool in ("Grep", "Glob"):
            with self.subTest(tool):
                self.assertEqual(self.search(tool, pattern="x"), ("allow", ""))

    def test_a_search_rooted_in_a_subdirectory_of_a_project_with_the_directory_is_denied_only_above_it(self):
        (self.root / "skills").mkdir()
        decision = decide({"tool_name": "Grep", "cwd": str(self.root / "skills"), "tool_input": {"pattern": "x"}})
        self.assertEqual(decision, ("allow", ""))  # cwd is below the project root, so it cannot reach data/
        decision = decide({"tool_name": "Grep", "cwd": str(self.root / "skills"), "tool_input": {"pattern": "x", "path": ".."}})
        self.assertEqual(decision[0], "deny")

    def test_wildcard_and_bracket_spellings_of_the_directory_are_denied(self):
        (self.root / "src").mkdir()
        for tool, key in (("Grep", "glob"), ("Glob", "pattern")):
            for spelling in ("data/00_r[a]w/*", "data/0?_raw/*", "data/[0]0_[r]aw/*", "data/00_r?w/*", "data/0*/*",
                             "data/*/sample_cohort.csv", "**/00_{raw,x}/*", "**/0?_RAW/*", "../data/*", "/tmp/anything/*",
                             "src/../data/00_r[a]w/*"):
                with self.subTest(tool=tool, spelling=spelling):
                    # path=src cannot reach the directory by itself, so the filter text alone must deny
                    kwargs = {key: spelling}
                    if tool == "Grep":
                        kwargs["pattern"] = "x"
                    decision, reason = self.search(tool, path="src", **kwargs)
                    self.assertEqual(decision, "deny")
                    self.assertIn("data/00_raw", reason)

    def test_plain_filters_under_a_safe_root_pass(self):
        (self.root / "src").mkdir()
        for tool, key in (("Grep", "glob"), ("Glob", "pattern")):
            for plain in ("*.py", "**/*.md", "test_*.py", "{a,b}/*.rst"):
                with self.subTest(tool=tool, plain=plain):
                    kwargs = {key: plain}
                    if tool == "Grep":
                        kwargs["pattern"] = "x"
                    self.assertEqual(self.search(tool, path="src", **kwargs), ("allow", ""))

    POINTER = "outs:\n- md5: d41d8cd98f00b204e9800998ecf8427e\n  size: 10\n  hash: md5\n  path: sample_cohort.csv\n"

    def test_a_genuine_dvc_pointer_and_gitignore_pass_for_read(self):
        raw = self.root / "data" / "00_raw"
        (raw / "sample_cohort.csv.dvc").write_text(self.POINTER)
        (raw / ".gitignore").write_text("/sample_cohort.csv\n")
        for name in ("sample_cohort.csv.dvc", ".gitignore"):
            with self.subTest(name):
                self.assertEqual(self.read(raw / name), ("allow", ""))

    def test_grep_and_glob_never_pass_by_suffix(self):
        raw = self.root / "data" / "00_raw"
        (raw / "sample_cohort.csv.dvc").write_text(self.POINTER)
        (raw / ".gitignore").write_text("/sample_cohort.csv\n")
        for tool in ("Grep", "Glob"):
            for name in ("sample_cohort.csv.dvc", ".gitignore"):
                with self.subTest(tool=tool, name=name):
                    self.assertEqual(self.read(raw / name, tool)[0], "deny")

    def test_a_dvc_named_file_holding_csv_text_is_denied(self):
        (self.root / "data" / "00_raw" / "participants.dvc").write_text("study_id\nZZTEST-001\n")
        self.assertDenied(self.root / "data" / "00_raw" / "participants.dvc")

    def test_a_dvc_named_file_that_mixes_pointer_lines_and_rows_is_denied(self):
        (self.root / "data" / "00_raw" / "mixed.dvc").write_text(self.POINTER + "ZZTEST-001,ZZTEST-002\n")
        self.assertDenied(self.root / "data" / "00_raw" / "mixed.dvc")

    def test_an_oversized_dvc_file_is_denied(self):
        (self.root / "data" / "00_raw" / "big.dvc").write_text(self.POINTER + "# " + "x" * 70000 + "\n")
        self.assertDenied(self.root / "data" / "00_raw" / "big.dvc")

    def test_a_missing_dvc_file_is_denied(self):
        self.assertDenied(self.root / "data" / "00_raw" / "absent.dvc")

    def test_a_directory_named_dvc_is_denied_for_read_and_grep(self):
        (self.root / "data" / "00_raw" / "cohort.dvc").mkdir()
        (self.root / "data" / "00_raw" / "cohort.dvc" / "rows.csv").write_text("x\n")
        for tool in ("Read", "Grep"):
            with self.subTest(tool):
                self.assertEqual(self.read(self.root / "data" / "00_raw" / "cohort.dvc", tool)[0], "deny")

    def test_a_dvc_named_alias_of_the_csv_is_still_denied(self):
        (self.root / "data" / "00_raw" / "alias.csv.dvc").symlink_to("sample_cohort.csv")
        self.assertDenied(self.root / "data" / "00_raw" / "alias.csv.dvc")
        (self.root / "data" / "00_raw" / "real.dvc").write_text(self.POINTER)
        (self.root / "data" / "00_raw" / "x.dvc").symlink_to("real.dvc")  # even a link to a real pointer
        self.assertDenied(self.root / "data" / "00_raw" / "x.dvc")
        (self.root / "conf" / "pointer.dvc").symlink_to(self.root / "data" / "00_raw" / "sample_cohort.csv")
        self.assertDenied(self.root / "conf" / "pointer.dvc")

    def test_csv_and_lookalike_names_are_still_denied(self):
        for name in ("sample_cohort.csv", "x.dvc.csv", "dvc", "notes.gitignore"):
            with self.subTest(name):
                self.assertDenied(self.root / "data" / "00_raw" / name)

    def test_write_to_the_directory_is_not_this_guards_concern(self):
        self.assertEqual(self.read(self.root / "data" / "00_raw" / "x.csv", "Write"), ("allow", ""))


@unittest.skipUnless(shutil.which("jq"), "the guard needs jq")
class PhysicalRawPaths(unittest.TestCase):
    """One rule: a target or a search root is denied when its lexical or its physical path is at or under the
    project's data/00_raw (lexical or physical), when a search root is above either, or when a bounded search
    under the root finds a data/00_raw entry of any type or a link into it (review findings 1 to 3)."""

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.top = Path(self._tmp.name).resolve()
        self.root = self.top / "proj"
        self.store = self.top / "store" / "raw"  # the physical home of a symlinked 00_raw
        for d in (self.root / "data", self.root / "skills", self.root / "src", self.store):
            d.mkdir(parents=True)
        (self.store / "sample_cohort.csv").write_text("study_id\nZZTEST-001\n")
        (self.root / "data" / "00_raw").symlink_to(self.store)

    def call(self, tool, path=None, cwd=None, **extra):
        tool_input = dict(extra)
        if path is not None:
            tool_input["file_path" if tool == "Read" else "path"] = str(path)
        if tool == "Grep":
            tool_input.setdefault("pattern", "x")
        return decide({"tool_name": tool, "cwd": str(cwd or self.root), "tool_input": tool_input})

    def assertDenied(self, tool, path=None, **kw):
        decision, reason = self.call(tool, path, **kw)
        self.assertEqual(decision, "deny", (tool, path))
        self.assertIn("data/00_raw", reason)
        self.assertNotIn("ZZTEST-001", reason)

    def test_finding_1_a_symlinked_00_raw_is_found_from_a_root_above_it(self):
        for tool in ("Grep", "Glob"):
            for root in (self.root, self.root / "data", self.top, ".", "data", ".."):
                with self.subTest(tool=tool, root=str(root)):
                    self.assertDenied(tool, root)
            with self.subTest(tool=tool, root="the physical store's parent"):
                self.assertDenied(tool, self.store.parent)

    def test_finding_2_the_symlink_target_is_denied_when_read_directly(self):
        self.assertDenied("Read", self.store / "sample_cohort.csv")
        self.assertDenied("Read", self.store / "not_yet.csv")
        self.assertDenied("Read", self.store)
        for tool in ("Grep", "Glob"):
            with self.subTest(tool=tool):
                self.assertDenied(tool, self.store)
                self.assertDenied(tool, self.store / "sample_cohort.csv")

    def test_finding_2_a_genuine_dvc_pointer_in_the_physical_store_still_reads(self):
        (self.store / "sample_cohort.csv.dvc").write_text(
            "outs:\n- md5: d41d8cd98f00b204e9800998ecf8427e\n  size: 10\n  hash: md5\n  path: sample_cohort.csv\n")
        self.assertEqual(self.call("Read", self.store / "sample_cohort.csv.dvc"), ("allow", ""))
        self.assertDenied("Grep", self.store / "sample_cohort.csv.dvc")

    def test_finding_2_holds_for_a_symlinked_data_directory_too(self):
        (self.root / "data" / "00_raw").unlink()
        far = self.top / "far" / "data"
        (far / "00_raw").mkdir(parents=True)
        (far / "00_raw" / "c.csv").write_text("study_id\nZZTEST-001\n")
        shutil.rmtree(self.root / "data")
        (self.root / "data").symlink_to(far)
        self.assertDenied("Read", far / "00_raw" / "c.csv")
        self.assertDenied("Grep", self.root)
        self.assertDenied("Glob", far)

    def test_finding_3_a_link_inside_the_root_into_00_raw_is_denied(self):
        (self.root / "data" / "00_raw").unlink()
        (self.root / "data" / "00_raw").mkdir()
        (self.root / "data" / "00_raw" / "sample_cohort.csv").write_text("study_id\nZZTEST-001\n")
        (self.root / "src" / "cohort").symlink_to("../data/00_raw")
        (self.root / "src" / "one.csv").symlink_to("../data/00_raw/sample_cohort.csv")
        (self.root / "skills" / "chain").symlink_to("../src/cohort")
        for tool in ("Grep", "Glob"):
            for root in ("src", "skills", str(self.root / "src")):
                with self.subTest(tool=tool, root=root):
                    self.assertDenied(tool, root)

    def test_finding_3_a_link_to_a_physical_store_and_to_another_projects_raw_is_denied(self):
        (self.root / "src" / "cohort").symlink_to(self.store)
        self.assertDenied("Grep", "src")
        (self.root / "src" / "cohort").unlink()
        (self.root / "src" / "file").symlink_to(self.store / "sample_cohort.csv")
        self.assertDenied("Glob", "src")
        (self.root / "src" / "file").unlink()
        other = self.top / "other" / "data" / "00_raw"
        other.mkdir(parents=True)
        (self.root / "src" / "theirs").symlink_to(other)
        self.assertDenied("Grep", "src")

    def test_a_data_00_raw_entry_of_any_type_below_the_root_is_denied(self):
        (self.root / "data" / "00_raw").unlink()
        (self.root / "data" / "00_raw").write_text("not a directory\n")  # a regular file
        outer = self.top / "elsewhere"
        outer.mkdir()
        for tool in ("Grep", "Glob"):
            with self.subTest(tool=tool, kind="file"):
                self.assertDenied(tool, self.root, cwd=outer)
        (self.root / "data" / "00_raw").unlink()
        (self.root / "data" / "00_raw").symlink_to("missing")  # a dangling link
        for tool in ("Grep", "Glob"):
            with self.subTest(tool=tool, kind="dangling link"):
                self.assertDenied(tool, self.root, cwd=outer)
                self.assertDenied(tool, self.top, cwd=outer)

    def test_roots_and_links_that_do_not_reach_the_directory_pass(self):
        (self.root / "src" / "to_skills").symlink_to("../skills")
        (self.root / "skills" / "a.py").write_text("x = 1\n")
        for tool in ("Grep", "Glob"):
            for root in ("skills", "src", str(self.root / "src")):
                with self.subTest(tool=tool, root=root):
                    self.assertEqual(self.call(tool, root), ("allow", ""))
        self.assertEqual(self.call("Read", self.root / "src" / "to_skills" / "a.py"), ("allow", ""))

    def test_a_link_with_no_project_around_it_into_a_stray_data_00_raw_is_denied(self):
        stray = self.top / "stray"
        (stray / "data" / "00_raw").mkdir(parents=True)
        free = self.top / "free"
        (free / "src").mkdir(parents=True)
        (free / "src" / "l").symlink_to(stray / "data" / "00_raw")
        for tool in ("Grep", "Glob"):
            with self.subTest(tool=tool):
                self.assertDenied(tool, free / "src", cwd=free)


@unittest.skipUnless(shutil.which("jq"), "the guard needs jq")
class FilterSegments(unittest.TestCase):
    """Finding 5: a glob or pattern is denied only when one of its path segments could be 00_raw."""

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.root = Path(self._tmp.name).resolve()
        (self.root / "data" / "00_raw").mkdir(parents=True)
        (self.root / "src").mkdir()

    def verdict(self, tool, spelling):
        key = "glob" if tool == "Grep" else "pattern"
        event = {"tool_name": tool, "cwd": str(self.root), "tool_input": {"path": "src", key: spelling}}
        if tool == "Grep":
            event["tool_input"]["pattern"] = "x"
        return decide(event)

    def test_names_that_only_contain_raw_pass(self):
        for spelling in ("*draw*.py", "*raw_sql*", "straw", "Drawing*.md", "**/*raw_sql*.py", "src/**/draw*.py",
                         "withdrawn/*.sql", "data/*.csv", "data/raw_*.sql", "**/straw/**", "{draw,straw}/*.py"):
            for tool in ("Grep", "Glob"):
                with self.subTest(tool=tool, spelling=spelling):
                    self.assertEqual(self.verdict(tool, spelling), ("allow", ""))

    def test_spellings_that_could_be_the_segment_are_denied(self):
        for spelling in ("data/00_r[a]w/*", "data/0?_raw/*", "**/00_RAW/**", "data/**", "data/*", "*/00_raw",
                         "data/00_raw*", "{data,x}/00_raw/*", "data/{00_raw,x}", "data/[0]0_[r]aw", "**/*raw*",
                         "data/00_raw./*", "data/00_raw /*", "DATA/00_RAW/x", "data/*/x.csv", "data/0*",
                         "!data/00_raw/*", "00_raw/**", "**/00_{raw,x}/*", "data/[!x]0_raw"):
            for tool in ("Grep", "Glob"):
                with self.subTest(tool=tool, spelling=spelling):
                    decision, reason = self.verdict(tool, spelling)
                    self.assertEqual(decision, "deny")
                    self.assertIn("data/00_raw", reason)

    def test_a_brace_list_that_is_too_long_to_check_is_denied(self):
        spelling = "{" + ",".join(f"a{i}" for i in range(300)) + "}/*.py"
        self.assertEqual(self.verdict("Glob", spelling)[0], "deny")


@unittest.skipUnless(shutil.which("jq"), "the guard needs jq")
class WildcardOnlyGlobs(unittest.TestCase):
    """F9: a glob whose segment after **/ is only wildcards (as in **/*) is denied when the root is at or above
    data/00_raw/, or when the root walk was cut short, and passes under a root the walk fully covered."""

    PATTERNS = ("**/*", "**/*.py", "src/**/*", "**/**")

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.root = Path(self._tmp.name).resolve()
        (self.root / "data" / "00_raw").mkdir(parents=True)
        (self.root / "data" / "00_raw" / "sample_cohort.csv").write_text("study_id\nZZTEST-001\n")
        (self.root / "src" / "pkg").mkdir(parents=True)
        (self.root / "src" / "pkg" / "a.py").write_text("x = 1\n")

    def verdict(self, tool, path, spelling):
        key = "glob" if tool == "Grep" else "pattern"
        tool_input = {"path": path, key: spelling}
        if tool == "Grep":
            tool_input["pattern"] = "x"
        return decide({"tool_name": tool, "cwd": str(self.root), "tool_input": tool_input})

    def test_a_wildcard_only_glob_passes_under_a_root_without_raw_data(self):
        for tool in ("Grep", "Glob"):
            for spelling in ("**/*", "**/*.py", "**/**"):
                for path in ("src", "src/pkg"):
                    with self.subTest(tool=tool, spelling=spelling, path=path):
                        self.assertEqual(self.verdict(tool, path, spelling), ("allow", ""))

    def test_the_same_glob_at_the_project_root_or_data_is_denied(self):
        for tool in ("Grep", "Glob"):
            for spelling in self.PATTERNS:
                for path in (".", "data", str(self.root), "src/..", "src/../data"):
                    with self.subTest(tool=tool, spelling=spelling, path=path):
                        self.assertEqual(self.verdict(tool, path, spelling)[0], "deny")

    def test_a_glob_that_names_the_directory_is_still_denied_under_a_clean_root(self):
        for tool in ("Grep", "Glob"):
            for spelling in ("**/00_RAW/**", "**/*raw*", "**/0*", "data/00_r[a]w/*", "**/00_raw", "**/?*"):
                with self.subTest(tool=tool, spelling=spelling):
                    self.assertEqual(self.verdict(tool, "src", spelling)[0], "deny")

    def test_a_link_into_the_directory_denies_the_glob(self):
        (self.root / "src" / "pkg" / "into_raw").symlink_to(self.root / "data" / "00_raw")
        for tool in ("Grep", "Glob"):
            with self.subTest(tool=tool):
                self.assertEqual(self.verdict(tool, "src", "**/*")[0], "deny")

    def test_a_root_deeper_than_the_walk_denies_the_glob(self):
        deep = self.root / "src" / "d1" / "d2" / "d3" / "d4" / "d5" / "d6"
        deep.mkdir(parents=True)
        (deep / "x.py").write_text("x = 1\n")
        for tool in ("Grep", "Glob"):
            with self.subTest(tool=tool):
                decision, reason = self.verdict(tool, "src", "**/*")
                self.assertEqual(decision, "deny")
                self.assertIn("narrower path inside the project", reason)
            with self.subTest(tool=tool, plain="a plain filter still passes"):
                self.assertEqual(self.verdict(tool, "src", "*.py"), ("allow", ""))

    def test_a_deep_node_modules_or_git_tree_does_not_count_as_deeper(self):
        deep = self.root / "src" / "node_modules" / "a" / "b" / "c" / "d" / "e"
        deep.mkdir(parents=True)
        (deep / "x.js").write_text("x = 1\n")
        self.assertEqual(self.verdict("Glob", "src", "**/*"), ("allow", ""))


@unittest.skipUnless(shutil.which("jq"), "the guard needs jq")
class OddProjectPaths(unittest.TestCase):
    """A project path with a space, a tab, a newline or a leading dash must not weaken the Grep and Glob root check."""

    NAMES = ("with space", "with\ttab", "with\nnewline", "-leading dash", "star*[x]")

    def project(self, name):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        root = Path(tmp.name).resolve() / name
        (root / "data" / "00_raw").mkdir(parents=True)
        (root / "skills").mkdir()
        (root / "data" / "00_raw" / "sample_cohort.csv").write_text("study_id\nZZTEST-001\n")
        return root

    def search(self, root, tool, **tool_input):
        tool_input = dict(tool_input)
        if tool == "Grep":
            tool_input.setdefault("pattern", "x")
        return decide({"tool_name": tool, "cwd": str(root), "tool_input": tool_input})

    def test_roots_at_or_above_the_directory_are_denied(self):
        for name in self.NAMES:
            root = self.project(name)
            for tool in ("Grep", "Glob"):
                for tool_input in ({"path": "."}, {}, {"path": "data"}, {"path": str(root)}):
                    with self.subTest(name=name, tool=tool, tool_input=tool_input):
                        self.assertEqual(self.search(root, tool, **tool_input)[0], "deny")

    def test_a_path_with_a_newline_fails_closed(self):
        # A control character in the project path is refused before any path step, so skills/ is denied too.
        root = self.project("with\nnewline")
        for tool in ("Grep", "Glob"):
            with self.subTest(tool=tool):
                self.assertEqual(self.search(root, tool, path="skills")[0], "deny")

    def test_a_search_under_skills_still_passes(self):
        for name in (n for n in self.NAMES if "\n" not in n and "\t" not in n):
            root = self.project(name)
            for tool in ("Grep", "Glob"):
                with self.subTest(name=name, tool=tool):
                    self.assertEqual(self.search(root, tool, path="skills"), ("allow", ""))


@unittest.skipUnless(shutil.which("jq"), "the guard needs jq")
class ControlCharacters(unittest.TestCase):
    """A control character in a hook field is denied before any shell step can trim or split it."""

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.base = Path(self._tmp.name).resolve()

    def project(self, name):
        root = self.base / name
        (root / "data" / "00_raw").mkdir(parents=True)
        (root / "skills").mkdir()
        return root

    def test_a_control_character_at_either_end_of_the_project_path_is_denied(self):
        for suffix in ("\n", "\t", "\r", "\x01", "\x7f"):
            for name in (f"proj{suffix}", f"{suffix}proj", f"pr{suffix}oj"):
                root = self.project(name)
                for tool in ("Grep", "Glob"):
                    for tool_input in ({"path": "."}, {}, {"path": "data"}, {"path": "skills"}):
                        with self.subTest(name=name, tool=tool, tool_input=tool_input):
                            event = {"tool_name": tool, "cwd": str(root), "tool_input": dict(tool_input, pattern="x")}
                            self.assertEqual(decide(event)[0], "deny")

    def test_a_control_character_in_file_path_path_pattern_or_glob_is_denied(self):
        root = self.project("proj")
        cases = (
            {"tool_name": "Read", "tool_input": {"file_path": str(root / "skills") + "\n"}},
            {"tool_name": "Read", "tool_input": {"file_path": "\t" + str(root / "skills")}},
            {"tool_name": "Glob", "tool_input": {"path": "skills", "pattern": "*.py\n"}},
            {"tool_name": "Glob", "tool_input": {"path": "skills", "pattern": "\r*.py"}},
            {"tool_name": "Grep", "tool_input": {"path": "skills", "pattern": "x", "glob": "*.py\n"}},
            {"tool_name": "Grep", "tool_input": {"path": "skills\n", "pattern": "x"}},
            {"tool_name": "Write", "tool_input": {"file_path": str(root / "a\n.txt"), "content": "x"}},
        )
        for event in cases:
            with self.subTest(event=event):
                self.assertEqual(decide(dict(event, cwd=str(root)))[0], "deny")

    def test_normal_paths_and_multiline_content_still_pass(self):
        root = self.project("proj")
        for event in ({"tool_name": "Grep", "tool_input": {"path": "skills", "pattern": "a\nb", "glob": "*.py"}},
                      {"tool_name": "Read", "tool_input": {"file_path": str(root / "skills" / "a.py")}},
                      {"tool_name": "Write", "tool_input": {"file_path": str(root / "notes.txt"), "content": "a\nb\n"}}):
            with self.subTest(tool=event["tool_name"]):
                self.assertEqual(decide(dict(event, cwd=str(root))), ("allow", ""))

    def test_a_symlink_to_a_directory_named_with_a_trailing_newline_is_denied(self):
        target = self.base / "proj\n"
        (target / "data" / "00_raw").mkdir(parents=True)
        link = self.base / "link"
        link.symlink_to(target)
        for tool in ("Grep", "Glob"):
            with self.subTest(tool=tool):
                event = {"tool_name": tool, "cwd": str(self.base), "tool_input": {"path": "link", "pattern": "x"}}
                self.assertEqual(decide(event)[0], "deny")


@unittest.skipUnless(shutil.which("jq"), "the guard needs jq")
class GuardBudget(unittest.TestCase):
    """F2: the Grep and Glob root walk has its own time budget, well under the 10 second hook timeout. Claude Code
    lets a tool call through when a hook times out, so a walk that runs past the budget must deny instead."""

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.top = Path(self._tmp.name).resolve()
        self.root = self.top / "proj"
        for d in ("data/00_raw", "src/pkg", "skills"):
            (self.root / d).mkdir(parents=True)
        (self.root / "data" / "00_raw" / "sample_cohort.csv").write_text("study_id\nZZTEST-001\n")
        (self.root / "src" / "pkg" / "a.py").write_text("x = 1\n")
        self.stubs = self.top / "stubs"
        self.stubs.mkdir()
        slow = self.stubs / "find"  # a walk that outlasts any budget used here
        slow.write_text("#!/bin/sh\nsleep 6\n")
        slow.chmod(0o755)

    def search(self, path="src", tool="Glob", env=None, path_env=None):
        tool_input = {"path": path, "pattern": "*.py"} if tool == "Glob" else {"path": path, "pattern": "x"}
        event = {"tool_name": tool, "cwd": str(self.root), "tool_input": tool_input}
        extra = dict(env or {})
        if path_env is not None:
            extra["PATH"] = path_env
        return decide(event, extra)

    def timed(self, **kw):
        start = time.monotonic()
        verdict = self.search(**kw)
        return verdict, time.monotonic() - start

    def test_a_walk_that_outlasts_the_budget_is_denied_inside_the_hook_timeout(self):
        for tool in ("Grep", "Glob"):
            with self.subTest(tool=tool):
                (decision, reason), took = self.timed(
                    tool=tool, env={"SQLREVIEW_GUARD_BUDGET": "1", "PATH": f"{self.stubs}:{os.environ['PATH']}"})
                self.assertEqual(decision, "deny")
                self.assertIn("narrower path inside the project", reason)
                self.assertLess(took, 4)

    def test_the_default_budget_is_well_under_the_hook_timeout(self):
        (decision, reason), took = self.timed(env={"PATH": f"{self.stubs}:{os.environ['PATH']}"})
        self.assertEqual(decision, "deny")
        self.assertIn("narrower path inside the project", reason)
        self.assertLess(took, 5)

    def test_without_a_timeout_command_the_reader_still_stops_at_the_budget(self):
        tools = self.top / "tools"
        tools.mkdir()
        wanted = ("jq", "awk", "tr", "sed", "dirname", "basename", "readlink", "wc", "grep", "cat", "sh", "sleep",
                  "mktemp", "rm", "cut", "head", "sort", "uniq", "env", "printf")
        for name in wanted:
            found = shutil.which(name)
            if found:
                (tools / name).symlink_to(found)
        shutil.copy(self.stubs / "find", tools / "find")
        self.assertFalse((tools / "timeout").exists())
        (decision, reason), took = self.timed(env={"SQLREVIEW_GUARD_BUDGET": "1"}, path_env=str(tools))
        self.assertEqual(decision, "deny")
        self.assertIn("narrower path inside the project", reason)
        self.assertLess(took, 4)

    def test_a_budget_of_zero_denies_every_walk(self):
        for tool in ("Grep", "Glob"):
            with self.subTest(tool=tool):
                decision, reason = self.search(tool=tool, env={"SQLREVIEW_GUARD_BUDGET": "0"})
                self.assertEqual(decision, "deny")
                self.assertIn("narrower path inside the project", reason)

    def test_a_budget_that_is_not_digits_falls_back_to_the_default(self):
        for value in ("abc", "-1", "1.5", "", " 2", "9999999999999999999999"):
            with self.subTest(value=value):
                self.assertEqual(self.search(env={"SQLREVIEW_GUARD_BUDGET": value}), ("allow", ""))

    def test_a_budget_with_a_leading_zero_is_a_number(self):
        self.assertEqual(self.search(env={"SQLREVIEW_GUARD_BUDGET": "08"}), ("allow", ""))

    def test_a_normal_search_inside_a_project_passes_and_stays_fast(self):
        for tool in ("Grep", "Glob"):
            for sub in ("src", "skills", "src/pkg"):
                with self.subTest(tool=tool, path=sub):
                    (decision, _), took = self.timed(tool=tool, path=sub)
                    self.assertEqual(decision, "allow")
                    self.assertLess(took, 2)

    def test_more_than_200_links_is_denied_with_the_same_message(self):
        links = self.root / "src" / "links"
        links.mkdir()
        for i in range(201):
            (links / f"l{i}").symlink_to(self.root / "skills")
        decision, reason = self.search()
        self.assertEqual(decision, "deny")
        self.assertIn("narrower path inside the project", reason)

    def test_the_first_link_that_leads_to_raw_data_ends_the_check(self):
        links = self.root / "src" / "links"
        links.mkdir()
        (links / "a_into_raw").symlink_to(self.root / "data" / "00_raw")
        for i in range(150):
            (links / f"z{i}").symlink_to(self.root / "skills")
        decision, reason = self.search()
        self.assertEqual(decision, "deny")
        self.assertIn("data/00_raw", reason)


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
