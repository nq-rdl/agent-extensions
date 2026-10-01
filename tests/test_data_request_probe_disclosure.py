"""Offline authored boundary contract, not a deployed formatter or disclosure lint."""
import re
import unittest
from decimal import Decimal, ROUND_HALF_UP
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
TREES = (
    REPO / "skills/data-request-guardrails",
    REPO / "plugins/data-request/skills/guardrails",
    REPO / "dist/codex/plugins/data-request/skills/guardrails",
)
EXPECTED = {
    0: "about 0", 1: "<7", 6: "<7",
    7: "between 7 and 14", 14: "between 7 and 14",
    15: "about 15", 17: "about 15", 18: "about 20",
    99: "about 100", 100: "about 100", 104: "about 100", 105: "about 110",
    994: "about 990", 995: "about 1.0k", 996: "about 1.0k", 999: "about 1.0k",
    1000: "about 1.0k", 1049: "about 1.0k", 1050: "about 1.1k",
    9999: "about 10k", 10000: "about 10k",
    99949: "about 100k", 99999: "about 100k", 100000: "about 100k",
    994999: "about 990k", 995000: "about 1.0M", 999499: "about 1.0M",
    999500: "about 1.0M", 999999: "about 1.0M", 1000000: "about 1.0M",
}

RAISED_EXPECTED = {
    (10, 1): "<15", (10, 9): "<15", (10, 10): "<15", (10, 14): "<15",
    (10, 15): "between 15 and 20", (10, 18): "about 20",
    (16, 1): "<16", (16, 15): "<16", (16, 16): "between 16 and 20",
    (16, 17): "between 16 and 20", (16, 18): "about 20",
    (21, 20): "<21", (21, 21): "between 21 and 25",
    (24, 24): "between 24 and 30",
}


def decimal_oracle(n, assessment_floor=7):
    """Independent decimal oracle for the published synthetic examples only."""
    floor = max(7, assessment_floor)
    if 7 < floor <= 14:
        floor = 15
    if n == 0:
        return "about 0"
    if n < floor:
        return f"<{floor}"
    if n < 15:
        return "between 7 and 14"
    step = 5 if n < 100 else 10 if n < 1000 else 10 ** (len(str(n)) - 2)
    rounded = (Decimal(n) / step).quantize(Decimal(1), rounding=ROUND_HALF_UP) * step
    if floor >= 15 and rounded - Decimal(step) / 2 < floor:
        return f"between {floor} and {rounded + step}"
    if rounded < 1000:
        return f"about {rounded}"
    unit, divisor = ("M", 1000000) if rounded >= 1000000 else ("k", 1000)
    value = rounded / divisor
    shown = f"{value:.1f}" if value < 10 else f"{value:.0f}"
    return f"about {shown}{unit}"


class ProbeDisclosure(unittest.TestCase):
    def test_boundary_table_is_pinned_and_decimal_half_up(self):
        for tree in TREES:
            with self.subTest(tree=tree):
                text = (tree / "references/release.rst").read_text()
                table = text.split("Boundary test table", 1)[1].split("Raised-floor boundary table", 1)[0]
                rows = re.findall(r"^  (\d+) \| (.+)$", table, re.M)
                self.assertEqual(len(rows), len(EXPECTED))
                self.assertEqual({int(n): shown for n, shown in rows}, EXPECTED)
                for n, shown in rows:
                    self.assertEqual(decimal_oracle(int(n)), shown, n)

    def test_raised_floor_table_and_half_up_formula(self):
        for tree in TREES:
            with self.subTest(tree=tree):
                text = (tree / "references/release.rst").read_text()
                flat = " ".join(text.split())
                self.assertIn("rounded = s * floor((2*n + s) / (2*s))", flat)
                self.assertIn("if 2*rounded - s < 2*F", flat)
                self.assertIn("X = rounded + s", flat)
                table = text.split("Raised-floor boundary table", 1)[1].split("Unlike the guideline", 1)[0]
                rows = re.findall(r"^  (\d+) \| (\d+) \| (.+)$", table, re.M)
                self.assertEqual(len(rows), len(RAISED_EXPECTED))
                self.assertEqual({(int(f), int(n)): shown for f, n, shown in rows}, RAISED_EXPECTED)
                for floor, n, shown in rows:
                    self.assertEqual(decimal_oracle(int(n), int(floor)), shown, (floor, n))

    def test_raised_floor_has_one_token_and_no_below_floor_interval(self):
        for assessment_floor in (10, 16, 21, 24, 105):
            floor = 15 if assessment_floor == 10 else assessment_floor
            for n in range(1, floor + 100):
                shown = decimal_oracle(n, assessment_floor)
                with self.subTest(floor=floor, n=n):
                    if n < floor:
                        self.assertEqual(shown, f"<{floor}")
                    elif shown.startswith("between"):
                        low, high = map(int, re.findall(r"\d+", shown))
                        self.assertEqual(low, floor)
                        self.assertLessEqual(low, n)
                        self.assertGreaterEqual(high, n)
                    else:
                        rounded = Decimal(shown.removeprefix("about "))
                        step = 5 if n < 100 else 10 if n < 1000 else 10 ** (len(str(n)) - 2)
                        self.assertGreaterEqual(rounded - Decimal(step) / 2, floor)

    def test_single_reference_is_synced_and_covers_review_controls(self):
        canonical = (TREES[0] / "references/release.rst").read_bytes()
        for tree in TREES:
            with self.subTest(tree=tree):
                self.assertEqual((tree / "references/release.rst").read_bytes(), canonical)
        text = " ".join(canonical.decode().split())
        for phrase in (
            "v2.0 (March 2026)", "RDL-only", "Handover", "Open channels",
            "distinct-label total", "exact operands", "checked equality",
            "every file of the handover set", "provenance hashes", "git history",
            "probe result id", "[structural-count]", "not an installed lint tool",
            "If exact counts reach you, do not repeat them", "including RDL-only results",
            "Only rounding is relaxed", "Never request unsuppressed totals for subtraction",
            "treat NULL/blank counts as parts", "never of an identifier, name or free-text column",
            "Runbooks reference that file rather than embedding exact counts",
            "A runbook or results file not excluded from the handover set is handover tier",
            "before writing any handover or open-channel text",
            "below F, never show the share/ratio as a number",
            "must not narrow that numerator or remainder more precisely than ``<F``",
            "rounding reaches 0% or 100% must use an open band",
            "cite the results file, SQL revision and run date",
            "fixed workbook format limits (1,048,575; 16,384; 32,767; 31)",
            "bare population counts of 1–6; reviewers must reject those too",
            "if that check fails, show the same ``<F`` token", "with no separate threshold",
            "except when rounding carries to a new power of ten", "decimal digit count",
            "No runner enforces these controls yet",
        ):
            self.assertIn(phrase, text)

    def test_stages_route_probes_to_shared_policy(self):
        for source in ("guardrails", "map", "draft", "validate", "release", "analyse", "fix"):
            with self.subTest(source=source):
                text = (REPO / f"skills/data-request-{source}/SKILL.md").read_text()
                self.assertIn("Probe disclosure control", text)
                self.assertIn("references/release.rst", text)
        performance = (TREES[0] / "references/performance.rst").read_text()
        self.assertIn("release.rst#probe-disclosure-control", performance)
        self.assertIn("take MIN and MAX samples per group", performance)
        mapping = (REPO / "skills/data-request-map/SKILL.md").read_text()
        self.assertIn("disclosure permission.\n\n**Exempt probes:**", mapping)
