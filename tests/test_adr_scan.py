"""Tests for skills/architecture-decision-records/scripts/adr-scan.sh (#202).

The scanner owns the two rules a model most often gets wrong: an ADR number is
never reused (deleted files, index rows and other branches still hold theirs),
and an existing log's location and file-name style win over the default.
"""
import os
import shlex
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
SCRIPT = REPO / "skills" / "architecture-decision-records" / "scripts" / "adr-scan.sh"

GIT_ENV = {
    "GIT_AUTHOR_NAME": "t", "GIT_AUTHOR_EMAIL": "t@example.com",
    "GIT_COMMITTER_NAME": "t", "GIT_COMMITTER_EMAIL": "t@example.com",
    "GIT_CONFIG_GLOBAL": os.devnull, "GIT_CONFIG_NOSYSTEM": "1",
}

MADR = '---\nstatus: "{status}"\ndate: 2026-01-02\n---\n\n# {title}\n\n## Context and Problem Statement\n\nx\n'
NYGARD = "# {title}\n\n## Status\n\nAccepted\n\n## Context\n\nx\n"


def write(root, rel, text):
    path = Path(root) / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text)


def parse(stdout):
    return dict(line.split("=", 1) for line in stdout.splitlines() if "=" in line)


class ScanCases:
    """Shared cases; subclasses supply ``execute(root, args)``."""

    def run_scan(self, root, *args):
        return self.execute(root, list(args))

    def git(self, root, *args):
        subprocess.run(["git", "-C", root, *args], check=True, capture_output=True,
                       env={**os.environ, **GIT_ENV})

    def test_empty_repo_defaults_to_docs_adr_and_0001(self):
        with tempfile.TemporaryDirectory() as root:
            r = self.run_scan(root, "next")
            self.assertEqual(r.returncode, 0, r.stderr)
            kv = parse(r.stdout)
            self.assertEqual(kv["dir"], "docs/adr")
            self.assertEqual(kv["exists"], "no")
            self.assertEqual(kv["next"], "0001")
            self.assertEqual(kv["highest"], "none")
            self.assertEqual(kv["style"], "NNNN-")

    def test_numbers_are_never_reused(self):
        with tempfile.TemporaryDirectory() as root:
            write(root, "docs/adr/0001-use-x.md", MADR.format(status="accepted", title="Use X"))
            # Index keeps the row of a deleted record: its number stays taken.
            write(root, "docs/adr/README.md",
                  "| [0001](0001-use-x.md) | Use X | accepted | 2026-01-02 |\n"
                  "| [0004](0004-gone.md) | Gone | accepted | 2026-01-03 |\n")
            kv = parse(self.run_scan(root, "next").stdout)
            self.assertEqual(kv["highest"], "0004")
            self.assertEqual(kv["next"], "0005")
            self.assertEqual(kv["index"], "docs/adr/README.md")

    def test_dates_in_index_are_not_numbers(self):
        with tempfile.TemporaryDirectory() as root:
            write(root, "docs/adr/0002-use-y.md", MADR.format(status="accepted", title="Use Y"))
            write(root, "docs/adr/README.md", "| [0002](0002-use-y.md) | Use Y | accepted | 2026-01-02 |\n")
            self.assertEqual(parse(self.run_scan(root, "next").stdout)["next"], "0003")

    def test_git_history_and_other_branches_hold_numbers(self):
        with tempfile.TemporaryDirectory() as root:
            self.git(root, "init", "-q", "-b", "main")
            write(root, "docs/adr/0001-a.md", MADR.format(status="accepted", title="A"))
            self.git(root, "add", "-A")
            self.git(root, "commit", "-qm", "a")
            self.git(root, "checkout", "-qb", "feature")
            write(root, "docs/adr/0006-b.md", MADR.format(status="proposed", title="B"))
            self.git(root, "add", "-A")
            self.git(root, "commit", "-qm", "b")
            self.git(root, "checkout", "-q", "main")
            write(root, "docs/adr/0003-c.md", MADR.format(status="accepted", title="C"))
            self.git(root, "add", "-A")
            self.git(root, "commit", "-qm", "c")
            self.git(root, "rm", "-q", "docs/adr/0003-c.md")
            self.git(root, "commit", "-qm", "rm c")
            self.assertEqual(parse(self.run_scan(root, "next").stdout)["next"], "0007")

    def test_existing_legacy_prefix_style_is_kept(self):
        with tempfile.TemporaryDirectory() as root:
            write(root, "docs/adr/adr-0001-a.md", NYGARD.format(title="A"))
            write(root, "docs/adr/adr-0002-b.md", NYGARD.format(title="B"))
            kv = parse(self.run_scan(root, "next").stdout)
            self.assertEqual(kv["style"], "adr-NNNN-")
            self.assertEqual(kv["next"], "0003")

    def test_adr_dir_file_and_other_directories(self):
        with tempfile.TemporaryDirectory() as root:
            write(root, ".adr-dir", "architecture/adr\n")
            write(root, "architecture/adr/0001-a.md", NYGARD.format(title="A"))
            self.assertEqual(parse(self.run_scan(root, "next").stdout)["dir"], "architecture/adr")
        with tempfile.TemporaryDirectory() as root:
            write(root, "docs/decisions/0001-a.md", MADR.format(status="accepted", title="A"))
            write(root, "doc/adr/0001-b.md", NYGARD.format(title="B"))
            kv = parse(self.run_scan(root, "next").stdout)
            self.assertEqual(kv["dir"], "docs/decisions")
            self.assertEqual(kv["others"], "doc/adr")

    def test_list_reads_madr_front_matter_and_nygard_status(self):
        with tempfile.TemporaryDirectory() as root:
            write(root, "docs/adr/0001-a.md", MADR.format(status="superseded by ADR-0002", title="Use A"))
            write(root, "docs/adr/0002-b.md", NYGARD.format(title="2. Use B"))
            rows = [line.split("\t") for line in self.run_scan(root, "list").stdout.splitlines()]
            self.assertEqual(rows[0], ["0001", "superseded by ADR-0002", "2026-01-02", "Use A", "docs/adr/0001-a.md"])
            self.assertEqual(rows[1], ["0002", "Accepted", "unknown", "2. Use B", "docs/adr/0002-b.md"])

    def test_check_reports_duplicates_unindexed_and_reserved(self):
        with tempfile.TemporaryDirectory() as root:
            write(root, "docs/adr/0001-a.md", MADR.format(status="accepted", title="A"))
            write(root, "docs/adr/0002-b.md", MADR.format(status="accepted", title="B"))
            write(root, "docs/adr/0002-c.md", MADR.format(status="proposed", title="C"))
            write(root, "docs/adr/README.md",
                  "| [0001](0001-a.md) | A | accepted | 2026-01-02 |\n"
                  "| [0002](0002-b.md) | B | accepted | 2026-01-02 |\n"
                  "| [0003](0003-gone.md) | Gone | accepted | 2026-01-02 |\n")
            r = self.run_scan(root, "check")
            self.assertEqual(r.returncode, 1, r.stdout + r.stderr)
            self.assertIn("duplicate 0002: 0002-b.md 0002-c.md", r.stdout)
            self.assertIn("unindexed 0002-c.md", r.stdout)
            self.assertIn("reserved 0003-gone.md", r.stdout)

    def test_check_passes_on_a_clean_log(self):
        with tempfile.TemporaryDirectory() as root:
            write(root, "docs/adr/0001-a.md", MADR.format(status="accepted", title="A"))
            write(root, "docs/adr/README.md", "| [0001](0001-a.md) | A | accepted | 2026-01-02 |\n")
            r = self.run_scan(root, "check")
            self.assertEqual((r.returncode, r.stdout), (0, ""), r.stderr)

    def test_bad_arguments_exit_2(self):
        with tempfile.TemporaryDirectory() as root:
            self.assertEqual(self.run_scan(root).returncode, 2)
            self.assertEqual(self.run_scan(root, "bogus").returncode, 2)


class HostScan(ScanCases, unittest.TestCase):
    def execute(self, root, args):
        return subprocess.run(["bash", str(SCRIPT), "--root", root, *args],
                              capture_output=True, text=True, env={**os.environ, **GIT_ENV})


class Bash32Scan(unittest.TestCase):
    """One combined case under the pinned Bash 3.2 / BusyBox image (no git there)."""

    def setUp(self):
        from bash32_fixture import container_runtime
        if not container_runtime():
            self.skipTest("needs pinned Bash 3.2 image; see docs/bash32-portability.md")

    def test_next_list_check_under_bash32(self):
        from bash32_fixture import run_container
        with tempfile.TemporaryDirectory() as tmp:
            shutil.copyfile(SCRIPT, Path(tmp) / "adr-scan.sh")
            write(tmp, "repo/docs/adr/adr-0001-a.md", NYGARD.format(title="A"))
            write(tmp, "repo/docs/adr/adr-0003-b.md", MADR.format(status="accepted", title="B"))
            write(tmp, "repo/docs/adr/README.md",
                  "| [0001](adr-0001-a.md) | A | accepted | 2026-01-02 |\n"
                  "| [0005](adr-0005-gone.md) | Gone | accepted | 2026-01-02 |\n")
            script = shlex.quote("/w/adr-scan.sh")
            command = (f"bash {script} --root /w/repo next; bash {script} --root /w/repo list; "
                       f"set +e; bash {script} --root /w/repo check; echo rc=$?")
            r = run_container(tmp, "/w", command)
            self.assertEqual(r.returncode, 0, r.stderr)
            kv = parse(r.stdout)
            self.assertEqual((kv["style"], kv["highest"], kv["next"]), ("adr-NNNN-", "0005", "0006"))
            self.assertIn("0003\taccepted\t2026-01-02\tB\tdocs/adr/adr-0003-b.md", r.stdout)
            self.assertIn("unindexed adr-0003-b.md", r.stdout)
            self.assertIn("rc=1", r.stdout)


if __name__ == "__main__":
    unittest.main()
