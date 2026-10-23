"""Instruction scenarios for committed-source reviews, including packaged boundaries."""
import re
import json
import os
import subprocess
import tempfile
import textwrap
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent


class SourceWorkflows(unittest.TestCase):
    def skill(self, name):
        return (REPO / f"skills/data-request-{name}/SKILL.md").read_text()

    def test_bootstrap_never_copies_sql_into_review_store(self):
        body = self.skill("bootstrap")
        self.assertNotRegex(body, r"scope\.(?:source|draft)\.sql")
        self.assertIn('delta "$SLUG" scope', body)
        self.assertIn("authenticated historical render", body)

    def test_analyse_publish_is_hash_only_and_git_required(self):
        body = self.skill("analyse")
        self.assertNotRegex(body, r"source\.sql|history/<revision>\.sql|git optional")
        self.assertIn("snapshot verifies", body.lower())
        self.assertIn("history/review/<revision>.json", body)
        self.assertIn("sql_provenance", body)

    def test_generated_sql_absent_is_not_scope_before_sql(self):
        body = self.skill("bootstrap")
        self.assertIn("Generated SQL may be absent", body)
        self.assertIn("adapter", body)
        self.assertIn("sql_provenance", body)

    def test_explain_materializes_exact_revisions_and_cleans_up(self):
        body = self.skill("explain")
        self.assertNotRegex(body, r"source\.sql|history/[^\n]*\.sql")
        self.assertRegex(body, r'materialize "\$SLUG" review "\$PREVIOUS" "\$T/previous.sql"')
        self.assertRegex(body, r'materialize "\$SLUG" review "\$REVISION" "\$T/reviewed.sql"')
        self.assertIn("trap 'rm -rf", body)
        self.assertIn("reassessment", body)

    def test_setup_ignore_rules_and_adapter_prerequisite_are_visible(self):
        body = self.skill("setup")
        for pattern in ("/reviews/**/source.sql", "/reviews/**/scope.source.sql", "/reviews/**/history/*.sql"):
            self.assertIn(pattern, body)
        self.assertIn("sql-provenance.rst", body)
        self.assertIn("scaffold#290", body)

    def test_bootstrap_header_check_renders_absent_generated_sql(self):
        body = self.skill("bootstrap")
        self.assertNotIn('if [ -f "<sql path>" ]', body)
        self.assertIn('sr_source_render HEAD "$SQL_PATH" "$T/current.sql"', body)

    def test_all_changed_skills_remain_small(self):
        for name in ("setup", "bootstrap", "analyse", "explain"):
            with self.subTest(name=name):
                self.assertLessEqual(len(self.skill(name).splitlines()), 500)

    def test_documented_notes_inspects_absent_generated_sql_and_cleans_up(self):
        from test_sql_review_scripts import Project, review_doc, run
        from test_sql_review_sources import ADAPTER
        from test_sql_review_notes import HEADER, BODY
        self.assertNotIn('notes "<sql path>"', self.skill("analyse"))
        reference = (REPO / "skills/data-request-analyse/references/source-notes.rst").read_text()
        block = re.search(r"\.\. code-block:: bash\n\n((?:    .*\n|\n)+)", reference)
        self.assertIsNotNone(block)
        recipe = textwrap.dedent(block.group(1)).replace("<sql path>", "sql/request.sql")
        with tempfile.TemporaryDirectory() as tmp:
            project = Project(tmp)
            root = project.root
            (root / "sql").mkdir()
            (root / ".gitignore").write_text("sql/request.sql\n")
            (root / "payload").write_text(HEADER + BODY)
            (root / "render.sh").write_text(ADAPTER)
            config = root / ".sqlreview/config.json"
            settings = json.loads(config.read_text())
            settings["sql_render"] = {"command": ["bash", "render.sh"]}
            config.write_text(json.dumps(settings))
            (root / "sql/provenance.json").write_text(json.dumps({"schema": 1, "requests": {
                "sql/request.sql": {"source": "builder"}}}))
            project.commit()
            fp = json.loads(run(["fingerprint", "sql/request.sql"], root).stdout)
            draft = project.write_json("sql__request", "review.draft.json", review_doc(
                "sql__request", **fp, logic=[], open_questions=[]))
            published = run(["publish", "sql__request", "review", str(draft)], root)
            self.assertEqual(published.returncode, 0, published.stderr)
            env = dict(os.environ, S=str(REPO / "skills/data-request-setup/scripts"), SLUG="sql__request")
            before = set(Path("/tmp").glob("sqlreview-notes.*"))

            def execute(expected):
                result = subprocess.run(["bash", "-c", recipe], cwd=root, env=env,
                                        capture_output=True, text=True, timeout=60)
                self.assertEqual(result.returncode, expected, result.stdout + result.stderr)
                self.assertEqual(set(Path("/tmp").glob("sqlreview-notes.*")), before)
                self.assertFalse((root / "sql/request.sql").exists())
                self.assertEqual(list((root / ".sqlreview").rglob("*.sql")), [])
                return result

            notes = json.loads(execute(0).stdout)
            self.assertTrue(notes["present"])
            explain = re.search(r"```bash\n(bash -s --.*?\nSH\n)```", self.skill("explain"), re.S).group(1)
            explain_before = set(Path("/tmp").glob("sqlreview-explain.*"))
            result = subprocess.run(["bash", "-c", explain], cwd=root, env=env,
                                    capture_output=True, text=True, timeout=60)
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            self.assertIn('"present": true', result.stdout)
            self.assertEqual(set(Path("/tmp").glob("sqlreview-explain.*")), explain_before)
            original_recipe = recipe
            recipe = recipe.replace('sr_source_clean || exit $?', 'kill -TERM $$')
            execute(143)  # Signal traps remove the disposable caller directory too.
            recipe = original_recipe
            (root / "payload").write_text("SELECT 2;\n")
            execute(2)  # A dirty source fails, with the caller's directory cleaned.
            (root / "payload").write_text(HEADER + BODY)
            recipe = recipe.replace('review.draft.json', 'missing.json')
            execute(2)  # Notes failure also cleans a successfully rendered temporary SQL.

    def test_no_snapshot_rollout_capability_is_packaged(self):
        for tree in ("plugins/data-request", "dist/codex/plugins/data-request"):
            for path in (REPO / tree).rglob("*"):
                if path.is_file():
                    with self.subTest(path=str(path.relative_to(REPO))):
                        self.assertNotIn("migrate_sqlreview_snapshots", path.name)
                        self.assertNotIn("sqlreview-snapshot-hashes.json", path.read_text())
                        self.assertNotRegex(path.read_text(), r"migrate_sqlreview_snapshots|migrate-snapshots")

    def test_temporary_shell_examples_parse(self):
        reference = (REPO / "skills/data-request-setup/references/sql-provenance.rst").read_text()
        snippet = textwrap.dedent(reference[reference.index('    bash -s --'):reference.index('    SH') + 6])
        examples = [snippet] + re.findall(r"```bash\n(.*?)```", self.skill("explain"), re.S)
        examples += re.findall(r"```bash\n(.*?)```", self.skill("bootstrap"), re.S)
        examples += re.findall(r"```bash\n(.*?)```", self.skill("analyse"), re.S)
        for example in examples:
            with self.subTest(example=example.splitlines()[0]):
                result = subprocess.run(["bash", "-n"], input=example + "\n", text=True, capture_output=True)
                self.assertEqual(result.returncode, 0, result.stderr)

    def test_strict_gate_selects_sql_source_cases(self):
        text = (REPO / "scripts/run_bash32_portability.py").read_text()
        self.assertIn("test_sql_review_sources_bash32.Bash32Sources.test_adapter_historical_publish_and_carry", text)


if __name__ == "__main__":
    unittest.main()
