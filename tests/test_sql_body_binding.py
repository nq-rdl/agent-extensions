"""Header edits preserve binding without relaxing snapshots or human decisions (#432)."""
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

    def publish(self, doc):
        draft = self.d / "draft.json"
        draft.write_text(json.dumps(doc))
        return run(["publish", "q", doc["kind"], str(draft)], self.p.root)

    def doc(self, kind="review", **over):
        return (review_doc if kind == "review" else scope_doc)("q", "q.sql", sql_sha256=sha(OLD),
                                                               sql_body_sha256=sha(BODY), **over)

    def test_fingerprint_keeps_both_hashes(self):
        self.p.commit()
        fp = json.loads(run(["fingerprint", "q.sql"], self.p.root).stdout)
        self.assertEqual(fp["sql_sha256"], sha(OLD))
        self.assertEqual(fp["sql_body_sha256"], sha(BODY))

    def test_header_publish_snapshot_status_delta_and_render(self):
        for kind in ("scope", "review"):
            self.assertEqual(self.publish(self.doc(kind)).returncode, 0)
        (self.d / "scope.source.sql").write_text(OLD)
        self.assertEqual(run(["snapshot", "q", "q.sql"], self.p.root).returncode, 0)
        self.sql.write_text(NEW)
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
            self.assertNotEqual(self.publish(self.doc()).returncode, 0)
            self.assertIn("stale", run(["status"], self.p.root).stdout)
            self.assertEqual(run(["delta", "q"], self.p.root).returncode, 10)

    def test_corrupt_snapshot_cannot_be_saved_by_body_match(self):
        self.assertEqual(self.publish(self.doc()).returncode, 0)
        run(["snapshot", "q", "q.sql"], self.p.root)
        (self.d / "source.sql").write_text(NEW)  # even header corruption destroys full-file evidence
        self.sql.write_text(NEW)
        self.assertIn("stale", run(["status"], self.p.root).stdout)
        self.assertNotEqual(self.publish(self.doc()).returncode, 0)
        self.assertNotEqual(run(["snapshot", "q", "q.sql"], self.p.root).returncode, 0)

    def test_legacy_full_hash_is_not_silently_upgraded_without_baseline(self):
        legacy = self.doc()
        del legacy["sql_body_sha256"]
        self.sql.write_text(NEW)
        self.assertNotEqual(self.publish(legacy).returncode, 0)

    def test_body_match_cannot_carry_changed_assumption(self):
        self.assertEqual(self.publish(self.doc()).returncode, 0)
        run(["snapshot", "q", "q.sql"], self.p.root)
        self.sql.write_text(NEW)
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
    def test_existing_scope_header_republish_requires_original_baseline(self):
        for legacy in (False, True):
            with self.subTest(legacy=legacy), tempfile.TemporaryDirectory() as tmp:
                p = Project(tmp)
                sql = p.sql("q.sql", OLD)
                d = p.review_dir("q")
                doc = scope_doc("q", "q.sql", sql_sha256=sha(OLD))
                if not legacy:
                    doc["sql_body_sha256"] = sha(BODY)
                published = p.write_json("q", "scope.json", doc)
                original = published.read_bytes()
                sql.write_text(NEW)
                result = run(["publish", "q", "scope", str(published)], p.root)
                self.assertEqual(result.returncode, 2, result.stdout + result.stderr)
                self.assertEqual(published.read_bytes(), original)
                # Restoring authenticated original bytes enables the same-revision path.
                (d / "scope.source.sql").write_text(OLD)
                result = run(["publish", "q", "scope", str(published)], p.root)
                self.assertEqual(result.returncode, 0, result.stderr)
                self.assertEqual(json.loads(published.read_text())["revision"], 1)
                self.assertEqual((d / "scope.source.sql").read_text(), OLD)

    def test_missing_scope_baseline_allows_full_reassessment_with_current_fingerprint(self):
        with tempfile.TemporaryDirectory() as tmp:
            p = Project(tmp)
            p.sql("q.sql", NEW)
            p.write_json("q", "scope.json", scope_doc("q", "q.sql", sql_sha256=sha(OLD),
                                                       sql_body_sha256=sha(BODY)))
            fresh = scope_doc("q", "q.sql", revision=2, sql_sha256=sha(NEW), sql_body_sha256=sha(BODY))
            for item in fresh["assumptions"] + fresh["limitations"]:
                item["confirmed_revision"] = 2
            draft = p.write_json("q", "scope.draft.json", fresh)
            result = run(["publish", "q", "scope", str(draft)], p.root)
            self.assertEqual(result.returncode, 0, result.stderr)

    def test_scope_alone_retains_header_binding_and_refuses_body_or_snapshot_corruption(self):
        with tempfile.TemporaryDirectory() as tmp:
            p = Project(tmp)
            sql = p.sql("q.sql", OLD)
            d = p.review_dir("q")
            doc = scope_doc("q", "q.sql", sql_sha256=sha(OLD), sql_body_sha256=sha(BODY))
            p.write_json("q", "scope.json", doc)
            baseline = d / "scope.source.sql"
            baseline.write_text(OLD)
            sql.write_text(NEW)
            self.assertIn("scoped-header-only", run(["status"], p.root).stdout)
            sql.write_text(NEW.replace("SELECT 1", "SELECT 2"))
            self.assertIn("stale", run(["status"], p.root).stdout)
            sql.write_text(NEW)
            baseline.write_text(NEW)
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

    def test_header_body_match_cannot_create_a_historical_snapshot_without_original_bytes(self):
        with tempfile.TemporaryDirectory() as tmp:
            p = Project(tmp)
            p.sql("q.sql", NEW)
            d = p.review_dir("q")
            doc = review_doc("q", "q.sql", sql_sha256=sha(OLD), sql_body_sha256=sha(BODY))
            draft = d / "review.draft.json"
            draft.write_text(json.dumps(doc))
            self.assertEqual(run(["publish", "q", "review", str(draft)], p.root).returncode, 0)
            result = run(["snapshot", "q", "q.sql"], p.root)
            self.assertNotEqual(result.returncode, 0)
            self.assertFalse((d / "source.sql").exists())
