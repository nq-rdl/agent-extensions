import fs from "node:fs";
import path from "node:path";
import test from "node:test";
import assert from "node:assert/strict";
import { fileURLToPath } from "node:url";

import { makeTempDir, run } from "./helpers.mjs";

const ROOT = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..", "..");
const PLUGIN_ROOT = path.join(ROOT, "plugins", "codex");
const SESSION_HOOK = path.join(PLUGIN_ROOT, "scripts", "session-lifecycle-hook.mjs");
const STOP_HOOK = path.join(PLUGIN_ROOT, "scripts", "stop-review-gate-hook.mjs");

test("session-lifecycle hook prefers the stdin event over argv", () => {
  // stdin says SessionStart; argv says SessionEnd. If the stdin payload wins, the
  // SessionStart branch runs and exports the session id into CLAUDE_ENV_FILE.
  const dir = makeTempDir();
  const envFile = path.join(dir, "claude-env");
  fs.writeFileSync(envFile, "", "utf8");

  const result = run("node", [SESSION_HOOK, "SessionEnd"], {
    cwd: dir,
    env: { ...process.env, CLAUDE_ENV_FILE: envFile },
    input: JSON.stringify({ hook_event_name: "SessionStart", session_id: "abc123" })
  });

  assert.equal(result.status, 0, result.stderr);
  const written = fs.readFileSync(envFile, "utf8");
  assert.match(written, /export CODEX_COMPANION_SESSION_ID='abc123'/);
});

test("session-lifecycle hook tolerates empty stdin", () => {
  const dir = makeTempDir();
  const result = run("node", [SESSION_HOOK, "SessionStart"], {
    cwd: dir,
    env: { ...process.env },
    input: ""
  });
  assert.equal(result.status, 0, result.stderr);
});

test("stop-review-gate short-circuits when stop_hook_active is set", () => {
  // The loop guard must return before touching the workspace, so an empty temp
  // cwd with no git/state is fine and no block decision is emitted.
  const dir = makeTempDir();
  const result = run("node", [STOP_HOOK], {
    cwd: dir,
    env: { ...process.env },
    input: JSON.stringify({ stop_hook_active: true, cwd: dir })
  });

  assert.equal(result.status, 0, result.stderr);
  assert.equal(result.stdout.trim(), "", "short-circuit must not emit a decision");
});

test("stop-review-gate stays silent when the gate is disabled by default", () => {
  const dir = makeTempDir();
  const result = run("node", [STOP_HOOK], {
    cwd: dir,
    env: { ...process.env },
    input: JSON.stringify({ cwd: dir })
  });

  assert.equal(result.status, 0, result.stderr);
  assert.doesNotMatch(result.stdout, /"decision"\s*:\s*"block"/);
});
