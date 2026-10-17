"""Instruction contracts for #424; these do not prove live operator or board outcomes."""

import json
import os
import re
import shutil
import subprocess
import tempfile
import textwrap
import unittest
from pathlib import Path

import yaml

REPO = Path(__file__).resolve().parent.parent
SUITE = REPO / "evals/claude/data-request"
CASES = {
    "handoff-stale-run": {"gate", "destination", "board", "reviewer", "release_owner"},
    "handoff-prerelease-presentation": {"workflow", "classification", "baseline", "record", "row_keys", "review"},
    "handoff-analyst-send-back": {"outcome", "logic_route", "presentation_route", "release", "posted"},
}


def text(leaf):
    return " ".join((REPO / f"skills/data-request-{leaf}/SKILL.md").read_text().split())


class HandoffContracts(unittest.TestCase):
    def test_analyse_routes_new_and_unchanged_reviews_to_existing_handoff(self):
        body = text("analyse")
        self.assertIn("## After review: operator run, UAT and analyst hand-off", body)
        self.assertIn("Continue with *After review* below", body)
        self.assertIn("${CLAUDE_PLUGIN_ROOT}/skills/triage/references/handoff.rst", body)
        for token in ("Delivery", "Data Engineer", "Data Analyst", "operator run", "UAT", "never releases"):
            self.assertIn(token, body)

    def test_gate_matches_review_to_sql_that_ran_and_preserves_authorization(self):
        handoff = " ".join((REPO / "skills/data-request-triage/references/handoff.rst").read_text().split())
        for token in ("run commit", "SQL that actually ran", "release.sh", "DVC", "UAT sections 1 to 3",
                      "counts-only QA", "open questions", "limitations", "flagged decisions",
                      "roles.analyst", "tracking issue", "In-Review", "explicit instruction"):
            self.assertIn(token, handoff)
        self.assertIn("stop", handoff)
        self.assertIn("restricted", handoff)

    def test_explain_loads_durable_handoff_before_outcomes_on_fresh_invocation(self):
        for path in (REPO / "skills/data-request-explain/SKILL.md",
                     REPO / "plugins/data-request/skills/explain/SKILL.md",
                     REPO / "dist/codex/plugins/data-request/skills/explain/SKILL.md"):
            with self.subTest(path=path):
                body = " ".join(path.read_text().split())
                self.assertIn("## Load the durable hand-off", body)
                load = body.split("## Load the durable hand-off", 1)[1].split("## Resume", 1)[0]
                for token in ("hand-off comment URL", "child tracking issue", "current PR head SHA",
                              "run commit", "review revision", "SQL fingerprint", "DVC", "UAT",
                              "flagged decisions", "restrictions", "linked evidence", "ask",
                              "do not offer acceptance", "walkthrough", "Send back"):
                    self.assertIn(token, load)
                self.assertLess(body.index("## Load the durable hand-off"), body.index("## Analyst outcome"))
                outcome = body.split("## Analyst outcome", 1)[1]
                self.assertIn("loaded and rechecked", outcome)

    def test_pre_release_amend_preserves_baseline_and_avoids_release_record(self):
        amend = text("amend")
        for token in ("operator-run extract as the baseline", "run commit", "Do not add an `AMD-` entry",
                      "previous SQL at the run commit", "row count and key set", "not run", "pending"):
            self.assertIn(token, amend)
        self.assertNotIn("applies only to a released extract", amend)

    def test_amend_role_opening_preserves_pre_and_post_release_routing(self):
        # Read the role opening, not the later boundary paragraph: both must agree.
        for tree in ("skills/data-request-amend", "plugins/data-request/skills/amend",
                     "dist/codex/plugins/data-request/skills/amend"):
            with self.subTest(tree=tree):
                body = (REPO / tree / "SKILL.md").read_text().split("\n# Data Request", 1)[1]
                opening = " ".join(body.split("Arguments:", 1)[0].replace("**", "").split())
                self.assertIn("Data Analyst", opening)
                self.assertRegex(opening, r"before (?:or|and) after release")
                self.assertIn("Data Engineer", opening)
                self.assertNotIn("runs amend after release", opening)

    def test_analyst_send_back_is_a_paste_ready_outcome_without_approval(self):
        explain = text("explain")
        for token in ("Accept for release preparation", "Send back", "Presentation amendment",
                      "finding:", "expected result:", "route:", "/data-request:fix",
                      "/data-request:amend", "open gates:", "paste-ready", "not acceptance"):
            self.assertIn(token, explain)
        self.assertIn("Send back", text("release"))
        self.assertIn("Data Analyst", text("release"))

    def test_order_is_visible_at_each_delivery_entrypoint(self):
        for leaf in ("analyse", "explain", "amend", "fix", "release", "triage"):
            with self.subTest(leaf=leaf):
                body = text(leaf)
                self.assertIn("operator run", body)
                self.assertIn("hand-off", body)
                self.assertIn("analyst", body.lower())


class CommittedHandoffEvidence(unittest.TestCase):
    """Execute the documented gate against a checked PR SHA, not merely local HEAD."""

    def test_review_and_committed_render_must_match_checked_head(self):
        from test_sql_review_scripts import Project, review_doc, run as helper_run
        from test_sql_review_sources import ADAPTER
        handoff = (REPO / "skills/data-request-triage/references/handoff.rst").read_text()
        block = re.search(r"\.\. code-block:: bash\n\n((?:     .*\n|\n)+)", handoff)
        self.assertIsNotNone(block, "hand-off needs an executable committed-evidence gate")
        gate = textwrap.dedent(block.group(1))
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            project = Project(root)
            (root / "sql").mkdir()
            (root / ".gitignore").write_text("sql/request.sql\n")
            (root / "payload").write_text("SELECT 1;\n")
            (root / "render.sh").write_text(ADAPTER)
            config = root / ".sqlreview/config.json"
            doc = json.loads(config.read_text())
            doc["sql_render"] = {"command": ["bash", "render.sh"]}
            config.write_text(json.dumps(doc))
            (root / "sql/provenance.json").write_text(json.dumps({"schema": 1, "requests": {
                "sql/request.sql": {"source": "builder"}}}))
            project.commit()
            fp = json.loads(helper_run(["fingerprint", "sql/request.sql"], root).stdout)
            draft = project.write_json("sql__request", "review.draft.json", review_doc(
                "sql__request", **fp, logic=[], open_questions=[]))
            result = helper_run(["publish", "sql__request", "review", str(draft)], root)
            self.assertEqual(result.returncode, 0, result.stderr)
            draft.unlink()
            checked = project.commit("checked review")
            env = {k: v for k, v in os.environ.items() if not k.startswith("GIT_")}
            env.update(SLUG="sql__request", PR_HEAD=checked, RUN_COMMIT=checked,
                       S=str(REPO / "skills/data-request-setup/scripts"))
            review = draft.with_name("review.json")
            original = review.read_bytes()

            def execute(expected):
                result = subprocess.run(["bash", "-c", gate], cwd=root, env=env,
                                        capture_output=True, text=True)
                self.assertEqual(result.returncode, expected, result.stdout + result.stderr)

            execute(0)  # SQL never existed in a Git tree or review store.
            review.write_text(review.read_text().replace('"revision": 1', '"revision": 2', 1))
            execute(4)  # Uncommitted review differs from checked PR head.
            project.commit("local unpublished review")
            execute(4)  # A clean local HEAD is not the checked PR head.
            review.write_bytes(original)
            (root / "payload").write_text("SELECT 2;\n")
            execute(2)  # Uncommitted maintained sources cannot supply fresh evidence.
            (root / "payload").write_text("SELECT 1;\n")
            execute(0)
            env["SLUG"] = "untracked"
            other = project.review_dir("untracked") / "review.json"
            other.write_bytes(original)
            execute(4)  # The checked commit must contain the actual reviewed record.
            other.unlink()
            env["SLUG"] = "sql__request"
            corrupt = json.loads(original)
            corrupt["sql_sha256"] = "0" * 64
            review.write_text(json.dumps(corrupt))
            env["PR_HEAD"] = project.commit("corrupt reviewed hash")
            env["RUN_COMMIT"] = env["PR_HEAD"]
            execute(10)  # Checked identity alone cannot authenticate SQL provenance.
            self.assertEqual(list((root / ".sqlreview").rglob("*.sql")), [])


class HandoffEvalFixtures(unittest.TestCase):
    """Grade synthetic replies in both engines; no model calls or live mutations."""

    def test_every_handoff_case_has_discriminating_graders_and_fixtures(self):
        self.assertEqual({p.parent.name for p in SUITE.glob("handoff-*/prompt.md")}, set(CASES))
        for case, names in CASES.items():
            with self.subTest(case=case):
                root = SUITE / case
                front = yaml.safe_load((root / "prompt.md").read_text().split("---\n")[1])
                self.assertIn("Skill", front["allowed_tools"])
                self.assertFalse(set(front["allowed_tools"]) & {"Bash", "Write", "Edit"})
                self.assertGreaterEqual(front["runs"], 3)
                metas = {p.stem: yaml.safe_load(p.read_text().split("---\n")[1])
                         for p in (root / "graders").glob("*.md")}
                sources = {k: v["pattern"] for k, v in metas.items() if v["type"] == "regex"}
                self.assertEqual(set(sources), names)
                self.assertEqual(metas["skill-fired"]["tool"], "Skill")
                fixtures = yaml.safe_load((root / "fixtures.yaml").read_text())
                self.assertTrue(fixtures["pass"], case)
                covered = set()
                for fixture in fixtures["pass"] + fixtures["fail"]:
                    reply = fixture["reply"]
                    python = {k: bool(re.search(v, reply)) for k, v in sources.items()}
                    if shutil.which("node"):
                        script = """
const x = JSON.parse(require('fs').readFileSync(0, 'utf8'));
const results = Object.fromEntries(Object.entries(x.patterns)
    .map(([key, pattern]) => [key, new RegExp(pattern).test(x.reply)]));
process.stdout.write(JSON.stringify(results));
"""
                        result = subprocess.run(["node", "-e", script], input=json.dumps({"patterns": sources, "reply": reply}),
                                                text=True, capture_output=True, check=True, timeout=30)
                        self.assertEqual(json.loads(result.stdout), python)
                    failed = {k for k, passed in python.items() if not passed}
                    self.assertEqual(failed, set(fixture.get("fails", [])), fixture["name"])
                    covered |= failed
                self.assertEqual(covered, names)


if __name__ == "__main__":
    unittest.main()
