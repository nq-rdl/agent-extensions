"""Recurring scope decisions as upstream (lift) candidates (issue #362).

The list of recurring decisions has one maintained home, the data-request-setup asset
`recurring-decisions.json`, read through `recurring-decisions.sh`. These tests pin:

* the list parses and every entry carries the fields the skills and the helper rely on;
* there is exactly one home: no skill restates an entry, and the packaged copies are the
  canonical bytes;
* bootstrap, analyse and lift carry a short pointer to the helper and the reference, in the
  canonical and the packaged trees;
* the helper's behaviour (`list`, `match`, `marked`), including the optional `upstream`
  marker, which the existing record machinery must keep accepting and carrying forward.

The subprocess runner strips GIT_* variables, so a test run inside a git hook never touches
the enclosing repository.
"""

import json
import os
import re
import subprocess
import tempfile
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
SETUP = REPO / "skills" / "data-request-setup"
LIST = SETUP / "assets" / "recurring-decisions.json"
HELPER = SETUP / "scripts" / "recurring-decisions.sh"
SQLREVIEW = SETUP / "scripts" / "sqlreview.sh"
REFERENCE = SETUP / "references" / "recurring-decisions.rst"

CLAUDE = REPO / "plugins" / "data-request" / "skills"
CODEX = REPO / "dist" / "codex" / "plugins" / "data-request" / "skills"
TREES = {"canonical": None, "claude": CLAUDE, "codex": CODEX}
LEAVES = {"bootstrap": "data-request-bootstrap", "analyse": "data-request-analyse",
          "lift": "data-request-lift", "guardrails": "data-request-guardrails",
          "setup": "data-request-setup"}

REQUIRED = {"id", "title", "kind", "status", "proposal", "match", "evidence",
            "library_issue", "related_issues", "retired_by"}
ISSUE_URL = re.compile(r"^https://github\.com/nq-rdl/query-builder(-plugins)?/(issues|pull)/[1-9][0-9]*$")
# The seed: the eight rows of nq-rdl/query-builder#172 plus the MRN row from its comment.
SEED = {"death-date-raw", "mortality-undercount", "iemr-event-dates", "output-aest",
        "iemr-result-validity", "half-open-date-window", "raw-dated-events",
        "current-demographics", "raw-episode-mrn"}


def skill_path(tree: str, leaf: str, rel: str) -> Path:
    if tree == "canonical":
        return REPO / "skills" / LEAVES[leaf] / rel
    return TREES[tree] / leaf / rel


def clean_env(extra=None):
    env = {k: v for k, v in os.environ.items()
           if not k.startswith("GIT_") and not k.startswith("SQLREVIEW_")}
    env.update(extra or {})
    return env


def run(script, args, cwd, env=None):
    return subprocess.run(["bash", str(script), *args], cwd=cwd, env=clean_env(env),
                          capture_output=True, text=True, timeout=60)


def load_list():
    return json.loads(LIST.read_text())


def item(id_, text, rationale="because", revision=1, **over):
    d = {"id": id_, "text": text, "rationale": rationale, "location": None,
         "status": "confirmed", "confirmed_by": "engineer@example",
         "confirmed_at": "2026-09-28T00:00:00Z", "confirmed_revision": revision}
    d.update(over)
    return d


class ListShape(unittest.TestCase):
    def setUp(self):
        self.doc = load_list()
        self.decisions = self.doc["decisions"]

    def test_parses_with_tracking_epic(self):
        self.assertEqual(self.doc["schemaVersion"], 1)
        self.assertEqual(self.doc["tracking_issue"], "https://github.com/nq-rdl/query-builder/issues/172")
        self.assertRegex(self.doc["updated"], r"^\d{4}-\d{2}-\d{2}$")

    def test_seeded_from_query_builder_172(self):
        self.assertTrue(SEED <= {d["id"] for d in self.decisions})

    def test_every_entry_has_the_required_fields(self):
        ids = [d["id"] for d in self.decisions]
        self.assertEqual(len(ids), len(set(ids)), "duplicate decision id")
        for d in self.decisions:
            with self.subTest(decision=d.get("id")):
                self.assertTrue(REQUIRED <= set(d), REQUIRED - set(d))
                self.assertRegex(d["id"], r"^[a-z][a-z0-9-]*$")
                self.assertTrue(d["title"].strip())
                self.assertIn(d["kind"], {"assumption", "limitation"})
                self.assertIn(d["status"], {"open", "retired"})
                self.assertTrue(d["proposal"]["text"].strip())
                self.assertTrue(d["proposal"]["rationale"].strip())
                self.assertTrue(d["match"] and all(g and all(isinstance(t, str) and t for t in g)
                                                   for g in d["match"]))
                self.assertTrue(d["evidence"])
                for url in d["evidence"]:
                    # The per-enquiry rows live in the private library issue, not here.
                    self.assertRegex(url, r"^https://github\.com/nq-rdl/query-builder(-plugins)?/issues/\d+(#issuecomment-\d+)?$")
                if d["library_issue"] is not None:
                    self.assertRegex(d["library_issue"], ISSUE_URL)
                for url in d["related_issues"]:
                    self.assertRegex(url, ISSUE_URL)
                if d["status"] == "retired":
                    self.assertTrue(d["retired_by"]["unit"] and d["retired_by"]["version"])

    def test_proposals_avoid_semicolons_and_contractions(self):
        # Bootstrap and analyse offer the proposal verbatim; keep it in the skills' plain style.
        for d in self.decisions:
            for field in ("text", "rationale"):
                with self.subTest(decision=d["id"], field=field):
                    value = d["proposal"][field]
                    self.assertNotIn(";", value)
                    self.assertNotRegex(value, r"\b\w+n't\b|\b\w+'(s|re|ll|ve|d)\b")
                    for sentence in re.split(r"(?<=\.)\s+", value):
                        self.assertLessEqual(len(sentence.split()), 25, sentence)

    def test_mrn_entry_names_the_library_default_and_opt_in(self):
        mrn = next(d for d in self.decisions if d["id"] == "raw-episode-mrn")
        self.assertEqual(mrn["library_issue"], "https://github.com/nq-rdl/query-builder/issues/150")
        self.assertIn("ADR 0003", mrn["proposal"]["rationale"])
        self.assertIn("canonicalize_mrn=True", mrn["proposal"]["rationale"])
        self.assertEqual(mrn["evidence"], ["https://github.com/nq-rdl/query-builder/issues/172#issuecomment-5806010117"])

    def test_every_proposal_matches_its_own_decision(self):
        draft = {"kind": "scope", "assumptions": [], "limitations": []}
        for d in self.decisions:
            key = "assumptions" if d["kind"] == "assumption" else "limitations"
            draft[key].append({"id": d["id"], **d["proposal"]})
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "draft.json"
            path.write_text(json.dumps(draft))
            r = run(HELPER, ["match", str(path)], tmp)
            self.assertEqual(r.returncode, 0, r.stderr)
            hits = {(m["id"], m["decision"]) for m in json.loads(r.stdout)["matches"]}
        for d in self.decisions:
            self.assertIn((d["id"], d["id"]), hits)


class OneHome(unittest.TestCase):
    def test_no_skill_restates_an_entry(self):
        decisions = load_list()["decisions"]
        texts = [d["proposal"]["text"] for d in decisions]
        ids = [d["id"] for d in decisions]
        for root in (REPO / "skills", CLAUDE, CODEX):
            for path in sorted(p for p in root.rglob("*") if p.is_file()):
                if path.name == LIST.name:
                    continue
                content = path.read_text(errors="ignore")
                with self.subTest(path=str(path.relative_to(REPO))):
                    for text in texts:
                        self.assertNotIn(text, content, "a proposal is copied outside the list")
                    self.assertLess(sum(i in content for i in ids), 3,
                                    "several decision ids: the list is restated here")

    def test_public_files_name_no_enquiry(self):
        # This repository is public: ticket-style ids (a capitalised prefix, a hyphen and
        # digits) and ENQ numbers stay in the private library issue that `evidence` links.
        ticket = re.compile(r"\b(?:ENQ\d{3,}|[A-Z]{4,}-\d{3,})\b")
        for path in (LIST, REFERENCE, HELPER):
            with self.subTest(path=path.name):
                self.assertIsNone(ticket.search(path.read_text()))

    def test_packaged_copies_are_the_canonical_bytes(self):
        for tree in ("claude", "codex"):
            with self.subTest(tree=tree):
                self.assertEqual(skill_path(tree, "setup", "assets/recurring-decisions.json").read_bytes(),
                                 LIST.read_bytes())

    def test_init_does_not_copy_the_list_into_projects(self):
        self.assertNotEqual(LIST.parent.name, "sqlreview")
        self.assertFalse((SETUP / "assets" / "sqlreview" / LIST.name).exists())


class Pointers(unittest.TestCase):
    def read(self, tree, leaf, rel="SKILL.md"):
        return skill_path(tree, leaf, rel).read_text()

    def assertIn(self, member, container, msg=None):  # keep failure output short
        if member not in container:
            self.fail(msg or f"{member!r} not found")

    def test_helper_and_reference_packaged(self):
        for tree in TREES:
            with self.subTest(tree=tree):
                self.assertTrue(skill_path(tree, "setup", "scripts/recurring-decisions.sh").is_file())
                ref = skill_path(tree, "setup", "references/recurring-decisions.rst")
                # Codex rewrites host variables in SKILL.md only; references stay host-neutral.
                self.assertNotIn("CLAUDE_PLUGIN_ROOT", ref.read_text())

    def test_bootstrap_and_analyse_run_match_before_asking(self):
        for tree in TREES:
            for leaf, draft in (("bootstrap", "scope.draft.json"), ("analyse", "review.draft.json")):
                with self.subTest(tree=tree, leaf=leaf):
                    text = self.read(tree, leaf)
                    self.assertIn('recurring-decisions.sh" match', text)
                    self.assertIn(draft, text)
                    self.assertIn("skills/setup/references/recurring-decisions.rst", text)
                    self.assertIn("upstream", text)
                    self.assertIn("prior enquiries", text)

    def test_bootstrap_pointer_covers_fresh_and_update_paths(self):
        text = self.read("canonical", "bootstrap")
        self.assertLess(text.index("recurring-decisions.sh"), text.index("## Existing scope"))

    def test_lift_reports_marked_items_beside_hand_sql(self):
        for tree in TREES:
            with self.subTest(tree=tree):
                text = self.read(tree, "lift")
                self.assertIn("recurring-decisions.sh", text)
                self.assertIn("marked", text)
                self.assertIn("skills/setup/references/recurring-decisions.rst", text)
                self.assertIn("without duplicates", text)

    def test_reference_keeps_confirmation_and_deduplication(self):
        text = REFERENCE.read_text()
        for token in ("Human confirmation is still", "open and closed issues",
                      "already cite this", "Never edit the installed plugin copy",
                      "do not authorise hand SQL", "retired_by"):
            self.assertIn(token, text)

    def test_guardrails_mrn_line(self):
        for tree in TREES:
            with self.subTest(tree=tree):
                text = self.read(tree, "guardrails")
                sect = text.split("## Leave modelling choices to the researcher", 1)[1].split("\n## ", 1)[0]
                line = next(l for l in sect.splitlines() if "canonicalize_mrn=True" in l)
                self.assertIn("raw", line)
                self.assertIn("MRN", line)
                self.assertIn("merged identities", line)
                self.assertIn("#150", line)


class Helper(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)

    def write(self, name, doc):
        path = self.root / name
        path.write_text(json.dumps(doc))
        return path

    def helper(self, *args, expected=0, env=None):
        r = run(HELPER, [str(a) for a in args], self.root, env)
        self.assertEqual(r.returncode, expected, r.stdout + r.stderr)
        return json.loads(r.stdout) if expected == 0 else r

    def custom_list(self, mutate):
        doc = load_list()
        mutate(doc)
        return {"SQLREVIEW_RECURRING_DECISIONS": str(self.write("list.json", doc))}

    def test_list(self):
        out = self.helper("list")
        self.assertEqual({d["id"] for d in out["decisions"]}, {d["id"] for d in load_list()["decisions"]})
        self.assertEqual(out["tracking_issue"], load_list()["tracking_issue"])

    def test_match_shows_prior_enquiries_and_library_issue(self):
        draft = self.write("scope.draft.json", {"kind": "scope", "assumptions": [
            item("A1", "The URN is the RAW EPISODE mrn.", "No Merge-chain walk."),
            item("A2", "Adults only.", "The request says so."),
            item("A3", "The MRN is the patient key.", "It is unique per site."),
        ], "limitations": [
            item("L1", "Deaths outside hospital undercount.", "No death-registry linkage."),
        ]})
        out = self.helper("match", draft)
        by_id = {(m["kind"], m["id"]): m for m in out["matches"]}
        mrn = by_id[("assumptions", "A1")]
        self.assertEqual(mrn["decision"], "raw-episode-mrn")
        self.assertEqual(mrn["evidence"], ["https://github.com/nq-rdl/query-builder/issues/172#issuecomment-5806010117"])
        self.assertEqual(mrn["library_issue"], "https://github.com/nq-rdl/query-builder/issues/150")
        self.assertEqual(mrn["tracking_issue"], "https://github.com/nq-rdl/query-builder/issues/172")
        self.assertFalse(mrn["marked"])
        self.assertTrue(mrn["proposal"]["text"])
        self.assertEqual(by_id[("limitations", "L1")]["decision"], "mortality-undercount")
        # Every term group must hit: "MRN" alone is not the merge decision.
        self.assertNotIn(("assumptions", "A2"), by_id)
        self.assertNotIn(("assumptions", "A3"), by_id)

    def test_match_reports_an_existing_marker(self):
        draft = self.write("review.draft.json", {"kind": "review", "assumptions": [
            item("A1", "The URN is the raw episode MRN.", "No merge chain.",
                 upstream={"decision": "raw-episode-mrn"})], "limitations": []})
        self.assertTrue(self.helper("match", draft)["matches"][0]["marked"])

    def test_match_carries_retirement(self):
        def retire(doc):
            d = next(d for d in doc["decisions"] if d["id"] == "raw-episode-mrn")
            d.update(status="retired", retired_by={"unit": "HBCISResolver", "version": "v0.6.0"})
        env = self.custom_list(retire)
        draft = self.write("d.json", {"assumptions": [item("A1", "URN is the raw episode MRN.")]})
        m = self.helper("match", draft, env=env)["matches"][0]
        self.assertEqual(m["status"], "retired")
        self.assertEqual(m["retired_by"], {"unit": "HBCISResolver", "version": "v0.6.0"})

    def test_invalid_list_is_refused(self):
        draft = self.write("d.json", {"assumptions": []})
        mutations = {
            "duplicate id": lambda doc: doc["decisions"].append(dict(doc["decisions"][0])),
            "no proposal": lambda doc: doc["decisions"][0].pop("proposal"),
            "empty group": lambda doc: doc["decisions"][0].update(match=[[]]),
            "retired without unit": lambda doc: doc["decisions"][0].update(status="retired"),
            "no evidence": lambda doc: doc["decisions"][0].update(evidence=[]),
            "evidence not a link": lambda doc: doc["decisions"][0].update(evidence=["ENQ9001 A1"]),
        }
        for name, mutate in mutations.items():
            with self.subTest(name):
                r = self.helper("match", draft, expected=4, env=self.custom_list(mutate))
                self.assertIn("list:", r.stderr)

    def test_marked_lists_items_across_records(self):
        scope = self.write("scope.json", {"kind": "scope", "assumptions": [
            item("A1", "URN is the raw episode MRN.", upstream={"decision": "raw-episode-mrn"}),
            item("A2", "Adults only."),
        ], "limitations": []})
        review = self.write("review.json", {"kind": "review", "assumptions": [], "limitations": [
            item("L4", "Something new recurs.", upstream={"decision": "not-listed-yet"}),
        ]})
        items = self.helper("marked", scope, review)["items"]
        self.assertEqual([(i["file"], i["id"], i["known"]) for i in items],
                         [(str(scope), "A1", True), (str(review), "L4", False)])
        self.assertEqual(items[0]["library_issue"], "https://github.com/nq-rdl/query-builder/issues/150")
        self.assertEqual(items[0]["evidence"], ["https://github.com/nq-rdl/query-builder/issues/172#issuecomment-5806010117"])

    def test_marked_without_markers_is_empty(self):
        scope = self.write("scope.json", {"schemaVersion": 1, "kind": "scope",
                                          "assumptions": [item("A1", "Adults only.")]})
        self.assertEqual(self.helper("marked", scope), {"items": []})

    def test_malformed_marker_is_refused(self):
        for bad in ("raw-episode-mrn", {"decision": ""}, {"issue": "x"}):
            with self.subTest(marker=bad):
                scope = self.write("scope.json", {"assumptions": [item("A1", "x", upstream=bad)]})
                r = self.helper("marked", scope, expected=4)
                self.assertIn("A1: upstream", r.stderr)

    def test_usage_and_missing_file(self):
        self.helper(expected=1)
        self.helper("bogus", expected=1)
        self.helper("match", expected=1)
        self.helper("match", self.root / "absent.json", expected=2)
        self.helper("list", env={"SQLREVIEW_RECURRING_DECISIONS": str(self.root / "absent.json")}, expected=2)


class MarkerCompatibility(unittest.TestCase):
    """The optional marker must not change what publish and carryforward accept."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.sqlreview("init")

    def sqlreview(self, *args, expected=0):
        r = run(SQLREVIEW, list(args), self.root)
        self.assertEqual(r.returncode, expected, r.stdout + r.stderr)
        return r

    def scope(self, revision, marker):
        a1 = item("A1", "The URN is the raw episode MRN.", "No merge chain.", revision=1)
        if marker:
            a1["upstream"] = {"decision": "raw-episode-mrn"}
        if revision > 1:
            a1["carried_from_revision"] = revision - 1
        return {"schemaVersion": 2, "kind": "scope", "slug": "cohort.sql", "sql_path": "cohort.sql",
                "title": "Cohort", "revision": revision, "recorded_at": "2026-09-28T00:00:00Z",
                "recorded_by": "engineer@example", "git_commit": None, "sql_sha256": None,
                "intent": "A cohort.", "inputs": [], "outputs": [],
                "assumptions": [a1], "limitations": [], "open_questions": []}

    def draft(self, doc):
        slug = self.sqlreview("slug", "cohort.sql").stdout.strip()
        d = self.root / ".sqlreview" / "reviews" / slug
        d.mkdir(parents=True, exist_ok=True)
        path = d / "scope.draft.json"
        doc["slug"] = slug
        path.write_text(json.dumps(doc))
        return slug, path

    def test_publish_accepts_the_marker_and_carryforward_ignores_it(self):
        slug, path = self.draft(self.scope(1, marker=False))
        self.sqlreview("publish", slug, "scope", str(path))
        # Revision 2 adds only the marker: the confirmation still carries forward.
        doc = self.scope(2, marker=True)
        del doc["assumptions"][0]["carried_from_revision"]
        slug, path = self.draft(doc)
        out = json.loads(self.sqlreview("carryforward", slug, "scope", str(path)).stdout)
        self.assertEqual([c["id"] for c in out["carry"]], ["A1"])
        self.assertEqual(out["walk"], [])
        doc["assumptions"][0].update(out["carry"][0]["set"])
        slug, path = self.draft(doc)
        self.sqlreview("publish", slug, "scope", str(path))
        published = json.loads((path.parent / "scope.json").read_text())
        self.assertEqual(published["revision"], 2)
        self.assertEqual(published["assumptions"][0]["upstream"], {"decision": "raw-episode-mrn"})

if __name__ == "__main__":
    unittest.main()
