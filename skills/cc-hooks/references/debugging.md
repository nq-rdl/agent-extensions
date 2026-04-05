# Debugging Hooks

## Universal Debugging Checklist

Work through these steps in order when a hook isn't working:

1. **Valid JSON?** — Run `jq . <settings-file>` to check for syntax errors in the config
2. **Correct event name?** — Event names are case-sensitive (`PreToolUse`, not `pretooluse`)
3. **Matcher correct?** — Tool name must match exactly (`Bash`, not `bash` or `shell`)
4. **Script runs standalone?** — Execute the script directly: `echo '{}' | bash hook.sh`
5. **Script parses stdin?** — Pipe realistic JSON and verify it reads it: `echo '{"tool_name":"Bash","tool_input":{"command":"ls"}}' | bash hook.sh`
6. **Valid output JSON?** — Script stdout must be valid JSON (or empty). Mixed text + JSON breaks parsing
7. **Sufficient timeout?** — If the script is slow, increase timeout. Hooks killed by timeout allow the action silently

---

## Testing a Hook Manually

Pipe sample event JSON and check the output:

```bash
# Test a Bash-blocking hook
echo '{"tool_name":"Bash","tool_input":{"command":"rm -rf /"}}' | bash hook.sh

# Expected output for a blocking hook:
# {"decision":"block","reason":"Destructive command blocked"}

# Test with a safe command (should produce no output or allow)
echo '{"tool_name":"Bash","tool_input":{"command":"ls -la"}}' | bash hook.sh

# Expected: no output (implicit allow)
```

---

## Claude Code Gotchas

| Issue | Cause | Fix |
|-------|-------|-----|
| Hook never fires | Wrong settings file level | Check global vs project vs local precedence |
| Hook fires for wrong tool | Missing or wrong `matcher` | Add `"matcher": "Bash"` (exact tool name) |
| Hook blocks but no reason shown | Missing `reason` field | Add `"reason"` to decision JSON |
| Hook killed silently | Timeout too short | Increase `"timeout"` (default: 60s, max: 600s) |
| Multiple hooks conflict | Settings merge order | Local > project shared > global; last hook in array wins |
| Exit code 2 vs other | Misunderstanding exit codes | 2 = intentional block; other non-zero = warning only |
| `"approve"` not working | Only valid for `PreToolUse` | `"approve"` auto-accepts tool calls; doesn't apply to other events |

---

## Gemini CLI Gotchas

| Issue | Cause | Fix |
|-------|-------|-----|
| Project hook rejected | Checksum changed | Edit triggers re-acceptance; user must approve in terminal |
| Hook doesn't block | Wrong decision keyword | Use `"deny"` (canonical) or `"block"` (accepted alias) |
| Hook killed too fast | Timeout in wrong units | Gemini uses **milliseconds**, not seconds (`10000` = 10s) |
| Hook fires but ignored | Wrong event name | Gemini events differ from Claude: `BeforeTool` not `PreToolUse` |
| Can't intercept model calls | Not using correct event | Use `BeforeModel`/`AfterModel` (unique to Gemini) |

---

## Common Mistakes

| Mistake | Symptom | Fix |
|---------|---------|-----|
| Mixed stdout (text + JSON) | Hook output ignored or garbled | Only write JSON to stdout; use stderr for debug logs |
| Wrong decision keyword | Action not blocked | Claude Code: `"block"`, Gemini CLI: `"deny"` |
| Timeout too short | Hook killed, action proceeds | Increase timeout; keep scripts fast |
| Missing `jq` | Script fails silently | Install jq or use Python for JSON parsing |
| Script not executable | Permission denied | `chmod +x hook.sh` |
| Regex escaping in JSON | Invalid JSON config | Double-escape backslashes in JSON strings (`\\s` not `\s`) |
| Forgetting `cat` for stdin | Script doesn't read input | Start bash scripts with `input=$(cat)` |
| Printing debug info to stdout | Corrupts JSON output | Use `echo "debug" >&2` for stderr |
