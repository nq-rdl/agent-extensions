"""asctl's local-reference check must know every Codex entrypoint override.

The Codex packager installs a `targets.codex.skillOverrides` file as the skill's
SKILL.md, so links in it resolve from the skill root. `asctl repo-check`
(tools/asctl/internal/localrefs) hard-codes those paths; this keeps the two in
step without making the Go checker read the registry.
"""

from pathlib import Path
import re
import unittest

import yaml

REPO = Path(__file__).resolve().parents[1]
LOCALREFS = REPO / "tools/asctl/internal/localrefs/localrefs.go"


class EntrypointOverrideContract(unittest.TestCase):
    def test_registry_overrides_are_known_to_asctl(self):
        match = re.search(r"EntrypointOverrides = \[\]string\{([^}]*)\}", LOCALREFS.read_text())
        self.assertIsNotNone(match, "EntrypointOverrides not found in localrefs.go")
        known = set(re.findall(r'"([^"]+)"', match[1]))
        used = set()
        for path in sorted((REPO / "registry/bundles").glob("*.yaml")):
            bundle = yaml.safe_load(path.read_text())
            codex = (bundle.get("targets") or {}).get("codex") or {}
            used.update((codex.get("skillOverrides") or {}).values())
        self.assertTrue(used, "expected at least one registry skillOverrides entry")
        self.assertLessEqual(used, known, "add new override paths to localrefs.EntrypointOverrides")


if __name__ == "__main__":
    unittest.main()
