"""Public library text carries no request provenance (issue #527).

A library issue or comment is public. House convention keeps enquiry and approval numbers,
private request-repository links and request-specific file references out of it, apart from
patient data. These tests pin:

* the leak oracle below flags every class of leak in the `*-leaky.md` fixture drafts (issue
  title, prose, URLs, file references) and none in the `*-anonymous.md` drafts;
* the anonymous issue draft follows the evidence block and its reproduction is usable;
* the lift evidence template, the recurring-decision procedure and the lift skill state the
  boundary, keep private traceability and deduplication without a public identifier, and do
  not assume that a library issue is private;
* every published copy carries the same text.

All identifiers in the fixtures are synthetic. No model call is made.
"""

import hashlib
import re
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
FIXTURES = REPO / "tests" / "fixtures" / "public-lift-drafts"
EVIDENCE = ("skills", "data-request-lift", "references", "evidence.rst")
DECISIONS = ("skills", "data-request-setup", "references", "recurring-decisions.rst")
LIFT = ("skills", "data-request-lift", "SKILL.md")
CLAUDE = Path("plugins/data-request/skills")
CODEX = Path("dist/codex/plugins/data-request/skills")
COPIES = {
    EVIDENCE: (CLAUDE / "lift/references/evidence.rst", CODEX / "lift/references/evidence.rst"),
    DECISIONS: (CLAUDE / "setup/references/recurring-decisions.rst",
                CODEX / "setup/references/recurring-decisions.rst"),
    LIFT: (CLAUDE / "lift/SKILL.md", CODEX / "lift/SKILL.md"),
}

ALLOWED_LIBRARY_REPOS = ("query-builder", "agent-extensions", "data-analysis-scaffold")
LEAKS = {
    "enquiry-or-approval-number": re.compile(r"\bTHHS[A-Z]+-\d+\b|\bENQ\d{3,}\b|\b\d{4,}_request\b"),
    "non-library-link": re.compile(
        r"https?://github\.com/(?!nq-rdl/(?:%s)\b)\S+|https?://\S*service-desk\S*" % "|".join(ALLOWED_LIBRARY_REPOS)),
    "request-file-reference": re.compile(
        r"\bsql/v\d+/|_request\.sql\b|\.sqlreview/|\banswers\.yaml\b|\bcohort/request\.json\b"
        r"|\bdata/0\d_|\bconf/base/"),
    "ledger-id": re.compile(r"\bLIFT-\d+\b"),
    "confirmer": re.compile(r"(?i)\bconfirmed by [a-z][\w.-]+"),
}


def leaks(text):
    return {name for name, pattern in LEAKS.items() if pattern.search(text)}


def read(rel):
    return " ".join((REPO / rel).read_text().split())


class Fixtures(unittest.TestCase):
    def test_leaky_issue_draft_is_flagged_in_every_class(self):
        draft = (FIXTURES / "issue-leaky.md").read_text()
        title = draft.splitlines()[0]
        self.assertEqual(leaks(title), {"enquiry-or-approval-number"}, "the title leaks on its own")
        self.assertEqual(leaks(draft), set(LEAKS))

    def test_leaky_comment_draft_is_flagged(self):
        found = leaks((FIXTURES / "comment-leaky.md").read_text())
        self.assertEqual(found, {"enquiry-or-approval-number", "non-library-link",
                                 "request-file-reference", "confirmer"})

    def test_each_leak_class_is_found_in_prose_a_url_and_a_file_reference(self):
        cases = {
            "prose": "Raised for THHSAQUIRE-8675309 last week.",
            "url": "See https://github.com/nq-rdl/request-example/issues/1 for the run.",
            "file": "Hand SQL in sql/v3/example_request.sql line 12.",
            "title": "THHSRDLENQ-90210 needs a unit",
        }
        for name, text in cases.items():
            with self.subTest(name):
                self.assertTrue(leaks(text))

    def test_library_links_are_not_flagged(self):
        for text in ("https://github.com/nq-rdl/query-builder/blob/v0.7.0/resolvers/iemr/resolver.py",
                     "https://github.com/nq-rdl/query-builder/issues/1",
                     "https://github.com/nq-rdl/agent-extensions/issues/527"):
            with self.subTest(text):
                self.assertEqual(leaks(text), set())

    def test_anonymous_drafts_are_clean(self):
        for name in ("issue-anonymous.md", "comment-anonymous.md"):
            with self.subTest(name):
                self.assertEqual(leaks((FIXTURES / name).read_text()), set())

    def test_anonymous_drafts_carry_one_random_token_not_a_derived_one(self):
        for name in ("issue-anonymous.md", "comment-anonymous.md"):
            text = (FIXTURES / name).read_text()
            tokens = re.findall(r"^occurrence ([0-9a-f]{8})$", text, re.M)
            with self.subTest(name):
                self.assertEqual(len(tokens), 1)
                for number in ("90210", "8675309"):  # synthetic request numbers
                    self.assertNotEqual(tokens[0], hashlib.sha256(number.encode()).hexdigest()[:8])
                    self.assertNotEqual(tokens[0], hashlib.md5(number.encode()).hexdigest()[:8])

    def test_same_wording_in_two_enquiries_differs_only_by_token(self):
        text = (FIXTURES / "comment-anonymous.md").read_text()
        second = re.sub(r"occurrence [0-9a-f]{8}", "occurrence 0c5e77b1", text)
        strip = lambda t: re.sub(r"occurrence [0-9a-f]{8}", "", t)
        self.assertNotEqual(text, second)
        self.assertEqual(strip(text), strip(second))  # wording cannot tell them apart; the token can

    def test_anonymous_issue_keeps_the_evidence_block_and_a_reproduction(self):
        draft = (FIXTURES / "issue-anonymous.md").read_text()
        for heading in ("Library baseline", "Need and classification", "Pinned capability inspected",
                        "Shortfall", "Delivered workaround", "Canonical SQL / expected contract",
                        "Proposed fix and tests", "Rollout"):
            with self.subTest(heading):
                self.assertIn(f"## {heading}", draft)
        self.assertIn("Synthetic reproduction", draft)
        self.assertIn("expected:", draft)
        self.assertIn("unconfirmed", draft)  # anonymising does not manufacture a confirmation

    def test_fixtures_use_only_synthetic_identifiers(self):
        for path in FIXTURES.glob("*.md"):
            text = path.read_text()
            for number in re.findall(r"\bTHHS[A-Z]+-(\d+)\b", text):
                with self.subTest(path.name):
                    self.assertIn(number, {"90210", "8675309"})


class Guidance(unittest.TestCase):
    def test_evidence_template_states_the_boundary(self):
        text = read("/".join(EVIDENCE))
        for token in ("Public by default", "Do not assume a destination is private",
                      "enquiry number, an approval number", "a link to a request repository",
                      "request-specific file reference", "a ledger id", "Library baseline",
                      "anonymous reproduction", "Anonymity is not a decision",
                      "Do not state an assumption or limitation as confirmed in public text",
                      "Private traceability", "The private side points to the public work",
                      "by its wording", "proof that this occurrence was already filed",
                      "per-occurrence line", "never derive it from a request number or a hash of one",
                      "search for that exact token only"):
            with self.subTest(token):
                self.assertIn(token, text)
        self.assertNotIn("Enquiry and pin", text)
        self.assertNotIn("enquiry reference, pipeline path/revision", text)

    def test_recurring_decisions_keep_dedup_and_retry_without_public_ids(self):
        text = read("/".join(DECISIONS))
        for token in ("Public evidence", "Tell a retry from a new recurrence",
                      "per-occurrence token, not with wording", "generate a random token",
                      "Never derive it from a request number", "found by trying them all",
                      "for that exact token only", "Matching on wording alone is not a duplicate check",
                      "record the comment URL beside the token",
                      "a library issue is not private merely because it is a library issue",
                      "an anonymous row on the tracking epic",
                      "Anonymous evidence says that the decision recurred",
                      "Count recurrences from private records"):
            with self.subTest(token):
                self.assertIn(token, text)
        self.assertNotIn("the decision ``id``, the enquiry, the ticket, the item ids", text)
        self.assertNotIn("already cite this enquiry", text)
        self.assertNotIn("your own earlier comment on the same decision", text)

    def test_lift_skill_points_at_the_boundary(self):
        text = read("/".join(LIFT))
        self.assertIn("**Public by default**", text)
        self.assertIn("anonymous reproduction", text)
        self.assertIn("private ledger and hand-off", text)
        self.assertIn("a public comment carries no enquiry identifier", text)

    def test_every_published_copy_matches(self):
        for canonical, copies in COPIES.items():
            if canonical == LIFT:  # SKILL.md is rewritten per host; the tests above read the canonical one
                continue
            for copy in copies:
                with self.subTest(str(copy)):
                    self.assertEqual((REPO / copy).read_text().split(), (REPO / Path(*canonical)).read_text().split())


if __name__ == "__main__":
    unittest.main()
