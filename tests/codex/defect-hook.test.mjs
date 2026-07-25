// SPDX-License-Identifier: Apache-2.0

import path from "node:path";
import process from "node:process";
import test from "node:test";
import assert from "node:assert/strict";
import { fileURLToPath } from "node:url";

import { makeTempDir, run } from "./helpers.mjs";
import { recordDefect } from "../../plugins/codex/scripts/lib/defect-log.mjs";
import { saveState } from "../../plugins/codex/scripts/lib/state.mjs";

const ROOT = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..", "..");
const HOOK = path.join(ROOT, "plugins", "codex", "scripts", "defect-report-hook.mjs");

function runHook(payload, cwd) {
  return run(process.execPath, [HOOK], {
    env: process.env,
    input: typeof payload === "string" ? payload : JSON.stringify({ cwd, ...payload })
  });
}

test("stays silent when there is nothing to report", () => {
  const result = runHook({ hook_event_name: "SessionStart" }, makeTempDir());

  assert.equal(result.status, 0);
  assert.equal(result.stdout.trim(), "");
});

test("tolerates empty and malformed stdin", () => {
  for (const input of ["", "not json at all", "{\"unclosed\": "]) {
    const result = runHook(input);
    assert.equal(result.status, 0, `input ${JSON.stringify(input)} must exit 0`);
    assert.equal(result.stdout.trim(), "");
  }
});

test("channel one: an unreported marker points at /codex:report-defect", () => {
  const workspace = makeTempDir();
  recordDefect(workspace, { message: "Stored job task-abc is missing its task request payload." });

  const result = runHook({ hook_event_name: "SubagentStop" }, workspace);
  assert.equal(result.status, 0);

  const payload = JSON.parse(result.stdout);
  assert.equal(payload.hookSpecificOutput.hookEventName, "SubagentStop");
  assert.match(payload.hookSpecificOutput.additionalContext, /\/codex:report-defect/);
});

test("channel two: a failed job is surfaced without offering to file", () => {
  const workspace = makeTempDir();
  saveState(workspace, {
    config: {},
    jobs: [
      {
        id: "task-abc",
        status: "failed",
        updatedAt: new Date().toISOString(),
        summary: "Your access token could not be refreshed because your refresh token was already used."
      }
    ]
  });

  const result = runHook({ hook_event_name: "SubagentStop" }, workspace);
  const context = JSON.parse(result.stdout).hookSpecificOutput.additionalContext;

  assert.match(context, /task-abc/);
  assert.match(context, /refresh token/);
  assert.match(context, /\/codex:result task-abc/);
  assert.equal(/report-defect/.test(context), false, "a Codex-side failure must not offer to file");
});

test("a failed job is surfaced exactly once", () => {
  const workspace = makeTempDir();
  saveState(workspace, {
    config: {},
    jobs: [{ id: "task-abc", status: "failed", updatedAt: new Date().toISOString(), summary: "boom" }]
  });

  const first = runHook({ hook_event_name: "SessionStart" }, workspace);
  assert.match(first.stdout, /task-abc/);

  const second = runHook({ hook_event_name: "SessionStart" }, workspace);
  assert.equal(second.stdout.trim(), "", "the same failed job must not be surfaced twice");
});

test("PostToolUse only fires for a codex-companion command", () => {
  const workspace = makeTempDir();
  recordDefect(workspace, { message: "Unknown subcommand: taks" });

  const unrelated = runHook(
    { hook_event_name: "PostToolUse", tool_name: "Bash", tool_input: { command: "ls -la" } },
    workspace
  );
  assert.equal(unrelated.stdout.trim(), "", "an unrelated Bash call must not trigger the nudge");

  const relevant = runHook(
    {
      hook_event_name: "PostToolUse",
      tool_name: "Bash",
      tool_input: { command: 'node "/x/scripts/codex-companion.mjs" status' }
    },
    workspace
  );
  assert.match(relevant.stdout, /\/codex:report-defect/);
});

test("completed and cancelled jobs are ignored", () => {
  const workspace = makeTempDir();
  saveState(workspace, {
    config: {},
    jobs: [
      { id: "task-ok", status: "completed", updatedAt: new Date().toISOString(), summary: "fine" },
      { id: "task-x", status: "cancelled", updatedAt: new Date().toISOString(), summary: "stopped" }
    ]
  });

  assert.equal(runHook({ hook_event_name: "SessionStart" }, workspace).stdout.trim(), "");
});
