"""Offline authored boundary/property contract, not a deployed disclosure formatter."""
import re
import unittest
from collections import defaultdict
from decimal import Decimal, ROUND_HALF_UP
from functools import cache
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
    (10, 15): "between 15 and 22", (10, 22): "between 15 and 22", (10, 23): "about 25",
    (16, 1): "<16", (16, 15): "<16", (16, 16): "between 16 and 22",
    (16, 22): "between 16 and 22", (16, 23): "about 25",
    (17, 16): "<17", (17, 17): "between 17 and 22",
    (17, 22): "between 17 and 22", (17, 23): "about 25",
    (21, 20): "<21", (21, 21): "between 21 and 27",
    (22, 21): "<22", (22, 22): "between 22 and 27",
    (22, 27): "between 22 and 27", (22, 28): "about 30",
    (24, 24): "between 24 and 32",
    (97, 96): "<97", (97, 97): "between 97 and 114",
    (97, 99): "between 97 and 114", (97, 114): "between 97 and 114", (97, 115): "about 120",
    (951, 951): "between 951 and 1149", (951, 995): "between 951 and 1149",
    (951, 1149): "between 951 and 1149", (951, 1150): "about 1.2k",
    (1000, 999): "<1000", (1000, 1000): "between 1000 and 1149",
    (1000, 1149): "between 1000 and 1149", (1000, 1150): "about 1.2k",
}


def step(n):
    return 5 if n < 100 else 10 if n < 1000 else 10 ** (len(str(n)) - 2)


def display_floor(assessment_floor):
    floor = max(7, assessment_floor)
    return 15 if 7 < floor <= 14 else floor


@cache
def rounded(n):
    """Independent decimal half-up oracle, not the documented integer formula."""
    s = step(n)
    return int((Decimal(n) / s).quantize(Decimal(1), rounding=ROUND_HALF_UP) * s)


@cache
def ordinary_display(n):
    r = rounded(n)
    if r < 1000:
        return f"about {r}"
    unit, divisor = ("M", 1000000) if r >= 1000000 else ("k", 1000)
    value = Decimal(r) / divisor
    shown = f"{value:.1f}" if value < 10 else f"{value:.0f}"
    return f"about {shown}{unit}"


@cache
def intervals():
    # Exact preimages, including BOTH sides of tier transitions, for the tested
    # floor domain (<=2000). 4000 is beyond all unsafe intervals in this domain.
    preimages = defaultdict(list)
    for n in range(15, 4001):
        preimages[rounded(n)].append(n)
    return [(r, ns, max(step(r), *(step(n) for n in ns)))
            for r, ns in sorted(preimages.items())]


@cache
def band_top(floor):
    assert 15 <= floor <= 2000, "oracle's raised-floor domain is intentionally bounded"
    rows = intervals()
    unsafe = [i for i, (r, ns, s) in enumerate(rows)
              if ns[-1] >= floor and 2*r - s < 2*floor]
    start = unsafe[-1] + 1 if unsafe else 0
    for r, ns, s in rows[start:]:
        if ns[-1] >= floor and 2*r - s >= 2*floor:
            return ns[-1]
    raise AssertionError(floor)


def decimal_oracle(n, assessment_floor=7):
    floor = display_floor(assessment_floor)
    if n == 0:
        return "about 0"  # only when the separate differencing check permits it
    if n < floor:
        return f"<{floor}"
    if n < 15:
        return "between 7 and 14"
    if floor >= 15 and n <= band_top(floor):
        return f"between {floor} and {band_top(floor)}"
    return ordinary_display(n)


class ProbeDisclosure(unittest.TestCase):
    def test_published_tables_match_decimal_oracle(self):
        for tree in TREES:
            with self.subTest(tree=tree):
                text = (tree / "references/release.rst").read_text()
                flat = " ".join(text.split())
                self.assertIn("rounded = s * floor((2*n + s) / (2*s))", flat)
                self.assertIn("require 2*r - S >= 2*F", flat)
                self.assertIn("at least **three exact preimages**", flat)
                table = text.split("Boundary test table", 1)[1].split("Raised-floor boundary table", 1)[0]
                rows = re.findall(r"^  (\d+) \| (.+)$", table, re.M)
                self.assertEqual(len(rows), len(EXPECTED))
                self.assertEqual({int(n): shown for n, shown in rows}, EXPECTED)
                for n, shown in rows:
                    self.assertEqual(decimal_oracle(int(n)), shown, n)
                table = text.split("Raised-floor boundary table", 1)[1].split("Unlike the guideline", 1)[0]
                rows = re.findall(r"^  (\d+) \| (\d+) \| (.+)$", table, re.M)
                self.assertEqual(len(rows), len(RAISED_EXPECTED))
                self.assertEqual({(int(f), int(n)): shown for f, n, shown in rows}, RAISED_EXPECTED)
                for floor, n, shown in rows:
                    self.assertEqual(decimal_oracle(int(n), int(floor)), shown, (floor, n))

    def test_integer_formula_matches_independent_decimal_rounding(self):
        for n in range(15, 100001):
            s = step(n)
            self.assertEqual(s * ((2*n + s) // (2*s)), rounded(n), n)

    def test_all_floors_preserve_intervals_and_three_preimages(self):
        # Properties cover every floor 7..2000 and positive input 1..3000.
        # Enumerate to 4000 so the last tested interval is not falsely truncated.
        base_steps = {n: step(n) for n in range(15, 4001)}
        centres = {ordinary_display(n): rounded(n) for n in range(15, 4001)}
        for assessment_floor in range(7, 2001):
            floor = display_floor(assessment_floor)
            groups = defaultdict(list)
            for n in range(1, 4001):
                groups[decimal_oracle(n, assessment_floor)].append(n)
            for shown, preimages in groups.items():
                if preimages[0] > 3000:
                    continue
                context = (assessment_floor, shown, preimages[:3])
                if shown.startswith("<"):
                    self.assertEqual(shown, f"<{floor}", context)
                    self.assertTrue(all(n < floor for n in preimages), context)
                    continue
                self.assertGreaterEqual(len(preimages), 3, context)
                if shown.startswith("between"):
                    low, high = map(int, re.findall(r"\d+", shown))
                    self.assertGreaterEqual(low, floor, context)
                    self.assertTrue(all(low <= n <= high for n in preimages), context)
                    # Every integer in a published band receives the SAME display.
                    self.assertEqual(preimages, list(range(low, high + 1)), context)
                else:
                    r = centres[shown]
                    for n in preimages:
                        s = max(base_steps[n], step(r))
                        self.assertGreaterEqual(2*r - s, 2*floor, context)

    def test_single_reference_is_synced_and_covers_review_controls(self):
        canonical = (TREES[0] / "references/release.rst").read_bytes()
        for tree in TREES:
            self.assertEqual((tree / "references/release.rst").read_bytes(), canonical)
        text = " ".join(canonical.decode().split())
        for phrase in (
            "v2.0 (March 2026)", "If exact counts reach you, do not repeat them",
            "including RDL-only results", "Only rounding is relaxed",
            "Never request unsuppressed totals for subtraction", "treat NULL/blank counts as parts",
            "never of an identifier, name or free-text column",
            "A runbook or results file not excluded from the handover set is handover tier",
            "If a numerator, denominator or remainder is below F",
            "exact denominator N is below 100", "combined count/share preimages",
            "rounding reaches 0% or 100% must use an open band",
            "manual/interim formatting", "an agent may compute them",
            "Band bounds are full ungrouped integers", "throughout handover/open text",
            "Delivered extracts use the assessment's tokens",
            "No runner enforces these controls yet",
        ):
            self.assertIn(phrase, text)

    def test_stages_route_probes_to_shared_policy(self):
        for source in ("guardrails", "map", "draft", "validate", "release", "analyse", "fix", "amend"):
            with self.subTest(source=source):
                text = (REPO / f"skills/data-request-{source}/SKILL.md").read_text()
                self.assertIn("Probe disclosure control", text)
                self.assertIn("references/release.rst", text)
        performance = (TREES[0] / "references/performance.rst").read_text()
        self.assertIn("release.rst#probe-disclosure-control", performance)
        self.assertIn("take MIN and MAX samples per group", performance)
