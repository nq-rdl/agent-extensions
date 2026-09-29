"""Skill-contract tests for the September 2026 triage field gaps.

Issues #376, #377, #378, #381, #382, #384, #387 and #368, and the triage parts of #386
and #367. Each test pins the non-inferable tokens a rule adds, in the file and section
where an agent reads it, so that a rule moved to the wrong place or lost in a rewrite
fails here. The packaged Claude and Codex copies must carry the same text.
No model call is made; the behavioural side lives in evals/claude/data-request/field-*.
"""

import re
import unittest
from pathlib import Path

import yaml

REPO = Path(__file__).resolve().parent.parent
TRIAGE = REPO / "skills" / "data-request-triage"
BOOTSTRAP = REPO / "skills" / "data-request-bootstrap"
REFS = TRIAGE / "references"
COPIES = {
    "claude": REPO / "plugins" / "data-request" / "skills",
    "codex": REPO / "dist" / "codex" / "plugins" / "data-request" / "skills",
}


def flat(text: str) -> str:
    """Collapse wrapping so that a phrase split across lines still matches."""
    return re.sub(r"\s+", " ", text)


def frontmatter(path: Path) -> dict:
    return yaml.safe_load(path.read_text().split("---\n", 2)[1]) or {}


def body(path: Path) -> str:
    return path.read_text().split("---\n", 2)[2]


def md_section(text: str, heading: str) -> str:
    match = re.search(r"^## " + re.escape(heading) + r"[^\n]*\n(.*?)(?=^## |\Z)", text, re.M | re.S)
    if not match:
        raise AssertionError(f"no '## {heading}' section")
    return match.group(1)


def rst_section(name: str, title: str) -> str:
    """The RST section titled `title` (underlined with '-') up to the next such section."""
    text = (REFS / name).read_text()
    match = re.search(r"^" + re.escape(title) + r"\n-{3,}\n(.*?)(?=^[^\n]+\n-{3,}\n|\Z)", text, re.M | re.S)
    if not match:
        raise AssertionError(f"{name} has no '{title}' section")
    return match.group(1)


def rst_bullet(section: str, label: str) -> str:
    """The `* **label.** ...` bullet of an RST section."""
    match = re.search(r"^\* \*\*" + re.escape(label) + r"\.\*\*(.*?)(?=^\* |^\S|\Z)", section, re.M | re.S)
    if not match:
        raise AssertionError(f"no '**{label}.**' bullet")
    return flat(match.group(1))


def rst_term(section: str, term: str) -> str:
    """The body of a definition-list term: the indented lines under it."""
    match = re.search(r"^" + re.escape(term) + r"\n((?:   [^\n]*\n|\n(?=   ))+)", section, re.M)
    if not match:
        raise AssertionError(f"no '{term}' definition")
    return flat(match.group(1))


def numbered_step(text: str, number: int) -> str:
    match = re.search(r"^ ?" + str(number) + r"\. (.*?)(?=^ ?\d+\. |^\S|\Z)", text, re.M | re.S)
    if not match:
        raise AssertionError(f"no step {number}")
    return flat(match.group(1))


def triage_only(text: str) -> str:
    return flat(md_section(text, "Choose the mode").split("**Co-development**")[0])


class GitHubMcpFallback(unittest.TestCase):
    """#376: name the GitHub MCP read tools when gh is absent."""

    TOOLS = ("search_issues", "issue_read", "list_issues")

    def test_compatibility_names_the_fallback(self):
        compat = frontmatter(TRIAGE / "SKILL.md")["compatibility"]
        self.assertIn("GitHub MCP", compat)
        for tool in self.TOOLS:
            with self.subTest(tool=tool):
                self.assertIn(tool, compat)

    def test_probe_and_triage_only_use_it(self):
        text = body(TRIAGE / "SKILL.md")
        self.assertRegex(numbered_step(md_section(text, "Assess each request"), 1), r"MCP fallback")
        self.assertRegex(triage_only(text), r"GitHub MCP read tools when `gh` is absent")

    def test_reference_maps_gh_reads_to_mcp_read_tools(self):
        access = flat(rst_section("repositories.rst", "Read-only access"))
        for tool in self.TOOLS + ("get_me", "get_file_contents", "list_pull_requests", "pull_request_read"):
            with self.subTest(tool=tool):
                self.assertIn(f"``{tool}``", access)
        self.assertRegex(access, r"``get_me``[^.;]*``gh auth status``")
        self.assertRegex(access, r"(?i)only the read tools")
        self.assertIn("pixi solve", access)


class LedgerDefaultLocation(unittest.TestCase):
    """#377: co-development with no agreed location returns the ledger as text."""

    def test_default_is_text_until_a_location_is_agreed(self):
        where = flat(rst_section("ledger.rst", "Where it lives"))
        default = where.split("no location is agreed", 1)
        self.assertEqual(len(default), 2, "no rule for a co-development session without an agreed location")
        self.assertRegex(default[1], r"(?i)entries as text")
        self.assertIn("triage-only", default[1])
        self.assertIn("tracking issue body", default[1])
        self.assertRegex(default[1], r"(?i)not pick a location")


class VerifyBeforeStale(unittest.TestCase):
    """#378: follow links, re-resolve before writes, trust merged_at, keep verbal decisions unlinked."""

    def setUp(self):
        self.resolve = flat(rst_section("repositories.rst", "Enquiry, issue and approval"))

    def test_link_is_followed_and_full_name_compared(self):
        self.assertRegex(self.resolve, r"(?i)follow the link")
        self.assertIn("--jq .full_name", self.resolve)
        self.assertRegex(self.resolve, r"``full_name``[^.]*approval ID")
        self.assertIn("rename redirect", self.resolve)
        self.assertIn("THHSRDLENQ-9003", self.resolve)

    def test_without_gh_an_unconfirmed_redirect_is_unverified(self):
        self.assertRegex(self.resolve, r"``search_repositories`` does not follow renames")
        self.assertIn("``get_file_contents``", self.resolve)
        self.assertIn("unverified", self.resolve)

    def test_old_unconditional_stale_rule_is_gone_everywhere(self):
        for root in [TRIAGE] + [c / "triage" for c in COPIES.values()]:
            for path in root.rglob("*"):
                if path.is_file():
                    with self.subTest(path=str(path.relative_to(REPO))):
                        self.assertNotIn("is stale or invented: report it", flat(path.read_text()))

    def test_naming_drift_and_mid_task_renames(self):
        self.assertIn("trailing punctuation", self.resolve)
        self.assertIn("THHSAQUIRE-9903-", self.resolve)
        self.assertRegex(self.resolve, r"(?i)re-resolve[^.]*before each write")

    def test_merge_state_from_merged_at(self):
        branches = flat(rst_section("repositories.rst", "Branches, owners and pins"))
        self.assertIn("``merged_at``", branches)
        self.assertIn("``merged`` flag alone", branches)
        self.assertIn("git merge-base --is-ancestor", branches)

    def test_merge_commit_sha_alone_is_not_evidence(self):
        branches = flat(rst_section("repositories.rst", "Branches, owners and pins"))
        self.assertRegex(branches, r"``merge_commit_sha`` alone is not evidence")
        self.assertRegex(branches, r"open PRs[^.]*closed without merging")
        for root in [TRIAGE] + [c / "triage" for c in COPIES.values()]:
            with self.subTest(root=str(root.relative_to(REPO))):
                self.assertNotIn("``merged_at`` or its merge commit", flat((root / "references" / "repositories.rst").read_text()))

    def test_verbal_decision_needs_a_written_dated_comment(self):
        verbal = rst_bullet(rst_section("checks.rst", "Interpretation checks"), "Verbal decision")
        self.assertIn("newest written comment", verbal)
        self.assertIn("written, dated comment", verbal)
        self.assertIn("unlinked", verbal)
        ledger = (REFS / "ledger.rst").read_text()
        self.assertIn("unlinked (verbal)", ledger)


class ScaffoldStates(unittest.TestCase):
    """#381: legacy-template seed, legacy shell with an outdated PR, answers.yaml parse, pixi skip."""

    def setUp(self):
        self.states = rst_section("repositories.rst", "Scaffold states")

    def test_answers_yaml_is_parsed_before_any_state(self):
        before = flat(self.states.split("\nLegacy shell\n")[0])
        self.assertIn("yaml.safe_load", before)
        self.assertRegex(before, r"(?i)before you decide")
        self.assertIn("line and column", before)

    def test_legacy_template_seed(self):
        seed = rst_term(self.states, "Legacy-template seed")
        for token in ("_src_path", "data-science-template", "cohort/", "sql/", "answers.yaml",
                      "does not parse", "``copier update`` cannot move", "fresh render"):
            with self.subTest(token=token):
                self.assertIn(token, seed)

    def test_legacy_shell_with_outdated_bootstrap_pr(self):
        overlay = rst_term(self.states, "Legacy shell with an outdated bootstrap PR")
        self.assertIn("request-filled answers", overlay)
        self.assertIn("fresh render", overlay)
        self.assertIn("owner", overlay)

    def test_fresh_render_recipe(self):
        recipe = rst_term(self.states, "Fresh render")
        for token in ("copier copy", "--vcs-ref", "--data-file answers.yaml",
                      "gh:nq-rdl/data-analysis-scaffold", "co-development", "byte-identical", "Re-lock pixi",
                      "``--trust`` runs the template's tasks", "pinned release tag", "list each one in the PR body",
                      "``.seed-manifest.yml``", "``scripts/template_sync.py``", "``src/service_desk/``"):
            with self.subTest(token=token):
                self.assertIn(token, recipe)
        self.assertNotRegex(recipe, r"run[^.]*copier update")

    def test_agents_still_never_run_copier_update(self):
        never = md_section(body(TRIAGE / "SKILL.md"), "Never infer permission")
        self.assertIn("copier update", never)
        self.assertIn("agents never run ``copier update``", flat(self.states))

    def test_pixi_solve_skipped_without_pyproject(self):
        step = numbered_step(md_section(body(TRIAGE / "SKILL.md"), "Assess each request"), 1)
        self.assertRegex(step, r"pixi solve \(skip[^)]*why[^)]*`pyproject.toml`\)")
        self.assertRegex(flat(self.states), r"no ``pyproject.toml``[^.]*\.[^.]*skips the pixi solve[^.]*why")


class CodeChecks(unittest.TestCase):
    """#382: internal range conflicts and classification-edition changes."""

    def setUp(self):
        self.checks = rst_section("checks.rst", "Interpretation checks")

    def test_internal_range_conflict_is_a_requester_clarification(self):
        bullet = rst_bullet(self.checks, "Internal range conflict")
        self.assertIn("C00 to C80", bullet)
        self.assertIn("not a library-concept broadening", bullet)
        self.assertIn("clarification for the requester", bullet)

    def test_edition_change_names_what_to_reverify(self):
        bullet = rst_bullet(self.checks, "Classification edition change")
        self.assertIn("ICD-10-AM 12th to 13th edition", bullet)
        self.assertIn("reference tables", bullet)
        self.assertIn("re-verify", bullet)


class ReadBranchWithoutCheckout(unittest.TestCase):
    """#384: read another child's branch with git show / ls-tree, never checkout."""

    def test_triage_only_mode_names_the_read_method(self):
        mode = triage_only(body(TRIAGE / "SKILL.md"))
        self.assertIn("`git show`", mode)
        self.assertIn("`git ls-tree`", mode)
        self.assertIn("never `git checkout`", mode)
        self.assertIn("hooks", mode)

    def test_branches_section_names_commands_and_the_hook_hazard(self):
        branches = flat(rst_section("repositories.rst", "Branches, owners and pins"))
        for token in ("git show", "git ls-tree", "--no-checkout", "Never run ``git checkout``",
                      "``git switch``", "``git worktree add``", "post-checkout", "DVC"):
            with self.subTest(token=token):
                self.assertIn(token, branches)


class DefaultsAndPriorVersions(unittest.TestCase):
    """#387: propose a default per open question; reuse a prior version's SQL or delivery."""

    def test_triage_reads_prior_versions_and_proposes_defaults(self):
        step = numbered_step(md_section(body(TRIAGE / "SKILL.md"), "Assess each request"), 2)
        self.assertIn("prior version's SQL or delivery", step)
        self.assertIn("propose a default for each open question", step)
        questions = flat(rst_section("checks.rst", "Open questions"))
        for token in ("proposed default", "scope assumption", "V1", "confirm-or-change", "named human"):
            with self.subTest(token=token):
                self.assertIn(token, questions)
        self.assertIn("Proposed default", (REFS / "comments.rst").read_text())

    def test_bootstrap_open_questions(self):
        step = numbered_step(md_section(body(BOOTSTRAP / "SKILL.md"), "Fresh scope → interview"), 5)
        for token in ("prior version's SQL or delivery", "V1", "confirm-or-change", "default answer",
                      "candidate assumption"):
            with self.subTest(token=token):
                self.assertIn(token, step)


class HandOffToReview(unittest.TestCase):
    """#368: gate, assign, comment, move, record; triage-only posts nothing."""

    def setUp(self):
        self.handoff = rst_section("handoff.rst", "Hand-off to review")

    def test_linked_from_co_development(self):
        codev = md_section(body(TRIAGE / "SKILL.md"), "Co-development")
        self.assertIn("](references/handoff.rst)", codev)
        self.assertIn("hand-off", codev)
        # Fulfilment rules moved to handoff.rst to leave SKILL.md headroom; +2 lines for the
        # amend and release routing rows (#306).
        self.assertLessEqual(len((TRIAGE / "SKILL.md").read_text().splitlines()), 138)
        fulfilment = flat(rst_section("handoff.rst", "Fulfilment"))
        for token in ("parity", "upstream", "/data-request:lift", "Re-pin", "depends_on", "drafts by default"):
            with self.subTest(token=token):
                self.assertIn(token, fulfilment)

    def test_steps_in_order(self):
        labels = re.findall(r"^\d+\. \*\*(\w+)\.?\*\*", self.handoff, re.M)
        self.assertEqual(labels, ["Gate", "Assign", "Comment", "Move", "Record"])

    def test_gate_reviewer_comment_board_and_record(self):
        text = flat(self.handoff)
        for token in ("out of draft", "green on the current head", "SQL review status is ``current``",
                      "``/data-request:analyse`` re-ran", "--reconfirm-all", "Actions toolset",
                      "open delivery gate", "Never guess a reviewer", "tracking issue",
                      "service-desk request issue", "**In-Review**", "head SHA", "reviewer",
                      "board state"):
            with self.subTest(token=token):
                self.assertIn(token, text)

    def test_writes_need_authorisation_and_triage_only_posts_nothing(self):
        text = flat(self.handoff)
        self.assertIn("explicit instruction", text)
        self.assertRegex(text, r"(?i)triage-only mode, post nothing")
        self.assertIn("board moves", text)
        self.assertIn("handoff.rst", (REFS / "comments.rst").read_text())

    def test_ledger_records_the_handoff(self):
        ledger = (REFS / "ledger.rst").read_text()
        for field in ("handoff:", "head_sha:", "reviewer:", "board_state:"):
            with self.subTest(field=field):
                self.assertIn(field, ledger)


class Ethnicity(unittest.TestCase):
    """#386 (triage part): ask the ethnicity question once during scoping."""

    def test_ethnicity_prompt(self):
        bullet = rst_bullet(rst_section("checks.rst", "Interpretation checks"), "Ethnicity")
        for token in ("no ethnicity field", "``PERSON_INFO``", "Indigenous status", "ask once",
                      "country of birth", "preferred language", "not held", "/data-request:guardrails"):
            with self.subTest(token=token):
                self.assertIn(token, bullet)


class SpecKitDirectMode(unittest.TestCase):
    """#367 (triage part): ask once for generativeMode "direct"; rerouting is not a workaround."""

    def test_direct_mode_question_and_record(self):
        spec = flat(rst_section("handoff.rst", "Library work through spec-kit"))
        self.assertIn('ask the human once', spec)
        self.assertIn('``generativeMode: "direct"``', spec)
        for stage in ("specify", "plan", "tasks", "analyze"):
            with self.subTest(stage=stage):
                self.assertIn(f"``{stage}``", spec)
        self.assertIn("disable-model-invocation", spec)
        self.assertIn("is not a workaround", spec)

    def test_decision_uses_the_shape_the_workflow_reuses(self):
        # rdl-team:house-style reuses only {"decision": "generativeMode", "value": "direct", by, at, scope}
        # (PR #402's directAuthorised()). Triage cannot know the unit's worktree path, so it records the
        # repository owner/name and the main session translates it into the unit's physicalWorktree.
        for name in ("handoff.rst", "ledger.rst"):
            with self.subTest(ref=name):
                objs = [yaml.safe_load(m) for m in re.findall(r'\{"decision": "generativeMode"[^}]*\}',
                                                              (REFS / name).read_text())]
                self.assertTrue(objs, f"{name} has no generativeMode decision object")
                for obj in objs:
                    self.assertEqual(set(obj), {"decision", "value", "by", "at", "scope"})
                    self.assertEqual(obj["value"], "direct")
                    self.assertEqual(obj["scope"], "<owner/name>")
        spec = flat(rst_section("handoff.rst", "Library work through spec-kit"))
        self.assertRegex(spec, r"``scope`` as the repository ``owner/name``")
        self.assertRegex(spec, r"(?i)keep these five keys exactly")
        self.assertRegex(spec, r"translates ``owner/name`` into that path")


class Packaging(unittest.TestCase):
    """Every rule above ships: references byte-identical, SKILL bodies carried."""

    def test_triage_references_are_byte_identical_in_both_targets(self):
        for target, root in COPIES.items():
            for ref in sorted(REFS.iterdir()):
                with self.subTest(target=target, ref=ref.name):
                    copy = root / "triage" / "references" / ref.name
                    self.assertTrue(copy.is_file(), "run pixi run bash scripts/sync-plugins.sh data-request")
                    self.assertEqual(copy.read_text(), ref.read_text())

    def test_skill_bodies_carry_the_rules(self):
        for leaf, canon in (("triage", TRIAGE), ("bootstrap", BOOTSTRAP)):
            with self.subTest(target="claude", leaf=leaf):
                self.assertEqual(body(COPIES["claude"] / leaf / "SKILL.md"), body(canon / "SKILL.md"))
            with self.subTest(target="codex", leaf=leaf):
                codex = flat((COPIES["codex"] / leaf / "SKILL.md").read_text())
                for token in {"triage": ("never `git checkout`", "GitHub MCP read tools", "handoff.rst",
                                         "prior version's SQL or delivery"),
                              "bootstrap": ("confirm-or-change", "default answer")}[leaf]:
                    self.assertIn(token, codex)

    def test_codex_compatibility_names_the_fallback(self):
        compat = frontmatter(COPIES["codex"] / "triage" / "SKILL.md")["compatibility"]
        self.assertIn("GitHub MCP", compat)


if __name__ == "__main__":
    unittest.main()
