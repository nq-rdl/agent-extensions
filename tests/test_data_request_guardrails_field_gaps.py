"""Skill-contract tests for the /data-request:guardrails field gaps.

Issues #370-#374, #380, #386, #388 and #389 each found a fact the guardrails skill
(and the shared lift-ledger contract in setup/references/lifts.rst) did not carry.
These tests pin the load-bearing tokens of each fix, the unsafe wordings a review
found (negative tests), that long material lives in linked references, and that the
packaged Claude Code and Codex copies carry the same content. No model call is made.
"""

import re
import unittest
from pathlib import Path

import yaml

REPO = Path(__file__).resolve().parent.parent
CANON = REPO / "skills" / "data-request-guardrails"
SKILL = CANON / "SKILL.md"
REFS = CANON / "references"
CLAUDE_COPY = REPO / "plugins" / "data-request" / "skills" / "guardrails"
CODEX_COPY = REPO / "dist" / "codex" / "plugins" / "data-request" / "skills" / "guardrails"
LIFTS = REPO / "skills" / "data-request-setup" / "references" / "lifts.rst"
LIFTS_COPIES = (
    LIFTS,
    REPO / "plugins" / "data-request" / "skills" / "setup" / "references" / "lifts.rst",
    REPO / "dist" / "codex" / "plugins" / "data-request" / "skills" / "setup" / "references" / "lifts.rst",
)
REFERENCES = ("performance.rst", "sources.rst", "checklist.rst", "release.rst", "modelling.rst")
# The sentence guardrails, lifts.rst and map share for proposal-only entries (#372).
PROPOSAL_ONLY = ("A proposal-only entry authorises no hand SQL: none is committed or run, "
                 "except exempt probes, until a writable run publishes the entry.")


def frontmatter(path: Path) -> dict:
    return yaml.safe_load(path.read_text().split("---\n", 2)[1]) or {}


def body(path: Path) -> str:
    return path.read_text().split("---\n", 2)[2]


def flat(text: str) -> str:
    """Collapse line wrapping so a token pin survives re-wrapping."""
    return re.sub(r"\s+", " ", text)


def section(text: str, heading: str) -> str:
    """The Markdown section under `## <heading>` up to the next `## ` heading."""
    match = re.search(r"^## " + re.escape(heading) + r"[^\n]*\n(.*?)(?=^## |\Z)", text, re.M | re.S)
    if not match:
        raise AssertionError(f"SKILL.md has no '## {heading}' section")
    return flat(match.group(1))


def ref(name: str) -> str:
    return flat((REFS / name).read_text())


def shipped_files():
    """Every guardrails file in all three trees, plus every copy of lifts.rst."""
    for root in (CANON, CLAUDE_COPY, CODEX_COPY):
        yield from sorted(p for p in root.rglob("*") if p.is_file())
    yield from LIFTS_COPIES


class Packaging(unittest.TestCase):
    def test_references_are_rst_and_linked_from_skill(self):
        self.assertEqual({p.name for p in REFS.iterdir()}, set(REFERENCES))
        text = body(SKILL)
        for name in REFERENCES:
            with self.subTest(ref=name):
                self.assertIn(f"](references/{name})", text)

    def test_references_packaged_for_claude_and_codex(self):
        for root in (CLAUDE_COPY, CODEX_COPY):
            for name in REFERENCES:
                copy = root / "references" / name
                with self.subTest(copy=str(copy.relative_to(REPO))):
                    self.assertTrue(copy.is_file(), "run pixi run bash scripts/sync-plugins.sh data-request")
                    self.assertEqual(copy.read_text(), (REFS / name).read_text())
        self.assertEqual(body(CLAUDE_COPY / "SKILL.md"), body(SKILL))
        self.assertEqual(frontmatter(CODEX_COPY / "SKILL.md")["name"], "guardrails")

    def test_lifts_contract_packaged_unchanged(self):
        for copy in LIFTS_COPIES[1:]:
            with self.subTest(copy=str(copy.relative_to(REPO))):
                self.assertEqual(copy.read_text(), LIFTS.read_text())

    def test_skill_md_stays_lean(self):
        self.assertLessEqual(len(SKILL.read_text().splitlines()), 300)


class PublicRepoHygiene(unittest.TestCase):
    """This repository is public: only fictional (9xxx) enquiry and approval IDs (#338)."""

    REAL_ID = re.compile(r"\bENQ(?!9\d{3}\b)\d+|\bSSAQHTS-(?!99)\d+|\bTHHS(?:AQUIRE|RDLENQ)-(?!9)\d+", re.I)

    def test_no_real_enquiry_ids(self):
        fragments = sorted((REPO / ".changes" / "unreleased").glob("*.yaml"))
        for path in (*shipped_files(), *fragments, Path(__file__)):
            with self.subTest(path=str(path.relative_to(REPO))):
                self.assertIsNone(self.REAL_ID.search(path.read_text()))


class Baseline(unittest.TestCase):
    """#380: query-builder v0.6.0 with consolidated resolvers; PyPika composition is compliant."""

    def test_archived_plugins_package_is_gone_everywhere(self):
        for path in shipped_files():
            with self.subTest(path=str(path.relative_to(REPO))):
                text = path.read_text()
                self.assertNotIn("query-builder-plugins", text)
                self.assertNotIn("qb_plugins", text)

    def test_compatibility_names_the_v060_baseline(self):
        compat = frontmatter(SKILL)["compatibility"]
        for token in ("query-builder 0.6.0", "resolvers/iemr", "resolvers/hbcis"):
            with self.subTest(token=token):
                self.assertIn(token, compat)
        self.assertNotIn("0.4.0", compat)

    def test_compose_section_states_baseline_and_compliant_pypika(self):
        text = section(body(SKILL), "Compose library units in requests")
        for token in ("`v0.6.0`", "resolvers/iemr/resolver.py", "resolvers/hbcis/resolver.py",
                      "TemporaryTableQueryBuilder", "TypedTable", "compliant composition"):
            with self.subTest(token=token):
                self.assertIn(token, text)
        self.assertNotIn("v0.4.0", text)

    def test_resolvers_moved_at_v050(self):
        text = section(body(SKILL), "Compose library units in requests")
        self.assertIn("Since v0.5.0 the source resolvers", text)

    def test_lifts_example_uses_the_consolidated_package(self):
        text = LIFTS.read_text()
        self.assertIn('"library": "nq-rdl/query-builder", "pinned_version": "v0.6.0"', text)
        self.assertIn("resolvers/iemr/resolver.py", text)


class LegacyOrg(unittest.TestCase):
    """#373: the retired org, or a pin below the baseline, is flagged before new SQL."""

    def setUp(self):
        self.text = section(body(SKILL), "Compose library units in requests")

    def test_retired_org_is_flagged(self):
        for token in ("rdl-service-desk/query-builder", "retired legacy org", "**blocker**",
                      "re-pin", "before drafting new SQL", "`v0.1.1`"):
            with self.subTest(token=token):
                self.assertIn(token, self.text)
        self.assertIn("rdl-service-desk/query-builder", frontmatter(SKILL)["compatibility"])

    def test_missing_apis_are_named_per_version(self):
        # register_result exists at v0.4.1 and v0.5.0; only the analysis-notes API is new in v0.6.0.
        self.assertRegex(self.text, r"Below `v0\.6\.0`, `record_assumption` and `record_limitation` are absent")
        self.assertRegex(self.text, r"`v0\.1\.1`[^.]*lacks `register_result`")

    def test_scaffold_default_and_delivered_enquiries(self):
        self.assertIn("scaffold (v0.5.0) still defaults to query-builder v0.5.0", self.text)
        for token in ("already-delivered", "no backport"):
            with self.subTest(token=token):
                self.assertIn(token, self.text)


class ModellingChoices(unittest.TestCase):
    """#374 (sequence example, HBCIS death source) and #386 (ethnicity convention)."""

    def setUp(self):
        self.text = section(body(SKILL), "Leave modelling choices to the researcher")
        self.ref = ref("modelling.rst")

    def test_cohort_sequence_example(self):
        self.assertIn("**Cohort sequence or transition date:**", self.text)
        self.assertIn("](references/modelling.rst)", self.text)
        for token in ("transition date", "paediatric", "attended states", "hard gate"):
            with self.subTest(token=token):
                self.assertIn(token, self.ref)

    def test_mortality_points_to_hbcis_death_source(self):
        mortality = self.text.split("**Mortality:**", 1)[1].split("- **", 1)[0]
        self.assertIn("DeathDate", mortality)
        self.assertIn("separation mode", mortality)

    def test_ethnicity_convention(self):
        ethnicity = self.text.split("**Ethnicity:**", 1)[1]
        for token in ("PERSON_INFO", "Indigenous status", "country of birth", "preferred language",
                      "optional surrogates", "ethnicity is not held"):
            with self.subTest(token=token):
                self.assertIn(token, ethnicity)
        self.assertIn("requester or engineer decides", self.ref)
        self.assertIn("PERSON.LANGUAGE_CD", self.ref)


class PerformanceFallbacks(unittest.TestCase):
    """#370: no-plan metadata route, unindexed tables, probe design and read isolation."""

    def setUp(self):
        self.ref = ref("performance.rst")

    def test_no_plan_route_uses_catalog_metadata(self):
        for token in ("SHOWPLAN", "VIEW DATABASE STATE", "sys.partitions", "sys.indexes",
                      "sys.index_columns", "sys.columns"):
            with self.subTest(token=token):
                self.assertIn(token, self.ref)
        self.assertRegex(self.ref, r"``mart_v`` views[^.]*return no index rows")
        self.assertIn("SHOWPLAN", section(body(SKILL), "Confirm sources before using a fact"))

    def test_unindexed_tables_scan_once_into_temp(self):
        self.assertIn("Bound the scan by date", self.ref)
        self.assertIn("Scan the source once into a ``#temp``", self.ref)
        self.assertIn("DataGrip", self.ref)
        perf = section(body(SKILL), "Performance: shift the anchor")
        self.assertIn("#temp", perf)
        self.assertIn("](references/performance.rst)", perf)

    def test_probe_design_rules(self):
        for token in ("MIN and MAX", "GROUPING SETS", "COUNT(DISTINCT", "clinician",
                      "local-only", "OBSERVED", "INFERRED"):
            with self.subTest(token=token):
                self.assertIn(token, self.ref)

    def test_min_max_restricted_and_suppressed(self):
        self.assertIn("never of an identifier, name or free-text column", self.ref)
        self.assertIn("Suppress the MIN and MAX of a small cell", self.ref)

    def test_codes_are_category_codes_never_staff_keys(self):
        for text in (self.ref, flat(LIFTS.read_text())):
            with self.subTest():
                self.assertIn("category or type codes", text)
                self.assertIn("never staff or person keys", text)
        self.assertNotIn("codes only, never names", self.ref)

    def test_threshold_parameter_comes_from_the_assessment(self):
        self.assertIn("@min_cell", self.ref)
        self.assertIn("de-identification assessment", self.ref)
        self.assertNotIn("that the operator sets", self.ref)

    def test_read_isolation_rule(self):
        skill = section(body(SKILL), "Read isolation")
        for text in (self.ref, skill):
            for token in ("READ_ISOLATION.md", "isolation_level", "ADR 0004", "NOLOCK"):
                with self.subTest(token=token):
                    self.assertIn(token, text)
        self.assertIn("record an assumption", skill)
        self.assertIn("record_assumption()", self.ref)

    def test_nolock_is_never_framed_as_expected_practice(self):
        compose = section(body(SKILL), "Compose library units in requests")
        skill = section(body(SKILL), "Read isolation")
        self.assertIn("records any `NOLOCK` or `READ UNCOMMITTED` use", compose)
        self.assertIn("Record any `NOLOCK` or `READ UNCOMMITTED` use", skill)
        for bad in ("`NOLOCK` use recorded", "suits feasibility counts and probes"):
            with self.subTest(bad=bad):
                self.assertNotIn(bad, flat(body(SKILL)))


class SourceEvidence(unittest.TestCase):
    """#371: fallback evidence order, dataops paths, per-source grain, crosswalk, currency."""

    def setUp(self):
        self.ref = ref("sources.rst")

    def test_fallback_order(self):
        order = [self.ref.index(t) for t in ("1. **dataops**", "2. **query-builder** ``schema_extracts",
                                             "3. **query-builder** ``ColumnMeta``",
                                             "4. **An operator probe**")]
        self.assertEqual(order, sorted(order))
        for token in ("OBSERVED", "INFERRED", "not yet curated", "resolvers/bireporting/tables.py"):
            with self.subTest(token=token):
                self.assertIn(token, self.ref)
        confirm = section(body(SKILL), "Confirm sources before using a fact")
        self.assertIn("](references/sources.rst)", confirm)
        order = [confirm.index(t) for t in ("dataops, then", "`schema_extracts/`", "`ColumnMeta`",
                                            "operator probe")]
        self.assertEqual(order, sorted(order))

    def test_dataops_locations(self):
        for token in ("src/da/mappings/catalog/ieMR/*.yaml", "marts/bronze/iemr/ddl/",
                      "ieMR_Raw.Raw", "ieMR.dbo"):
            with self.subTest(token=token):
                self.assertIn(token, self.ref)

    def test_every_source_gets_its_own_grain_check(self):
        joins = section(body(SKILL), "Join and index patterns")
        for token in ("own grain check", "SCH_APPT", "one row per role", "OPD_Appointments",
                      "mart_iemr_hbcis_mapping_*"):
            with self.subTest(token=token):
                self.assertIn(token, joins)
        self.assertIn("SCH_APPT", self.ref)

    def test_crosswalk_and_currency_caveat(self):
        for token in ("mart_iemr_hbcis_mapping_episode_encounter_view", "Guard uniqueness",
                      "VALID_UNTIL_DT_TM", "docs/sources/data-caveats.md"):
            with self.subTest(token=token):
                self.assertIn(token, self.ref)


class LiftGate(unittest.TestCase):
    """#372: proposal-only mode for read-only or store-less mapping runs; exempt probes."""

    def setUp(self):
        self.lifts = flat(LIFTS.read_text())
        self.compose = section(body(SKILL), "Compose library units in requests")

    def test_lifts_contract_has_proposal_only_mode_and_probe_exemption(self):
        tail = self.lifts.split("No published entry means no hand SQL.", 1)[1]
        for token in ("proposal-only", "read-only", "``.sqlreview/``", "as text in the task output",
                      "aggregate-only", "small-cell", "single scan", "NOLOCK",
                      "Do not run ``init`` or ``publish``", "outside this gate"):
            with self.subTest(token=token):
                self.assertIn(token, tail)

    def test_shared_proposal_only_sentence(self):
        for name, text in (("guardrails", self.compose), ("lifts.rst", self.lifts)):
            with self.subTest(where=name):
                self.assertIn(PROPOSAL_ONLY, text)
                self.assertNotIn("the hand SQL stays a proposal", text)

    def test_mapping_never_initialises_and_uses_an_or_trigger(self):
        for name, text in (("guardrails", self.compose), ("lifts.rst", self.lifts)):
            with self.subTest(where=name):
                self.assertIn("A mapping run never initialises", text)
                self.assertRegex(text, r"read-only, (?:the|when the) repository cannot be written, or "
                                       r"(?:when )?a mapping run finds no")
                self.assertNotIn("and cannot be written", text)
                self.assertNotIn("and the agent may not write to it", text)
        # Stages that own the store still initialise it (line ~10 of lifts.rst).
        head = self.lifts.split("No published entry means no hand SQL.", 1)[0]
        self.assertIn("setup, bootstrap", head)
        self.assertIn("``sqlreview.sh init``", head)

    def test_guardrails_probe_exemption_matches_lifts(self):
        self.assertIn("**proposal-only mode**", self.compose)
        for token in ("aggregate-only", "small-cell suppressed", "single scan",
                      "no patient identifier", "feeds no delivered extract"):
            with self.subTest(token=token):
                self.assertIn(token, self.compose)
                self.assertIn(token.replace("feeds no", "feed no"), self.lifts)
        # #413: clinician names are not personal information, so neither file exempts them.
        for text in (self.compose, self.lifts):
            self.assertNotIn("clinician identifier", text)


class PersonalInformation(unittest.TestCase):
    """#413: the 2026-09-28 ruling that clinician names are not personal information."""

    def setUp(self):
        self.release = ref("release.rst")
        self.ref = ref("performance.rst")

    def test_patient_identifiers_listed_and_clinician_names_excluded(self):
        for token in ("name, URN/MRN, date of birth, address, Medicare number and free text",
                      "clinician names are not personal information", "2026-09-28",
                      "OPD_Appointments.Resource", "Staff and person keys stay out",
                      "small-cell suppression still applies", "overrides this ruling"):
            with self.subTest(token=token):
                self.assertIn(token, self.release)

    def test_pii_scan_allowlists_exact_labels_never_patient_names(self):
        for token in ("Presidio ``PERSON``", "data-analysis-scaffold v0.5.0", "``.pii-allowlist``",
                      "exact label", "Never allowlist a patient's name"):
            with self.subTest(token=token):
                self.assertIn(token, self.release)

    def test_skill_points_to_the_ruling(self):
        release = section(body(SKILL), "Release conventions")
        self.assertIn("Clinician and resource names are not personal information", release)
        self.assertIn('"Personal information" in `release.rst`', release)

    def test_probe_redacts_only_patient_names(self):
        self.assertIn("Free of patient identifiers", self.ref)
        self.assertIn("pastes those labels as they are", self.ref)
        self.assertIn("Only a label that looks like a patient's name is written as \"name removed\"",
                      self.ref)
        self.assertNotIn("such as a clinician or resource name", self.ref)
        self.assertNotIn("Free of identifying values", self.ref)

    def test_lifts_defers_to_the_ruling(self):
        self.assertIn("Clinician and resource names are not patient identifiers",
                      flat(LIFTS.read_text()))


class Checklist(unittest.TestCase):
    """#388: seven hand-SQL defect patterns, each with symptom and fix."""

    PATTERNS = ("23:59:59.999", "UNIQUE INDEX", "Noradrenaline", "ciclosporin", "frusemide",
                "AEST", "FORMAT()", "ED encounter", "event-set explode")

    def test_each_pattern_with_symptom_and_fix(self):
        raw = (REFS / "checklist.rst").read_text()
        text = flat(raw)
        for token in self.PATTERNS:
            with self.subTest(token=token):
                self.assertIn(token, text)
        self.assertEqual(len(re.findall(r"^Symptom$", raw, re.M)), 7)
        self.assertEqual(len(re.findall(r"^Fix$", raw, re.M)), 7)

    def test_linked_from_review_section(self):
        self.assertIn("](references/checklist.rst)", section(body(SKILL), "Review hand SQL"))


class ReleaseConventions(unittest.TestCase):
    """#389: raw vs derived, listings kept out of delivery, study IDs, suppression source."""

    def setUp(self):
        self.ref = ref("release.rst")
        self.skill = section(body(SKILL), "Release conventions")

    def test_four_conventions(self):
        for token in ("Raw dates or a derived outcome", "-- @extract: <name> internal",
                      "Study IDs", "ROW_NUMBER()", "link table", "Small-cell suppression"):
            with self.subTest(token=token):
                self.assertIn(token, self.ref)

    def test_default_keeps_listings_out_of_the_delivery_run(self):
        default = self.ref.index("keep them out of the delivery run")
        self.assertLess(default, self.ref.index("-- @extract: <name> internal"))
        self.assertIn("lands in the delivered workbook", self.ref)
        self.assertIn("v0.5.0", self.ref)
        self.assertNotIn("Mark each such result batch", self.ref)

    def test_skill_release_rule_carries_the_runner_condition(self):
        for token in ("out of the delivery run", "`-- @extract: <name> internal`", "only after confirming",
                      "`scripts/run_extract.py`", "v0.5.0"):
            with self.subTest(token=token):
                self.assertIn(token, self.skill)

    def test_study_id_link_table_never_in_an_extract_by_default(self):
        step3 = self.ref.split("3. ", 1)[1].split("4. ", 1)[0]
        self.assertIn("never goes in any extract of the delivery run", step3)
        self.assertIn("only when the pinned runner supports the flag", step3)
        for path in shipped_files():
            with self.subTest(path=str(path.relative_to(REPO))):
                self.assertNotIn("as an internal extract", flat(path.read_text()))
        self.assertIn("not yet confirmed as a house convention", self.ref)

    def test_threshold_is_not_invented(self):
        for token in ("de-identification assessment", "Cell suppression threshold",
                      "deidentification-assessment.md", "Do not choose a number"):
            with self.subTest(token=token):
                self.assertIn(token, self.ref)
        self.assertIn("](references/release.rst)", self.skill)
        self.assertIn("de-identification assessment", self.skill)
        self.assertIn("ask and record it", self.skill)
        numeric = re.compile(r"(?i)(?:threshold of|fewer than|less than|below|under|<)\s*\d+")
        for name, text in (("release section", self.skill), ("release.rst", self.ref),
                           ("performance.rst", ref("performance.rst"))):
            with self.subTest(where=name):
                self.assertIsNone(numeric.search(text))


if __name__ == "__main__":
    unittest.main()
