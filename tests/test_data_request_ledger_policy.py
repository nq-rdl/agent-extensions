"""L5: ledger resume never hashes a data/ file or unreviewed sql/ (the #552 path policy).

A ledger artifact records a path and a SHA-256. If resume hashed data/00_raw/x.csv and compared it to the
recorded digest, a changed ledger would confirm a guess about researcher values. Resume now applies the
path policy first. A refused artifact is not read, its stage is rechecked, and one fixed message goes to
stderr. Synthetic data only: the ZZTEST marker stands in for a researcher value.
"""
import copy
import hashlib
import importlib
import json
import unittest

# `unittest discover -s tests` puts tests/ on sys.path; `-m unittest tests.x` does not
base = importlib.import_module(f"{__package__}.test_data_request_ledger" if __package__ else "test_data_request_ledger")

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


def legacy_entry(ticket=TICKET):
    """An entry saved before the rename: its SQL revision key is the old name sql."""
    doc = entry(ticket)
    doc["evidence_revision"] = {"ticket": "2026-09-29", "sql": "abc123"}
    doc["stage_evidence"]["draft"]["sources"] = ["sql"]
    return doc


class LedgerSqlCommitKey(unittest.TestCase):
    """The scaffold data-plane sweep refuses a field named sql, so the ledger writes sql_commit.

    Ledgers saved with the old key stay readable, and set renames the key so the store can be committed.
    """
    setUp = base.Ledger.setUp
    run_helper = base.Ledger.run_helper
    save = base.Ledger.save

    def write_store(self, *entries):
        self.dest.parent.mkdir(parents=True, exist_ok=True)
        self.dest.write_text(json.dumps({"schemaVersion": 1, "entries": list(entries)}))

    def test_sql_commit_is_accepted_and_stored_as_given(self):
        self.save()
        stored = json.loads(self.dest.read_text())["entries"][0]
        self.assertEqual(stored["evidence_revision"], {"ticket": "2026-09-29", "sql_commit": "abc123"})
        self.assertNotIn('"sql"', self.dest.read_text())

    def test_an_existing_ledger_with_the_old_key_is_still_read(self):
        self.write_store(legacy_entry())
        self.run_helper("check", str(self.dest))
        self.assertEqual(json.loads(self.run_helper("get", TICKET).stdout), legacy_entry())
        current = self.root / "current.json"
        for revisions in ({"ticket": "2026-09-29", "sql": "abc123"}, {"ticket": "2026-09-29", "sql_commit": "abc123"}):
            with self.subTest(revisions=revisions):
                current.write_text(json.dumps(revisions))
                self.assertEqual(json.loads(self.run_helper("get", TICKET, "--against", str(current)).stdout)["recheck"], [])
        current.write_text(json.dumps({"ticket": "2026-09-29", "sql_commit": "def456"}))
        self.assertEqual(json.loads(self.run_helper("get", TICKET, "--against", str(current)).stdout)["recheck"], ["draft"])

    def test_a_new_ledger_compares_against_old_current_revisions(self):
        self.save()
        current = self.root / "current.json"
        current.write_text(json.dumps({"ticket": "2026-09-29", "sql": "abc123"}))
        self.assertEqual(json.loads(self.run_helper("get", TICKET, "--against", str(current)).stdout)["recheck"], [])

    def test_set_saves_the_old_key_as_sql_commit_with_a_hint(self):
        other = "rdl-service-desk/service-desk#904"
        self.write_store(legacy_entry(other))
        r = self.save(legacy_entry())
        self.assertIn("sql_commit", r.stderr)
        self.assertNotIn("abc123", r.stderr)
        text = self.dest.read_text()
        self.assertNotIn('"sql"', text)
        for stored in json.loads(text)["entries"]:
            with self.subTest(ticket=stored["ticket"]):
                self.assertEqual(stored["evidence_revision"]["sql_commit"], "abc123")
                self.assertEqual(stored["stage_evidence"]["draft"]["sources"], ["sql_commit"])
        self.assertEqual(json.loads(self.run_helper("get", TICKET).stdout), entry())

    def test_both_keys_in_one_entry_are_refused(self):
        doc = entry()
        doc["evidence_revision"]["sql"] = "abc123"
        r = self.save(doc, ok=False)
        self.assertEqual(r.returncode, 4)
        self.assertIn("evidence_revision", r.stderr)
        self.assertIn("sql_commit", r.stderr)
        self.assertFalse(self.dest.exists())

    CLASH = "field evidence_revision has both sql and sql_commit (rule: use sql_commit only)"

    def assert_clash_refused(self, r, *values):
        self.assertEqual(r.returncode, 4, r.stderr)
        self.assertIn(self.CLASH, r.stderr)
        self.assertEqual(r.stdout, "")
        for text in (*values, str(self.root)):
            self.assertNotIn(text, r.stderr)

    def test_a_stored_entry_with_both_keys_is_refused_on_every_read(self):
        # A completed stage names sql. A comparison that preferred sql_commit would miss the change to sql.
        current = self.root / "current.json"
        current.write_text(json.dumps({"ticket": "2026-09-29", "sql": "ZZTEST-NEW"}))
        for old in ("ZZTEST-OLD", "abc123"):
            doc = legacy_entry()
            doc["evidence_revision"].update(sql=old, sql_commit="abc123")
            self.write_store(doc)
            before = self.dest.read_bytes()
            for args in (("check", str(self.dest)), ("get", TICKET), ("get", TICKET, "--against", str(current)),
                         ("waivers", TICKET, "0" * 40)):
                with self.subTest(sql=old, args=args):
                    self.assert_clash_refused(self.run_helper(*args, ok=False), old, "ZZTEST-NEW")
            with self.subTest(sql=old, args="set"):
                # A write for another ticket must not carry the clashing entry forward.
                other = "rdl-service-desk/service-desk#904"
                self.draft.write_text(json.dumps(entry(other)))
                self.assert_clash_refused(self.run_helper("set", other, str(self.draft), ok=False), old)
                self.assertEqual(self.dest.read_bytes(), before)

    def test_current_revisions_with_both_keys_are_refused(self):
        current = self.root / "current.json"
        for stored in (entry(), legacy_entry()):
            for sql in ("ZZTEST-NEW", "abc123"):
                with self.subTest(stored=stored["evidence_revision"], sql=sql):
                    self.write_store(stored)
                    current.write_text(json.dumps({"ticket": "2026-09-29", "sql": sql, "sql_commit": "abc123"}))
                    self.assert_clash_refused(self.run_helper("get", TICKET, "--against", str(current), ok=False), sql)


def waiver(**changes):
    doc = {"gate": "ci", "check": "unit-tests", "head_sha": "0123456789abcdef0123456789abcdef01234567",
           "issue": "example-org/example-scaffold#12", "by": "engineer-handle", "at": "2026-11-11",
           "source": "https://github.com/example-org/example-request/pull/4#issuecomment-1001",
           "reason": "Known scaffold test failure, not caused by this request"}
    doc.update(changes)
    return doc


class LedgerGateWaivers(unittest.TestCase):
    """A waiver names the check, the head it applies to, the human who waived it and their written record."""
    setUp = base.Ledger.setUp
    run_helper = base.Ledger.run_helper
    save = base.Ledger.save
    HEAD = "0123456789abcdef0123456789abcdef01234567"

    def with_waivers(self, *waivers):
        doc = entry()
        doc["gate_waivers"] = list(waivers)
        return doc

    def test_a_complete_waiver_validates_and_round_trips(self):
        doc = self.with_waivers(waiver(), waiver(check="framework-tests",
                                                 source="https://github.com/example-org/example-request/pull/4#pullrequestreview-77"))
        self.save(doc)
        self.assertEqual(json.loads(self.run_helper("get", TICKET).stdout), doc)

    def test_incomplete_or_agent_waivers_are_refused_by_field(self):
        cases = [("gate", waiver(gate="sql-review")), ("check", waiver(check=" ")),
                 ("head_sha", waiver(head_sha="abc123")), ("issue", waiver(issue="see chat")),
                 ("by", waiver(by="jane.smith@example.org")), ("by", waiver(by="claude")),
                 ("by", waiver(by="github-actions[bot]")), ("source", waiver(source="unlinked (verbal)")),
                 ("source", waiver(source="https://github.com/example-org/example-request/pull/4")),
                 ("reason", waiver(reason="")), ("at", {k: v for k, v in waiver().items() if k != "at"}),
                 ("extra", waiver(extra="x"))]
        for field, bad in cases:
            with self.subTest(field=field, waiver=bad):
                r = self.save(self.with_waivers(bad), ok=False)
                self.assertEqual(r.returncode, 4)
                self.assertIn("field gate_waivers", r.stderr)
                self.assertFalse(self.dest.exists())

    def test_a_tab_or_newline_in_a_waiver_field_is_refused(self):
        # The waivers command prints tab-separated rows, so a control character could forge or split a row.
        for field in ("check", "at", "by"):
            for bad in ("x\twaived", "x\ny"):
                with self.subTest(field=field, bad=bad):
                    r = self.save(self.with_waivers(waiver(**{field: bad})), ok=False)
                    self.assertEqual(r.returncode, 4)
                    self.assertIn("field gate_waivers", r.stderr)

    def test_a_duplicate_waiver_for_one_check_and_head_is_refused(self):
        r = self.save(self.with_waivers(waiver(), waiver(reason="again")), ok=False)
        self.assertEqual(r.returncode, 4)

    def test_waivers_apply_only_to_the_head_they_name(self):
        other = "fedcba9876543210fedcba9876543210fedcba98"
        self.save(self.with_waivers(waiver(), waiver(check="framework-tests", head_sha=other)))
        rows = self.run_helper("waivers", TICKET, self.HEAD).stdout.splitlines()
        self.assertEqual(rows, [
            "waived\tci\tunit-tests\tengineer-handle\t2026-11-11\t"
            "https://github.com/example-org/example-request/pull/4#issuecomment-1001",
            "lapsed\tci\tframework-tests\thead " + other[:12]])
        self.assertEqual(self.run_helper("waivers", TICKET, other).stdout.splitlines()[0][:6], "lapsed")

    def test_waivers_without_any_waiver_print_nothing(self):
        self.save()
        self.assertEqual(self.run_helper("waivers", TICKET, self.HEAD).stdout, "")

    def test_waivers_need_a_full_head_sha_and_a_stored_ticket(self):
        self.save()
        self.assertEqual(self.run_helper("waivers", TICKET, "abc123", ok=False).returncode, 4)
        self.assertEqual(self.run_helper("waivers", "rdl-service-desk/service-desk#905", self.HEAD, ok=False).returncode, 6)


class LedgerDeliveryStages(unittest.TestCase):
    """The operator run, UAT and hand-off are stages of their own."""
    setUp = base.Ledger.setUp
    run_helper = base.Ledger.run_helper
    save = base.Ledger.save

    def test_run_uat_and_handoff_are_stages(self):
        doc = entry()
        doc["stage"] = "handoff"
        doc["stages_done"] = doc["stages_done"] + ["validate", "analyse", "run", "uat"]
        for stage in ("validate", "analyse", "run", "uat"):
            doc["stage_evidence"][stage] = {"sources": ["sql_commit"], "artifacts": []}
        self.save(doc)
        self.assertEqual(json.loads(self.run_helper("get", TICKET).stdout), doc)


class LedgerRefusalNamesTheField(unittest.TestCase):
    """A refused entry names the field that failed and the expected ticket form, never a value."""
    setUp = base.Ledger.setUp
    run_helper = base.Ledger.run_helper
    save = base.Ledger.save

    def test_each_refusal_names_its_field(self):
        for field, value in (("stage", "unknown"), ("verification", {"status": "verified"}),
                             ("owner", "jane.smith@example.org"), ("next_action", "")):
            with self.subTest(field=field):
                bad = copy.deepcopy(entry())
                bad[field] = value
                r = self.save(bad, ok=False)
                self.assertEqual(r.returncode, 4)
                self.assertIn("field " + field, r.stderr)
                self.assertNotIn("example.org", r.stderr)
                self.assertNotIn(str(self.draft), r.stderr)

    def test_a_bad_ticket_names_the_expected_form(self):
        r = self.run_helper("get", "903", ok=False)
        self.assertEqual(r.returncode, 4)
        self.assertIn("owner/repo#N", r.stderr)


if __name__ == "__main__":
    unittest.main()
