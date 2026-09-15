"""Exercise the advisory hook through the packaged Claude command."""
import json
import os
from pathlib import Path
import subprocess
import unittest

ROOT = Path(__file__).resolve().parent.parent
PLUGIN = ROOT / "plugins/tech-writing"


class StylepediaHookTests(unittest.TestCase):
    def run_hook(self, event, payload):
        config = json.loads((PLUGIN / "hooks/hooks.json").read_text())
        command = config["hooks"][event][0]["hooks"][0]["command"]
        result = subprocess.run(command, shell=True, input=payload, text=True,
                                capture_output=True,
                                env={**os.environ, "CLAUDE_PLUGIN_ROOT": str(PLUGIN)})
        self.assertEqual(result.returncode, 0, result.stderr)
        return result.stdout

    def test_agent_and_direct_invocations_receive_advisory_context(self):
        for name in ("tech-writing:copyedit", "tech-writing-copyedit"):
            for event, fields in (
                ("PreToolUse", {"tool_name": "Skill", "tool_input": {"skill": name}}),
                ("UserPromptExpansion", {"expansion_type": "slash_command", "command_name": name}),
            ):
                with self.subTest(event=event, name=name):
                    output = json.loads(self.run_hook(event, json.dumps({"hook_event_name": event, **fields})))
                    self.assertEqual(set(output), {"hookSpecificOutput"})
                    context = output["hookSpecificOutput"]
                    self.assertEqual(set(context), {"hookEventName", "additionalContext"})
                    self.assertEqual(context["hookEventName"], event)
                    self.assertIn("https://stylepedia.net/style/#part-Writing_Style_Guide", context["additionalContext"])

    def test_unrelated_or_malformed_input_is_silent(self):
        cases = ["", "not json", "null", "[]", "{}"]
        cases += [json.dumps(x) for x in (
            {"hook_event_name": "PreToolUse", "tool_name": "Skill", "tool_input": {"skill": "go:naming"}},
            {"hook_event_name": "PreToolUse", "tool_name": "Bash", "tool_input": {"skill": "tech-writing:copyedit"}},
            {"hook_event_name": "PreToolUse", "tool_name": "Skill", "tool_input": {"skill": {}}},
            {"hook_event_name": "UserPromptExpansion", "expansion_type": "mcp_prompt", "command_name": "tech-writing:copyedit"},
            {"hook_event_name": "Stop"},
        )]
        for payload in cases:
            with self.subTest(payload=payload):
                self.assertEqual(self.run_hook("PreToolUse", payload), "")
