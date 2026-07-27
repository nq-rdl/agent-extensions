// SPDX-License-Identifier: Apache-2.0
// SPDX-FileCopyrightText: 2026 nq-rdl

import path from "node:path";
import process from "node:process";
import test from "node:test";
import assert from "node:assert/strict";
import { fileURLToPath } from "node:url";

import { makeTempDir, run } from "./helpers.mjs";
import { listDefects } from "../../plugins/codex/scripts/lib/defect-log.mjs";

const ROOT = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..", "..");
const COMPANION = path.join(ROOT, "plugins", "codex", "scripts", "codex-companion.mjs");

test("a failing companion run records a defect marker", () => {
  const workspace = makeTempDir();

  // An unknown subcommand throws at codex-companion.mjs:1075 and lands in main().catch().
  const result = run(process.execPath, [COMPANION, "frobnicate", "--cwd", workspace], { env: process.env });

  assert.equal(result.status, 1);
  assert.match(result.stderr, /Unknown subcommand/);

  const markers = listDefects(workspace);
  assert.equal(markers.length, 1, "the failure must leave a marker behind");
  assert.match(markers[0].message, /Unknown subcommand/);
  assert.equal(markers[0].surface, "companion");
  assert.equal(markers[0].argv[0], "frobnicate");
});

test("the marker's surface distinguishes a background worker from a foreground run", () => {
  const workspace = makeTempDir();

  // task-worker without --job-id throws at codex-companion.mjs:854.
  const result = run(process.execPath, [COMPANION, "task-worker", "--cwd", workspace], { env: process.env });

  assert.equal(result.status, 1);
  assert.equal(listDefects(workspace)[0].surface, "background-job");
});

test("stderr is unchanged by the marker write", () => {
  const workspace = makeTempDir();
  const result = run(process.execPath, [COMPANION, "frobnicate", "--cwd", workspace], { env: process.env });

  assert.equal(result.stderr.trim(), "Unknown subcommand: frobnicate");
});
