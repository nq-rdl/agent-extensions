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


# #505 criterion 1, static half: nothing in the data-request tree writes or stages rendered SQL under .sqlreview/.
STORE = re.compile(r"\.sqlreview|\bSR_DIR\b|\bSR_REVIEWS\b|\$target\b|\breviews/")
SQL_FILE = re.compile(r"\.sql\b")  # \b keeps ".sqlreview" from matching
# A file write: a redirection to something other than /dev/null or an fd (2>&1, >&2), or cp/mv/tee/install/ln.
WRITE_OP = re.compile(r"(?<![\d&>-])>>?(?![&>=])\s*(?!/dev/null)|\b(?:cp|mv|tee|install|ln)\b")
# Each allow-listed logical line only NAMES legacy SQL paths. It never creates one.
LEGACY_NAMING = (
    # `init` writes the store's .gitignore: the line holds the legacy patterns as text, the redirection targets .gitignore.
    "'/reviews/**/source.sql' '/reviews/**/scope.source.sql' '/reviews/**/history/*.sql'",
)
SQL_STORE_ADD = re.compile(r"git\s+add\b[^\n]*\.sqlreview[^\n]*\.sql\b")
# A line that names a .sql path under .sqlreview/ and tells the reader to write it (a refusal or "never" line is fine).
SQL_STORE_PATH = re.compile(r"\.sqlreview/\S*\.sql\b|\.sqlreview\b[^\n]{0,60}\.sql\b")
WRITE_VERB = re.compile(r"\b(?:write|writes|create|creates|save|saves|copy|copies|store|stores|stage|stages|put|cp|mv|tee)\b", re.I)
REFUSAL = re.compile(r"\b(?:never|nothing|no|not|legacy|refus\w*|den\w+|ignor\w+|without)\b", re.I)


def logical_lines(text):
    """Join backslash continuations and drop comment-only lines."""
    joined = re.sub(r"\\\n\s*", " ", text)
    return [l for l in joined.splitlines() if not l.lstrip().startswith("#")]


class NoSqlCopiesInStore(unittest.TestCase):
    def scripts(self):
        found = sorted((REPO / "skills/data-request-setup/scripts").glob("*.sh")) + sorted((REPO / "hooks").glob("data-request-*.sh"))
        self.assertTrue(found)
        return found

    def test_no_script_writes_or_copies_sql_into_the_store(self):
        for path in self.scripts():
            for line in logical_lines(path.read_text()):
                if not (STORE.search(line) and SQL_FILE.search(line) and WRITE_OP.search(line)):
                    continue
                with self.subTest(script=path.name, line=line.strip()):
                    self.assertTrue(any(n in line for n in LEGACY_NAMING), "writes a .sql file into the store")

    def test_the_scan_catches_the_leak_it_guards_against(self):
        leak = 'cp "$output" .sqlreview/reviews/leak/copy.sql'
        self.assertTrue(STORE.search(leak) and SQL_FILE.search(leak) and WRITE_OP.search(leak))
        redirect = 'printf %s "$sql" > "$SR_REVIEWS/$slug/current.sql"'
        self.assertTrue(STORE.search(redirect) and SQL_FILE.search(redirect) and WRITE_OP.search(redirect))
        for instruction in ("Write the SQL to .sqlreview/reviews/x/source.sql now", "Save a copy as .sqlreview/reviews/x/a.sql"):
            self.assertTrue(SQL_STORE_PATH.search(instruction) and WRITE_VERB.search(instruction), instruction)
            self.assertIsNone(REFUSAL.search(instruction), instruction)
        self.assertTrue(SQL_STORE_ADD.search("git add .sqlreview/reviews/x/a.sql"))
        for harmless in ('git show "$c:$p" > "$tmp/old.sql"', 'jq -r .x "$SR_REVIEWS/q/review.json" 2>/dev/null',
                         'case "$rel" in reviews/*/source.sql) decide deny "legacy" ;;'):
            self.assertFalse(STORE.search(harmless) and SQL_FILE.search(harmless) and WRITE_OP.search(harmless), harmless)

    def test_no_instruction_adds_or_writes_sql_under_the_store(self):
        docs = sorted(REPO.glob("skills/data-request-*/SKILL.md")) + sorted(REPO.glob("skills/data-request-*/references/*.rst"))
        self.assertTrue(docs)
        for path in docs:
            text = path.read_text()
            with self.subTest(doc=str(path.relative_to(REPO))):
                self.assertIsNone(SQL_STORE_ADD.search(text), "stages SQL under .sqlreview")
                for line in text.splitlines():
                    if SQL_STORE_PATH.search(line) and WRITE_VERB.search(line):
                        self.assertTrue(REFUSAL.search(line), f"tells the reader to write SQL under .sqlreview: {line.strip()}")


if __name__ == "__main__":
    unittest.main()
