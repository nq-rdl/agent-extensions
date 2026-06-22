"""Tests that every skill's ``metadata.repo`` points at this repository.

Skills were merged here from the now-archived ``nq-rdl/agent-skills`` repo (see
``docs/ARCHITECTURE.md``). The ``report-skill-issue`` skill files bug reports to
the *target* skill's ``metadata.repo`` field, so a stale pointer routes reports
to the dead upstream instead of here. This is the regression guard for #133:
every ``metadata.repo`` — in the canonical ``skills/`` tree and in the shipped
``plugins/<bundle>/skills/`` copies — must reference ``nq-rdl/agent-extensions``,
never ``nq-rdl/agent-skills``.

Frontmatter is parsed as YAML (not grepped) so documentation bodies that mention
``repo:`` in example configs are not mistaken for the real metadata field.
"""

import unittest
from pathlib import Path

import yaml

REPO_ROOT = Path(__file__).resolve().parent.parent
ARCHIVED_REPO = "nq-rdl/agent-skills"
CANONICAL_REPO = "https://github.com/nq-rdl/agent-extensions"


def _iter_skill_md_files():
    """Yield every shipped/authored SKILL.md: canonical + plugin copies."""
    yield from sorted((REPO_ROOT / "skills").glob("*/SKILL.md"))
    yield from sorted((REPO_ROOT / "plugins").glob("*/skills/*/SKILL.md"))


def _frontmatter_repo(skill_md: Path):
    """Return ``metadata.repo`` from a SKILL.md's YAML frontmatter, or None."""
    text = skill_md.read_text(encoding="utf-8")
    parts = text.split("---", 2)
    # A valid frontmatter block is: "", <yaml>, <body> -> at least 3 parts with
    # an empty leading segment.
    if len(parts) < 3 or parts[0].strip():
        return None
    front = yaml.safe_load(parts[1]) or {}
    metadata = front.get("metadata") or {}
    return metadata.get("repo")


class TestSkillRepoMetadata(unittest.TestCase):
    def test_no_skill_points_to_archived_agent_skills_repo(self):
        offenders = [
            str(p.relative_to(REPO_ROOT))
            for p in _iter_skill_md_files()
            if ARCHIVED_REPO in (_frontmatter_repo(p) or "")
        ]
        self.assertEqual(
            offenders,
            [],
            f"{len(offenders)} SKILL.md still point metadata.repo at the archived "
            f"{ARCHIVED_REPO} repo; reports would route to the dead upstream:\n"
            + "\n".join(offenders),
        )

    def test_every_skill_repo_is_agent_extensions(self):
        wrong = [
            f"{p.relative_to(REPO_ROOT)}: {_frontmatter_repo(p)!r}"
            for p in _iter_skill_md_files()
            if (_frontmatter_repo(p) or "") != CANONICAL_REPO
        ]
        self.assertEqual(
            wrong,
            [],
            f"{len(wrong)} SKILL.md have metadata.repo != {CANONICAL_REPO}:\n"
            + "\n".join(wrong),
        )


if __name__ == "__main__":
    unittest.main()
