"""#442: triage branch naming and ownership documentation contracts.

These tests inspect published guidance and parse its ledger example; they do not
execute an agent or rename/create a branch. Both installed targets must retain
the enquiry-versus-ticket distinction and existing-branch protections.
"""

import re
import unittest
from pathlib import Path

import yaml

REPO = Path(__file__).resolve().parent.parent
REFERENCES = {
    "canonical": REPO / "skills/data-request-triage/references",
    "claude": REPO / "plugins/data-request/skills/triage/references",
    "codex": REPO / "dist/codex/plugins/data-request/skills/triage/references",
}


def branches(root):
    text = (root / "repositories.rst").read_text()
    section = text.split("Branches, owners and pins\n", 1)[1]
    return re.sub(r"\s+", " ", section)


class EnquiryBranchNaming(unittest.TestCase):
    def test_new_branch_uses_enquiry_not_service_desk_issue(self):
        for target, root in REFERENCES.items():
            with self.subTest(target=target):
                text = branches(root)
                self.assertIn("new request branch", text)
                self.assertIn("``enq/<enquiry number>``", text)
                self.assertIn("``ENQ9003``", text)
                self.assertIn("``enq/9003``", text)
                self.assertIn("not the service-desk issue number", text)
                self.assertIn("``#903``", text)

    def test_later_version_keeps_enquiry_number(self):
        for target, root in REFERENCES.items():
            with self.subTest(target=target):
                text = branches(root)
                self.assertIn("later version", text)
                self.assertIn("``enq/9003-v2``", text)

    def test_existing_branches_are_preserved_with_owner_agreement(self):
        for target, root in REFERENCES.items():
            with self.subTest(target=target):
                text = branches(root)
                self.assertIn("Reuse a sound existing branch", text)
                self.assertIn("owner's agreement", text)
                self.assertIn("Keep existing ``triage/<n>`` branch names", text)
                self.assertIn("never rename a branch someone else owns", text)
                self.assertIn("never reuse, rebase or delete it unasked", text)

    def test_naming_rule_does_not_authorise_writes_in_triage_only(self):
        text = (REPO / "skills/data-request-triage/SKILL.md").read_text()
        mode = text.split("**Triage only**", 1)[1].split("**Co-development**", 1)[0]
        self.assertIn("read-only in every repository", mode)
        self.assertIn("no branch,", mode)
        self.assertIn("write only to the branches the human agreed", text)

    def test_ledger_branch_matches_enquiry_digits_not_ticket(self):
        for target, root in REFERENCES.items():
            with self.subTest(target=target):
                text = (root / "ledger.rst").read_text()
                example = text.split(".. code-block:: yaml\n", 1)[1].split("\nRules\n", 1)[0]
                entry = yaml.safe_load(example)
                self.assertEqual(entry["enquiry"], "ENQ9003")
                self.assertEqual(entry["ticket"], "rdl-service-desk/service-desk#903")
                self.assertEqual(entry["branch"], "enq/" + entry["enquiry"].removeprefix("ENQ"))
                self.assertNotEqual(entry["branch"].split("/")[1], entry["ticket"].split("#")[1])


if __name__ == "__main__":
    unittest.main()
