"""Offline regressions for the separately recorded Obsidian application pilot.

These tests check evidence and shipped guidance; they do not launch Obsidian.
"""

import json
import unittest
from pathlib import Path

import yaml

REPO = Path(__file__).resolve().parent.parent


class DateGuidanceContracts(unittest.TestCase):
    def test_elapsed_days_and_dst_are_explicit_in_both_entrypoints(self):
        for relative in (
            "skills/obsidian-bases/SKILL.md",
            "skills/obsidian-bases/references/FUNCTIONS_REFERENCE.rst",
        ):
            with self.subTest(path=relative):
                text = (REPO / relative).read_text()
                self.assertIn("elapsed 24-hour days", text)
                self.assertIn("23 or 25 hours", text)
                self.assertIn("1.13.7", text)

    def test_duration_field_table_identifies_elapsed_not_calendar_days(self):
        text = (REPO / "skills/obsidian-bases/references/FUNCTIONS_REFERENCE.rst").read_text()
        self.assertIn("| `duration.days` | Number | Elapsed 24-hour days |", text)
        self.assertNotIn("# CORRECT: Calculate days between dates", text)

    def test_current_application_support_does_not_imply_all_older_versions(self):
        text = (REPO / "skills/obsidian-bases/SKILL.md").read_text()
        self.assertIn("other versions", text)
        self.assertIn(".days.round(0)", text)
        self.assertIn("verify", text.lower())


class ApplicationEvidenceContracts(unittest.TestCase):
    """Check captured evidence completeness without pretending to rerun the app."""

    fixtures = REPO / "tests/fixtures/obsidian-bases-dates"

    def captures(self):
        for filename in ("america-new-york.json", "utc.json"):
            capture = json.loads((self.fixtures / filename).read_text())
            self.assertNotIn("exceptionDetails", capture["result"])
            yield filename, capture["result"]["result"]["value"]

    def test_capture_matches_the_disposable_vault_and_actual_version(self):
        fixture = yaml.safe_load((self.fixtures / "vault/date-arithmetic.base").read_text())
        for filename, capture in self.captures():
            with self.subTest(capture=filename):
                self.assertIn("Obsidian 1.13.7", capture["title"])
                self.assertTrue(capture["corePluginEnabled"])
                self.assertEqual(capture["query"]["formulas"], fixture["formulas"])
                self.assertEqual(capture["query"]["filters"], fixture["filters"])
                self.assertEqual({row["file"] for row in capture["rows"]}, {"fixture.md", "missing-due.md"})
                for row in capture["rows"]:
                    self.assertEqual({v["name"] for v in row["values"]}, set(fixture["formulas"]))
                    self.assertTrue(all("error" not in v for v in row["values"]))

    def test_known_duration_values_and_rounding(self):
        expected = {
            "one_day": (86400000, 1, 1, 1, 1),
            "fraction": (131400000, 1.5208333333333333, 2, 1, 2),
            "zero": (0, 0, 0, 0, 0),
            "negative": (-129600000, -1.5, -1, -2, -1),
        }
        for filename, capture in self.captures():
            for row in capture["rows"]:
                values = {v["name"]: v for v in row["values"]}
                for case, (milliseconds, days, rounded, floored, ceiled) in expected.items():
                    with self.subTest(capture=filename, file=row["file"], case=case):
                        self.assertEqual(values[case + "_raw"]["type"], "Duration")
                        self.assertEqual(values[case + "_raw"]["milliseconds"], milliseconds)
                        self.assertTrue(values[case + "_is_duration"]["data"])
                        self.assertFalse(values[case + "_is_number"]["data"])
                        for suffix, expected_value in (("days", days), ("milliseconds", milliseconds),
                                                       ("days_round", rounded), ("days_floor", floored),
                                                       ("days_ceil", ceiled)):
                            self.assertEqual(values[f"{case}_{suffix}"]["type"], "Number")
                            self.assertAlmostEqual(values[f"{case}_{suffix}"]["data"], expected_value)
                        for suffix in ("direct_round", "divide_round"):
                            self.assertEqual(values[f"{case}_{suffix}"]["type"], "Error")
                            self.assertIn('Cannot find function "round" on type Duration', values[f"{case}_{suffix}"]["text"])

    def test_timezone_changes_the_elapsed_day_count_at_both_dst_boundaries(self):
        for filename, capture in self.captures():
            self.assertEqual(capture["timezone"], "UTC" if filename == "utc.json" else "America/New_York")
            expected_hours = {"spring_dst": 24, "fall_dst": 24} if capture["timezone"] == "UTC" else {
                "spring_dst": 23, "fall_dst": 25,
            }
            for row in capture["rows"]:
                values = {v["name"]: v for v in row["values"]}
                for case, hours in expected_hours.items():
                    with self.subTest(capture=filename, file=row["file"], case=case):
                        self.assertEqual(values[f"{case}_hours"]["data"], hours)
                        self.assertAlmostEqual(values[f"{case}_days"]["data"], hours / 24)
                        self.assertEqual(values[f"{case}_milliseconds"]["data"], hours * 3600000)
                        self.assertEqual(values[f"{case}_days_round"]["data"], 1)
                        self.assertEqual(values[f"{case}_raw"]["type"], "Duration")
                        self.assertEqual(values[f"{case}_raw"]["milliseconds"], hours * 3600000)
                        self.assertTrue(values[f"{case}_is_duration"]["data"])
                        self.assertFalse(values[f"{case}_is_number"]["data"])
                        for suffix in ("hours", "days", "milliseconds", "days_floor", "days_ceil"):
                            self.assertEqual(values[f"{case}_{suffix}"]["type"], "Number")
                        self.assertEqual(values[f"{case}_days_floor"]["data"], 0 if hours == 23 else 1)
                        self.assertEqual(values[f"{case}_days_ceil"]["data"], 2 if hours == 25 else 1)
                        for suffix in ("direct_round", "divide_round"):
                            self.assertEqual(values[f"{case}_{suffix}"]["type"], "Error")
                            self.assertIn('Cannot find function "round" on type Duration',
                                          values[f"{case}_{suffix}"]["text"])

    def test_numeric_date_conversion_and_decimal_rounding(self):
        for filename, capture in self.captures():
            for row in capture["rows"]:
                values = {v["name"]: v for v in row["values"]}
                for case in ("one_day", "fraction", "zero", "negative", "spring_dst", "fall_dst"):
                    with self.subTest(capture=filename, file=row["file"], case=case):
                        self.assertEqual(values[f"{case}_numeric_dates"]["type"], "Number")
                        self.assertAlmostEqual(values[f"{case}_numeric_dates"]["data"],
                                               values[f"{case}_days"]["data"])
                        self.assertEqual(values[f"{case}_hours"]["type"], "Number")
                        self.assertAlmostEqual(values[f"{case}_hours"]["data"],
                                               values[f"{case}_milliseconds"]["data"] / 3600000)
                expected = {"fraction": 1.521, "spring_dst": 1, "fall_dst": 1}
                if capture["timezone"] == "America/New_York":
                    expected.update(spring_dst=0.958, fall_dst=1.042)
                for case, rounded in expected.items():
                    with self.subTest(capture=filename, file=row["file"], case=case):
                        self.assertEqual(values[f"{case}_days_round_3"]["type"], "Number")
                        self.assertEqual(values[f"{case}_days_round_3"]["data"], rounded)

    def test_explicit_duration_conversion_and_missing_optional_property(self):
        for filename, capture in self.captures():
            for row in capture["rows"]:
                values = {v["name"]: v for v in row["values"]}
                with self.subTest(capture=filename, file=row["file"]):
                    self.assertEqual(values["duration_day"]["type"], "Duration")
                    self.assertEqual(values["duration_day"]["milliseconds"], 86400000)
                    for name, expected in (("duration_days", 1.5), ("duration_hours", 36),
                                           ("duration_milliseconds", 129600000), ("duration_days_round", 2)):
                        self.assertEqual(values[name]["type"], "Number")
                        self.assertEqual(values[name]["data"], expected)
                    self.assertEqual(values["duration_round"]["type"], "Error")
                    self.assertIn('Cannot find function "round" on type Duration', values["duration_round"]["text"])
                    self.assertEqual(values["duration_double"]["type"], "Date")
                    self.assertEqual(values["duration_double"]["text"], "2026-01-03")
                    if row["file"] == "missing-due.md":
                        self.assertEqual(values["optional_due"]["type"], "String")
                        self.assertEqual(values["optional_due"]["data"], "")


if __name__ == "__main__":
    unittest.main()
