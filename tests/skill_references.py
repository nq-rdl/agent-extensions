"""Reference files a skill ships, discovered from its references/ directory.

A skill's tests used to list its reference files by hand, so every new reference edited the same
tuple. These helpers read the directory instead: each file must be reStructuredText and linked from
SKILL.md as ``](references/<name>)``, and each such link must name a file that exists.
"""

import re
from pathlib import Path

LINK = re.compile(r"\]\(references/([^)#\s]+)(?:#[^)\s]*)?\)")


def body(skill_md: Path) -> str:
    """SKILL.md without its YAML front matter."""
    return skill_md.read_text().split("---\n", 2)[2]


def references(skill_dir: Path) -> tuple:
    """The file names in <skill>/references/, sorted."""
    return tuple(sorted(p.name for p in (Path(skill_dir) / "references").iterdir()))


def linked(skill_dir: Path) -> set:
    """Reference names that SKILL.md links as ](references/<name>)."""
    return set(LINK.findall(body(Path(skill_dir) / "SKILL.md")))


def problems(skill_dir: Path) -> list:
    """One message per reference that is not .rst, not linked, or linked but missing."""
    names, links = set(references(skill_dir)), linked(skill_dir)
    out = [f"references/{n} is not .rst" for n in sorted(names) if not n.endswith(".rst")]
    out += [f"SKILL.md does not link references/{n}" for n in sorted(names - links)]
    out += [f"SKILL.md links missing references/{n}" for n in sorted(links - names)]
    return out
