// SPDX-License-Identifier: Apache-2.0

import fs from "node:fs";
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

  assert.equal(listDefects(workspace).length, 20);
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
