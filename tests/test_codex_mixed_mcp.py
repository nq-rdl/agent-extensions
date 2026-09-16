"""Mixed MCP packages must satisfy both independent submission gates."""

import json
from pathlib import Path
import tempfile
import unittest

import yaml

from scripts import codex_directory as directory
from scripts import codex_package as package
from tests.test_codex_package import fixture


class MixedMcpReadiness(unittest.TestCase):
    def test_local_approval_cannot_authorize_remote_servers_or_the_reverse(self):
        for hooks in (False, True):
            with self.subTest(hooks=hooks), tempfile.TemporaryDirectory() as temp:
                repo = Path(temp)
                data = fixture(repo, mcp=True, hooks=hooks)
                data["mcp"].append("local")
                config = data["targets"]["codex"]
                config["interface"] = {
                    "logo": "./assets/logo.svg",
                    "privacyPolicyURL": "https://example.com/privacy",
                    "termsOfServiceURL": "https://example.com/terms",
                }
                config["resources"] = [{
                    "source": "logo.svg", "destination": "assets/logo.svg",
                }]
                (repo / "logo.svg").write_text('<svg xmlns="http://www.w3.org/2000/svg"/>')
                (repo / "registry/bundles/sample.yaml").write_text(yaml.safe_dump(data))
                source = repo / "mcp/source.json"
                servers = json.loads(source.read_text())
                servers["mcpServers"]["local"] = {"command": "example-server"}
                source.write_text(json.dumps(servers))
                package.sync(repo)
                self.assertEqual(package.validate(repo), [])
                for local, remote in ((False, False), (True, False), (False, True), (True, True)):
                    with self.subTest(local=local, remote=remote):
                        publisher = {
                            "supportURL": "https://example.com/support",
                            "identityVerified": True,
                            "behavioralEvidence": {"sample": True},
                            "availabilityRegions": ["US"],
                            "localMcpApproved": {"sample": local},
                            "remoteMcpAuthorized": {"sample": remote},
                        }
                        (repo / "registry/codex-directory.yaml").write_text(yaml.safe_dump(publisher))
                        result = directory.report(repo)
                        entry = result["plugins"][0]
                        expected_route = "mixed-mcp+hooks" if hooks else "mixed-mcp"
                        self.assertEqual(entry["route"], expected_route)
                        self.assertIn(f"| {expected_route} |", directory.markdown(result))
                        self.assertEqual(entry["submissionReady"], local and remote)
                        self.assertEqual(len(entry["blockers"]), int(not local) + int(not remote))
                        self.assertEqual(any("Local MCP" in b for b in entry["blockers"]), not local)
                        self.assertEqual(any("Remote MCP" in b for b in entry["blockers"]), not remote)
