// SPDX-License-Identifier: Apache-2.0
// SPDX-FileCopyrightText: 2026 nq-rdl

import fs from "node:fs";
import path from "node:path";
import process from "node:process";
import test from "node:test";
import assert from "node:assert/strict";
import { fileURLToPath } from "node:url";

import { makeTempDir, run } from "./helpers.mjs";
import { listSurfacedJobs, listUnreportedDefects, recordDefect } from "../../plugins/codex/scripts/lib/defect-log.mjs";
import { saveState } from "../../plugins/codex/scripts/lib/state.mjs";

const ROOT = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..", "..");
const HOOK = path.join(ROOT, "plugins", "codex", "scripts", "defect-report-hook.mjs");

// The child's own cwd matters: malformed stdin parses to {}, so the hook falls
// back to process.cwd(). Spawning inside the temp workspace keeps those cases
// off the developer's real state directory -- which the hook would otherwise
// both read and write.
function runHook(payload, cwd) {
  return run(process.execPath, [HOOK], {
    cwd,
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
  const workspace = makeTempDir();
  for (const input of ["", "not json at all", "{\"unclosed\": "]) {
    const result = runHook(input, workspace);
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

// Both tool outcomes, not just the success one. A Bash call that exits non-zero
// raises PostToolUseFailure and *not* PostToolUse -- and recordDefect always
// precedes a non-zero exit, so the failure event is the one carrying the turn a
// marker is actually written on.
for (const event of ["PostToolUse", "PostToolUseFailure"]) {
  test(`${event} only fires for a codex-companion command`, () => {
    const workspace = makeTempDir();
    recordDefect(workspace, { message: "Unknown subcommand: taks" });

    const unrelated = runHook(
      { hook_event_name: event, tool_name: "Bash", tool_input: { command: "ls -la" } },
      workspace
    );
    assert.equal(unrelated.stdout.trim(), "", "an unrelated Bash call must not trigger the nudge");

    const relevant = runHook(
      {
        hook_event_name: event,
        tool_name: "Bash",
        tool_input: { command: 'node "/x/scripts/codex-companion.mjs" status' }
      },
      workspace
    );
    assert.match(relevant.stdout, /\/codex:report-defect/);
    assert.equal(
      JSON.parse(relevant.stdout).hookSpecificOutput.hookEventName,
      event,
      "the advisory must be labelled with the event Claude Code sent"
    );
  });
}

// The gap this closes was a wiring omission, not a logic bug: the hook handled
// the events correctly and hooks.json simply never sent it the ones that matter.
// Nothing else in the suite reads hooks.json, so nothing else can catch that.
test("hooks.json wires the defect hook for every event it handles", () => {
  const hooks = JSON.parse(
    fs.readFileSync(path.join(ROOT, "plugins", "codex", "hooks", "hooks.json"), "utf8")
  ).hooks;

  const wiredFor = (event) =>
    (hooks[event] ?? []).some((entry) =>
      (entry.hooks ?? []).some((hook) => String(hook.command).includes("codex-defect-report.sh"))
    );

  // PostToolUseFailure is the load-bearing one: a recorded defect exits non-zero,
  // so without it the nudge waits for an unrelated later event.
  for (const event of ["SessionStart", "SubagentStop", "PostToolUse", "PostToolUseFailure"]) {
    assert.equal(wiredFor(event), true, `${event} must invoke codex-defect-report.sh`);
  }

  // Both tool events must stay narrowed to Bash; the hook's own command filter
  // assumes tool_input.command exists.
  for (const event of ["PostToolUse", "PostToolUseFailure"]) {
    const entry = hooks[event].find((candidate) =>
      (candidate.hooks ?? []).some((hook) => String(hook.command).includes("codex-defect-report.sh"))
    );
    assert.equal(entry.matcher, "Bash", `${event} must match only Bash`);
  }
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

test("a payload with no hook_event_name is ignored and consumes nothing", () => {
  const workspace = makeTempDir();
  recordDefect(workspace, { message: "Unknown subcommand: taks" });

  const result = runHook({}, workspace); // valid JSON, no hook_event_name
  assert.equal(result.status, 0);
  assert.equal(result.stdout.trim(), "", "an unnamed event must not emit a nudge");
  assert.equal(listUnreportedDefects(workspace).length, 1, "the marker must stay unreported");
});

test("a marker the classifier explains away does not trigger the nudge", () => {
  const workspace = makeTempDir();
  recordDefect(workspace, { message: "git is not installed. Install Git and retry." });

  const result = runHook({ hook_event_name: "SessionStart" }, workspace);
  assert.equal(result.status, 0);
  assert.equal(result.stdout.trim(), "", "a not-a-defect marker must not offer to file");
});

test("the nudge names the newest reportable marker, not the newest marker", () => {
  const workspace = makeTempDir();
  recordDefect(workspace, { message: "Stored job task-abc is missing its task request payload." });
  recordDefect(workspace, { message: "Choose either --enable-review-gate or --disable-review-gate." });

  const context = JSON.parse(runHook({ hook_event_name: "SessionStart" }, workspace).stdout)
    .hookSpecificOutput.additionalContext;

  assert.match(context, /task request payload/);
  assert.equal(/review-gate/.test(context), false, "the flag typo must not be quoted back");
  assert.equal(
    /older also unreported/.test(context),
    false,
    "a filtered-out marker must not be counted in the tally"
  );
});

test("a long job summary is capped", () => {
  const workspace = makeTempDir();
  saveState(workspace, {
    config: {},
    jobs: [
      {
        id: "task-long",
        status: "failed",
        updatedAt: new Date().toISOString(),
        summary: "z".repeat(5000)
      }
    ]
  });

  const context = JSON.parse(runHook({ hook_event_name: "SessionStart" }, workspace).stdout)
    .hookSpecificOutput.additionalContext;
  const detail = context.slice(context.indexOf('surfaced: "') + 11, context.indexOf('". See'));

  assert.ok(detail.length <= 200, `detail is ${detail.length} chars, over the 200-char cap`);
  assert.equal(detail.endsWith("..."), true, "a truncated detail must be elided");
});

test("a cold start bounds the payload and drains the backlog over turns", () => {
  const workspace = makeTempDir();
  saveState(workspace, {
    config: {},
    jobs: Array.from({ length: 50 }, (_unused, i) => ({
      id: `task-${i}`,
      status: "failed",
      updatedAt: new Date().toISOString(),
      summary: `failure ${i} `.padEnd(261, "detail ")
    }))
  });

  const first = JSON.parse(runHook({ hook_event_name: "SessionStart" }, workspace).stdout)
    .hookSpecificOutput.additionalContext;

  // additionalContext over ~10k chars is spilled to a file and replaced by a
  // preview -- and all 50 ids would already have been marked. Pre-fix this
  // payload measured 23,698 chars.
  assert.ok(first.length < 10000, `additionalContext is ${first.length} chars`);
  assert.equal(listSurfacedJobs(workspace).length, 5, "only the emitted jobs may be marked");
  assert.match(first, /45 older failed Codex job\(s\) are also unsurfaced/);

  const second = JSON.parse(runHook({ hook_event_name: "SessionStart" }, workspace).stdout)
    .hookSpecificOutput.additionalContext;
  assert.equal(listSurfacedJobs(workspace).length, 10, "the backlog must drain, not be lost");
  assert.notEqual(second, first);
});
