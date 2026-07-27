// SPDX-License-Identifier: Apache-2.0
// SPDX-FileCopyrightText: 2026 nq-rdl

import path from "node:path";
import process from "node:process";
import test from "node:test";
import assert from "node:assert/strict";
import { fileURLToPath } from "node:url";

import { buildEnv, installFakeCodex } from "./fake-codex-fixture.mjs";
import { makeTempDir, run } from "./helpers.mjs";
import {
  listDefects,
  markDefectReported,
  recordDefect,
  resolveDefectsDir
} from "../../plugins/codex/scripts/lib/defect-log.mjs";

const ROOT = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..", "..");
const CLI = path.join(ROOT, "plugins", "codex", "scripts", "codex-defects.mjs");

function runCli(args, cwd, env = process.env) {
  return run(process.execPath, [CLI, ...args, "--cwd", cwd], { env });
}

test("list reports unreported defects with a classification verdict", () => {
  const workspace = makeTempDir();
  recordDefect(workspace, { message: "Stored job task-abc is missing its task request payload." });

  const result = runCli(["list", "--json"], workspace);
  assert.equal(result.status, 0, result.stderr);

  const payload = JSON.parse(result.stdout);
  assert.equal(payload.defects.length, 1);

  const [marker] = listDefects(workspace);
  const [entry] = payload.defects;
  assert.equal(entry.id, marker.id);
  assert.equal(entry.recordedAt, marker.recordedAt);
  assert.equal(entry.surface, marker.surface);
  assert.equal(entry.message, marker.message);
  assert.equal(entry.verdict, "candidate-defect");
  assert.equal(entry.cause, "unclassified");
});

test("list defaults to unreported markers; --all returns every retained marker", () => {
  const workspace = makeTempDir();
  recordDefect(workspace, { message: "Stored job task-abc is missing its task request payload." });
  recordDefect(workspace, { message: "Unknown subcommand: taks" });
  const [newest] = listDefects(workspace);
  assert.ok(markDefectReported(workspace, newest.id, { url: "https://example.test/issues/1" }));

  const unreportedOnly = runCli(["list", "--json"], workspace);
  assert.equal(unreportedOnly.status, 0, unreportedOnly.stderr);
  assert.equal(JSON.parse(unreportedOnly.stdout).defects.length, 1);

  const all = runCli(["list", "--all", "--json"], workspace);
  assert.equal(all.status, 0, all.stderr);
  assert.equal(JSON.parse(all.stdout).defects.length, 2);
});

test("list is empty and still valid JSON when there are no defects", () => {
  const result = runCli(["list", "--json"], makeTempDir());

  assert.equal(result.status, 0, result.stderr);
  assert.deepEqual(JSON.parse(result.stdout).defects, []);
});

test("--json is accepted but is a no-op: output is identical with and without it", () => {
  const workspace = makeTempDir();
  recordDefect(workspace, { message: "Stored job task-abc is missing its task request payload." });

  const withFlag = runCli(["list", "--json"], workspace);
  const withoutFlag = runCli(["list"], workspace);

  assert.equal(withFlag.status, 0, withFlag.stderr);
  assert.equal(withoutFlag.status, 0, withoutFlag.stderr);
  assert.equal(withFlag.stdout, withoutFlag.stdout);
  assert.equal(JSON.parse(withoutFlag.stdout).defects.length, 1);
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

  const payload = JSON.parse(result.stdout);
  assert.deepEqual(payload, { ok: true, id, url: "https://example.test/issues/7" });

  assert.equal(listDefects(workspace)[0].reportedUrl, "https://example.test/issues/7");
});

test("mark-reported exits non-zero for an unknown id", () => {
  const result = runCli(
    ["mark-reported", "defect-does-not-exist", "--url", "https://example.test/issues/9"],
    makeTempDir()
  );

  assert.equal(result.status, 1);
  assert.match(result.stderr, /Could not mark/i);
});

test("mark-reported with a missing --url value exits non-zero without a stack trace", () => {
  const workspace = makeTempDir();
  recordDefect(workspace, { message: "Unknown subcommand: taks" });
  const { id } = listDefects(workspace)[0];

  // Deliberately not using runCli here: it always appends "--cwd <dir>"
  // after the caller's args, which would swallow a trailing bare "--url" as
  // the (bogus) value of --cwd instead of leaving it truly value-less. Put
  // --cwd first so --url is the last, value-less token on the line.
  const result = run(process.execPath, [CLI, "mark-reported", id, "--cwd", workspace, "--url"], {
    env: process.env
  });

  assert.equal(result.status, 1);
  assert.equal(result.stderr.trim(), "Missing value for --url");
});

test("a relative --cwd resolves to the same defects as an absolute --cwd", () => {
  const workspace = makeTempDir();
  recordDefect(workspace, { message: "git is not installed. Install Git and retry." });

  const absolute = runCli(["list", "--json"], workspace);
  assert.equal(absolute.status, 0, absolute.stderr);

  const relative = path.relative(process.cwd(), workspace);
  const result = run(process.execPath, [CLI, "list", "--json", "--cwd", relative], { env: process.env });
  assert.equal(result.status, 0, result.stderr);

  assert.deepEqual(JSON.parse(result.stdout), JSON.parse(absolute.stdout));
});

test("an unknown subcommand exits non-zero", () => {
  const result = runCli(["frobnicate"], makeTempDir());

  assert.equal(result.status, 1);
  assert.match(result.stderr, /Unknown subcommand/);
});

// The message defect-classify.test.mjs already pins to needs-cross-check.
const AUTH_FAILURE =
  "Your access token could not be refreshed because your refresh token was already used. Please log out and sign in again.";

test("an auth marker resolves to a terminal verdict when the readiness check reports ready", () => {
  const workspace = makeTempDir();
  const binDir = makeTempDir();
  installFakeCodex(binDir); // default behavior: logged in
  recordDefect(workspace, { message: AUTH_FAILURE });

  const result = runCli(["show", "--latest"], workspace, buildEnv(binDir));
  assert.equal(result.status, 0, result.stderr);

  const payload = JSON.parse(result.stdout);
  assert.equal(payload.classification.verdict, "candidate-defect");
  assert.equal(payload.classification.cause, "readiness-check-disagreement");
});

test("an auth marker resolves to not-a-defect when the readiness check agrees the session is logged out", () => {
  const workspace = makeTempDir();
  const binDir = makeTempDir();
  installFakeCodex(binDir, "logged-out");
  recordDefect(workspace, { message: AUTH_FAILURE });

  const result = runCli(["list"], workspace, buildEnv(binDir));
  assert.equal(result.status, 0, result.stderr);

  const [entry] = JSON.parse(result.stdout).defects;
  assert.notEqual(entry.verdict, "needs-cross-check", "list must never emit a non-terminal verdict");
  assert.equal(entry.verdict, "not-a-defect");
  assert.equal(entry.cause, "auth");
});
