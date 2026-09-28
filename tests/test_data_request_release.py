"""Analyst-approved researcher release summary (issue #407).

`/data-request:release` drafts the researcher-facing Extraction Summary and Extraction
Assumptions / Important limitations from the release tag's own artifacts, checked against
the confirmed scope and the `.sqlreview` reviews. These tests pin:

* packaging: the canonical skill, the bundle registry and the Claude Code and Codex copies
  change together, and the skill is discoverable beside its siblings;
* the skill contract: applicability before use, discrepancies held for resolution, relevance
  selection, per-claim analyst decisions, a record that never touches the technical review,
  and no publishing;
* the worked example evaluates the named review items after an applicability check, with a
  fictional enquiry number;
* the helper `release.sh`: `evidence` (does each review apply to the release tag), `check`
  (the release record's invariants) and `render` (the paste-ready body);
* the guard validates a written release record;
* the `release-*` eval cases, graded in Python always and in Node when it is on PATH.

No model call is made. The subprocess runner strips GIT_* and SQLREVIEW_* variables, so a
test run inside a git hook never touches the enclosing repository.
"""

import hashlib
import json
import os
import re
import shutil
import subprocess
import tempfile
import time
import unittest
from pathlib import Path

import yaml

REPO = Path(__file__).resolve().parent.parent
SETUP = REPO / "skills" / "data-request-setup"
SQLREVIEW = SETUP / "scripts" / "sqlreview.sh"
RELEASE = SETUP / "scripts" / "release.sh"
GUARD = REPO / "hooks" / "data-request-guard.sh"
HOOK = REPO / "skills/cc-setup/assets/forced-eval-hook.sh"
SUITE = REPO / "evals/claude/data-request"
BUNDLE = REPO / "registry/bundles/data-request.yaml"

SKILL = {
    "canonical": REPO / "skills/data-request-release/SKILL.md",
    "claude": REPO / "plugins/data-request/skills/release/SKILL.md",
    "codex": REPO / "dist/codex/plugins/data-request/skills/release/SKILL.md",
}
EXAMPLE = {
    "canonical": REPO / "skills/data-request-release/references/worked-example.rst",
    "claude": REPO / "plugins/data-request/skills/release/references/worked-example.rst",
    "codex": REPO / "dist/codex/plugins/data-request/skills/release/references/worked-example.rst",
}
HELPER_COPIES = {
    "canonical": RELEASE,
    "claude": REPO / "plugins/data-request/skills/setup/scripts/release.sh",
    "codex": REPO / "dist/codex/plugins/data-request/skills/setup/scripts/release.sh",
}


def frontmatter(path: Path) -> tuple[dict, str]:
    # The Codex copy invokes siblings as `$data-request:<leaf>`; compare in Claude's form.
    _, meta, body = path.read_text().replace("$data-request:", "/data-request:").split("---\n", 2)
    return yaml.safe_load(meta), body


def flat(text: str) -> str:
    return " ".join(text.split())


def section(body: str, heading: str) -> str:
    start = body.index(heading)
    end = body.find("\n## ", start + len(heading))
    return body[start:] if end < 0 else body[start:end]


def clean_env(extra=None):
    env = {k: v for k, v in os.environ.items()
           if not k.startswith("GIT_") and not k.startswith("SQLREVIEW_")}
    # The guard resolves its checker via CLAUDE_PLUGIN_ROOT first; test this checkout's copy.
    env.pop("CLAUDE_PLUGIN_ROOT", None)
    env.update(extra or {})
    return env


def run(script, args, cwd, stdin=None, env=None):
    return subprocess.run(["bash", str(script), *args], cwd=cwd, env=clean_env(env), input=stdin,
                          capture_output=True, text=True, timeout=60)


# --- packaging ------------------------------------------------------------------------------

class Packaging(unittest.TestCase):
    def test_registry_exposes_the_release_leaf(self):
        bundle = yaml.safe_load(BUNDLE.read_text())
        self.assertIn({"source": "data-request-release", "leaf": "release"}, bundle["skills"])
        self.assertIn("release", bundle["keywords"])

    def test_skill_and_references_exist_in_every_tree(self):
        for tree in SKILL:
            with self.subTest(tree=tree):
                self.assertTrue(SKILL[tree].is_file(), SKILL[tree])
                self.assertTrue(EXAMPLE[tree].is_file(), EXAMPLE[tree])
                self.assertTrue(HELPER_COPIES[tree].is_file(), HELPER_COPIES[tree])

    def test_packaged_helper_is_the_canonical_bytes(self):
        canonical = RELEASE.read_bytes()
        for tree in ("claude", "codex"):
            with self.subTest(tree=tree):
                self.assertEqual(HELPER_COPIES[tree].read_bytes(), canonical)

    def test_frontmatter(self):
        meta, _ = frontmatter(SKILL["canonical"])
        self.assertEqual(meta["name"], "data-request-release")
        self.assertTrue(meta["user-invocable"])
        self.assertNotIn("Edit", meta["allowed-tools"], "the record is written whole, never patched")
        self.assertIn("AskUserQuestion", meta["allowed-tools"])
        desc = flat(meta["description"])
        for phrase in ("Extraction Summary", "researcher", "analyst", "release tag", "never publishes"):
            self.assertIn(phrase, desc)
        # The Claude copy drops name: so /data-request lists it as data-request:release.
        self.assertNotIn("name", frontmatter(SKILL["claude"])[0])
        self.assertEqual(frontmatter(SKILL["codex"])[0]["name"], "release")

    def test_sibling_skills_point_to_release(self):
        for leaf, source in (("analyse", "data-request-analyse"), ("explain", "data-request-explain")):
            for path in (REPO / f"skills/{source}/SKILL.md",
                         REPO / f"plugins/data-request/skills/{leaf}/SKILL.md",
                         REPO / f"dist/codex/plugins/data-request/skills/{leaf}/SKILL.md"):
                with self.subTest(path=path.relative_to(REPO)):
                    self.assertIn("/data-request:release", frontmatter(path)[1])


@unittest.skipUnless(shutil.which("jq"), "plugin discovery requires jq")
class Discovery(unittest.TestCase):
    def test_release_prompts_surface_the_release_skill(self):
        with tempfile.TemporaryDirectory() as tmp:
            home = Path(tmp)
            manifest = home / ".claude/plugins/installed_plugins.json"
            manifest.parent.mkdir(parents=True)
            manifest.write_text(json.dumps({"plugins": {"data-request@rdl-agent-extensions": [
                {"installPath": str(REPO / "plugins/data-request")}]}}))
            env = {**os.environ, "HOME": str(home), "XDG_CACHE_HOME": str(home / ".cache")}
            for prompt in ("Draft the release summary for the data request extract",
                           "/data-request:release v1.0.0"):
                with self.subTest(prompt=prompt):
                    result = subprocess.run(["bash", str(HOOK)], input=json.dumps({"prompt": prompt}),
                                            text=True, capture_output=True, env=env, check=True)
                    context = json.loads(result.stdout)["hookSpecificOutput"]["additionalContext"]
                    self.assertIn("data-request:release", context)
                    self.assertIn("data-request:analyse", context)


# --- skill contract -------------------------------------------------------------------------

class SkillContract(unittest.TestCase):
    def body(self, tree="canonical"):
        return frontmatter(SKILL[tree])[1]

    def each(self):
        for tree in SKILL:
            with self.subTest(tree=tree):
                yield flat(self.body(tree))

    def test_audience_and_boundaries(self):
        for text in self.each():
            self.assertIn("`/data-request:analyse` stays the engineer's detailed review", text)
            self.assertIn("Analyst → Researcher", text)
            self.assertIn("never changes a scope, review or SQL file", text)
            self.assertIn("never publishes a release, pushes a tag or posts the body", text)

    def test_reads_the_release_tags_own_artifacts(self):
        for tree in SKILL:
            with self.subTest(tree=tree):
                text = flat(section(self.body(tree), "## 1. Gather the release evidence"))
                for thing in ("confirmed scope", "open questions", "`specs/amendments.md`",
                              "pipeline", "output manifest", "schema", "validation", "UAT"):
                    self.assertIn(thing, text)
                self.assertIn("`git show <tag>:<path>`", text)
                self.assertIn("never the working tree or another branch", text)
                self.assertIn('bash "$S/release.sh" evidence', text)

    def test_applicability_before_any_item_is_used(self):
        for tree in SKILL:
            with self.subTest(tree=tree):
                text = flat(section(self.body(tree), "## 2. Check that each review applies"))
                for state in ("`current`", "`header-only`", "`changed`", "`missing-at-ref`",
                              "`unreviewed`"):
                    self.assertIn(state, text)
                self.assertIn("`reviewed_commit_in_ref`", text)
                self.assertIn("A review that does not apply blocks every claim based on it", text)
                self.assertIn("Never infer confirmation from an old review", text)
                self.assertIn("draft SQL", text)

    def test_discrepancies_hold_the_draft(self):
        for tree in SKILL:
            with self.subTest(tree=tree):
                text = flat(section(self.body(tree), "## 3. Compare the release"))
                for check in ("inclusion rule", "unit of observation", "delivered outputs",
                              "requested element", "age basis"):
                    self.assertIn(check, text)
                self.assertIn("Boolean", text)
                self.assertIn("conflicting evidence from each source and a proposed correction", text)
                self.assertIn("Never soften a discrepancy into boilerplate", text)
                self.assertIn("A prose or typo pass comes after", text)

    def test_selection_by_researcher_effect(self):
        for tree in SKILL:
            with self.subTest(tree=tree):
                text = flat(section(self.body(tree), "## 4. Select and translate"))
                for effect in ("cohort membership", "field meaning", "completeness",
                               "comparability", "interpretation"):
                    self.assertIn(effect, text)
                self.assertIn("Merge related items", text)
                self.assertIn("state the consequence, not the mechanism", text)
                self.assertIn("kept internal", text)
                self.assertIn("no omission is silent", text)
                self.assertIn("**Extraction Summary**", text)
                self.assertIn("**Extraction Assumptions / Important limitations**", text)
                for part in ("population", "site", "period", "unit of observation",
                             "delivered files and fields", "major derivations"):
                    self.assertIn(part, text)
                for label in ("confirmed fact", "question", "proposed wording"):
                    self.assertIn(label, text)

    def test_analyst_decides_each_claim(self):
        for tree in SKILL:
            with self.subTest(tree=tree):
                text = flat(section(self.body(tree), "## 5. The analyst decides each claim"))
                for option in ("**Accept (Recommended)**", "**Reword**", "**Reject**"):
                    self.assertIn(option, text)
                self.assertIn("Never fill `decided_by` or `decided_at` from anything but an "
                              "answered question", text)
                self.assertIn("An unresolved question holds the release", text)

    def test_record_and_render(self):
        for tree in SKILL:
            with self.subTest(tree=tree):
                text = flat(section(self.body(tree), "## 6. Record and render"))
                self.assertIn(".sqlreview/releases/<tag>/release.json", text)
                self.assertIn('bash "$S/release.sh" check', text)
                self.assertIn('bash "$S/release.sh" render', text)
                self.assertIn("The confirmed technical review is not changed", text)
                self.assertIn("row-level data", text)
                self.assertIn("paste-ready", text)

    def test_worked_example_is_linked(self):
        for text in self.each():
            self.assertIn("references/worked-example.rst", text)


class WorkedExample(unittest.TestCase):
    def test_every_named_item_gets_a_verdict_after_the_applicability_check(self):
        for tree, path in EXAMPLE.items():
            with self.subTest(tree=tree):
                text = path.read_text()
                applies = text.index("Does the review apply")
                for item in ("A1", "A3", "A4", "L1", "L2", "L5", "L6", "A2", "L3", "L4"):
                    self.assertRegex(text, rf"\*\*{item}\*\*")
                    self.assertGreater(text.index(f"**{item}**"), applies,
                                       f"{item} is evaluated before the applicability check")

    def test_example_holds_the_meaning_changing_differences(self):
        text = flat(EXAMPLE["canonical"].read_text())
        for phrase in ("diagnosis **or** chief complaint **or** visit reason",
                       "`measurement_granularity: Patient`", "encounter-level",
                       "`Encounter_Level`", "`Clinical_events`", "at arrival",
                       "blocking discrepancy"):
            self.assertIn(phrase, text)
        self.assertIn("THHSAQUIRE-99", text, "use the fictional 9xxx range")


# --- helper: evidence -----------------------------------------------------------------------

def git(cwd, *args):
    return subprocess.run(["git", *args], cwd=cwd, capture_output=True, text=True, check=True,
                          env=clean_env()).stdout.strip()


def item(id_, text, revision=1):
    return {"id": id_, "text": text, "rationale": "because", "location": None,
            "status": "confirmed", "confirmed_by": "engineer@example",
            "confirmed_at": "2026-09-28T00:00:00Z", "confirmed_revision": revision}


SQL_V1 = ("/* assumptions:\n  - draft header\n*/\nSELECT e.encounter_id, e.arrival\n"
          "FROM ed.encounter e\nWHERE e.complaint LIKE '%FALL%';\n")
SQL_HEADER = SQL_V1.replace("draft header", "release header")
SQL_V2 = SQL_V1.replace("e.complaint LIKE '%FALL%'", "(e.complaint LIKE '%FALL%' OR e.dx LIKE '%FALL%')")
SLUG = "sql__v1__falls"
SQL_PATH = "sql/v1/falls.sql"


class Project:
    """A temp git repo with an initialised .sqlreview/ and one confirmed review of SQL_V1."""

    def __init__(self, tmp):
        self.root = Path(tmp)
        git(self.root, "init", "-q", "-b", "main")
        git(self.root, "config", "user.email", "t@example")
        git(self.root, "config", "user.name", "t")
        r = run(SQLREVIEW, ["init"], self.root)
        assert r.returncode == 0, r.stderr
        self.write(SQL_PATH, SQL_V1)
        self.commit("draft sql")
        self.review_commit = git(self.root, "rev-parse", "HEAD")
        self.review(SQL_V1)
        self.commit("review")

    def write(self, rel, text):
        p = self.root / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(text)

    def commit(self, msg):
        git(self.root, "add", "-A")
        git(self.root, "commit", "-q", "-m", msg)

    def review(self, sql, slug=SLUG, sql_path=SQL_PATH):
        d = self.root / ".sqlreview/reviews" / slug
        d.mkdir(parents=True, exist_ok=True)
        (d / "source.sql").write_text(sql)
        doc = {"schemaVersion": 2, "kind": "review", "slug": slug, "sql_path": sql_path,
               "title": "Falls", "revision": 2, "recorded_at": "2026-09-28T00:00:00Z",
               "recorded_by": "engineer@example",
               "sql_sha256": hashlib.sha256(sql.encode()).hexdigest(),
               "git_commit": self.review_commit, "git_dirty": False,
               "purpose": "Falls presentations.", "grain": "one row per encounter",
               "inputs": [{"name": "ed.encounter", "description": "one row per encounter"}],
               "outputs": [{"name": "encounter_id", "description": "encounter"}],
               "logic": [{"step": 1, "title": "Filter", "lines": [4, 6], "description": "falls"}],
               "assumptions": [item("A1", "Falls are identified by complaint text.", 2)],
               "limitations": [item("L1", "Text matching includes some non-falls.", 2)],
               "open_questions": ["Is the diagnosis also a source?"],
               "changes": [{"revision": 2, "at": "2026-09-28T00:00:00Z", "by": "engineer@example",
                            "summary": "update"}]}
        (d / "review.json").write_text(json.dumps(doc, indent=2))

    def tag(self, name):
        git(self.root, "tag", name)

    def evidence(self, *args):
        return run(RELEASE, ["evidence", *args], self.root)


@unittest.skipUnless(shutil.which("jq") and shutil.which("git"), "release.sh needs jq and git")
class Evidence(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.p = Project(self.tmp.name)

    def only(self, result):
        doc = json.loads(result.stdout)
        self.assertEqual(len(doc["reviews"]), 1, doc)
        return doc, doc["reviews"][0]

    def test_current_review_applies(self):
        self.p.tag("v1.0.0")
        r = self.p.evidence("v1.0.0")
        self.assertEqual(r.returncode, 0, r.stderr)
        doc, rev = self.only(r)
        self.assertEqual(doc["ref"], "v1.0.0")
        self.assertEqual(doc["commit"], git(self.p.root, "rev-parse", "v1.0.0^{commit}"))
        self.assertEqual(rev["slug"], SLUG)
        self.assertEqual(rev["applies"], "current")
        self.assertEqual(rev["revision"], 2)
        self.assertTrue(rev["reviewed_commit_in_ref"])
        self.assertEqual([i["id"] for i in rev["assumptions"]], ["A1"])
        self.assertEqual([i["id"] for i in rev["limitations"]], ["L1"])
        self.assertEqual(rev["open_questions"], ["Is the diagnosis also a source?"])

    def test_changed_sql_at_the_tag_makes_the_review_stale(self):
        self.p.write(SQL_PATH, SQL_V2)
        self.p.commit("widen criteria")
        self.p.tag("v1.0.0")
        r = self.p.evidence("v1.0.0")
        self.assertEqual(r.returncode, 10, r.stderr)
        _, rev = self.only(r)
        self.assertEqual(rev["applies"], "changed")
        self.assertNotEqual(rev["sql_sha256_at_ref"], rev["sql_sha256_reviewed"])

    def test_working_tree_is_not_the_release(self):
        # The tag holds the reviewed SQL; an uncommitted edit afterwards does not change that.
        self.p.tag("v1.0.0")
        self.p.write(SQL_PATH, SQL_V2)
        _, rev = self.only(self.p.evidence("v1.0.0"))
        self.assertEqual(rev["applies"], "current")

    def test_header_only_change_still_applies(self):
        self.p.write(SQL_PATH, SQL_HEADER)
        self.p.commit("regenerate header")
        self.p.tag("v1.0.0")
        r = self.p.evidence("v1.0.0")
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertEqual(self.only(r)[1]["applies"], "header-only")

    def test_review_of_draft_sql_absent_from_the_release(self):
        # SQL-only review on a branch; the release is cut from a pipeline without that file.
        git(self.p.root, "checkout", "-q", "-b", "release", self.p.review_commit + "~0")
        git(self.p.root, "rm", "-q", SQL_PATH)
        self.p.write("src/pipelines/falls.py", "# builds the extract\n")
        self.p.review(SQL_V1)  # the review directory travels with the branch
        self.p.commit("pipeline release")
        self.p.tag("v1.0.0")
        git(self.p.root, "checkout", "-q", "main")
        r = self.p.evidence("v1.0.0")
        self.assertEqual(r.returncode, 10, r.stderr)
        _, rev = self.only(r)
        self.assertEqual(rev["applies"], "missing-at-ref")
        self.assertIsNone(rev["sql_sha256_at_ref"])

    def test_reviewed_commit_outside_the_release_is_reported(self):
        git(self.p.root, "checkout", "-q", "-b", "enq/draft")
        self.p.write(SQL_PATH, SQL_V2)
        self.p.commit("draft only")
        self.p.review_commit = git(self.p.root, "rev-parse", "HEAD")
        self.p.review(SQL_V2)
        self.p.commit("review of draft")
        git(self.p.root, "checkout", "-q", "main")
        git(self.p.root, "checkout", "-q", "enq/draft", "--", ".sqlreview")
        self.p.commit("bring the review over")
        self.p.tag("v1.0.0")
        r = self.p.evidence("v1.0.0")
        _, rev = self.only(r)
        self.assertEqual(rev["applies"], "changed")
        self.assertFalse(rev["reviewed_commit_in_ref"])

    def test_scope_only_directory_is_unreviewed(self):
        d = self.p.root / ".sqlreview/reviews/sql__v1__later"
        d.mkdir(parents=True)
        (d / "scope.json").write_text(json.dumps({
            "schemaVersion": 2, "kind": "scope", "slug": "sql__v1__later",
            "sql_path": "sql/v1/later.sql", "title": "Later", "revision": 1,
            "recorded_at": "2026-09-28T00:00:00Z", "recorded_by": "engineer@example",
            "git_commit": None, "intent": "Later.", "inputs": [], "outputs": [],
            "assumptions": [], "limitations": [], "open_questions": []}))
        self.p.commit("scope")
        self.p.tag("v1.0.0")
        r = self.p.evidence("v1.0.0")
        self.assertEqual(r.returncode, 10, r.stderr)
        states = {x["slug"]: x["applies"] for x in json.loads(r.stdout)["reviews"]}
        self.assertEqual(states, {SLUG: "current", "sql__v1__later": "unreviewed"})

    def test_slug_filter(self):
        self.p.tag("v1.0.0")
        r = self.p.evidence("v1.0.0", SLUG)
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertEqual(self.only(r)[1]["slug"], SLUG)
        self.assertEqual(self.p.evidence("v1.0.0", "no__such").returncode, 2)
        self.assertEqual(self.p.evidence("v1.0.0", "../x").returncode, 2)

    def test_unknown_ref_and_usage(self):
        self.assertEqual(self.p.evidence("v9.9.9").returncode, 2)
        self.assertEqual(self.p.evidence("--upload-pack=x").returncode, 2)
        self.assertEqual(self.p.evidence().returncode, 1)

    def test_not_initialised(self):
        with tempfile.TemporaryDirectory() as other:
            git(Path(other), "init", "-q")
            self.assertEqual(run(RELEASE, ["evidence", "HEAD"], other).returncode, 3)

    def test_read_only(self):
        self.p.tag("v1.0.0")
        before = git(self.p.root, "status", "--porcelain", "--ignored")
        self.p.evidence("v1.0.0")
        self.assertEqual(git(self.p.root, "status", "--porcelain", "--ignored"), before)

    def test_status_still_works_beside_a_release_record(self):
        rel = self.p.root / ".sqlreview/releases/v1.0.0"
        rel.mkdir(parents=True)
        (rel / "release.json").write_text(json.dumps(record()))
        r = run(SQLREVIEW, ["status", "--json"], self.p.root)
        self.assertEqual(r.returncode, 0, r.stderr)


# --- helper: check and render ---------------------------------------------------------------

def claim(id_, section_, text, decision="accepted", final=None, sources=None):
    d = {"id": id_, "section": section_, "proposed": text, "decision": decision,
         "final": text if decision == "accepted" else final,
         "sources": sources or [{"kind": "file", "path": "src/pipelines/falls.py", "ref": "v1.0.0"}]}
    if decision != "pending":
        d.update(decided_by="analyst@example", decided_at="2026-09-28T01:00:00Z")
    return d


def record(**over):
    d = {"schemaVersion": 1, "kind": "release", "tag": "v1.0.0", "commit": "a" * 40,
         "status": "approved", "recorded_at": "2026-09-28T01:00:00Z",
         "recorded_by": "analyst@example",
         "evidence": [{"slug": SLUG, "revision": 2, "applies": "current"},
                      {"slug": "sql__v0__draft", "revision": 1, "applies": "missing-at-ref"}],
         "claims": [
             claim("C1", "summary", "Adults who presented to the emergency department after a fall.",
                   sources=[{"kind": "review", "slug": SLUG, "item": "A1", "revision": 2},
                            {"kind": "file", "path": "src/pipelines/falls.py", "ref": "v1.0.0"}]),
             claim("C2", "assumptions", "Age is age at arrival.", decision="reworded",
                   final="Age is the patient's age on the day they arrived."),
             claim("C3", "assumptions", "Rows are unordered.", decision="rejected"),
         ],
         "questions": [{"id": "Q1", "text": "Is the diagnosis a fall source?",
                        "sources": [{"kind": "review", "slug": SLUG, "item": "A1", "revision": 2}],
                        "resolution": "Yes: the pipeline also matches the diagnosis.",
                        "resolved_by": "analyst@example", "resolved_at": "2026-09-28T01:00:00Z"}]}
    d.update(over)
    return d


def violations(doc):
    r = run(RELEASE, ["check", "--stdin"], REPO, stdin=json.dumps(doc))
    return r.returncode, r.stdout + r.stderr


@unittest.skipUnless(shutil.which("jq"), "release.sh needs jq")
class Check(unittest.TestCase):
    def assertViolation(self, doc, fragment):
        code, out = violations(doc)
        self.assertEqual(code, 4, out)
        self.assertIn(fragment, out)

    def test_valid_approved_record(self):
        code, out = violations(record())
        self.assertEqual(code, 0, out)
        self.assertIn("ok", out)

    def test_file_argument(self):
        with tempfile.TemporaryDirectory() as tmp:
            f = Path(tmp) / "release.json"
            f.write_text(json.dumps(record()))
            self.assertEqual(run(RELEASE, ["check", str(f)], tmp).returncode, 0)
            f.write_text("{not json")
            self.assertEqual(run(RELEASE, ["check", str(f)], tmp).returncode, 4)

    def test_shape(self):
        self.assertViolation(record(kind="review"), "kind must be release")
        self.assertViolation(record(schemaVersion=2), "schemaVersion must be 1")
        self.assertViolation(record(tag="../v1"), "tag")
        self.assertViolation(record(commit="main"), "commit")
        self.assertViolation(record(status="published"), "status")
        self.assertViolation(record(claims=[]), "claims")

    def test_decided_claims_need_who_and_when(self):
        doc = record()
        del doc["claims"][0]["decided_by"]
        self.assertViolation(doc, "C1: decided_by")

    def test_decisions_and_final_wording_agree(self):
        doc = record()
        doc["claims"][0]["final"] = "Something else."
        self.assertViolation(doc, "C1: an accepted claim keeps the proposed wording")
        doc = record()
        doc["claims"][1]["final"] = doc["claims"][1]["proposed"]
        self.assertViolation(doc, "C2: a reworded claim needs new final wording")
        doc = record()
        doc["claims"][2]["final"] = "Rows are unordered."
        self.assertViolation(doc, "C3: a rejected claim has no final wording")
        doc = record()
        doc["claims"][0]["decision"] = "maybe"
        self.assertViolation(doc, "C1: decision")

    def test_claims_need_sources(self):
        doc = record()
        doc["claims"][0]["sources"] = []
        self.assertViolation(doc, "C1: sources")
        doc = record()
        doc["claims"][0]["sources"] = [{"kind": "review", "slug": SLUG}]
        self.assertViolation(doc, "C1: a review source needs slug, item and revision")

    def test_stale_review_blocks_a_kept_claim(self):
        doc = record()
        doc["claims"][0]["sources"] = [{"kind": "review", "slug": "sql__v0__draft",
                                        "item": "L2", "revision": 1}]
        self.assertViolation(doc, "C1: review sql__v0__draft does not apply to the release "
                                  "(missing-at-ref)")
        # A rejected claim may still record where it came from.
        doc["claims"][0].update(decision="rejected", final=None)
        doc["claims"].append(claim("C4", "summary", "Encounter-level falls extract."))
        self.assertEqual(violations(doc)[0], 0, violations(doc)[1])

    def test_review_source_must_match_the_evidence(self):
        doc = record()
        doc["claims"][0]["sources"][0]["slug"] = "sql__v1__other"
        self.assertViolation(doc, "C1: review sql__v1__other is not in evidence")
        doc = record()
        doc["claims"][0]["sources"][0]["revision"] = 1
        self.assertViolation(doc, "C1: review sql__v1__falls revision 1 is not the revision in evidence (2)")

    def test_approval_needs_every_claim_decided_and_every_question_resolved(self):
        doc = record()
        doc["claims"][1] = claim("C2", "assumptions", "Age is age at arrival.", decision="pending")
        self.assertViolation(doc, "approved: C2 is pending")
        doc = record()
        doc["questions"][0].update(resolution=None, resolved_by=None, resolved_at=None)
        self.assertViolation(doc, "approved: Q1 is unresolved")
        doc = record()
        doc["claims"][1].update(decision="rejected", final=None)
        self.assertViolation(doc, "approved: no kept claim in assumptions")

    def test_draft_may_hold_pending_claims_and_open_questions(self):
        doc = record(status="draft")
        doc["claims"][1] = claim("C2", "assumptions", "Age is age at arrival.", decision="pending")
        doc["questions"][0].update(resolution=None, resolved_by=None, resolved_at=None)
        code, out = violations(doc)
        self.assertEqual(code, 0, out)

    def test_ids_are_unique(self):
        doc = record()
        doc["claims"][1]["id"] = "C1"
        self.assertViolation(doc, "duplicate claim id C1")
        doc = record()
        doc["questions"].append(dict(doc["questions"][0]))
        self.assertViolation(doc, "duplicate question id Q1")


@unittest.skipUnless(shutil.which("jq"), "release.sh needs jq")
class Render(unittest.TestCase):
    def render(self, doc):
        with tempfile.TemporaryDirectory() as tmp:
            f = Path(tmp) / "release.json"
            f.write_text(json.dumps(doc))
            return run(RELEASE, ["render", str(f)], tmp)

    def test_approved_body(self):
        r = self.render(record())
        self.assertEqual(r.returncode, 0, r.stderr)
        out = r.stdout
        self.assertLess(out.index("## Extraction Summary"),
                        out.index("## Extraction Assumptions / Important limitations"))
        summary = section(out, "## Extraction Summary")
        self.assertIn("- Adults who presented to the emergency department after a fall.", summary)
        self.assertIn("- Age is the patient's age on the day they arrived.", out)
        self.assertNotIn("Age is age at arrival.", out, "the reworded text replaces the proposal")
        self.assertNotIn("unordered", out, "a rejected claim is not rendered")
        self.assertNotIn("Draft", out)
        # Provenance stays with each claim but is hidden from the rendered release page.
        self.assertIn("<!-- C1: review sql__v1__falls A1 r2; file src/pipelines/falls.py@v1.0.0 -->", out)

    def test_draft_body_shows_what_is_still_open(self):
        doc = record(status="draft")
        doc["claims"][1] = claim("C2", "assumptions", "Age is age at arrival.", decision="pending")
        doc["questions"][0].update(resolution=None, resolved_by=None, resolved_at=None)
        r = self.render(doc)
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertTrue(r.stdout.startswith("> **Draft, not approved.**"), r.stdout[:80])
        self.assertIn("- [pending] Age is age at arrival.", r.stdout)
        self.assertIn("## Open questions (resolve before release)", r.stdout)
        self.assertIn("- Q1: Is the diagnosis a fall source?", r.stdout)

    def test_invalid_record_is_not_rendered(self):
        r = self.render(record(kind="review"))
        self.assertEqual(r.returncode, 4)
        self.assertEqual(r.stdout, "")


# --- guard ----------------------------------------------------------------------------------

@unittest.skipUnless(shutil.which("jq"), "the guard needs jq")
class Guard(unittest.TestCase):
    def decide(self, tool, rel, content=None):
        with tempfile.TemporaryDirectory() as tmp:
            (Path(tmp) / ".sqlreview").mkdir()
            event = {"tool_name": tool, "cwd": tmp,
                     "tool_input": {"file_path": f"{tmp}/.sqlreview/{rel}"}}
            if content is not None:
                event["tool_input"]["content"] = content
            r = subprocess.run(["bash", str(GUARD)], input=json.dumps(event), text=True,
                               capture_output=True, env=clean_env(), timeout=60)
            if not r.stdout.strip():
                return "allow", ""
            out = json.loads(r.stdout)["hookSpecificOutput"]
            return out["permissionDecision"], out["permissionDecisionReason"]

    def test_valid_record_passes(self):
        decision, reason = self.decide("Write", "releases/v1.0.0/release.json", json.dumps(record()))
        self.assertEqual(decision, "allow", reason)

    def test_invalid_record_is_denied_with_its_violations(self):
        doc = record()
        del doc["claims"][0]["decided_by"]
        decision, reason = self.decide("Write", "releases/v1.0.0/release.json", json.dumps(doc))
        self.assertEqual(decision, "deny")
        self.assertIn("C1: decided_by", reason)
        self.assertIn("AskUserQuestion", reason)

    def test_tag_must_match_the_directory(self):
        decision, reason = self.decide("Write", "releases/v2.0.0/release.json", json.dumps(record()))
        self.assertEqual(decision, "deny")
        self.assertIn("v2.0.0", reason)

    def test_edit_is_denied(self):
        decision, _ = self.decide("Edit", "releases/v1.0.0/release.json")
        self.assertEqual(decision, "deny")

    def test_rendered_body_is_not_hand_written(self):
        decision, reason = self.decide("Write", "releases/v1.0.0/release.md", "# body")
        self.assertEqual(decision, "deny")
        self.assertIn("release.sh render", reason)


# --- eval cases -----------------------------------------------------------------------------

# Eval case -> the regex graders its answer is decided by.
CASES = {
    "release-current-review": {"review-current", "hold-no", "include-a1-l1", "internal-l2-l3"},
    "release-stale-review": {"review-stale", "hold-yes", "no-review-items"},
    "release-output-differs": {"hold-yes", "blocker-inclusion-rule", "blocker-grain",
                               "blocker-missing-element"},
    "release-technical-limitation": {"include-l4", "internal-l3", "claims-no-sql-jargon",
                                     "claims-current-record"},
}
NODE = shutil.which("node")
NODE_SCRIPT = """
const {patterns, reply} = JSON.parse(require('fs').readFileSync(0, 'utf8'));
const out = {};
for (const [name, source] of Object.entries(patterns)) out[name] = new RegExp(source).test(reply);
process.stdout.write(JSON.stringify(out));
"""
MUTATING_TOOLS = {"Bash", "Write", "Edit", "NotebookEdit"}


def grader_meta(path: Path) -> dict:
    return yaml.safe_load(path.read_text().split("\n---\n")[0].removeprefix("---\n"))


def graders(case: str) -> dict:
    return {p.stem: grader_meta(p) for p in sorted((SUITE / case / "graders").glob("*.md"))}


def regex_sources(case: str) -> dict:
    return {name: g["pattern"] for name, g in graders(case).items() if g["type"] == "regex"}


class EvalCases(unittest.TestCase):
    def test_this_module_owns_every_release_case(self):
        found = {p.name for p in SUITE.glob("release-*") if p.is_dir()}
        self.assertEqual(found, set(CASES))
        source = (REPO / "tests/test_eval_data_request_graders.py").read_text()
        self.assertIn('"release-"', source)

    def test_case_shape(self):
        for case, expected in CASES.items():
            with self.subTest(case=case):
                meta = grader_meta(SUITE / case / "prompt.md")
                prompt = (SUITE / case / "prompt.md").read_text()
                self.assertTrue(meta["description"])
                self.assertIn("release", meta["tags"])
                self.assertGreaterEqual(meta["runs"], 3)
                self.assertIn("Skill", meta["allowed_tools"])
                self.assertFalse(MUTATING_TOOLS & set(meta["allowed_tools"]))
                self.assertIn("End your reply with one fenced `yaml` block", prompt)
                self.assertEqual(set(regex_sources(case)), expected)
                for name, source in regex_sources(case).items():
                    re.compile(source)
                    self.assertEqual(graders(case)[name]["target"], "last_message")
                    self.assertIn("`{3,}ya?ml", source, f"{name} must read the yaml block")
                matcher = re.compile(graders(case)["skill-fired"]["input_match"])
                self.assertTrue(matcher.search('{"skill": "data-request:release"}'))
                self.assertTrue(matcher.search('{"skill":"release"}'))
                self.assertFalse(matcher.search('{"skill": "data-request:analyse"}'))
                self.assertFalse(matcher.search('{"skill": "data-request:prerelease"}'))


class EvalFixtures(unittest.TestCase):
    def grade(self, sources: dict, reply: str) -> set:
        """Names of the regex graders that FAIL the reply (both engines when node exists)."""
        python = {name: bool(re.search(src, reply)) for name, src in sources.items()}
        if NODE:
            result = subprocess.run(
                [NODE, "-e", NODE_SCRIPT], input=json.dumps({"patterns": sources, "reply": reply}),
                capture_output=True, text=True, check=True, timeout=30)
            self.assertEqual(json.loads(result.stdout), python, "JavaScript and Python disagree")
        return {name for name, ok in python.items() if not ok}

    def test_empty_reply_fails_every_regex_grader(self):
        for case in CASES:
            with self.subTest(case=case):
                sources = regex_sources(case)
                self.assertEqual(self.grade(sources, ""), set(sources))

    def test_fixtures(self):
        for case in CASES:
            sources = regex_sources(case)
            fixtures = yaml.safe_load((SUITE / case / "fixtures.yaml").read_text())
            self.assertTrue(fixtures["pass"], case)
            for fixture in fixtures["pass"]:
                with self.subTest(case=case, fixture=fixture["name"]):
                    self.assertEqual(self.grade(sources, fixture["reply"]), set())
            covered = set()
            for fixture in fixtures["fail"]:
                with self.subTest(case=case, fixture=fixture["name"]):
                    self.assertTrue(fixture["fails"])
                    self.assertEqual(self.grade(sources, fixture["reply"]), set(fixture["fails"]))
                    covered |= set(fixture["fails"])
            self.assertEqual(covered, set(sources), f"{case}: every grader needs a failing fixture")

    def test_large_replies_grade_quickly(self):
        reply = ("```yaml\n" + "include: [A1]\n" * 2000 + "```\n" + "hold: no\n" * 2000) * 3
        for case in CASES:
            with self.subTest(case=case):
                start = time.monotonic()
                self.grade(regex_sources(case), reply)
                self.assertLess(time.monotonic() - start, 5)


if __name__ == "__main__":
    unittest.main()
