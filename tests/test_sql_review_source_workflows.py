"""Instruction scenarios for hash-only reviews over committed SQL, including packaged boundaries."""
import re
import subprocess
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent


class SourceWorkflows(unittest.TestCase):
    def skill(self, name):
        return (REPO / f"skills/data-request-{name}/SKILL.md").read_text()

    def test_no_skill_routes_sql_through_a_render_adapter(self):
        for name in ("setup", "bootstrap", "analyse", "explain"):
            with self.subTest(name=name):
                body = self.skill(name)
                self.assertNotRegex(body, r"sql_render|render-only|adapter|sql_provenance")
        reference = (REPO / "skills/data-request-setup/references/sql-provenance.rst").read_text()
        self.assertNotRegex(reference, r"sql_render|adapter|env -i|clone")
        self.assertIn("git show <git_commit>:<sql_path>", reference)
        self.assertFalse((REPO / "skills/data-request-analyse/references/source-notes.rst").exists())

    def test_bootstrap_never_copies_sql_into_review_store(self):
        body = self.skill("bootstrap")
        self.assertNotRegex(body, r"scope\.(?:source|draft)\.sql")
        self.assertIn('delta "$SLUG" scope', body)
        self.assertIn('git diff "<draft git_commit>" HEAD', body)

    def test_analyse_publish_is_hash_only_and_git_required(self):
        body = self.skill("analyse")
        self.assertNotRegex(body, r"source\.sql|history/<revision>\.sql|git optional")
        self.assertIn("Snapshot verifies", body)
        self.assertIn("history/review/<revision>.json", body)
        self.assertIn('"git_dirty": false', body)

    def test_explain_materializes_exact_revisions(self):
        body = self.skill("explain")
        self.assertNotRegex(body, r"source\.sql|history/[^\n]*\.sql")
        self.assertRegex(body, r'materialize "\$SLUG" review "\$PREVIOUS" "\$T/previous.sql"')
        self.assertRegex(body, r'materialize "\$SLUG" review "\$REVISION" "\$T/reviewed.sql"')
        self.assertIn('rm -rf "$T"', body)

    def test_setup_ignore_rules_are_visible(self):
        body = self.skill("setup")
        for pattern in ("/reviews/**/source.sql", "/reviews/**/scope.source.sql", "/reviews/**/history/*.sql"):
            self.assertIn(pattern, body)
        self.assertIn("sql-provenance.rst", body)

    def test_all_changed_skills_remain_small(self):
        for name in ("setup", "bootstrap", "analyse", "explain"):
            with self.subTest(name=name):
                self.assertLessEqual(len(self.skill(name).splitlines()), 500)

    def test_no_snapshot_rollout_capability_is_packaged(self):
        for tree in ("plugins/data-request", "dist/codex/plugins/data-request"):
            for path in (REPO / tree).rglob("*"):
                if path.is_file():
                    with self.subTest(path=str(path.relative_to(REPO))):
                        self.assertNotIn("migrate_sqlreview_snapshots", path.name)
                        self.assertNotIn("sqlreview-snapshot-hashes.json", path.read_text())
                        self.assertNotRegex(path.read_text(), r"migrate_sqlreview_snapshots|migrate-snapshots")

    def test_shell_examples_parse(self):
        examples = []
        for name in ("explain", "bootstrap", "analyse"):
            examples += re.findall(r"```bash\n(.*?)```", self.skill(name), re.S)
        for example in examples:
            with self.subTest(example=example.splitlines()[0]):
                result = subprocess.run(["bash", "-n"], input=example + "\n", text=True, capture_output=True)
                self.assertEqual(result.returncode, 0, result.stderr)

    def test_strict_gate_selects_sql_source_cases(self):
        text = (REPO / "scripts/run_bash32_portability.py").read_text()
        self.assertIn("test_sql_review_sources_bash32.Bash32Sources.test_committed_publish_diff_and_carry", text)


if __name__ == "__main__":
    unittest.main()
