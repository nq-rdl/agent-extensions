// SPDX-License-Identifier: Apache-2.0
// SPDX-FileCopyrightText: 2026 nq-rdl

import path from "node:path";
import fs from "node:fs";
import process from "node:process";
import test from "node:test";
import assert from "node:assert/strict";
import { fileURLToPath } from "node:url";

import { makeTempDir, run } from "./helpers.mjs";
import { listDefects } from "../../plugins/codex/scripts/lib/defect-log.mjs";

const ROOT = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..", "..");
const COMPANION = path.join(ROOT, "plugins", "codex", "scripts", "codex-companion.mjs");

for (const [target, source] of [[".claude-plugin", "plugins/codex"], [".codex-plugin", "dist/codex/plugins/codex"]]) {
  test(`installed ${target} failure records its own version in private storage`, () => {
    const workspace = makeTempDir();
    const cache = path.join(makeTempDir(), "installed plugin with spaces");
    fs.cpSync(path.join(ROOT, source), cache, { recursive: true });
    const manifest = path.join(cache, target, "plugin.json");
    const metadata = JSON.parse(fs.readFileSync(manifest, "utf8"));
    metadata.version = "9.8.7";
    fs.writeFileSync(manifest, JSON.stringify(metadata));
    const stateHome = makeTempDir();
    const env = { ...process.env, XDG_STATE_HOME: stateHome };
    delete env.CLAUDE_PLUGIN_DATA;
    const result = run(process.execPath, [path.join(cache, "scripts/codex-companion.mjs"), "frobnicate", "--cwd", workspace], { env });
    assert.equal(result.status, 1);
    const stateRoot = path.join(stateHome, "codex-companion");
    const state = path.join(stateRoot, fs.readdirSync(stateRoot)[0]);
    const defects = path.join(state, "defects");
    const marker = path.join(defects, fs.readdirSync(defects).find((name) => name.startsWith("defect-")));
    assert.equal(JSON.parse(fs.readFileSync(marker, "utf8")).environment.plugin, "9.8.7");
    assert.equal(fs.statSync(marker).mode & 0o777, 0o600);
    for (const dir of [stateRoot, state, defects]) assert.equal(fs.statSync(dir).mode & 0o777, 0o700);
  });
}

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
