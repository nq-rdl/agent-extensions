"""Contract tests for the claude-code / rdl-team skill review (#307, #310).

* #310 - the delegation contract lives in ``cc-agent-create``'s normalization
  reference, in the canonical skill and in every packaged copy.
* #310 - the team marketplace list has one owner, ``cc-setup/assets/
  marketplaces.json``. The discovery skill reads it and must not carry a second,
  hand-maintained copy of its marketplace repositories.
* #307 - cc-setup's settings example is valid JSON and its hook command keeps
  the path variable double-quoted inside the JSON string.
"""

import json
import re
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent

CONTRACT = (
    "Complete the delegated scope using available tools. If blocked by missing "
    "information or authorization, return the blocker and questions to the "
    "caller. Do not perform unauthorized actions. The caller may provide "
    "answers and resume the work."
)

NORMALIZATION = "references/normalization.rst"
ASSET = REPO / "skills" / "cc-setup" / "assets" / "marketplaces.json"


def flat(text: str) -> str:
    return " ".join(text.split())


def copies(source: str, leaf: str, bundle: str):
    """Canonical skill dir plus its Claude and Codex packaged copies that exist."""
    dirs = [REPO / "skills" / source,
            REPO / "plugins" / bundle / "skills" / leaf,
            REPO / "dist" / "codex" / "plugins" / bundle / "skills" / leaf]
    return [d for d in dirs if d.is_dir()]


class DelegationContractTest(unittest.TestCase):
    def test_normalization_states_contract_in_every_copy(self):
        dirs = copies("cc-agent-create", "agent-create", "claude-code")
        self.assertGreaterEqual(len(dirs), 2, "canonical and packaged copies expected")
        for d in dirs:
            with self.subTest(copy=str(d.relative_to(REPO))):
                text = flat((d / NORMALIZATION).read_text(encoding="utf-8"))
                self.assertIn(CONTRACT, text)


class MarketplaceAssetOwnerTest(unittest.TestCase):
    def test_single_canonical_marketplace_list(self):
        found = sorted(p.relative_to(REPO).as_posix()
                       for p in (REPO / "skills").glob("*/assets/marketplaces.json"))
        self.assertEqual(found, ["skills/cc-setup/assets/marketplaces.json"])

    def test_discovery_skill_has_no_second_copy_of_the_list(self):
        repos = [m["source"]["repo"] for m in json.loads(ASSET.read_text())["marketplaces"].values()]
        self.assertTrue(repos)
        for d in copies("marketplace-scout", "discover-plugins", "claude-code") + \
                copies("marketplace-scout", "discover-plugins", "rdl-team")[1:]:
            for f in sorted(d.rglob("*")):
                if not f.is_file():
                    continue
                text = f.read_text(encoding="utf-8")
                if f.name == "SKILL.md":  # metadata.repo names this catalog; not a list copy
                    text = re.sub(r"\A---\n.*?\n---\n", "", text, flags=re.S)
                for repo in repos:
                    with self.subTest(file=str(f.relative_to(REPO)), repo=repo):
                        self.assertNotIn(repo, text,
                                         "marketplace repositories belong in cc-setup's marketplaces.json only")


class CcSetupExampleTest(unittest.TestCase):
    def test_settings_example_is_json_with_quoted_command(self):
        text = (REPO / "skills" / "cc-setup" / "SKILL.md").read_text(encoding="utf-8")
        blocks = re.findall(r"```json\n(.*?)```", text, re.S)
        commands = []
        for block in blocks:
            data = json.loads(block)
            for group in data["hooks"]["UserPromptSubmit"]:
                commands += [h["command"] for h in group["hooks"]]
        self.assertTrue(commands, "no UserPromptSubmit example found")
        for cmd in commands:
            with self.subTest(command=cmd):
                self.assertRegex(cmd, r'^"\$\{?[A-Z_]+\}?"/\.claude/hooks/forced-eval-hook\.sh$')


if __name__ == "__main__":
    unittest.main()
