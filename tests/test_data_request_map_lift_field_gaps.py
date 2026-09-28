"""Skill-contract tests for the map and lift field gaps (#375, #383, #385, #372, #380, #386, #367).

These pin the non-inferable rules the September enquiries showed were missing, in the
section where each belongs, and check that stale references are gone from the canonical
skills and from both packaged copies (Claude Code and Codex). No model call is made.
"""

import json
import re
import unittest
from pathlib import Path

import yaml

REPO = Path(__file__).resolve().parent.parent
LEAVES = ("map", "lift")


def canon(leaf: str) -> Path:
    return REPO / "skills" / f"data-request-{leaf}"


def copies(leaf: str) -> dict[str, Path]:
    return {
        "canonical": canon(leaf),
        "claude": REPO / "plugins" / "data-request" / "skills" / leaf,
        "codex": REPO / "dist" / "codex" / "plugins" / "data-request" / "skills" / leaf,
    }


def frontmatter(path: Path) -> dict:
    return yaml.safe_load(path.read_text().split("---\n", 2)[1]) or {}


def body(path: Path) -> str:
    return path.read_text().split("---\n", 2)[2]


def files(root: Path) -> list[Path]:
    return sorted(p for p in root.rglob("*") if p.is_file())


def raw_section(text: str, heading: str) -> str:
    """The Markdown section under `## <heading>` up to the next `## ` heading."""
    match = re.search(r"^## " + re.escape(heading) + r"[^\n]*\n(.*?)(?=^## |\Z)", text, re.M | re.S)
    if not match:
        raise AssertionError(f"SKILL.md has no '## {heading}' section")
    return match.group(1)


def section(text: str, heading: str) -> str:
    """The same section with whitespace collapsed, so wrapping does not matter."""
    return " ".join(raw_section(text, heading).split())


def flat(text: str) -> str:
    return " ".join(text.split())


MAP = flat(body(canon("map") / "SKILL.md"))
MAP_RAW = body(canon("map") / "SKILL.md")
LIFT = flat(body(canon("lift") / "SKILL.md"))
LIFT_RAW = body(canon("lift") / "SKILL.md")


class Packaging(unittest.TestCase):
    def test_packaged_copies_match_the_canonical_body(self):
        for leaf in LEAVES:
            paths = copies(leaf)
            with self.subTest(leaf=leaf):
                claude = paths["claude"] / "SKILL.md"
                self.assertTrue(claude.is_file(), "run pixi run bash scripts/sync-plugins.sh data-request")
                self.assertEqual(body(claude), body(paths["canonical"] / "SKILL.md"))
                self.assertEqual(frontmatter(paths["codex"] / "SKILL.md")["name"], leaf)


class GuardrailsInvocation(unittest.TestCase):
    """#375: map invokes the guardrails skill instead of reading its file."""

    def test_no_guardrails_file_path_in_map_or_its_copies(self):
        for target, root in copies("map").items():
            for path in files(root):
                with self.subTest(target=target, path=path.name):
                    self.assertNotIn("skills/guardrails/SKILL.md", path.read_text())

    def test_map_invokes_guardrails_first(self):
        self.assertRegex(MAP_RAW.split("\n## ", 1)[0], r"Invoke `/data-request:guardrails` first")

    def test_codex_copy_uses_the_codex_invocation(self):
        text = (copies("map")["codex"] / "SKILL.md").read_text()
        self.assertIn("`$data-request:guardrails`", text)
        self.assertNotIn("/data-request:guardrails", text)


class MapInputsAndOutput(unittest.TestCase):
    """#383: flexible rows, answers.yaml, hand SQL and a partial map."""

    def test_inputs_name_answers_yaml_and_hand_sql(self):
        inputs = section(MAP_RAW, "Inputs")
        self.assertIn("`cohort/request.json`", inputs)
        self.assertRegex(inputs, r"legacy shell's `answers\.yaml`")
        self.assertIn("From hand SQL", inputs)
        self.assertRegex(inputs, r"evidence of intent, not of correctness")

    def test_one_row_per_element_and_candidate_with_library_support(self):
        output = section(MAP_RAW, "Mapping output")
        self.assertIn("one row per requested element (event, date or output) and candidate", output)
        self.assertIn("library support", output.lower())
        self.assertIn("one table per output or source system", output)
        self.assertNotIn("Return one mapping table", MAP)

    def test_partial_map_lists_pending_data_elements_separately(self):
        output = section(MAP_RAW, "Mapping output")
        self.assertIn("Partial map", output)
        self.assertIn("map the confirmed cohort concepts only", output)
        self.assertIn("List the pending data elements separately", output)


class MapLiftCapture(unittest.TestCase):
    """#372 (map part): read-only proposal and the operator-probe exemption."""

    def test_mapping_never_initialises_the_store(self):
        capture = section(MAP_RAW, "Lift capture")
        self.assertIn("Mapping never initialises `.sqlreview/`; stages that own the store "
                      "(setup, bootstrap) still initialise it.", capture)

    def test_proposal_only_entry_is_returned_as_text_and_authorises_nothing(self):
        capture = section(MAP_RAW, "Lift capture")
        self.assertIn("if the run is read-only, the child repo has no `.sqlreview/` yet, "
                      "or you cannot write to it, publish nothing", capture)
        self.assertIn("Return the candidate ledger entry as text, marked proposal-only", capture)
        # Shared verbatim with the guardrails rule (#372).
        self.assertIn("A proposal-only entry authorises no hand SQL: none is committed or run, "
                      "except exempt probes, until a writable run publishes the entry.", capture)
        self.assertNotIn("draft publishes it before writing", capture)

    def test_exempt_probes_carry_every_condition_and_defer_to_guardrails(self):
        capture = section(MAP_RAW, "Lift capture")
        for token in ("outside the hand-SQL gate only when", "aggregate-only", "small-cell-suppressed",
                      "single-scan",
                      "returns no identifying values (no patient or clinician identifiers, no staff or person keys)",
                      "feeds no delivered extract", "Record any `NOLOCK` use",
                      "Guardrails is the source of truth"):
            with self.subTest(token=token):
                self.assertIn(token, capture)


class MapEthnicity(unittest.TestCase):
    """#386 (map part): an ethnicity element maps to Indigenous status."""

    def test_ethnicity_prompt(self):
        inputs = section(MAP_RAW, "Inputs")
        for token in ("**Ethnicity:**", "Indigenous status from `PERSON_INFO`", "country of birth",
                      "preferred language", "optional surrogates", "ethnicity is not held"):
            with self.subTest(token=token):
                self.assertIn(token, inputs)


class LiftClassifyOnly(unittest.TestCase):
    """#385: a read-only proposal mode, and request-local units are request-specific."""

    def test_classify_only_stops_before_any_write(self):
        mode = section(LIFT_RAW, "Classify-only mode")
        self.assertIn("read-only run", mode)
        self.assertIn("as text", mode)
        # The list form, so "run sqlreview.sh publish" elsewhere cannot satisfy it.
        self.assertIn("then stop before any write: no `/data-request:setup`, no `sqlreview.sh` `init`, "
                      "`publish` or `render`, no AskUserQuestion, no issue filing.", mode)
        self.assertIn("Proposed buckets are unconfirmed", mode)
        self.assertNotRegex(mode, r"(?i)\brun `?sqlreview\.sh`? `?(?:init|publish|render)")

    def test_classify_only_precedes_the_writing_steps(self):
        order = [LIFT_RAW.index(f"## {h}") for h in
                 ("Classify-only mode", "Discover before classifying", "Confirm the boundary",
                  "File and record delivery")]
        self.assertEqual(order, sorted(order))

    def test_request_local_typed_table_is_request_specific(self):
        boundary = section(LIFT_RAW, "Confirm the boundary")
        self.assertRegex(boundary, r"request-local TypedTable or unit is a `request-specific` candidate")
        self.assertIn("record it in the ledger", boundary)
        self.assertIn("needs no library issue", boundary)
        self.assertIn("request-local TypedTables", section(LIFT_RAW, "Discover before classifying"))


class LiftQueryBuilderBaseline(unittest.TestCase):
    """#380 (lift part): v0.6.0 baseline; resolvers consolidated into query-builder."""

    def test_no_archived_plugins_package_anywhere_in_lift(self):
        for target, root in copies("lift").items():
            for path in files(root):
                with self.subTest(target=target, path=path.name):
                    self.assertNotIn("query-builder-plugins", path.read_text())
                    self.assertNotIn("qb_plugins", path.read_text())

    def test_compatibility_names_v060_and_resolver_paths(self):
        compat = flat(frontmatter(canon("lift") / "SKILL.md")["compatibility"])
        self.assertIn("query-builder 0.6.0", compat)
        self.assertIn("resolvers/iemr and resolvers/hbcis from 0.5.0", compat)
        self.assertNotRegex(compat, r"0\.[34]\.0")

    def test_resolvers_moved_at_v050_and_baseline_is_v060(self):
        intro = flat(LIFT_RAW.split("\n## ", 1)[0])
        self.assertIn("live under `resolvers/iemr` and `resolvers/hbcis` from v0.5.0; the baseline is v0.6.0", intro)

    def test_source_resolver_candidates_file_on_query_builder(self):
        delivery = section(LIFT_RAW, "File and record delivery")
        self.assertRegex(delivery, r"owning repo is `nq-rdl/query-builder`, for shared composition/spec "
                                   r"infrastructure and for source-specific resolvers")
        self.assertIn("`resolvers/iemr`", delivery)


class LiftHouseStyleDirectMode(unittest.TestCase):
    """#367 (lift part): ask once for direct generative mode; no routing workaround."""

    def test_ask_once_after_reusing_a_recorded_decision(self):
        handoff = section(LIFT_RAW, "House-style hand-off")
        reuse = handoff.index("first reuse a recorded direct-mode decision for the same repository `owner/name`")
        self.assertIn("do not ask twice", handoff)
        self.assertGreater(handoff.index("Otherwise ask once, up front"), reuse)
        self.assertIn('`generativeMode: "direct"`', handoff)
        for stage in ("`specify`", "`plan`", "`tasks`", "`analyze`"):
            with self.subTest(stage=stage):
                self.assertIn(stage, handoff)

    def test_decision_has_the_shape_the_workflow_reuses(self):
        handoff = raw_section(LIFT_RAW, "House-style hand-off")
        blocks = re.findall(r"```json\n(.*?)```", handoff, re.S)
        self.assertEqual(len(blocks), 1, "one JSON decision example")
        decision = json.loads(blocks[0])
        self.assertEqual(list(decision), ["decision", "value", "by", "at", "scope"])
        self.assertEqual((decision["decision"], decision["value"]), ("generativeMode", "direct"))
        self.assertEqual(decision["scope"], "nq-rdl/query-builder")  # owner/name, not a guessed path
        text = flat(handoff)
        self.assertIn("Set `scope` to the owning repository's `owner/name`", text)
        self.assertIn("If a worktree for the work already exists, add the same record with its absolute path", text)
        self.assertIn("translates `owner/name` into the unit's `physicalWorktree`", text)

    def test_routing_through_another_agent_is_not_a_workaround(self):
        handoff = section(LIFT_RAW, "House-style hand-off")
        self.assertRegex(handoff, r"Routing `/speckit\.\*` through another agent \(Codex, a subagent\) to avoid "
                                  r"`disable-model-invocation` is not a workaround")
        self.assertIn("direct mode is the supported path", handoff)


if __name__ == "__main__":
    unittest.main()
