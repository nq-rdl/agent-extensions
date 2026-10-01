"""Contract tests for Codex model aliases (issues #392, #393).

The alias map lives in three places that drifted apart before: `MODEL_ALIASES` in the
companion runtime, the alias table in `codex:model-guide`, and the model table in the
`codex:rescue` worker outline. These tests parse all three and require them to agree,
in the canonical sources and in the packaged Claude and Codex copies. They also pin the
alias decision (bare names stay on GPT-5.6), the GPT-6 rows and default efforts, and
the `--model` documentation for the review commands.
The runtime behaviour (aliases resolved on task, review, and adversarial-review) is
tested in tests/codex/model-aliases.test.mjs.
"""

import re
import unittest
from pathlib import Path

import yaml

REPO = Path(__file__).resolve().parent.parent
SKILLS = REPO / "skills"
COMPANION = REPO / "plugins" / "codex" / "scripts" / "codex-companion.mjs"
CODEX_COMPANION = REPO / "dist" / "codex" / "plugins" / "codex" / "scripts" / "codex-companion.mjs"
GUIDE = SKILLS / "codex-model-guide" / "SKILL.md"
OUTLINE = SKILLS / "codex-rescue" / "references" / "subagent.rst"
PACKAGED_ROOTS = [
    REPO / "plugins" / "codex" / "skills",
    REPO / "dist" / "codex" / "plugins" / "codex" / "skills",
]

EXPECTED = {
    "spark": "gpt-5.3-codex-spark",
    "sol": "gpt-5.6-sol",
    "terra": "gpt-5.6-terra",
    "luna": "gpt-5.6-luna",
    "sol-5.6": "gpt-5.6-sol",
    "terra-5.6": "gpt-5.6-terra",
    "luna-5.6": "gpt-5.6-luna",
    "astra": "gpt-6-astra",
    "astra-6": "gpt-6-astra",
    "sol-6": "gpt-6-sol",
    "luna-6": "gpt-6-luna",
}


def js_aliases(path: Path) -> dict:
    src = path.read_text()
    block = re.search(r"const MODEL_ALIASES = new Map\(\[(.*?)\]\);", src, re.S)
    assert block, f"{path}: MODEL_ALIASES Map literal not found"
    return dict(re.findall(r'\[\s*"([^"]+)"\s*,\s*"([^"]+)"\s*\]', block.group(1)))


def section(text: str, heading: str) -> str:
    match = re.search(rf"^## {re.escape(heading)}\n(.*?)(?=^## |\Z)", text, re.S | re.M)
    assert match, f"missing section: {heading}"
    return match.group(1)


def guide_table(path: Path) -> tuple[list[str], list[dict]]:
    """Header and rows (dicts keyed by header cell) of the '## Models and aliases' table."""
    body = section(path.read_text(), "Models and aliases")
    lines = [line for line in body.splitlines() if line.startswith("|")]
    split = lambda line: [cell.strip() for cell in line.strip("|").split("|")]
    header = split(lines[0])
    assert "Aliases (`--model`)" in header and "Full id" in header, header
    return header, [dict(zip(header, split(line))) for line in lines[2:]]


def guide_rows(path: Path) -> list[dict]:
    return guide_table(path)[1]


def guide_aliases(path: Path) -> dict:
    mapping = {}
    for row in guide_rows(path):
        full = re.fullmatch(r"`([^`]+)`", row["Full id"])
        assert full, f"full-id cell must be one code span: {row['Full id']!r}"
        for alias in re.findall(r"`([^`]+)`", row["Aliases (`--model`)"]):
            assert alias not in mapping, f"alias {alias} listed twice"
            mapping[alias] = full.group(1)
    return mapping


def outline_table(path: Path) -> list[tuple[str, str]]:
    """(user-says cell, --model cell) rows of the rescue outline's RST simple table."""
    lines = path.read_text().splitlines()
    rules = [i for i, line in enumerate(lines) if re.fullmatch(r"\s*=+\s+=+\s*", line)]
    assert len(rules) == 3, f"expected one simple table with 3 rules, found {len(rules)}"
    split = lines[rules[0]].rindex(" ") + 1
    rows = []
    for line in lines[rules[1] + 1 : rules[2]]:
        rows.append((line[:split].strip(), line[split:].strip()))
    return rows


def outline_aliases(path: Path) -> dict:
    mapping = {}
    for says, model in outline_table(path):
        full = re.fullmatch(r"``([^`]+)``", model)
        assert full, f"--model cell must be one literal: {model!r}"
        for alias in re.findall(r"``([^`]+)``", says):
            mapping[alias] = full.group(1)
    return mapping


def outline_phrases(path: Path) -> dict:
    mapping = {}
    for says, model in outline_table(path):
        for phrase in re.findall(r'"([^"]+)"', says):
            mapping[phrase.lower()] = model.strip("`")
    return mapping


def frontmatter(path: Path) -> dict:
    return yaml.safe_load(path.read_text().split("---\n", 2)[1]) or {}


class AliasSourcesAgree(unittest.TestCase):
    def test_companion_holds_the_decided_map(self):
        self.assertEqual(js_aliases(COMPANION), EXPECTED)

    def test_packaged_codex_companion_matches(self):
        self.assertEqual(js_aliases(CODEX_COMPANION), js_aliases(COMPANION))

    def test_model_guide_table_matches_companion(self):
        self.assertEqual(guide_aliases(GUIDE), js_aliases(COMPANION))

    def test_rescue_outline_table_matches_companion(self):
        aliases = js_aliases(COMPANION)
        without_spark = {k: v for k, v in aliases.items() if k != "spark"}
        self.assertEqual(outline_aliases(OUTLINE), without_spark)
        # spark keeps its own forwarding rule above the table.
        self.assertIn("``--model gpt-5.3-codex-spark``", OUTLINE.read_text())

    def test_packaged_copies_agree(self):
        for root in PACKAGED_ROOTS:
            with self.subTest(root=root):
                self.assertEqual(guide_aliases(root / "model-guide" / "SKILL.md"), EXPECTED)
                self.assertEqual(
                    outline_aliases(root / "rescue" / "references" / "subagent.rst"),
                    {k: v for k, v in EXPECTED.items() if k != "spark"},
                )


class AliasDecision(unittest.TestCase):
    def test_bare_names_stay_on_gpt_5_6(self):
        # Pinned against the parsed runtime map, not EXPECTED, so it can fail on its own.
        aliases = js_aliases(COMPANION)
        for name in ("sol", "terra", "luna"):
            self.assertEqual(aliases[name], f"gpt-5.6-{name}")

    def test_gpt6_rejection_is_reported_not_retried(self):
        # A user who asked for luna-6 must not silently get gpt-5.6-luna: the rescue
        # contract allows exactly one task call and no substitution.
        caveats = section(GUIDE.read_text(), "GPT-6 availability caveats")
        self.assertIn("report the rejection", caveats)
        self.assertIn("Do not retry automatically", caveats)
        self.assertNotRegex(caveats, r"(?i)\bretry with\b")
        for root in PACKAGED_ROOTS:
            packaged = section((root / "model-guide" / "SKILL.md").read_text(), "GPT-6 availability caveats")
            self.assertIn("Do not retry automatically", packaged, str(root))

    def test_version_phrasings_in_rescue_outline(self):
        # #393: "luna 6" through /codex:rescue must reach gpt-6-luna.
        phrases = outline_phrases(OUTLINE)
        self.assertEqual(phrases["luna 6"], "gpt-6-luna")
        self.assertEqual(phrases["sol 6"], "gpt-6-sol")
        self.assertEqual(phrases["astra 6"], "gpt-6-astra")
        self.assertEqual(phrases["luna 5.6"], "gpt-5.6-luna")
        self.assertEqual(phrases["sol 5.6"], "gpt-5.6-sol")
        self.assertEqual(phrases["terra 5.6"], "gpt-5.6-terra")

    def test_no_gpt6_terra_mapping(self):
        for mapping in (js_aliases(COMPANION), guide_aliases(GUIDE), outline_aliases(OUTLINE)):
            self.assertNotIn("terra-6", mapping)
            self.assertNotIn("gpt-6-terra", mapping.values())
        # Both docs say so, so "terra 6" is not silently mapped to another model.
        self.assertIn("no** `gpt-6-terra`", GUIDE.read_text())
        self.assertIn("no GPT-6 Terra", OUTLINE.read_text())

    def test_rescue_skill_names_gpt6_forms(self):
        # codex:rescue owns the spoken-form mapping; codex:cli-runtime is loaded in
        # the same context and defers to it and to codex:model-guide (#310).
        text = (SKILLS / "codex-rescue" / "SKILL.md").read_text()
        for token in ("gpt-5.6-luna", "sol-6", "luna-6", "astra", "gpt-6-luna", "codex:model-guide"):
            self.assertIn(token, text)
        runtime = (SKILLS / "codex-cli-runtime" / "SKILL.md").read_text()
        self.assertIn("codex:model-guide", runtime)
        self.assertNotIn("gpt-6-luna", runtime)


class ModelGuideFacts(unittest.TestCase):
    def rows(self) -> dict:
        return {row["Full id"].strip("`"): row for row in guide_rows(GUIDE)}

    def test_gpt6_rows_and_default_efforts(self):
        rows = self.rows()
        for model in ("gpt-6-astra", "gpt-6-sol", "gpt-6-luna"):
            self.assertIn(model, rows)
        self.assertEqual(rows["gpt-6-sol"]["Default effort"], "medium")
        self.assertEqual(rows["gpt-6-luna"]["Default effort"], "medium")
        # Sol's `low` default is a GPT-5.6-only fact (#393).
        self.assertEqual(rows["gpt-5.6-sol"]["Default effort"], "low")
        effort = section(GUIDE.read_text(), "Reasoning effort ladder")
        self.assertIn("`gpt-5.6-sol` defaults to `low`", effort)
        self.assertNotIn("Sol defaults to `low`", effort)

    def test_ultra_column_matches_catalog(self):
        rows = self.rows()
        for model, ultra in {
            "gpt-5.6-sol": "yes", "gpt-5.6-terra": "yes", "gpt-5.6-luna": "no",
            "gpt-6-astra": "yes", "gpt-6-sol": "yes", "gpt-6-luna": "no",
        }.items():
            self.assertEqual(rows[model]["`ultra`"], ultra, model)
        # The old "Sol/Terra only" wording is wrong once Astra exists.
        for path in SKILLS.glob("codex-*/**/*"):
            if path.is_file():
                self.assertNotRegex(path.read_text(), r"Sol/Terra\s+only", str(path))

    def test_spark_and_context_facts(self):
        rows = self.rows()
        self.assertRegex(rows["gpt-5.3-codex-spark"]["Position"], r"Unverified.*0\.157\.0")
        aliases = section(GUIDE.read_text(), "Models and aliases")
        self.assertRegex(aliases, r"GPT-6: Codex harness context 272,000 tokens.*0\.157\.0")
        self.assertIn("by design", aliases)

    def test_review_model_precedence_has_bounded_live_evidence(self):
        for text in (
            (SKILLS / "codex-review" / "SKILL.md").read_text(),
            section(GUIDE.read_text(), "Review commands"),
        ):
            self.assertRegex(text, r"\d{4}-\d{2}-\d{2} with CLI \d+\.\d+\.\d+")
            self.assertIn("a persisted app-server probe", text)
            self.assertIn("nq-rdl/agent-extensions#430", text)
            self.assertIn("ephemeral", text)
            self.assertIn("does not expose the reviewer model", text)
            self.assertNotIn("not verified against a live backend", text)

    def test_no_unmaintained_prices(self):
        # #308: no price source or maintenance process exists in this repo.
        header, _ = guide_table(GUIDE)
        self.assertFalse([cell for cell in header if "price" in cell.lower()], header)
        text = GUIDE.read_text()
        self.assertNotRegex(text, r"\$\d")
        self.assertNotIn("relative cost signal", text)

    def test_pin_and_gpt6_caveats(self):
        text = GUIDE.read_text()
        self.assertIn("0.144.6", text)
        self.assertIn("0.156.1", text)
        caveats = section(text, "GPT-6 availability caveats")
        self.assertIn("0.155.0", caveats)
        self.assertIn("ChatGPT", caveats)
        self.assertIn("GPT-6", frontmatter(GUIDE)["description"])


class ReviewModelDocs(unittest.TestCase):
    def test_argument_hints_list_model(self):
        for name in ("codex-review", "codex-adversarial-review"):
            with self.subTest(skill=name):
                self.assertIn("--model <model|alias>", frontmatter(SKILLS / name / "SKILL.md")["argument-hint"])
                self.assertIn("--model", (SKILLS / name / "references" / "codex.rst").read_text())

    def test_review_model_config_key_documented(self):
        self.assertIn("review_model", (SKILLS / "codex-review" / "SKILL.md").read_text())
        self.assertIn("review_model", section(GUIDE.read_text(), "Review commands"))

    def test_companion_usage_lists_model_for_reviews(self):
        src = COMPANION.read_text()
        for sub in ("review", "adversarial-review"):
            line = re.search(rf'"  node scripts/codex-companion\.mjs {sub} ([^"]*)"', src)
            self.assertIsNotNone(line, sub)
            self.assertIn("--model <model|alias>", line.group(1))

    # Review-path normalisation is tested behaviourally in
    # tests/codex/model-aliases.test.mjs, not by grepping the source here.

if __name__ == "__main__":
    unittest.main()
