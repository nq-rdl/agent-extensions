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


def decimal_oracle(n):
    """Independent decimal oracle for the published synthetic examples only."""
    if n == 0:
        return "about 0"
    if n < 7:
        return "<7"
    if n < 15:
        return "between 7 and 14"
    step = 5 if n < 100 else 10 if n < 1000 else 10 ** (len(str(n)) - 2)
    rounded = (Decimal(n) / step).quantize(Decimal(1), rounding=ROUND_HALF_UP) * step
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
                table = text.split("Boundary test table", 1)[1].split("Unlike the guideline", 1)[0]
                rows = re.findall(r"^  (\d+) \| (.+)$", table, re.M)
                self.assertEqual(len(rows), len(EXPECTED))
                self.assertEqual({int(n): shown for n, shown in rows}, EXPECTED)
                for n, shown in rows:
                    self.assertEqual(decimal_oracle(int(n)), shown, n)

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
        ):
            self.assertIn(phrase, text)

    def test_stages_route_probes_to_shared_policy(self):
        for source in ("guardrails", "map", "draft", "validate"):
            with self.subTest(source=source):
                text = (REPO / f"skills/data-request-{source}/SKILL.md").read_text()
                self.assertIn("Probe disclosure control", text)
                self.assertIn("references/release.rst", text)
        performance = (TREES[0] / "references/performance.rst").read_text()
        self.assertIn("release.rst#probe-disclosure-control", performance)
