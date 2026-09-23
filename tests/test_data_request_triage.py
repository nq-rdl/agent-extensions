"""Skill-contract tests for /data-request:triage (issue #338).

These pin what the generic validators cannot see: the skill is registered under the
`triage` leaf, packaged for Claude Code and Codex, states both modes with triage-only
read-only, selects models by capability, composes the other data-request stages by
reference instead of restating them, keeps SKILL.md lean with long material in linked
references, and carries the non-inferable field notes from the September triage.
No model call is made; the behavioural side lives in evals/claude/data-request/.
"""

import re
import unittest
from pathlib import Path

import yaml

REPO = Path(__file__).resolve().parent.parent
BUNDLE = REPO / "registry" / "bundles" / "data-request.yaml"
CANON = REPO / "skills" / "data-request-triage"
SKILL = CANON / "SKILL.md"
CLAUDE_COPY = REPO / "plugins" / "data-request" / "skills" / "triage"
CODEX_COPY = REPO / "dist" / "codex" / "plugins" / "data-request" / "skills" / "triage"

# Hard-coded model families the issue forbids (capability-based selection only).
MODEL_NAMES = re.compile(r"(?i)\b(?:opus|sonnet|haiku|fable|gpt-\d[\w.-]*|claude-[a-z]+-\d)\b")


def frontmatter(path: Path) -> dict:
    return yaml.safe_load(path.read_text().split("---\n", 2)[1]) or {}


def body(path: Path) -> str:
    return path.read_text().split("---\n", 2)[2]


def skill_files(root: Path):
    return sorted(p for p in root.rglob("*") if p.is_file())


def section(text: str, heading: str) -> str:
    """The Markdown section under `## <heading>` up to the next `## ` heading."""
    match = re.search(r"^## " + re.escape(heading) + r"[^\n]*\n(.*?)(?=^## |\Z)", text, re.M | re.S)
    if not match:
        raise AssertionError(f"SKILL.md has no '## {heading}' section")
    return match.group(1)


class Registration(unittest.TestCase):
    def test_registered_under_the_triage_leaf(self):
        members = yaml.safe_load(BUNDLE.read_text())["skills"]
        self.assertIn({"source": "data-request-triage", "leaf": "triage"}, members)

    def test_canonical_frontmatter_matches_siblings(self):
        fm = frontmatter(SKILL)
        self.assertEqual(fm["name"], "data-request-triage")
        self.assertEqual(fm["license"], "CC-BY-4.0")
        self.assertTrue(fm.get("user-invocable"))
        self.assertIn("AskUserQuestion", fm["allowed-tools"])
        self.assertIn("argument-hint", fm)
        self.assertTrue(fm.get("compatibility"))
        self.assertEqual(fm["metadata"]["repo"], "https://github.com/nq-rdl/agent-extensions")
        description = fm["description"]
        for word in ("enquir", "approval", "queue", "read-only", "co-develop"):
            with self.subTest(word=word):
                self.assertIn(word, description.lower())

    def test_packaged_for_claude_without_a_name(self):
        copy = CLAUDE_COPY / "SKILL.md"
        self.assertTrue(copy.is_file(), "run pixi run bash scripts/sync-plugins.sh data-request")
        self.assertNotIn("name", frontmatter(copy))
        self.assertEqual(body(copy), body(SKILL))
        canon_refs = {p.relative_to(CANON) for p in skill_files(CANON)}
        self.assertEqual({p.relative_to(CLAUDE_COPY) for p in skill_files(CLAUDE_COPY)}, canon_refs)

    def test_packaged_for_codex_with_the_leaf_name(self):
        copy = CODEX_COPY / "SKILL.md"
        self.assertTrue(copy.is_file(), "run pixi run bash scripts/sync-plugins.sh data-request")
        self.assertEqual(frontmatter(copy)["name"], "triage")
        text = copy.read_text()
        self.assertIn("$data-request:bootstrap", text)
        self.assertNotIn("${CLAUDE_PLUGIN_ROOT}", text)
        self.assertTrue((CODEX_COPY / "references" / "subagent.rst").is_file())

    def test_no_agents_tree_anywhere(self):
        for root in (CANON, CLAUDE_COPY, CODEX_COPY):
            with self.subTest(root=root):
                self.assertFalse((root / "agents").exists())


class Modes(unittest.TestCase):
    def setUp(self):
        self.text = body(SKILL)

    def test_both_modes_are_explicit(self):
        self.assertRegex(self.text, r"\*\*Triage only\*\*")
        self.assertRegex(self.text, r"\*\*Co-development\*\*")
        self.assertIn("--triage-only", frontmatter(SKILL)["argument-hint"])
        self.assertIn("--co-develop", frontmatter(SKILL)["argument-hint"])

    def test_triage_only_is_read_only(self):
        modes = section(self.text, "Choose the mode")
        triage = modes.split("**Co-development**")[0]
        self.assertIn("read-only", triage)
        # Every write channel the September triage touched is named as forbidden.
        for channel in ("comment", "branch", "commit", "push", "pull request", "label", "project field"):
            with self.subTest(channel=channel):
                self.assertIn(channel, triage.lower())
        self.assertRegex(triage, r"paste-ready")
        self.assertRegex(triage, r"ordered queue")

    def test_stops_at_triage_when_that_is_the_scope(self):
        self.assertRegex(self.text, r"(?i)stop at triage")


class Composition(unittest.TestCase):
    """Reuse the other stages by reference; never restate their procedures."""

    STAGES = ("bootstrap", "map", "draft", "analyse", "validate", "fix", "guardrails", "lift")

    def test_references_every_reused_skill(self):
        text = body(SKILL)
        for stage in self.STAGES:
            with self.subTest(stage=stage):
                self.assertIn(f"/data-request:{stage}", text)
        self.assertIn("/tech-writing:copyedit", text)

    def test_does_not_restate_stage_procedures(self):
        for path in skill_files(CANON):
            text = path.read_text()
            with self.subTest(path=path.name):
                # sqlreview publication, confirmation fields and SQL mechanics belong to
                # setup/bootstrap/analyse/guardrails.
                for owned in ("sqlreview.sh", "carryforward", "confirmed_revision", "DATEADD",
                              "CREATE TABLE", "scope.draft.json"):
                    self.assertNotIn(owned, text)

    def test_skill_md_is_lean(self):
        self.assertLessEqual(len(SKILL.read_text().splitlines()), 140)


class ModelSelection(unittest.TestCase):
    def test_no_hard_coded_model_names_in_any_shipped_copy(self):
        for root in (CANON, CLAUDE_COPY, CODEX_COPY):
            for path in skill_files(root):
                with self.subTest(path=str(path.relative_to(REPO))):
                    self.assertIsNone(MODEL_NAMES.search(path.read_text()))

    def test_capability_based_selection_and_disclosed_limits(self):
        outline = (CANON / "references" / "subagent.rst").read_text()
        joined = body(SKILL) + outline
        self.assertRegex(joined, r"(?i)by capability")
        self.assertRegex(joined, r"(?i)models? the host (?:offers|makes available|reports)")
        self.assertIn("add_repo", joined)
        self.assertRegex(joined, r"(?i)unavailable")
        self.assertRegex(outline, r"(?i)one writer per worktree")

    def test_attribution_is_truthful(self):
        self.assertRegex(body(SKILL), r"(?i)attribut\w+ [^.\n]*model that actually")


class References(unittest.TestCase):
    EXPECTED = {"subagent.rst", "ledger.rst", "repositories.rst", "checks.rst", "comments.rst"}

    def test_references_exist_are_rst_and_linked_with_when_to_read(self):
        refs = CANON / "references"
        self.assertEqual({p.name for p in refs.iterdir()}, self.EXPECTED)
        text = body(SKILL)
        for name in self.EXPECTED:
            with self.subTest(ref=name):
                link = re.search(r"\]\(references/" + re.escape(name) + r"\)([^\n]*)", text)
                self.assertIsNotNone(link, f"SKILL.md does not link references/{name}")

    def test_ledger_schema_fields(self):
        ledger = (CANON / "references" / "ledger.rst").read_text()
        for field in ("ticket", "enquiry", "approval", "repo", "branch", "owner", "stage",
                      "evidence_revision", "decisions", "next_action", "verification", "depends_on"):
            with self.subTest(field=field):
                self.assertIn(field, ledger)
        # Decisions are dated and attributed; the ledger is durable, not a scratchpad.
        self.assertRegex(ledger, r"(?i)who")
        self.assertRegex(ledger, r"(?i)durable")
        self.assertRegex(ledger, r"(?i)scratchpad")

    def test_blocker_taxonomy(self):
        checks = (CANON / "references" / "checks.rst").read_text().lower()
        for kind in ("clarification", "source availability", "governance", "scaffold",
                     "dependency", "correctness bug", "missing capability"):
            with self.subTest(kind=kind):
                self.assertIn(kind, checks)


class FieldNotes(unittest.TestCase):
    """Non-inferable facts from the September multi-enquiry triage (#338 comment)."""

    def setUp(self):
        self.all = "\n".join(p.read_text() for p in skill_files(CANON))

    def test_repository_and_scaffold_facts(self):
        for fact in ("_src_path", "data-science-template", "copier-runner.yml", "answers.yaml",
                     ".copier-answers.yml", "framework_ref", "GOVERNANCE.md",
                     "THHSAQUIRE-9903", "THHSRDLENQ-9003"):
            with self.subTest(fact=fact):
                self.assertIn(fact, self.all)
        self.assertRegex(self.all, r"(?i)unapplied")
        self.assertRegex(self.all, r"(?i)outdated")
        self.assertRegex(self.all, r"(?i)original spelling")
        self.assertRegex(self.all, r"query-builder-plugins[^.]*consolidated")

    def test_requirement_checks(self):
        for pattern in (r"(?i)half-open", r"UTC", r"AEST", r"(?i)screening[- ]log",
                        r"(?i)source system and grain", r"(?i)supplied cohort",
                        r"(?i)code list", r"(?i)amendment", r"(?i)unanswered question",
                        r"(?i)raw dated events"):
            with self.subTest(pattern=pattern):
                self.assertRegex(self.all, pattern)

    def test_verification_discipline(self):
        text = body(SKILL)
        self.assertRegex(text, r"(?i)recheck every")
        self.assertRegex(text, r"(?i)probe")
        self.assertRegex(text, r"(?i)drafts? by default|as drafts?")
        self.assertRegex(text, r"(?i)business[- ]day")

    def test_never_inferred_permissions(self):
        never = section(body(SKILL), "Never infer permission").lower()
        for action in ("extract", "releas", "merg", "hook", "copier update", "service-desk"):
            with self.subTest(action=action):
                self.assertIn(action, never)

    def test_fulfilment_handoff(self):
        text = body(SKILL)
        self.assertRegex(text, r"(?i)parity")
        self.assertRegex(text, r"(?i)upstream")
        self.assertRegex(text, r"(?i)re-pin")


if __name__ == "__main__":
    unittest.main()
