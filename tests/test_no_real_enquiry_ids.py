"""Shipped content must not carry real-looking service-desk or approval IDs.

The repository is public. Commit 6090979 (#338) replaced real enquiry and approval
numbers with fictional ones of the same shape, but nothing stopped new ones from
coming back (PR #398 briefly cited two). Skills, packaged copies, evals and docs
may cite only the fictional range: numbers that start with 9, for example
ENQ9001-9004, THHSAQUIRE-9901-9903, THHSRDLENQ-9003 and SSAQHTS-99001. Describe a
real incident generically, and keep its real ID in the GitHub issue.
"""

import re
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
ROOTS = ("skills", "plugins", "dist/codex", "evals", "docs")

# Enquiry and approval ID prefixes. SSAQTHS is a variant spelling used in some text.
PREFIXES = ("ENQ", "THHSAQUIRE", "THHSRDLENQ", "SSAQHTS", "SSAQTHS")
ID = re.compile(
    r"(?<![A-Za-z0-9])(" + "|".join(PREFIXES) + r")[-_ ]?(\d+)(?!\d)",
    re.IGNORECASE,
)
BINARY_SUFFIXES = {".png", ".jpg", ".jpeg", ".gif", ".ico", ".pdf", ".woff", ".woff2",
                   ".ttf", ".zip", ".gz", ".xlsx", ".docx", ".pptx", ".exe"}


def real_ids(text: str):
    """IDs outside the fictional range (numbers starting with 9)."""
    return [m.group(0) for m in ID.finditer(text) if not m.group(2).startswith("9")]


def shipped_files():
    for root in ROOTS:
        base = REPO / root
        if not base.is_dir():
            continue
        for path in base.rglob("*"):
            if path.is_file() and path.suffix.lower() not in BINARY_SUFFIXES \
                    and "bin" not in path.relative_to(REPO).parts:
                yield path


class Matcher(unittest.TestCase):
    """Pin the matcher itself, so a regex change cannot make the scan vacuous."""

    def test_flags_real_looking_ids(self):
        # Built by concatenation so this file never contains a literal real ID.
        for sample in ("ENQ" + "1177", "enq" + "1219", "THHSAQUIRE-" + "2125",
                       "THHSRDLENQ-" + "1181", "SSAQHTS-" + "43408", "SSAQTHS-" + "123456"):
            with self.subTest(sample=sample):
                self.assertEqual(real_ids(f"see {sample}."), [sample])

    def test_allows_the_fictional_range_and_unrelated_words(self):
        for sample in ("ENQ9003", "THHSAQUIRE-9903", "THHSRDLENQ-9003", "SSAQHTS-99001",
                       "enq9003-cohort", "FREQ1177", "ENQUIRY 12"):
            with self.subTest(sample=sample):
                self.assertEqual(real_ids(sample), [])


class ShippedContent(unittest.TestCase):
    def test_no_real_looking_enquiry_or_approval_ids(self):
        found = []
        for path in shipped_files():
            try:
                text = path.read_text(encoding="utf-8")
            except UnicodeDecodeError:
                continue
            for lineno, line in enumerate(text.splitlines(), 1):
                for hit in real_ids(line):
                    found.append(f"{path.relative_to(REPO)}:{lineno}: {hit}")
        self.assertEqual(found, [], "real-looking IDs in public content; use the "
                         "fictional 9xxx range or describe the incident generically:\n"
                         + "\n".join(found))


if __name__ == "__main__":
    unittest.main()
