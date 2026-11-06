"""L5: ledger resume never hashes a data/ file or unreviewed sql/ (the #552 path policy).

A ledger artifact records a path and a SHA-256. If resume hashed data/00_raw/x.csv and compared it to the
recorded digest, a changed ledger would confirm a guess about researcher values. Resume now applies the
path policy first. A refused artifact is not read, its stage is rechecked, and one fixed message goes to
stderr. Synthetic data only: the ZZTEST marker stands in for a researcher value.
"""
import hashlib
import json
import unittest

try:  # `unittest discover -s tests` puts tests/ on sys.path; `-m unittest tests.x` does not
    import test_data_request_ledger as base
except ModuleNotFoundError:
    import tests.test_data_request_ledger as base

TICKET, entry = base.TICKET, base.entry

MARKER = "ZZTEST-90210-ROW"
MESSAGE = "ledger artifact not read: data/ and unreviewed sql/ paths are refused"


class LedgerArtifactPolicy(unittest.TestCase):
    # Reuse the fixture of the ledger tests without running them again.
    setUp = base.Ledger.setUp
    run_helper = base.Ledger.run_helper
    save = base.Ledger.save

    def resume(self, rel, text):
        """Save a ledger whose draft artifact is REL with the digest of TEXT, then resume against it."""
        target = self.root / rel
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(text)
        (self.root / ".sqlreview").mkdir(exist_ok=True)
        doc = entry()
        doc["stage_evidence"]["draft"]["artifacts"] = [{"path": rel, "sha256": hashlib.sha256(text.encode()).hexdigest()}]
        self.save(doc)
        current = self.root / "current.json"
        current.write_text(json.dumps(doc["evidence_revision"]))
        return self.run_helper("get", TICKET, "--against", str(current))

    def test_a_data_path_is_not_hashed_and_its_stage_is_rechecked(self):
        # The digest matches the file, so a hashing resume would report no recheck.
        r = self.resume("data/00_raw/x.csv", f"id,value\n1,{MARKER}\n")
        self.assertEqual(json.loads(r.stdout)["recheck"], ["draft"])
        self.assertIn(MESSAGE, r.stderr)
        self.assertNotIn(MARKER, r.stdout + r.stderr)
        self.assertNotIn("x.csv", r.stderr)

    def test_an_unreviewed_sql_path_is_not_hashed(self):
        for rel in ("sql/pipeline_a/q.sql", "sql/loose.sql", "Data/x.csv"):
            with self.subTest(rel=rel):
                r = self.resume(rel, f"-- {MARKER}\nSELECT 1;\n")
                self.assertEqual(json.loads(r.stdout)["recheck"], ["draft"])
                self.assertIn(MESSAGE, r.stderr)

    def test_a_reviewed_sql_path_and_a_plain_path_are_still_hashed(self):
        for rel in ("sql/v1/q.sql", "sql/v2.1/q.sql", "query.sql"):
            with self.subTest(rel=rel):
                r = self.resume(rel, "SELECT 1;\n")
                self.assertEqual(json.loads(r.stdout)["recheck"], [])
                self.assertNotIn(MESSAGE, r.stderr)


if __name__ == "__main__":
    unittest.main()
