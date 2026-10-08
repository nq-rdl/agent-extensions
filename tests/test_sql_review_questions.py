"""Issue 437: shared question lifecycle, real helper and consumers (not a live agent pilot)."""
import copy
import json
import os
import shutil
import subprocess
import tempfile
import time
import unittest
from pathlib import Path

from test_sql_review_scripts import Project, REPO, SCRIPT, SQL_V1, git, run, scope_doc, review_doc
from test_sql_review_hooks import GUARD, decision, edit_event, env_for, run_hook, write_event

CLOSED = {"answer": "Use the approved wards.", "by": "engineer-login", "at": "2026-09-29",
          "source": "request.md#answer"}


class Questions(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.p = Project(self.tmp.name)
        self.p.sql("q.sql", SQL_V1)
        (self.p.root / ".gitignore").write_text("questions.draft.json\n")
        self.p.commit()
        fp = json.loads(run(["fingerprint", "q.sql"], self.p.root).stdout)
        self.d = self.p.review_dir("q")
        self.p.write_json("q", "scope.json", scope_doc("q", **fp, open_questions=["Which wards?", "Which wards?"]))
        self.p.write_json("q", "review.json", review_doc("q", **fp, open_questions=["Which wards?", "Count transfers?"]))
        self.assertEqual(run(["snapshot", "q", "q.sql"], self.p.root).returncode, 0)
        self.store = self.d / "questions.json"
        self.draft = self.p.root / "questions.draft.json"

    def migrate(self):
        r = run(["migrate-questions", "q"], self.p.root)
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
        return json.loads(self.store.read_text())

    def publish(self, doc):
        self.draft.write_text(json.dumps(doc))
        return run(["publish-questions", "q", str(self.draft)], self.p.root)

    def bytes(self):
        return {str(p.relative_to(self.d)): p.read_bytes() for p in self.d.rglob("*") if p.is_file()}

    def test_migration_and_closure_change_only_one_file_preserving_all_sql_evidence(self):
        before = self.bytes()
        doc = self.migrate()
        self.assertEqual({k: v for k, v in self.bytes().items() if k != "questions.json"}, before)
        self.assertEqual([(q["id"], q["applies"], q["owner"]) for q in doc["questions"]],
                         [("Q1", "scope", None), ("Q2", "review", None)])
        before = self.bytes()
        doc["questions"][0].update(status="closed", closed=CLOSED)
        self.assertEqual(self.publish(doc).returncode, 0)
        after = self.bytes()
        self.assertEqual([k for k in before if before[k] != after[k]], ["questions.json"])
        self.assertEqual(run(["delta", "q"], self.p.root).returncode, 0)
        self.assertEqual(json.loads(run(["status", "--json"], self.p.root).stdout)["reviews"][0]["state"], "current")

    def test_read_and_render_shared_and_review_only_questions_with_closure(self):
        doc = self.migrate()
        doc["questions"][0].update(status="closed", closed=CLOSED)
        self.assertEqual(self.publish(doc).returncode, 0)
        for kind in ("scope", "review"):
            r = run(["questions", "q", kind], self.p.root)
            self.assertEqual(r.returncode, 0, r.stderr)
            rows = json.loads(r.stdout)["questions"]
            self.assertEqual([q["id"] for q in rows], ["Q1"] if kind == "scope" else ["Q1", "Q2"])
            self.assertEqual(run(["render", "q", kind], self.p.root).returncode, 0)
            text = (self.d / (kind + ".md")).read_text()
            for token in ("Q1", "closed", CLOSED["answer"], CLOSED["by"], CLOSED["source"], "2026-09-29"):
                self.assertIn(token, text)
            self.assertEqual("Count transfers?" in text, kind == "review")
            open_section = text.split("## Open questions\n", 1)[1].split("\n## ", 1)[0]
            self.assertNotIn("Q1", open_section)
            self.assertNotIn(CLOSED["answer"], open_section)
            self.assertEqual("Q2" in open_section, kind == "review")
            history = text.split("## Closed questions\n", 1)[1].split("\n## ", 1)[0]
            self.assertIn("Q1", history)
            self.assertNotIn("Q2", history)

    def test_decision_origin_is_independent_visible_and_date_precision_is_retained(self):
        doc = self.migrate()
        origin = {"by": "requester-login", "role": "requester", "at": "2026-09-28", "source": "unlinked (verbal)"}
        doc["questions"][0].update(status="closed", closed=CLOSED, decided=origin)
        self.assertEqual(self.publish(doc).returncode, 0)
        stored = json.loads(self.store.read_text())["questions"][0]
        self.assertEqual(stored["decided"], origin)
        self.assertEqual(stored["closed"], CLOSED)
        self.assertEqual(run(["render", "q", "scope"], self.p.root).returncode, 0)
        text = (self.d / "scope.md").read_text()
        for token in ("requester-login", "engineer-login", "2026-09-28", "2026-09-29", "UNLINKED"):
            self.assertIn(token, text)

    def test_malformed_drafts_and_failed_migration_preserve_evidence(self):
        before = self.bytes()
        scope = scope_doc("q", "q.sql", open_questions=[42])
        self.p.write_json("q", "scope.json", scope)
        r = run(["migrate-questions", "q"], self.p.root)
        self.assertEqual(r.returncode, 4)
        self.assertFalse(self.store.exists())
        (self.d / "scope.json").write_bytes(before["scope.json"])
        self.migrate()
        before = self.bytes()
        for raw in ("{", "[]", "{}", "{} {}"):
            self.draft.write_text(raw)
            self.assertEqual(run(["publish-questions", "q", str(self.draft)], self.p.root).returncode, 4)
            self.assertEqual(self.bytes(), before)
        self.draft.unlink()
        self.draft.symlink_to(self.store)
        self.assertEqual(run(["publish-questions", "q", str(self.draft)], self.p.root).returncode, 2)
        self.assertEqual(self.bytes(), before)

    def test_overlapping_publishers_refuse_busy_store_then_reconcile_stale_draft(self):
        doc = self.migrate()
        added = copy.deepcopy(doc)
        added["questions"].append({"id": "Q3", "text": "New question?", "applies": "review",
                                   "owner": None, "status": "open"})
        self.draft.write_text(json.dumps(added))
        closed = copy.deepcopy(doc)
        closed["questions"][0].update(status="closed", closed=CLOSED)
        other = self.p.root / "closure.draft.json"
        other.write_text(json.dumps(closed))
        # Pause the first real publisher after loading history, before staging its draft.
        wrappers = self.p.root / "wrappers"
        wrappers.mkdir()
        ready, resume = self.p.root / "ready", self.p.root / "resume"
        cp = wrappers / "cp"
        cp.write_text('#!/usr/bin/env bash\n: > "$READY"\n'
                      'while [ ! -f "$RESUME" ]; do sleep 0.02; done\nexec "$REAL_CP" "$@"\n')
        cp.chmod(0o755)
        env = {k: v for k, v in os.environ.items() if not k.startswith("SQLREVIEW_")}
        env.update(PATH=str(wrappers) + os.pathsep + env["PATH"], READY=str(ready),
                   RESUME=str(resume), REAL_CP=shutil.which("cp"))
        first = subprocess.Popen(["bash", str(SCRIPT), "publish-questions", "q", str(self.draft)],
                                 cwd=self.p.root, env=env, stdout=subprocess.PIPE,
                                 stderr=subprocess.PIPE, text=True)
        try:
            deadline = time.monotonic() + 10
            while not ready.exists() and first.poll() is None and time.monotonic() < deadline:
                time.sleep(0.02)
            self.assertTrue(ready.exists(), "first publisher never reached staging")
            second = run(["publish-questions", "q", str(other)], self.p.root)
            migration = run(["migrate-questions", "q"], self.p.root)
        finally:
            resume.touch()
            stdout, stderr = first.communicate(timeout=15)
        self.assertEqual(first.returncode, 0, stdout + stderr)
        self.assertEqual(second.returncode, 2, second.stdout + second.stderr)
        self.assertIn("busy", second.stderr)
        self.assertEqual(migration.returncode, 2, migration.stdout + migration.stderr)
        self.assertEqual(json.loads(self.store.read_text()), added)
        self.assertFalse((self.d / ".questions.lock").exists())
        self.assertEqual(run(["publish-questions", "q", str(other)], self.p.root).returncode, 4)
        added["questions"][0].update(status="closed", closed=CLOSED)
        self.assertEqual(self.publish(added).returncode, 0)
        self.assertEqual(json.loads(self.store.read_text()), added)

    def test_symlink_before_dotdot_in_draft_is_refused_before_copy(self):
        doc = self.migrate()
        doc["questions"][0].update(status="closed", closed=CLOSED)
        before = self.bytes()
        with tempfile.TemporaryDirectory() as outside:
            external = Path(outside)
            (external / "subdir").mkdir()
            (external / "questions.draft.json").write_text(json.dumps(doc))
            (self.p.root / "link").symlink_to(external / "subdir", target_is_directory=True)
            # Lexical normalization would point at this innocent local file instead.
            self.draft.write_text(json.dumps(doc))
            for path in ("link/../questions.draft.json", str(self.p.root) + "/link/../questions.draft.json"):
                with self.subTest(path=path):
                    r = run(["publish-questions", "q", path], self.p.root)
                    self.assertEqual(r.returncode, 2, r.stdout + r.stderr)
                    self.assertIn("symlink", r.stderr)
                    self.assertEqual(self.bytes(), before)
        (self.p.root / "safe").mkdir()
        self.assertEqual(run(["publish-questions", "q", "safe/../questions.draft.json"], self.p.root).returncode, 0)

    def test_custom_open_placeholder_never_shows_closed_history(self):
        doc = self.migrate()
        doc["questions"][0].update(status="closed", closed=CLOSED)
        self.assertEqual(self.publish(doc).returncode, 0)
        template = self.p.root / ".sqlreview/templates/review.md"
        template.write_text("## Open questions\n\n{{open_questions_list}}\n")
        self.assertEqual(run(["render", "q", "review"], self.p.root).returncode, 0)
        text = (self.d / "review.md").read_text()
        self.assertIn("Q2", text)
        self.assertNotIn("Q1", text)
        self.assertEqual(template.read_text(), "## Open questions\n\n{{open_questions_list}}\n")

    def test_near_match_legacy_questions_keep_distinct_ids_and_publish_retry_keeps_bytes(self):
        self.p.write_json("q", "review.json", review_doc("q", "q.sql", open_questions=["which wards?"]))
        doc = self.migrate()
        self.assertEqual([q["text"] for q in doc["questions"]], ["Which wards?", "which wards?"])
        before = self.bytes()
        self.assertEqual(self.publish(doc).returncode, 0)
        self.assertEqual(self.bytes(), before)

    def test_legacy_read_is_read_only_and_includes_scope_questions_in_review(self):
        before = self.bytes()
        r = run(["questions", "q", "review"], self.p.root)
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertEqual(len(json.loads(r.stdout)["questions"]), 2)
        self.assertEqual(self.bytes(), before)

    def test_migration_retry_preserves_closed_questions_and_stable_ids(self):
        doc = self.migrate()
        doc["questions"][0].update(status="closed", closed=CLOSED)
        self.assertEqual(self.publish(doc).returncode, 0)
        before = self.bytes()
        self.migrate()
        self.assertEqual(self.bytes(), before)
        doc["questions"].append({"id": "Q3", "text": "New question?", "applies": "review", "owner": "analyst-login", "status": "open"})
        self.assertEqual(self.publish(doc).returncode, 0)

    def test_invalid_schema_or_unanswered_closure_is_atomic(self):
        doc = self.migrate()
        values = [{"id": "../Q1"}, {"id": "Q2"}, {"status": "answered"}, {"applies": "all"},
                  {"owner": "private@example.com"}, {"status": "closed"},
                  *[{"status": "closed", "closed": {**CLOSED, k: v}} for k in CLOSED for v in (None, "", "  ", 42)],
                  {"status": "open", "closed": CLOSED}, {"decided": {"by": "engineer-login"}}]
        before = self.bytes()
        for updates in values:
            with self.subTest(updates=updates):
                bad = copy.deepcopy(doc)
                bad["questions"][0].update(updates)
                r = self.publish(bad)
                self.assertEqual(r.returncode, 4, r.stdout + r.stderr)
                self.assertNotIn("private@example.com", r.stdout + r.stderr)
                self.assertEqual(self.bytes(), before)

    def test_closed_history_and_question_identity_cannot_be_silently_changed_or_deleted(self):
        doc = self.migrate()
        doc["questions"][0].update(status="closed", closed=CLOSED)
        self.assertEqual(self.publish(doc).returncode, 0)
        bads = [dict(doc, questions=doc["questions"][1:])]
        for updates in ({"text": "Different?"}, {"applies": "review"}, {"status": "open"},
                        {"closed": {**CLOSED, "answer": "Different"}}):
            bad = copy.deepcopy(doc)
            bad["questions"][0].update(updates)
            bads.append(bad)
        for bad in bads:
            self.assertEqual(self.publish(bad).returncode, 4)

    def test_unsafe_paths_and_slug_or_pipeline_mismatch_refused(self):
        doc = self.migrate()
        for updates in ({"slug": "other"}, {"sql_path": "other.sql"}):
            self.assertEqual(self.publish({**doc, **updates}).returncode, 4)
        self.assertEqual(run(["migrate-questions", "../q"], self.p.root).returncode, 2)
        self.store.unlink()
        outside = self.p.root / "outside.json"
        outside.write_text(json.dumps(doc))
        self.store.symlink_to(outside)
        for args in (["migrate-questions", "q"], ["questions", "q"], ["publish-questions", "q", str(outside)], ["render", "q", "review"]):
            self.assertEqual(run(args, self.p.root).returncode, 2)
        self.assertEqual(json.loads(outside.read_text()), doc)

    def test_scope_without_sql_and_explicit_store_reference(self):
        self.p.sql("q.sql", SQL_V1).unlink()
        (self.d / "review.json").unlink()
        doc = self.migrate()
        self.assertEqual(len(doc["questions"]), 1)
        scope = scope_doc("q", "q.sql")
        del scope["open_questions"]
        scope["question_store"] = "questions.json"
        self.draft.write_text(json.dumps(scope))
        self.assertEqual(run(["check", str(self.draft)], self.p.root).returncode, 0)
        self.assertEqual(run(["publish", "q", "scope", str(self.draft)], self.p.root).returncode, 4)  # still not a semantic revision
        self.p.write_json("q", "scope.json", scope)
        self.assertEqual(run(["render", "q", "scope"], self.p.root).returncode, 0)
        self.store.unlink()
        self.assertEqual(run(["render", "q", "scope"], self.p.root).returncode, 4)

    def test_new_legacy_strings_after_migration_are_not_silently_ignored(self):
        self.migrate()
        doc = scope_doc("q", "q.sql", open_questions=["New untracked question?"])
        self.p.write_json("q", "scope.json", doc)
        self.assertEqual(run(["questions", "q"], self.p.root).returncode, 4)
        self.assertEqual(run(["render", "q", "review"], self.p.root).returncode, 4)
        # Reconcile the mistaken legacy edit through the store's guarded publisher.
        store = json.loads(self.store.read_text())
        store["questions"].append({"id": "Q3", "text": "New untracked question?", "applies": "scope", "owner": None, "status": "open"})
        self.assertEqual(self.publish(store).returncode, 0)
        self.assertEqual(run(["questions", "q"], self.p.root).returncode, 0)

    def test_guard_denies_final_question_writes_and_edits_but_allows_drafts(self):
        for event in (write_event(self.store, "{}", self.p.root), edit_event(self.store, self.p.root)):
            r = run_hook(GUARD, event, env_for())
            self.assertEqual(decision(r)["permissionDecision"], "deny")
            self.assertIn("publish-questions", r.stdout)
        r = run_hook(GUARD, write_event(self.d / "questions.draft.json", "{}", self.p.root), env_for())
        self.assertEqual(r.stdout, "")

    def test_missing_or_invalid_store_is_invalid_status_without_sql_becoming_stale(self):
        self.migrate()
        self.store.write_text("{}")
        row = json.loads(run(["status", "--json", "--verbose"], self.p.root).stdout)["reviews"][0]
        self.assertEqual(row["state"], "invalid")
        self.assertIn("question", row["reason"])

    def test_first_store_can_follow_a_new_referenced_scope(self):
        for f in ("scope.json", "review.json"):
            (self.d / f).unlink()
        scope = scope_doc("q", "q.sql")
        del scope["open_questions"]
        scope["question_store"] = "questions.json"
        self.draft.write_text(json.dumps(scope))
        self.assertEqual(run(["publish", "q", "scope", str(self.draft)], self.p.root).returncode, 0)
        store = {"schemaVersion": 1, "kind": "questions", "slug": "q", "sql_path": "q.sql", "questions": [
            {"id": "Q1", "text": "Which wards?", "owner": None, "status": "open", "applies": "scope"}]}
        self.assertEqual(self.publish(store).returncode, 0)
        self.assertEqual(run(["render", "q", "scope"], self.p.root).returncode, 0)

    def test_move_rebinds_store_and_preserves_question_history(self):
        doc = self.migrate()
        doc["questions"][0].update(status="closed", closed=CLOSED)
        self.assertEqual(self.publish(doc).returncode, 0)
        self.assertEqual(run(["move", "q.sql", "new.sql"], self.p.root).returncode, 0)
        r = run(["questions", "new"], self.p.root)
        self.assertEqual(r.returncode, 0, r.stderr)
        moved = json.loads(r.stdout)
        self.assertEqual(moved["slug"], "new")
        self.assertEqual(moved["sql_path"], "new.sql")
        self.assertEqual(moved["questions"], doc["questions"])

    def test_bad_question_evidence_returns_invalid_json_not_operational_error(self):
        self.migrate()
        review = json.loads((self.d / "review.json").read_text())
        review.pop("open_questions")
        review["question_store"] = "questions.json"
        self.p.write_json("q", "review.json", review)
        git(self.p.root, "add", ".")
        git(self.p.root, "commit", "-qm", "fixture")
        release = REPO / "skills/data-request-setup/scripts/release.sh"
        for raw in (None, "{", "{}"):
            with self.subTest(raw=raw):
                if raw is None:
                    self.store.unlink()
                else:
                    self.store.write_text(raw)
                r = subprocess.run(["bash", str(release), "evidence", "HEAD", "q"],
                                   cwd=self.p.root, capture_output=True, text=True)
                self.assertEqual(r.returncode, 10, r.stdout + r.stderr)
                row = json.loads(r.stdout)["reviews"][0]
                self.assertEqual(row["applies"], "invalid")
                self.assertEqual(row["slug"], "q")
        for ref, slug in (("missing-ref", "q"), ("HEAD", "unknown-slug")):
            r = subprocess.run(["bash", str(release), "evidence", ref, slug],
                               cwd=self.p.root, capture_output=True, text=True)
            self.assertEqual(r.returncode, 2)
            self.assertEqual(r.stdout, "")

    def test_release_evidence_uses_authoritative_store_not_obsolete_embedded_copies(self):
        doc = self.migrate()
        doc["questions"][0].update(status="closed", closed=CLOSED)
        self.assertEqual(self.publish(doc).returncode, 0)
        git(self.p.root, "add", ".")
        git(self.p.root, "commit", "-qm", "fixture")
        r = subprocess.run(["bash", str(REPO / "skills/data-request-setup/scripts/release.sh"), "evidence", "HEAD", "q"],
                           cwd=self.p.root, capture_output=True, text=True)
        self.assertEqual(r.returncode, 0, r.stderr)
        row = json.loads(r.stdout)["reviews"][0]
        self.assertEqual(row["open_questions"], ["Count transfers?"])
        self.assertEqual(row["questions"][0]["closed"], CLOSED)


class Instructions(unittest.TestCase):
    def test_children_assert_ids_not_revision_numbers(self):
        for stage in ("draft", "fix"):
            text = (REPO / f"skills/data-request-{stage}/SKILL.md").read_text()
            self.assertIn("item identifier lists", text)
            self.assertIn("must not pin revision numbers", text)

    def test_authors_and_consumers_use_the_shared_question_store(self):
        for stage in ("bootstrap", "analyse", "explain", "release"):
            text = (REPO / f"skills/data-request-{stage}/SKILL.md").read_text()
            self.assertIn("questions.json", text)
            self.assertIn("sqlreview.sh\" questions", text)
