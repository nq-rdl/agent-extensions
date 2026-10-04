"""Tests for the SkillSpector OWASP Agentic Skills Top 10 classification.

``tools/skillspector/merge-sarif.sh`` merges the per-skill SARIF reports from
``scan.sh`` and tags every rule and result with its OWASP AST risk from
``tools/skillspector/owasp-ast10.json``; ``owasp-summary.sh`` renders the CI
job-summary table. Both are exercised here on fixture reports, so no Docker or
SkillSpector image is needed. Requires ``jq`` (as the scripts do).
"""

import json
import re
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
TOOLS = ROOT / "tools" / "skillspector"
MAP = json.loads((TOOLS / "owasp-ast10.json").read_text())


def result(rule_id, uri="SKILL.md", suppressed=False):
    r = {
        "ruleId": rule_id,
        "level": "error",
        "message": {"text": f"{rule_id} finding"},
        "locations": [
            {
                "physicalLocation": {
                    "artifactLocation": {"uri": uri},
                    "region": {"startLine": 1},
                }
            }
        ],
    }
    if suppressed:
        r["suppressions"] = [{"kind": "external", "justification": "baseline"}]
    return r


def report(results, rules=None):
    driver = {"name": "skillspector", "version": "test"}
    if rules is not None:
        driver["rules"] = [{"id": r, "shortDescription": {"text": r}} for r in rules]
    return {
        "$schema": "https://json.schemastore.org/sarif-2.1.0.json",
        "version": "2.1.0",
        "runs": [{"tool": {"driver": driver}, "results": results}],
    }


@unittest.skipUnless(shutil.which("jq"), "jq is required")
class SkillSpectorOwaspTest(unittest.TestCase):
    def merge(self, reports):
        """Write {skill: report} as <skill>.report, merge, and return the SARIF."""
        with tempfile.TemporaryDirectory() as tmp:
            outdir = Path(tmp) / "out"
            outdir.mkdir()
            for name, body in reports.items():
                text = body if isinstance(body, str) else json.dumps(body)
                (outdir / f"{name}.report").write_text(text)
            dest = Path(tmp) / "merged.sarif"
            subprocess.run(
                [str(TOOLS / "merge-sarif.sh"), str(outdir), str(dest)],
                check=True,
                capture_output=True,
                text=True,
            )
            return json.loads(dest.read_text())

    def summary(self, sarif):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "merged.sarif"
            path.write_text(json.dumps(sarif))
            proc = subprocess.run(
                [str(TOOLS / "owasp-summary.sh"), str(path)],
                check=True,
                capture_output=True,
                text=True,
            )
            return proc.stdout

    def test_mapping_targets_known_risks(self):
        self.assertEqual(sorted(MAP["risks"]), [f"AST{i:02d}" for i in range(1, 11)])
        for table in ("families", "rules"):
            for rule, entry in MAP[table].items():
                with self.subTest(table=table, rule=rule):
                    self.assertIn(entry["risk"], MAP["risks"])
                    self.assertTrue(entry["why"].strip())
        for family in MAP["families"]:
            self.assertRegex(family, r"^[A-Z]+$")

    def test_merge_single_run_prefixed_and_note_level(self):
        merged = self.merge(
            {
                "alpha": report([result("PE2", "scripts/run.sh")], rules=["PE2"]),
                "beta": report([result("SC1")]),
                "broken": "not sarif",
            }
        )
        self.assertEqual(len(merged["runs"]), 1)
        results = merged["runs"][0]["results"]
        uris = [r["locations"][0]["physicalLocation"]["artifactLocation"]["uri"] for r in results]
        self.assertEqual(uris, ["skills/alpha/scripts/run.sh", "skills/beta/SKILL.md"])
        self.assertEqual({r["level"] for r in results}, {"note"})

    def test_results_and_rules_tagged_with_owasp_risk(self):
        merged = self.merge(
            {
                "alpha": report([result("PE2"), result("TM4"), result("ZZ9")], rules=["PE2"]),
                "beta": report([result("PE2"), result("SC10")], rules=["PE2", "SC10"]),
            }
        )
        run = merged["runs"][0]
        got = {r["ruleId"]: r["properties"]["owasp-ast10"] for r in run["results"]}
        # Family prefix, exact-rule override, multi-digit suffix, and unmapped.
        self.assertEqual(got, {"PE2": "AST03", "TM4": "AST06", "SC10": "AST02", "ZZ9": "unmapped"})
        for r in run["results"]:
            self.assertIn("owasp-ast10/" + r["properties"]["owasp-ast10"], r["properties"]["tags"])

        rules = {r["id"]: r for r in run["tool"]["driver"]["rules"]}
        # Declared descriptors are unioned by id; result-only rule ids get a stub.
        self.assertEqual(sorted(rules), ["PE2", "SC10", "TM4", "ZZ9"])
        self.assertEqual(rules["PE2"]["shortDescription"]["text"], "PE2")
        self.assertEqual(rules["PE2"]["properties"]["tags"], ["owasp-ast10/AST03"])
        self.assertTrue(rules["TM4"]["helpUri"].endswith("/ast06"))
        self.assertNotIn("helpUri", rules["ZZ9"])

    def test_skillspector_ast10_is_not_owasp_ast10(self):
        # SkillSpector's AST10 is its Python-AST deserialization rule (OWASP AST04).
        merged = self.merge({"alpha": report([result("AST10"), result("AST4")])})
        got = [r["properties"]["owasp-ast10"] for r in merged["runs"][0]["results"]]
        self.assertEqual(got, ["AST04", "AST03"])

    def test_summary_counts_unsuppressed_findings(self):
        merged = self.merge(
            {
                "alpha": report(
                    [result("PE2"), result("EA1"), result("P1", suppressed=True), result("ZZ9")]
                )
            }
        )
        rows = {}
        for line in self.summary(merged).splitlines()[2:]:
            label, count = [c.strip() for c in line.strip("|").split("|")]
            rows[re.sub(r"^\[(AST\d\d) .*", r"\1", label)] = count
        self.assertEqual(rows["AST01"], "0")  # P1 is suppressed
        self.assertEqual(rows["AST03"], "2")
        self.assertEqual(rows["AST07"], "no SkillSpector rule")
        self.assertEqual(rows[next(k for k in rows if k.startswith("Unmapped"))], "1")

    def test_summary_omits_unmapped_row_when_none(self):
        merged = self.merge({"alpha": report([result("PE2")])})
        self.assertNotIn("Unmapped", self.summary(merged))


if __name__ == "__main__":
    unittest.main()
