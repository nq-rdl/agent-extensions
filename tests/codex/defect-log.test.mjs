// SPDX-License-Identifier: Apache-2.0

import fs from "node:fs";
import os from "node:os";
import path from "node:path";
import test from "node:test";
import assert from "node:assert/strict";

import { makeTempDir } from "./helpers.mjs";
import { resolveJobsDir, saveState } from "../../plugins/codex/scripts/lib/state.mjs";
import {
  listDefects,
  listSurfacedJobs,
  listUnreportedDefects,
  markDefectReported,
  markJobSurfaced,
  readDefect,
  recordDefect,
  redactArgv,
  resolveDefectsDir,
  tailText
} from "../../plugins/codex/scripts/lib/defect-log.mjs";

test("resolveDefectsDir is a sibling of the jobs dir, not a child", () => {
  const workspace = makeTempDir();
  const defectsDir = resolveDefectsDir(workspace);
  const jobsDir = resolveJobsDir(workspace);

  assert.equal(path.dirname(defectsDir), path.dirname(jobsDir));
  assert.equal(path.basename(defectsDir), "defects");
  assert.equal(defectsDir.startsWith(jobsDir), false, "must not nest under jobs/");
});

test("a marker survives job pruning that deletes every job", () => {
  const workspace = makeTempDir();
  const markerPath = recordDefect(workspace, { message: "boom" });
  assert.ok(markerPath, "recordDefect must return a path");

  // Simulate cleanupSessionJobs: save state with no jobs at all.
  saveState(workspace, { config: {}, jobs: [] });

  assert.equal(fs.existsSync(markerPath), true, "defect marker must outlive job pruning");
  assert.equal(listDefects(workspace).length, 1);
});

test("redactArgv keeps the subcommand and flag names but drops prompt text", () => {
  const redacted = redactArgv(["task", "refactor the billing module", "--write", "--model", "gpt-5.6-sol"]);

  assert.deepEqual(redacted, ["task", "<redacted>", "--write", "--model", "gpt-5.6-sol"]);
  assert.equal(redacted.includes("refactor the billing module"), false);
});

test("redactArgv redacts values of flags not on the safe list", () => {
  assert.deepEqual(redactArgv(["task", "--cwd", "/home/someone/secret-project"]), ["task", "--cwd", "<redacted>"]);
  assert.deepEqual(redactArgv(["status", "--job-id=task-abc"]), ["status", "--job-id=task-abc"]);
  assert.deepEqual(redactArgv(["transfer", "--source=/home/someone/x.jsonl"]), ["transfer", "--source=<redacted>"]);
});

test("recordDefect never writes positional prompt text into the marker", () => {
  const workspace = makeTempDir();
  const secret = "PROPRIETARY-PROMPT-TEXT";
  const markerPath = recordDefect(workspace, { argv: ["task", secret], message: "failed" });

  assert.equal(fs.readFileSync(markerPath, "utf8").includes(secret), false);
});

test("tailText keeps only the last 40 lines", () => {
  const tail = tailText(Array.from({ length: 100 }, (_, i) => `line${i}`).join("\n"));

  assert.equal(tail.split("\n").length, 40);
  assert.equal(tail.split("\n")[0], "line60");
  assert.equal(tail.includes("line59"), false);
});

test("recordDefect returns null instead of throwing when the dir cannot be written", () => {
  const workspace = makeTempDir();
  const defectsDir = resolveDefectsDir(workspace);
  fs.mkdirSync(path.dirname(defectsDir), { recursive: true });
  // Occupy the defects path with a FILE so mkdirSync must fail.
  fs.writeFileSync(defectsDir, "not a directory", "utf8");

  assert.equal(recordDefect(workspace, { message: "boom" }), null);
});

test("pruning retains only the newest 20 markers", () => {
  const workspace = makeTempDir();
  for (let i = 0; i < 25; i += 1) {
    recordDefect(workspace, { message: `boom ${i}` });
  }

  // Assert identity, not just cardinality: pin which 20 survive (the newest,
  // boom 5..boom 24, newest first) so a reversed sort that pruned the newest
  // 20 instead of the oldest 5 would fail this test even though it still
  // leaves exactly 20 markers on disk.
  const retained = listDefects(workspace).map((marker) => marker.message);
  assert.deepEqual(retained, Array.from({ length: 20 }, (_, i) => `boom ${24 - i}`));
  for (let i = 0; i < 5; i += 1) {
    assert.equal(retained.includes(`boom ${i}`), false, `boom ${i} must be pruned`);
  }
});

test("listUnreportedDefects excludes markers carrying reportedAt", () => {
  const workspace = makeTempDir();
  recordDefect(workspace, { message: "first" });
  const second = listDefects(workspace)[0];

  assert.equal(markDefectReported(workspace, second.id, { url: "https://example.test/1" }), true);

  assert.equal(listUnreportedDefects(workspace).length, 0);
  assert.equal(readDefect(workspace, second.id).reportedUrl, "https://example.test/1");
});

test("surfaced-job bookkeeping lives in defects/, keyed by job id", () => {
  const workspace = makeTempDir();

  assert.deepEqual(listSurfacedJobs(workspace), []);
  assert.equal(markJobSurfaced(workspace, "task-abc"), true);
  assert.deepEqual(listSurfacedJobs(workspace), ["task-abc"]);

  // Idempotent: marking twice must not duplicate.
  markJobSurfaced(workspace, "task-abc");
  assert.deepEqual(listSurfacedJobs(workspace), ["task-abc"]);
  assert.equal(fs.existsSync(path.join(resolveDefectsDir(workspace), "surfaced.json")), true);
});

test("resolveDefectsDir never throws, even for a malformed cwd", () => {
  // resolveStateDir (via resolveWorkspaceRoot -> path operations) throws
  // TypeError for a non-string, non-nullish cwd. Every exported function here
  // must be incapable of throwing, including this one.
  for (const badCwd of [123, {}, []]) {
    assert.doesNotThrow(() => resolveDefectsDir(badCwd));
    assert.equal(typeof resolveDefectsDir(badCwd), "string");
  }
});

test("markDefectReported rejects ids that don't match recordDefect's shape", () => {
  const workspace = makeTempDir();
  recordDefect(workspace, { message: "first" });

  assert.equal(
    markDefectReported(workspace, "../../../../etc/passwd", { url: "https://example.test" }),
    false
  );
  assert.equal(
    markDefectReported(workspace, "../defects/../../secret", { url: "https://example.test" }),
    false
  );
  assert.equal(markDefectReported(workspace, "not-a-defect-id-at-all", { url: "https://example.test" }), false);
  assert.equal(markDefectReported(workspace, 123, { url: "https://example.test" }), false);

  // A real id, generated by recordDefect itself, must still work.
  const real = listDefects(workspace)[0];
  assert.equal(markDefectReported(workspace, real.id, { url: "https://example.test" }), true);
});

test("recordDefect scrubs the user's home directory out of message and stderrTail", () => {
  const workspace = makeTempDir();
  const home = os.homedir();
  const markerPath = recordDefect(workspace, {
    message: `boom at ${home}/secret-project/index.js`,
    stderr: `Error: Claude session file not found: ${home}/.claude/projects/foo/bar.jsonl\n    at ${home}/plugins/codex/scripts/lib/claude-session-transfer.mjs:37:11`
  });

  const marker = JSON.parse(fs.readFileSync(markerPath, "utf8"));
  assert.equal(marker.message.includes(home), false);
  assert.equal(marker.message, "boom at ~/secret-project/index.js");
  assert.equal(marker.stderrTail.includes(home), false);
  assert.match(marker.stderrTail, /^Error: Claude session file not found: ~\/\.claude\/projects\/foo\/bar\.jsonl/);
  assert.match(marker.stderrTail, /at ~\/plugins\/codex\/scripts\/lib\/claude-session-transfer\.mjs:37:11$/);
});
