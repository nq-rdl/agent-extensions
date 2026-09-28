"""Skill-contract tests for the /data-request:guardrails field gaps.

Issues #370-#374, #380, #386, #388 and #389 each found a fact the guardrails skill
(and the shared lift-ledger contract in setup/references/lifts.rst) did not carry.
These tests pin the load-bearing tokens of each fix, check that long material lives
in linked references, and check that the packaged Claude Code and Codex copies carry
the same content. No model call is made.
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
REFERENCES = ("performance.rst", "sources.rst", "checklist.rst", "release.rst")


def frontmatter(path: Path) -> dict:
    return yaml.safe_load(path.read_text().split("---\n", 2)[1]) or {}


def body(path: Path) -> str:
    return path.read_text().split("---\n", 2)[2]


def section(text: str, heading: str) -> str:
    """The Markdown section under `## <heading>` up to the next `## ` heading."""
    match = re.search(r"^## " + re.escape(heading) + r"[^\n]*\n(.*?)(?=^## |\Z)", text, re.M | re.S)
    if not match:
        raise AssertionError(f"SKILL.md has no '## {heading}' section")
    return match.group(1)


def ref(name: str) -> str:
    return (REFS / name).read_text()


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
                    self.assertEqual(copy.read_text(), ref(name))
        self.assertEqual(body(CLAUDE_COPY / "SKILL.md"), body(SKILL))
        self.assertEqual(frontmatter(CODEX_COPY / "SKILL.md")["name"], "guardrails")

    def test_lifts_contract_packaged_unchanged(self):
        for copy in LIFTS_COPIES[1:]:
            with self.subTest(copy=str(copy.relative_to(REPO))):
                self.assertEqual(copy.read_text(), LIFTS.read_text())

    def test_skill_md_stays_lean(self):
        self.assertLessEqual(len(SKILL.read_text().splitlines()), 300)


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
                      "TemporaryTableQueryBuilder", "TypedTable"):
            with self.subTest(token=token):
                self.assertIn(token, text)
        self.assertRegex(text, r"TemporaryTableQueryBuilder[^.]*TypedTable[^.]*compliant composition")
        self.assertNotIn("v0.4.0", text)

    def test_lifts_example_uses_the_consolidated_package(self):
        text = LIFTS.read_text()
        self.assertIn('"library": "nq-rdl/query-builder", "pinned_version": "v0.6.0"', text)
        self.assertIn("resolvers/iemr/resolver.py", text)


class LegacyOrg(unittest.TestCase):
    """#373: the retired rdl-service-desk org, or a pin below the baseline, blocks drafting."""

    def test_retired_org_is_a_blocker_before_drafting(self):
        text = section(body(SKILL), "Compose library units in requests")
        self.assertIn("rdl-service-desk/query-builder", text)
        self.assertRegex(text, r"rdl-service-desk/query-builder`? is the retired legacy org")
        self.assertRegex(text, r"below `v0\.6\.0`, is a \*\*blocker\*\*")
        self.assertRegex(text, r"re-pin[^.]*before drafting")
        self.assertIn("rdl-service-desk/query-builder", frontmatter(SKILL)["compatibility"])


class ModellingChoices(unittest.TestCase):
    """#374 (sequence example, HBCIS death source) and #386 (ethnicity convention)."""

    def setUp(self):
        self.text = section(body(SKILL), "Leave modelling choices to the researcher")

    def test_cohort_sequence_example(self):
        self.assertRegex(self.text, r"\*\*Cohort sequence or transition date:\*\*")
        for token in ("transition date", "paediatric", "attended"):
            with self.subTest(token=token):
                self.assertIn(token, self.text)

    def test_mortality_points_to_hbcis_death_source(self):
        mortality = self.text.split("**Mortality:**", 1)[1].split("- **", 1)[0]
        self.assertIn("DeathDate", mortality)
        self.assertIn("separation mode", mortality)

    def test_ethnicity_convention(self):
        ethnicity = self.text.split("**Ethnicity:**", 1)[1].split("\n\n", 1)[0]
        for token in ("PERSON_INFO", "Indigenous status", "country of birth",
                      "preferred language", "optional surrogates"):
            with self.subTest(token=token):
                self.assertIn(token, ethnicity)
        self.assertRegex(ethnicity, r"requester\s+or engineer decides")
        self.assertRegex(ethnicity, r"limitation that ethnicity is not held")


class PerformanceFallbacks(unittest.TestCase):
    """#370: no-plan metadata route, unindexed tables, probe design and read isolation."""

    def setUp(self):
        self.ref = ref("performance.rst")

    def test_no_plan_route_uses_catalog_metadata(self):
        for token in ("SHOWPLAN", "VIEW DATABASE STATE", "sys.partitions", "sys.indexes",
                      "sys.index_columns", "sys.columns"):
            with self.subTest(token=token):
                self.assertIn(token, self.ref)
        self.assertRegex(self.ref, r"``mart_v`` views[^.]*return no\s+index rows")
        self.assertIn("SHOWPLAN", section(body(SKILL), "Confirm sources before using a fact"))

    def test_unindexed_tables_scan_once_into_temp(self):
        self.assertRegex(self.ref, r"(?i)bound the scan by date")
        self.assertRegex(self.ref, r"(?i)scan the source once into a ``#temp``")
        self.assertIn("DataGrip", self.ref)
        perf = section(body(SKILL), "Performance: shift the anchor")
        self.assertIn("#temp", perf)
        self.assertIn("](references/performance.rst)", perf)

    def test_probe_design_rules(self):
        for token in ("MIN and MAX", "GROUPING SETS", "COUNT(DISTINCT", "clinician",
                      "local-only", "codes only", "OBSERVED", "INFERRED"):
            with self.subTest(token=token):
                self.assertIn(token, self.ref)

    def test_read_isolation_rule(self):
        for text in (self.ref, section(body(SKILL), "Read isolation")):
            for token in ("READ_ISOLATION.md", "isolation_level", "ADR 0004", "NOLOCK"):
                with self.subTest(token=token):
                    self.assertIn(token, text)
        self.assertRegex(section(body(SKILL), "Read isolation"),
                         r"reads uncommitted data, record an assumption")
        self.assertIn("record_assumption()", self.ref)


class SourceEvidence(unittest.TestCase):
    """#371: fallback evidence order, dataops paths, per-source grain, crosswalk, currency."""

    def setUp(self):
        self.ref = ref("sources.rst")

    def test_fallback_order(self):
        order = [self.ref.index(t) for t in ("1. **dataops**", "2. **query-builder** ``schema_extracts",
                                             "3. **query-builder** ``ColumnMeta``",
                                             "4. **An operator probe**")]
        self.assertEqual(order, sorted(order))
        self.assertIn("OBSERVED", self.ref)
        self.assertIn("INFERRED", self.ref)
        self.assertIn("not yet curated", self.ref)
        confirm = section(body(SKILL), "Confirm sources before using a fact")
        self.assertIn("](references/sources.rst)", confirm)
        self.assertRegex(confirm, r"dataops, then query-builder\s+`schema_extracts/`, then `ColumnMeta`")

    def test_dataops_locations(self):
        for token in ("src/da/mappings/catalog/ieMR/*.yaml", "marts/bronze/iemr/ddl/",
                      "ieMR_Raw.Raw", "ieMR.dbo"):
            with self.subTest(token=token):
                self.assertIn(token, self.ref)

    def test_every_source_gets_its_own_grain_check(self):
        joins = section(body(SKILL), "Join and index patterns")
        self.assertRegex(joins, r"Every source needs its own grain check")
        for token in ("SCH_APPT", "one row per role", "OPD_Appointments", "mart_iemr_hbcis_mapping_*"):
            with self.subTest(token=token):
                self.assertIn(token, joins)
        self.assertIn("SCH_APPT", self.ref)

    def test_crosswalk_and_currency_caveat(self):
        self.assertIn("mart_iemr_hbcis_mapping_episode_encounter_view", self.ref)
        self.assertRegex(self.ref, r"(?i)guard uniqueness")
        self.assertIn("VALID_UNTIL_DT_TM", self.ref)
        self.assertIn("docs/sources/data-caveats.md", self.ref)


class LiftGate(unittest.TestCase):
    """#372: proposal-only mode for read-only runs; aggregate probes sit outside the gate."""

    def test_lifts_contract_has_proposal_only_mode_and_probe_exemption(self):
        text = LIFTS.read_text()
        tail = text.split("No published entry means no hand SQL.", 1)[1]
        for token in ("proposal-only", "read-only", "``.sqlreview/``", "as text in the task output",
                      "aggregate-only", "small-cell", "single scan", "NOLOCK"):
            with self.subTest(token=token):
                self.assertIn(token, tail)
        self.assertRegex(tail, r"(?i)do not run ``init`` or ``publish``")
        self.assertRegex(tail, r"outside this gate")

    def test_guardrails_states_both_rules(self):
        text = section(body(SKILL), "Compose library units in requests")
        self.assertIn("**proposal-only mode**", text)
        self.assertRegex(text, r"single-scan operator probes with `NOLOCK` use recorded are\s+outside the gate")


class Checklist(unittest.TestCase):
    """#388: seven hand-SQL defect patterns, each with symptom and fix."""

    PATTERNS = ("23:59:59.999", "UNIQUE INDEX", "Noradrenaline", "ciclosporin", "frusemide",
                "AEST", "FORMAT()", "ED\n   encounter", "event-set explode")

    def test_each_pattern_with_symptom_and_fix(self):
        text = ref("checklist.rst")
        for token in self.PATTERNS:
            with self.subTest(token=token):
                self.assertIn(token, text)
        self.assertEqual(len(re.findall(r"^Symptom$", text, re.M)), 7)
        self.assertEqual(len(re.findall(r"^Fix$", text, re.M)), 7)

    def test_linked_from_review_section(self):
        self.assertIn("](references/checklist.rst)", section(body(SKILL), "Review hand SQL"))


class ReleaseConventions(unittest.TestCase):
    """#389: raw vs derived, internal marker, study IDs, suppression without an invented threshold."""

    def setUp(self):
        self.ref = ref("release.rst")

    def test_four_conventions(self):
        for token in ("Raw dates or a derived outcome", "-- @extract: <name> internal",
                      "Study IDs", "ROW_NUMBER()", "link table", "Small-cell suppression"):
            with self.subTest(token=token):
                self.assertIn(token, self.ref)

    def test_old_runner_hazard_is_stated(self):
        self.assertIn("v0.5.0", self.ref)
        self.assertRegex(self.ref, r"lands in the delivered\s+workbook")

    def test_threshold_is_not_invented(self):
        self.assertRegex(self.ref, r"governing approval")
        self.assertRegex(self.ref, r"(?i)do not\s+choose a number")
        release = section(body(SKILL), "Release conventions")
        self.assertIn("](references/release.rst)", release)
        self.assertRegex(release, r"governing approval's threshold; if none is stated, ask\s+and record it")
        numeric = re.compile(r"(?i)(?:threshold of|fewer than|less than|below|under|<)\s*\d+")
        for name, text in (("release section", release), ("release.rst", self.ref),
                           ("performance.rst", ref("performance.rst"))):
            with self.subTest(where=name):
                self.assertIsNone(numeric.search(text))


if __name__ == "__main__":
    unittest.main()
