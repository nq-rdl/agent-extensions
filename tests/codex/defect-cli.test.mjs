// SPDX-License-Identifier: Apache-2.0

import path from "node:path";
import process from "node:process";
import test from "node:test";
import assert from "node:assert/strict";
import { fileURLToPath } from "node:url";

import { makeTempDir, run } from "./helpers.mjs";
import { listDefects, recordDefect, resolveDefectsDir } from "../../plugins/codex/scripts/lib/defect-log.mjs";

const ROOT = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..", "..");
const CLI = path.join(ROOT, "plugins", "codex", "scripts", "codex-defects.mjs");

function runCli(args, cwd) {
  return run(process.execPath, [CLI, ...args, "--cwd", cwd], { env: process.env });
}

test("list --json reports unreported defects with a classification verdict", () => {
  const workspace = makeTempDir();
  recordDefect(workspace, { message: "Stored job task-abc is missing its task request payload." });

  const result = runCli(["list", "--json"], workspace);
  assert.equal(result.status, 0, result.stderr);

  const payload = JSON.parse(result.stdout);
  assert.equal(payload.defects.length, 1);
  assert.equal(payload.defects[0].verdict, "candidate-defect");
});

test("list --json is empty and still valid JSON when there are no defects", () => {
  const result = runCli(["list", "--json"], makeTempDir());

  assert.equal(result.status, 0, result.stderr);
  assert.deepEqual(JSON.parse(result.stdout).defects, []);
});

test("show --latest returns the full marker plus its classification", () => {
  const workspace = makeTempDir();
  recordDefect(workspace, { message: "git is not installed. Install Git and retry." });

  const result = runCli(["show", "--latest", "--json"], workspace);
  assert.equal(result.status, 0, result.stderr);

  const payload = JSON.parse(result.stdout);
  assert.equal(payload.classification.verdict, "not-a-defect");
  assert.equal(payload.classification.cause, "git-environment");
  assert.ok(payload.environment, "the marker's environment block must be included");
  assert.equal(payload.defectsDir, resolveDefectsDir(workspace), "the skill needs the dir to write its report into");
});

test("show exits non-zero for an unknown id", () => {
  const result = runCli(["show", "defect-nope", "--json"], makeTempDir());

  assert.equal(result.status, 1);
  assert.match(result.stderr, /not found/i);
});

test("mark-reported records the issue url", () => {
  const workspace = makeTempDir();
  recordDefect(workspace, { message: "Unknown subcommand: taks" });
  const { id } = listDefects(workspace)[0];

  const result = runCli(["mark-reported", id, "--url", "https://example.test/issues/7"], workspace);
  assert.equal(result.status, 0, result.stderr);

  assert.equal(listDefects(workspace)[0].reportedUrl, "https://example.test/issues/7");
});

test("an unknown subcommand exits non-zero", () => {
  const result = runCli(["frobnicate"], makeTempDir());

  assert.equal(result.status, 1);
  assert.match(result.stderr, /Unknown subcommand/);
});
