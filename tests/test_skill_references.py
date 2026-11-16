"""The reference discovery in skill_references catches each omission a hand list used to catch."""

import tempfile
import unittest
from pathlib import Path

try:  # `unittest discover -s tests` puts tests/ on sys.path; `-m unittest tests.x` does not
    import skill_references
except ModuleNotFoundError:
    from tests import skill_references

SKILL = "---\nname: fixture\n---\n\n# Fixture\n\nRead [the first reference](references/first.rst) first.\n"


class Discovery(unittest.TestCase):
    def skill(self, text=SKILL, files=("first.rst",)):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        root = Path(tmp.name)
        (root / "references").mkdir()
        (root / "SKILL.md").write_text(text)
        for name in files:
            (root / "references" / name).write_text("Fixture\n=======\n")
        return root

    def test_a_linked_reference_passes(self):
        root = self.skill()
        self.assertEqual(skill_references.references(root), ("first.rst",))
        self.assertEqual(skill_references.problems(root), [])

    def test_an_unlinked_reference_fails(self):
        root = self.skill(files=("first.rst", "second.rst"))
        self.assertEqual(skill_references.problems(root), ["SKILL.md does not link references/second.rst"])

    def test_a_reference_that_is_not_rst_fails(self):
        root = self.skill(SKILL + "See [notes](references/notes.md).\n", files=("first.rst", "notes.md"))
        self.assertEqual(skill_references.problems(root), ["references/notes.md is not .rst"])

    def test_a_link_to_a_missing_reference_fails(self):
        root = self.skill(SKILL + "See [gone](references/gone.rst#part).\n")
        self.assertEqual(skill_references.problems(root), ["SKILL.md links missing references/gone.rst"])

    def test_a_link_in_front_matter_does_not_count(self):
        text = "---\nname: fixture\ndescription: '[x](references/second.rst)'\n---\n\n# Fixture\n" \
               "Read [the first reference](references/first.rst).\n"
        root = self.skill(text, files=("first.rst", "second.rst"))
        self.assertEqual(skill_references.problems(root), ["SKILL.md does not link references/second.rst"])


if __name__ == "__main__":
    unittest.main()
