"""Header edits retain authenticated committed provenance and human decisions."""
import hashlib
import json
import tempfile
import unittest
from pathlib import Path

from tests.test_sql_review_scripts import Project, run, review_doc, scope_doc

BODY = "SELECT 1;\n-- body comment\n"
OLD = "/* analysis notes: Male or Female */\n" + BODY
NEW = "/* analysis notes: MALE or FEMALE */\n" + BODY


def sha(text):
    return hashlib.sha256(text.encode()).hexdigest()


class BodyBinding(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.p = Project(self.tmp.name)
        self.sql = self.p.sql("q.sql", OLD)
        self.d = self.p.review_dir("q")
        self.p.commit()
        self.fp = json.loads(run(["fingerprint", "q.sql"], self.p.root).stdout)

    def publish(self, doc):
        draft = self.d / "draft.json"
        draft.write_text(json.dumps(doc))
        return run(["publish", "q", doc["kind"], str(draft)], self.p.root)

    def doc(self, kind="review", **over):
        values = dict(self.fp, **over)
        return (review_doc if kind == "review" else scope_doc)("q", **values)

    def test_fingerprint_keeps_both_hashes(self):
        fp = json.loads(run(["fingerprint", "q.sql"], self.p.root).stdout)
        self.assertEqual(fp["sql_sha256"], sha(OLD))
        self.assertEqual(fp["sql_body_sha256"], sha(BODY))

    def test_header_publish_snapshot_status_delta_and_render(self):
        for kind in ("scope", "review"):
            self.assertEqual(self.publish(self.doc(kind)).returncode, 0)
        self.assertEqual(run(["snapshot", "q", "q.sql"], self.p.root).returncode, 0)
        self.sql.write_text(NEW)
        self.p.commit("header")
        self.assertIn("header-only", run(["status"], self.p.root).stdout)
        delta = run(["delta", "q"], self.p.root)
        self.assertEqual(delta.returncode, 0, delta.stderr)
        self.assertIn("header-only revision; SQL body unchanged", delta.stdout)
        self.assertIn("-/* analysis notes: Male or Female */", delta.stdout)
        self.assertIn("+/* analysis notes: MALE or FEMALE */", delta.stdout)
        self.assertNotIn("unchanged since the reviewed snapshot", delta.stdout)
        impact = run(["impact", "q"], self.p.root)
        self.assertEqual(impact.returncode, 0, impact.stderr)
        self.assertIn("no SQL body change", impact.stdout)
        self.assertNotIn("no change since the reviewed snapshot", impact.stdout)
        for kind in ("scope", "review"):
            result = self.publish(self.doc(kind))
            self.assertEqual(result.returncode, 0, result.stderr)
            stored = json.loads((self.d / f"{kind}.json").read_text())
            self.assertEqual(stored["sql_sha256"], sha(OLD))
            self.assertEqual(stored["header_revisions"][-1]["sql_sha256"], sha(NEW))
            self.assertEqual(run(["render", "q", kind], self.p.root).returncode, 0)
            self.assertIn("Header revision", (self.d / f"{kind}.md").read_text())
        result = run(["snapshot", "q", "q.sql"], self.p.root)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("header-only", run(["status"], self.p.root).stdout)

    def test_body_changes_refuse_publish_and_unbind(self):
        self.assertEqual(self.publish(self.doc()).returncode, 0)
        run(["snapshot", "q", "q.sql"], self.p.root)
        for changed in (BODY.replace("1", "2"), BODY.replace("comment", "changed"), BODY + "\n", BODY.replace("\n", "\r\n")):
            self.sql.write_bytes(("-- new header\n" + changed).encode())
            self.p.commit("body")
            self.assertNotEqual(self.publish(self.doc()).returncode, 0)
            self.assertIn("stale", run(["status"], self.p.root).stdout)
            self.assertEqual(run(["delta", "q"], self.p.root).returncode, 10)

    def test_corrupt_recorded_hash_cannot_be_saved_by_body_match(self):
        self.assertEqual(self.publish(self.doc()).returncode, 0)
        run(["snapshot", "q", "q.sql"], self.p.root)
        corrupted = json.loads((self.d / "review.json").read_text())
        corrupted["sql_sha256"] = "0" * 64
        (self.d / "review.json").write_text(json.dumps(corrupted))
        self.sql.write_text(NEW)
        self.p.commit("header")
        self.assertIn("stale", run(["status"], self.p.root).stdout)
        self.assertNotEqual(self.publish(corrupted).returncode, 0)
        self.assertNotEqual(run(["snapshot", "q", "q.sql"], self.p.root).returncode, 0)

    def test_legacy_full_hash_authenticates_source_before_header_binding(self):
        legacy = self.doc()
        del legacy["sql_body_sha256"]
        self.sql.write_text(NEW)
        self.p.commit("header")
        self.assertEqual(self.publish(legacy).returncode, 0)
        stored = json.loads((self.d / "review.json").read_text())
        self.assertEqual(stored["sql_sha256"], sha(OLD))

    def test_body_match_cannot_carry_changed_assumption(self):
        self.assertEqual(self.publish(self.doc()).returncode, 0)
        run(["snapshot", "q", "q.sql"], self.p.root)
        self.sql.write_text(NEW)
        self.p.commit("header")
        changed = self.doc(revision=2)
        changed["assumptions"][0].update(text="Changed meaning", confirmed_revision=1,
                                      carried_from_revision=1)
        changed["limitations"][0]["confirmed_revision"] = 2
        result = self.publish(changed)
        self.assertEqual(result.returncode, 4, result.stdout + result.stderr)
        self.assertIn("carried", result.stderr)


class BodyHashFixtures(unittest.TestCase):
    def test_shared_conservative_fixtures(self):
        import subprocess
        from tests.test_sql_review_scripts import REPO
        cases = json.loads((REPO / "tests/fixtures/sql-body-hashes.json").read_text())
        lib = REPO / "skills/data-request-setup/scripts/sqlreview-lib.sh"
        with tempfile.TemporaryDirectory() as tmp:
            sql = Path(tmp) / "q.sql"
            for case in cases:
                with self.subTest(case=case["name"]):
                    sql.write_bytes(case["sql"].encode())
                    result = subprocess.run(["bash", "-c", 'source "$1"; sr_body_sha256 "$2"',
                                             "body-hash", str(lib), str(sql)], capture_output=True, text=True)
                    expected = "" if case["body"] is None else sha(case["body"])
                    self.assertEqual(result.stdout.strip(), expected)
                    self.assertEqual(result.returncode == 0, case["body"] is not None)


class BindingIntegrity(BodyBinding):
    def test_inconsistent_full_and_body_pair_is_refused_without_baseline(self):
        doc = self.doc()
        doc["sql_body_sha256"] = sha(BODY.replace("1", "2"))
        self.assertNotEqual(self.publish(doc).returncode, 0)

    def test_header_history_is_helper_owned_and_cannot_be_erased_or_fabricated(self):
        self.assertEqual(self.publish(self.doc()).returncode, 0)
        run(["snapshot", "q", "q.sql"], self.p.root)
        self.sql.write_text(NEW)
        self.p.commit("header")
        self.assertEqual(self.publish(self.doc()).returncode, 0)
        original = (self.d / "review.json").read_bytes()
        for history in ([], [{"sql_sha256": "1" * 64, "at": "fake"}]):
            doc = self.doc()
            doc["header_revisions"] = history
            self.assertNotEqual(self.publish(doc).returncode, 0)
            self.assertEqual((self.d / "review.json").read_bytes(), original)
        # Omitting helper-owned history in a normal draft preserves it.
        self.assertEqual(self.publish(self.doc()).returncode, 0)
        self.assertEqual((self.d / "review.json").read_bytes(), original)

    def test_header_revision_schema_rejects_bad_entries(self):
        doc = self.doc()
        doc["header_revisions"] = [{"sql_sha256": "garbage", "at": ""}]
        result = run(["check", "--stdin"], self.p.root, stdin=json.dumps(doc))
        self.assertEqual(result.returncode, 4)


class ScopeBodyState(unittest.TestCase):
    def test_existing_scope_header_republish_requires_authenticated_original_commit(self):
        for legacy in (False, True):
            with self.subTest(legacy=legacy), tempfile.TemporaryDirectory() as tmp:
                p = Project(tmp)
                sql = p.sql("q.sql", OLD)
                p.commit()
                fp = json.loads(run(["fingerprint", "q.sql"], p.root).stdout)
                doc = scope_doc("q", **fp)
                if legacy:
                    del doc["sql_body_sha256"]
                    del doc["sql_provenance"]
                published = p.write_json("q", "scope.json", doc)
                sql.write_text(NEW)
                p.commit("header")
                result = run(["publish", "q", "scope", str(published)], p.root)
                self.assertEqual(result.returncode, 0, result.stderr)
                saved = json.loads(published.read_text())
                self.assertEqual(saved["revision"], 1)
                self.assertEqual(saved["sql_sha256"], fp["sql_sha256"])
                self.assertFalse(list((p.root / ".sqlreview").rglob("*.sql")))

    def test_missing_scope_source_evidence_allows_full_reassessment_with_current_fingerprint(self):
        with tempfile.TemporaryDirectory() as tmp:
            p = Project(tmp)
            p.sql("q.sql", NEW)
            p.commit()
            p.write_json("q", "scope.json", scope_doc("q", "q.sql", sql_sha256=sha(OLD),
                                                       sql_body_sha256=sha(BODY)))
            fp = json.loads(run(["fingerprint", "q.sql"], p.root).stdout)
            fresh = scope_doc("q", revision=2, **fp)
            draft = p.write_json("q", "scope.draft.json", fresh)
            result = run(["publish", "q", "scope", str(draft)], p.root)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertTrue((draft.parent / "history/scope/1.json").is_file())

    def test_scope_alone_retains_header_binding_and_refuses_body_or_record_corruption(self):
        with tempfile.TemporaryDirectory() as tmp:
            p = Project(tmp)
            sql = p.sql("q.sql", OLD)
            p.commit()
            fp = json.loads(run(["fingerprint", "q.sql"], p.root).stdout)
            scope = p.write_json("q", "scope.json", scope_doc("q", **fp))
            sql.write_text(NEW)
            p.commit("header")
            self.assertIn("scoped-header-only", run(["status"], p.root).stdout)
            sql.write_text(NEW.replace("SELECT 1", "SELECT 2"))
            p.commit("body")
            self.assertIn("stale", run(["status"], p.root).stdout)
            sql.write_text(NEW)
            p.commit("restore body")
            corrupt = json.loads(scope.read_text())
            corrupt["sql_sha256"] = "0" * 64
            scope.write_text(json.dumps(corrupt))
            self.assertIn("stale", run(["status"], p.root).stdout)

    def test_scope_baseline_symlink_is_not_binding_evidence(self):
        with tempfile.TemporaryDirectory() as tmp:
            p = Project(tmp)
            p.sql("q.sql", NEW)
            d = p.review_dir("q")
            p.write_json("q", "scope.json", scope_doc("q", "q.sql", sql_sha256=sha(OLD), sql_body_sha256=sha(BODY)))
            outside = Path(tmp) / "outside.sql"
            outside.write_text(OLD)
            (d / "scope.source.sql").symlink_to(outside)
            self.assertIn("stale", run(["status"], p.root).stdout)

    def test_missing_original_commit_cannot_be_saved_by_claimed_body_digest(self):
        with tempfile.TemporaryDirectory() as tmp:
            p = Project(tmp)
            p.sql("q.sql", NEW)
            p.commit()
            d = p.review_dir("q")
            doc = review_doc("q", "q.sql", sql_sha256=sha(OLD), sql_body_sha256=sha(BODY))
            draft = d / "review.draft.json"
            draft.write_text(json.dumps(doc))
            result = run(["publish", "q", "review", str(draft)], p.root)
            self.assertEqual(result.returncode, 6, result.stderr)
            self.assertFalse((d / "review.json").exists())
            self.assertFalse(list(d.rglob("*.sql")))
