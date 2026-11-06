"""Contract tests for the `data-request:amend` entry point (issue #356).

The skill classifies an analyst amendment against query-builder's boundary document
and links to it rather than restating it. These checks keep it registered, packaged
for Claude Code and Codex, discoverable beside the other leaves, and free of any
instruction to hand-edit generated SQL. No model call is made.
"""

import re
import unittest
from pathlib import Path

import yaml

REPO = Path(__file__).resolve().parent.parent
CANONICAL = REPO / "skills/data-request-amend/SKILL.md"
CLAUDE_COPY = REPO / "plugins/data-request/skills/amend/SKILL.md"
CODEX_COPY = REPO / "dist/codex/plugins/data-request/skills/amend/SKILL.md"

BOUNDARY_DOC = "https://github.com/nq-rdl/query-builder/blob/main/docs/ANALYST_AMENDMENTS.md"
GOVERNANCE_SOP = "zensical/governance/docs/governance/data-amendments.md"
EXTENSION_POINTS = ("rename=", "SelectFields", "projection", "cohort.yaml", "SelectStep",
                    "AnalysisPipeline.select", "output_name", "register_result(")
# Distinctive rows of the boundary document's example table. The skill classifies
# against the document; copying its rule set here would let the two drift apart.
BOUNDARY_TABLE_ROWS = (
    "`DedupeByKeyStep`", "dedupe_or", "`FacilitySpec`", "ADR 0003",
    "a combined address", "inclusive or half-open",
)


def flat(text: str) -> str:
    return " ".join(text.split())


def frontmatter(path: Path) -> tuple[dict, str]:
    text = path.read_text()
    _, meta, body = text.split("---\n", 2)
    return yaml.safe_load(meta), body


class Registration(unittest.TestCase):
    def test_bundle_maps_the_canonical_skill_to_the_amend_leaf(self):
        bundle = yaml.safe_load((REPO / "registry/bundles/data-request.yaml").read_text())
        self.assertIn({"source": "data-request-amend", "leaf": "amend"}, bundle["skills"])

    def test_canonical_frontmatter_names_the_source(self):
        meta, _ = frontmatter(CANONICAL)
        self.assertEqual(meta["name"], "data-request-amend")
        self.assertTrue(meta["user-invocable"])
        self.assertIn("amend", meta["description"].lower())

    def test_claude_copy_is_namespaced_by_its_leaf(self):
        meta, body = frontmatter(CLAUDE_COPY)
        self.assertNotIn("name", meta, "sync strips name: so /data-request:amend is namespaced")
        self.assertEqual(body, frontmatter(CANONICAL)[1])

    def test_codex_copy_names_the_leaf(self):
        meta, _ = frontmatter(CODEX_COPY)
        self.assertEqual(meta["name"], "amend")

    def test_bundle_doc_lists_amend_for_both_targets(self):
        doc = (REPO / "docs/bundles.md").read_text()
        for entry in ("- `/data-request:amend`", "- `$data-request:amend`"):
            self.assertTrue(entry in doc, f"docs/bundles.md lacks {entry}")


class Content(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.meta, cls.body = frontmatter(CANONICAL)

    def test_links_the_boundary_document_at_its_permanent_location(self):
        self.assertIn(BOUNDARY_DOC, self.body)

    def test_does_not_restate_the_boundary_rule_set(self):
        for row in BOUNDARY_TABLE_ROWS:
            with self.subTest(row=row):
                self.assertNotIn(row, self.body)
        self.assertNotRegex(self.body, r"\|\s*Analyst-safe\s*\|\s*Engineer-required\s*\|")

    def test_classifies_before_editing_and_defaults_to_engineer_required(self):
        classify = self.body.index("classification: analyst-safe")
        self.assertLess(classify, self.body.index("rename="))
        self.assertIn("classification: engineer-required", self.body)
        self.assertRegex(self.body, r"(?i)in doubt[^.]*engineer-required")

    def test_engineer_required_hand_off_names_rule_change_and_files(self):
        for field in ("requested change:", "boundary rule:", "affected files:"):
            with self.subTest(field=field):
                self.assertIn(field, self.body)
        self.assertRegex(self.body, r"(?i)make no edit")

    def test_governance_is_a_separate_check_pointing_to_the_sop(self):
        self.assertIn(GOVERNANCE_SOP, self.body)
        self.assertIn("Data Amendments SOP", self.body)
        self.assertRegex(self.body, r"(?i)original request ID")
        self.assertRegex(self.body, r"(?i)reason for the amendment")

    def test_safe_changes_use_only_the_supported_extension_points(self):
        for point in EXTENSION_POINTS:
            with self.subTest(point=point):
                self.assertIn(point, self.body)

    def test_records_the_amendment_with_its_classification(self):
        self.assertIn("specs/amendments.md", self.body)
        self.assertNotIn("data-analysis-scaffold/issues", self.body)

    def test_validation_gates(self):
        for gate in ("sql_gate", "spec-validate", "final projection", "row count", "key set",
                     "blocker"):
            with self.subTest(gate=gate):
                self.assertIn(gate, self.body)

    def test_reuses_sibling_actions_by_reference(self):
        self.assertIn("`/data-request:guardrails`", self.body)
        for leaf in ("validate", "fix", "analyse"):
            with self.subTest(leaf=leaf):
                self.assertIn(f"/data-request:{leaf}", self.body)

    def test_never_instructs_a_hand_edit_of_generated_sql(self):
        self.assertNotRegex(self.body, r"```\s*sql", "the skill ships no SQL to paste")
        sentences = re.split(r"(?<=[.!?])\s+", " ".join(self.body.split()))
        edits = [s for s in sentences
                 if re.search(r"(?i)generated SQL", s) and re.search(r"(?i)\b(hand-?)?edit", s)]
        self.assertTrue(edits, "the skill must address hand edits of generated SQL")
        for sentence in edits:
            with self.subTest(sentence=sentence):
                self.assertRegex(sentence, r"(?i)\b(never|not|refus\w*|no)\b")


    def test_a_combined_request_is_split_per_part(self):
        self.assertIn("### Split a combined request", self.body)
        split = self.body.split("### Split a combined request", 1)[1].split("## 2.", 1)[0]
        self.assertRegex(split, r"P1: <the change[^>]*>\nclassification: <analyst-safe \| engineer-required>")
        self.assertRegex(split, r"(?i)ambiguous is engineer-required")
        self.assertIn("Do not guess", split)
        self.assertRegex(split, r"(?i)never change rows or meaning")
        self.assertRegex(split, r"(?i)one part does not stop the others")

    def test_safe_parts_are_checked_one_at_a_time(self):
        split = flat(self.body.split("### Split a combined request", 1)[1].split("## 2.", 1)[0])
        self.assertIn("Do one part at a time in P order, and regenerate after each", split)
        self.assertIn("so that a failed check belongs to that part", split)
        self.assertIn("you cannot name the part, undo them all", split)
        self.assertIn("apply and check them again one at a time", split)

    def test_a_dependent_safe_part_keeps_its_classification(self):
        split = flat(self.body.split("### Split a combined request", 1)[1].split("## 2.", 1)[0])
        self.assertIn("Keep its classification `analyst-safe`", split)
        self.assertIn('"held with P2"', split)
        self.assertIn("classification: <engineer-required | analyst-safe, held with P<n>>", self.body)
        self.assertIn("Never relabel a change to fit analyst-safe or engineer-required", self.body)

    def test_engineer_parts_share_one_hand_off_on_the_deliverable_pr(self):
        handoff = self.body.split("## 2.", 1)[1].split("## 3.", 1)[0]
        for token in ("single hand-off comment", "deliverable PR", "Communication channel",
                      "amendment hand-off:", "already done by the analyst:", "part:",
                      "open question:", "route:"):
            with self.subTest(token=token):
                self.assertIn(token, handoff)
        self.assertLess(handoff.index("amendment hand-off:"), handoff.index("\npart: <P3>"))

    def test_hand_off_does_not_wait_for_an_operator_run(self):
        handoff = flat(self.body.split("## 2.", 1)[1].split("## 3.", 1)[0])
        self.assertIn("Draft it when the checks that can run in steps 3 to 6 have finished", handoff)
        self.assertIn("Do not wait for a check that needs an operator run", handoff)
        self.assertIn("List it as pending under `already done by the analyst:`", handoff)
        self.assertIn("in a second comment that lists only that part", handoff)

    def test_split_evidence_and_resume_are_readable_by_the_next_run(self):
        for token in ("`done`, `handed off` or `withdrawn`", "Do not add an entry for a handed-off part",
                      "done:", "handed off:", "open decision:", "open delivery gate",
                      "## Resume a split request", "Do not post the hand-off again"):
            with self.subTest(token=token):
                self.assertIn(token, self.body)
        resume = self.body.split("## Resume a split request", 1)[1]
        self.assertRegex(resume, r"(?i)do not redo it")

    def test_released_extract_keeps_part_lines_in_the_pr_description(self):
        record = flat(self.body.split("## 5.", 1)[1].split("## 6.", 1)[0])
        self.assertIn("On a released extract, put these lines in the pull request description", record)
        self.assertIn("takes no entry for a handed-off or withdrawn part", record)
        self.assertIn("part's own classification", record)

    def test_only_two_strict_forms_close_a_handed_off_part(self):
        close = self.body.split("### Close a handed-off part", 1)[1].split("## 3.", 1)[0]
        self.assertIn("```text\nwithdrawn: P<n> <reason>\ndone: P<n> <commit>\n```", close)
        self.assertIn("Only two comment forms on the deliverable PR close a handed-off part", close)
        self.assertIn("The reason is required", close)
        self.assertIn("A `withdrawn:` line with no\n  reason does not close the part", close)
        self.assertIn("Any other comment that names the part leaves it open", close)
        self.assertIn("P3 is still in progress", close)
        self.assertIn("Post it only when the analyst authorises", close)
        # Amend runs its own check and does not claim that the release skill does.
        self.assertNotIn("/data-request:release", close)

    def test_a_close_line_counts_only_from_the_right_writer(self):
        close = flat(self.body.split("### Close a handed-off part", 1)[1].split("## 3.", 1)[0])
        self.assertIn("gh pr view <PR> --json author,assignees,reviewRequests,comments", close)
        self.assertIn("skills/setup/references/close-line-authors.rst", close)
        self.assertIn("The `done:` line counts only from the engineer", close)
        self.assertIn("the `withdrawn:` line counts only from the analyst", close)
        self.assertIn("A line from anyone else leaves the part open", close)
        # The writer is checked before the commit is.
        self.assertLess(close.index("Check who wrote the line"), close.index("git merge-base"))
        rule = flat((REPO / "skills/data-request-setup/references/close-line-authors.rst").read_text())
        for token in ("gh pr view PR --json author,assignees,reviewRequests,comments",
                      "``done:`` line counts only from the engineer named in the hand-off comment",
                      "only from the PR author or an assignee",
                      "``withdrawn:`` line counts only from the analyst named on the PR",
                      "The analyst cannot close a part with ``done:``",
                      "The engineer cannot close a part with ``withdrawn:``",
                      "A line from anyone else leaves the part open"):
            self.assertIn(token, rule)

    def test_a_done_commit_is_fetched_resolved_and_checked_by_exit_code(self):
        close = flat(self.body.split("### Close a handed-off part", 1)[1].split("## 3.", 1)[0])
        steps = [close.index(s) for s in ("fetch-command",
                                          "git rev-parse --verify --quiet <commit>^{commit}",
                                          "git merge-base --is-ancestor <full SHA> <release ref>")]
        self.assertEqual(steps, sorted(steps), "fetch, then resolve, then ancestry")
        self.assertIn("A short SHA that matches several objects, or none, gives no SHA", close)
        self.assertIn("Exit 0 verifies the part", close)
        self.assertIn("Exit 1 means the commit is not in the release ref", close)
        self.assertIn("Any other exit, such as 128 for an unknown object or ref, means not verified", close)
        self.assertIn("If a step fails, the part stays handed off", close)
        self.assertIn("name a remote-tracking ref such as `origin/<branch>` or a tag as the release ref", close)
        self.assertNotIn("git fetch origin", close)

    def test_the_release_ref_is_never_left_undefined(self):
        close = flat(self.body.split("### Close a handed-off part", 1)[1].split("## 3.", 1)[0])
        self.assertNotIn("candidate ref", self.body)
        self.assertIn("The release ref is the release tag. Before a tag exists, it is the ref that the analyst names", close)
        self.assertIn("If none is named, ask the analyst for it", close)

    def test_hand_off_entry_keys_in_order(self):
        handoff = self.body.split("```text\namendment hand-off:", 1)[1].split("```", 1)[0]
        keys = re.findall(r"^([a-z][a-z -]*):", "amendment hand-off:" + handoff, re.M)
        self.assertEqual(keys, ["amendment hand-off", "enquiry", "already done by the analyst", "part",
                                "classification", "requested change", "boundary rule",
                                "open question", "affected files", "governance", "route"])

    def test_record_and_resume_share_the_three_states(self):
        self.assertIn("`done`, `handed off` or `withdrawn`", self.body)
        self.assertIn("A withdrawn part also gets the reason and the `withdrawn:` comment URL", self.body)
        self.assertIn("Do not add an entry for a handed-off part or a withdrawn part", self.body)
        self.assertIn('withdrawn: <each withdrawn part: P number and reason, or "none">', self.body)
        resume = flat(self.body.split("## Resume a split request", 1)[1])
        self.assertIn("a `done: P<n> <commit>` comment closes it only when the author check and the commit check pass", resume)
        self.assertIn("Run both from *Close a handed-off part* (step 2)", resume)
        self.assertIn("a `withdrawn: P<n> <reason>` comment from the analyst named on the PR closes it", resume)
        self.assertIn("It no longer blocks the release", resume)
        self.assertIn("it stays handed off, whatever other comments name it", resume)
        self.assertIn("`done` for a verified `done:` comment", resume)
        self.assertIn("`withdrawn` for a `withdrawn:` comment", resume)

    def test_an_analyst_safe_reply_is_not_a_close_form(self):
        resume = flat(self.body.split("## Resume a split request", 1)[1])
        self.assertIn("a reply is not a close form and does not change the status", resume)
        self.assertIn("ask them to confirm the new classification", resume)
        self.assertIn("Only after they confirm, complete the part through steps 3 to 6", resume)
        self.assertIn('Silence, "probably fine" or a reply from anyone else is not an answer', resume)


class Routing(unittest.TestCase):
    def test_fix_points_change_requests_to_amend(self):
        body = frontmatter(REPO / "skills/data-request-fix/SKILL.md")[1]
        line = next((l for l in body.splitlines() if "/data-request:amend" in l), "")
        self.assertRegex(line, r"(?i)change request")

    def test_validate_routes_amendments_to_amend(self):
        body = frontmatter(REPO / "skills/data-request-validate/SKILL.md")[1]
        self.assertIn("/data-request:amend", body)


if __name__ == "__main__":
    unittest.main()
