"""sqlreview.sh move: a byte-identical move keeps carried evidence, a changed one forces reassessment.

Carried evidence after a move is still re-proved from git: the pre-move record is archived under
history/, and delta, remap and carryforward read the old path at the recorded commit and check the
recorded SHA (#505). The move itself never makes a confirmation.
"""
import json
import subprocess
import tempfile
import unittest
from pathlib import Path

from test_sql_review_sources import committed

try:
    from test_sql_review_scripts import Project, SQL_V1, item, review_doc, run, scope_doc
except ModuleNotFoundError:
    from tests.test_sql_review_scripts import Project, SQL_V1, item, review_doc, run, scope_doc


class Move(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.p = Project(self.tmp.name)
        self.p.sql("q.sql", SQL_V1)
        self.reviews = self.p.root / ".sqlreview" / "reviews"

    def git(self, *args):
        subprocess.run(["git", "-C", str(self.p.root), *args], check=True, capture_output=True)

    def publish(self, slug, kind, doc):
        draft = self.p.write_json(slug, kind + ".draft.json", doc)
        r = run(["publish", slug, kind, str(draft)], self.p.root)
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        draft.unlink()
        committed(self.p)

    def reviewed(self, scope=True):
        committed(self.p)
        fp = json.loads(run(["fingerprint", "q.sql"], self.p.root).stdout)
        if scope:
            self.publish("q", "scope", scope_doc("q", **fp, assumptions=[
                item("A1", "Only completed stays are in scope", location={"lines": [3, 3]})]))
        self.publish("q", "review", review_doc("q", **fp,
            assumptions=[item("A1", "Discharge date marks completion", location={"lines": [3, 3]})],
            limitations=[item("L1", "Monthly grain", location=None)],
            logic=[{"step": 1, "title": "Filter", "lines": [1, 4], "description": "Filter stays"}]))
        for kind in ("scope", "review") if scope else ("review",):
            self.assertEqual(run(["render", "q", kind], self.p.root).returncode, 0)
        committed(self.p)

    def move(self, new="new.sql", change=None):
        self.git("mv", "q.sql", new)
        if change is not None:
            (self.p.root / new).write_text(change)
        committed(self.p)
        r = run(["move", "q.sql", new], self.p.root)
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        return r, self.reviews / new.replace(".sql", "")

    def next_review(self, moved):
        draft = json.loads((moved / "review.json").read_text())
        fp = json.loads(run(["fingerprint", "new.sql"], self.p.root).stdout)
        draft.update(fp, revision=2)
        draft["changes"] = draft["changes"] + [
            {"revision": 2, "at": "2026-11-16T00:00:00Z", "by": "engineer-login", "summary": "moved"}]
        path = moved / "review.draft.json"
        path.write_text(json.dumps(draft))
        return path

    def test_byte_identical_move_keeps_carry_and_remap(self):
        self.reviewed()
        r, moved = self.move()
        self.assertIn("bytes unchanged", r.stderr)
        self.assertEqual((moved / "rebind-required").read_text(), "sql-identical\n")
        d = run(["delta", "new"], self.p.root)
        # Exit 10: the record still names the pre-move commit, so a new revision is due.
        self.assertEqual(d.returncode, 10, d.stdout + d.stderr)
        self.assertIn("unchanged since the reviewed source", d.stdout)
        self.assertIn("path moved with identical bytes", d.stdout)
        self.assertNotIn("requires reassessment", d.stdout)
        draft = self.next_review(moved)
        r = run(["remap", "new", str(draft)], self.p.root)
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertEqual(json.loads(r.stdout)["walk"], [])
        r = run(["carryforward", "new", "review", str(draft)], self.p.root)
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        verdict = json.loads(r.stdout)
        self.assertEqual({(c["id"], c["basis"]) for c in verdict["carry"]},
                         {("A1", "sql-unchanged"), ("L1", "sql-unchanged")})
        self.assertEqual(verdict["walk"], [])
        doc = json.loads(draft.read_text())
        for k in ("assumptions", "limitations"):
            for it in doc[k]:
                it.update(next(c["set"] for c in verdict["carry"] if c["id"] == it["id"]))
        draft.write_text(json.dumps(doc))
        r = run(["publish", "new", "review", str(draft)], self.p.root)
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        committed(self.p)
        r = run(["snapshot", "new", "new.sql"], self.p.root)
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertFalse((moved / "rebind-required").exists())
        rows = json.loads(run(["status", "--json"], self.p.root).stdout)["reviews"]
        self.assertEqual({row["slug"]: row["state"] for row in rows}["new"], "current")
        d = run(["delta", "new"], self.p.root)
        self.assertEqual(d.returncode, 0, d.stdout + d.stderr)
        self.assertEqual(list((self.p.root / ".sqlreview").rglob("*.sql")), [])  # #505: no SQL copies

    def test_carry_after_an_identical_move_is_still_proved_from_git(self):
        self.reviewed()
        _, moved = self.move()
        archive = moved / "history" / "review" / "1.json"
        doc = json.loads(archive.read_text())
        archive.write_text(json.dumps(dict(doc, sql_sha256="0" * 64)))
        committed(self.p)
        draft = self.next_review(moved)
        for args in (["delta", "new"], ["remap", "new", str(draft)]):
            with self.subTest(command=args[0]):
                r = run(args, self.p.root)
                self.assertEqual(r.returncode, 6, r.stdout + r.stderr)
        # carryforward reports the failed re-proof: every item is touched and walked, none carries.
        r = run(["carryforward", "new", "review", str(draft)], self.p.root)
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        out = json.loads(r.stdout)
        self.assertTrue(out["reproof_failed"])
        self.assertEqual((out["carry"], out["carry_question"]), ([], []))
        self.assertEqual(sorted(w["id"] for w in out["walk"]), ["A1", "L1"])
        # publish still refuses a carried item when the re-proof fails.
        doc = json.loads(draft.read_text())
        for k in ("assumptions", "limitations"):
            doc[k][0].update(carried_from_revision=1, carried_basis="sql-unchanged")
        draft.write_text(json.dumps(doc))
        self.assertEqual(run(["publish", "new", "review", str(draft)], self.p.root).returncode, 6)

    def test_changed_bytes_still_require_reassessment(self):
        self.reviewed()
        r, moved = self.move(change=SQL_V1.replace("IS NOT NULL", "IS NOT NULL AND ward <> 'X'"))
        self.assertIn("bytes changed", r.stderr)
        self.assertEqual((moved / "rebind-required").read_text(), "sql-changed\n")
        d = run(["delta", "new"], self.p.root)
        self.assertEqual(d.returncode, 10)
        self.assertIn("requires reassessment", d.stdout)
        self.assertEqual(run(["impact", "new"], self.p.root).returncode, 10)
        r = run(["remap", "new", str(self.next_review(moved))], self.p.root)
        self.assertEqual(r.returncode, 6, r.stdout + r.stderr)

    def test_a_later_identical_move_keeps_an_earlier_changed_marker(self):
        self.reviewed()
        _, moved = self.move(change=SQL_V1 + "-- trailing\n")
        self.git("mv", "new.sql", "third.sql")
        committed(self.p)
        self.assertEqual(run(["move", "new.sql", "third.sql"], self.p.root).returncode, 0)
        self.assertEqual((self.reviews / "third" / "rebind-required").read_text(), "sql-changed\n")

    def test_a_legacy_empty_marker_counts_as_changed(self):
        self.reviewed()
        _, moved = self.move()
        (moved / "rebind-required").write_text("")
        self.assertIn("requires reassessment", run(["delta", "new"], self.p.root).stdout)

    def test_move_before_the_file_moves_marks_changed(self):
        self.reviewed()
        r = run(["move", "q.sql", "new.sql"], self.p.root)
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        self.assertEqual((self.reviews / "new" / "rebind-required").read_text(), "sql-changed\n")

    def test_move_re_renders_the_markdown_it_replaces(self):
        self.reviewed()
        r, moved = self.move()
        self.assertEqual(r.stdout.strip().split("\t"), ["moved", "q", "new", "new.sql"])
        for kind in ("scope", "review"):
            with self.subTest(kind=kind):
                text = (moved / (kind + ".md")).read_text()
                self.assertIn("`new.sql`", text)
                self.assertNotIn("`q.sql`", text)

    def test_a_failed_render_is_named_and_does_not_fail_the_move(self):
        self.reviewed()
        (self.p.root / ".sqlreview" / "config.json").unlink()
        committed(self.p)
        r, moved = self.move()
        self.assertIn("render required", r.stderr)
        self.assertIn("sqlreview.sh render new review", r.stderr)
        self.assertFalse((moved / "review.md").exists())

    def test_an_unbound_scope_moves_without_a_marker(self):
        self.p.write_json("q", "scope.json", scope_doc("q", "q.sql", sql_sha256=None))
        committed(self.p)
        r, moved = self.move()
        self.assertFalse((moved / "rebind-required").exists())


class SkillContract(unittest.TestCase):
    """The move, carry-list and walk-question rules are stated in every shipped copy."""

    REPO = Path(__file__).resolve().parent.parent

    def copies(self, skill, leaf, rel):
        return [self.REPO / "skills" / skill / rel,
                self.REPO / "plugins" / "data-request" / "skills" / leaf / rel,
                self.REPO / "dist" / "codex" / "plugins" / "data-request" / "skills" / leaf / rel]

    def assert_tokens(self, skill, leaf, rel, tokens):
        for path in self.copies(skill, leaf, rel):
            with self.subTest(path=str(path.relative_to(self.REPO))):
                text = " ".join(path.read_text().split())
                for token in tokens:
                    self.assertIn(token, text)

    def test_carry_reference(self):
        self.assert_tokens("data-request-analyse", "analyse", "references/carry.rst", (
            "carry-list", "more than four items", "``clear`` fields", "``first_binding`` is true",
            "``header_settled``", "Delete the file after the answer",
            "decided by the Data Engineer", "``carry_question``", "**Carry all** / **Name the items to re-walk**",
            "Do not add items to the walk by your own judgement", "``reproof_failed``", "not-implemented"))

    def test_analyse_names_the_two_move_outcomes(self):
        self.assert_tokens("data-request-analyse", "analyse", "SKILL.md", (
            "path moved with identical bytes", "requires reassessment", "header_settled"))

    def test_bootstrap_walk_questions_and_locations(self):
        self.assert_tokens("data-request-bootstrap", "bootstrap", "SKILL.md", (
            "## Walk questions", "Define each id when the question first names it", "verbatim. Never shorten them",
            "Each option says what gets recorded", "exact new text counts as the re-ask",
            "never to the header comment lines", "path moved with identical bytes", "`clear` fields",
            "walks only the rows that the change touches", "`criteria-lines-unchanged`",
            "`sql_status: \"not-implemented\"`", "ask **one** carry question"))


if __name__ == "__main__":
    unittest.main()
