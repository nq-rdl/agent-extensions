// SPDX-License-Identifier: Apache-2.0
// SPDX-FileCopyrightText: 2026 nq-rdl
//
// Model-alias contract for the codex companion (issues #392, #393).
// - Every alias in MODEL_ALIASES resolves to its full id on `task`.
// - `review` and `adversarial-review` normalise `--model` the same way
//   (before #392 the review paths sent the literal alias to the backend).
// - The usage text documents `--model` for both review commands.
// The docs side (model-guide table, rescue outline) is pinned by
// tests/test_codex_model_aliases.py.

import fs from "node:fs";
import path from "node:path";
import test from "node:test";
import assert from "node:assert/strict";
import { fileURLToPath } from "node:url";

import { buildEnv, installFakeCodex } from "./fake-codex-fixture.mjs";
import { initGitRepo, makeTempDir, run } from "./helpers.mjs";

const ROOT = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..", "..");
const SCRIPT = path.join(ROOT, "plugins", "codex", "scripts", "codex-companion.mjs");

// The decided mapping. Bare `sol`/`terra`/`luna` stay on GPT-5.6: it runs on every
// account and every supported CLI, and there is no gpt-6-terra. GPT-6 needs an
// explicit suffixed form (or `astra`, which only exists in GPT-6).
const EXPECTED_ALIASES = {
  spark: "gpt-5.3-codex-spark",
  sol: "gpt-5.6-sol",
  terra: "gpt-5.6-terra",
  luna: "gpt-5.6-luna",
  "sol-5.6": "gpt-5.6-sol",
  "terra-5.6": "gpt-5.6-terra",
  "luna-5.6": "gpt-5.6-luna",
  astra: "gpt-6-astra",
  "astra-6": "gpt-6-astra",
  "sol-6": "gpt-6-sol",
  "luna-6": "gpt-6-luna"
};

function parseModelAliases() {
  const src = fs.readFileSync(SCRIPT, "utf8");
  const block = src.match(/const MODEL_ALIASES = new Map\(\[([\s\S]*?)\]\);/);
  assert.ok(block, "codex-companion.mjs must define MODEL_ALIASES as a Map literal");
  return Object.fromEntries([...block[1].matchAll(/\[\s*"([^"]+)"\s*,\s*"([^"]+)"\s*\]/g)].map((m) => [m[1], m[2]]));
}

function makeRepo() {
  const repo = makeTempDir();
  const binDir = makeTempDir();
  installFakeCodex(binDir);
  initGitRepo(repo);
  fs.mkdirSync(path.join(repo, "src"));
  fs.writeFileSync(path.join(repo, "src", "app.js"), "export const value = items[0];\n");
  run("git", ["add", "src/app.js"], { cwd: repo });
  run("git", ["commit", "-m", "init"], { cwd: repo });
  fs.writeFileSync(path.join(repo, "src", "app.js"), "export const value = items[0].id;\n");
  return { repo, binDir, statePath: path.join(binDir, "fake-codex-state.json") };
}

function readFakeState(statePath) {
  return JSON.parse(fs.readFileSync(statePath, "utf8"));
}

test("MODEL_ALIASES holds exactly the decided alias set", () => {
  assert.deepEqual(parseModelAliases(), EXPECTED_ALIASES);
});

test("task resolves every alias to its full model id", () => {
  const { repo, binDir, statePath } = makeRepo();
  for (const [alias, full] of Object.entries(EXPECTED_ALIASES)) {
    const result = run("node", [SCRIPT, "task", "--model", alias, "diagnose the failing test"], {
      cwd: repo,
      env: buildEnv(binDir)
    });
    assert.equal(result.status, 0, result.stderr);
    assert.equal(readFakeState(statePath).lastTurnStart.model, full, `alias ${alias}`);
  }
});

test("task alias lookup ignores case and surrounding space; full ids and unknown names pass through", () => {
  const { repo, binDir, statePath } = makeRepo();
  for (const [requested, expected] of [
    ["Luna-6", "gpt-6-luna"],
    [" SOL ", "gpt-5.6-sol"],
    ["gpt-6-sol", "gpt-6-sol"],
    ["gpt-5.6-luna", "gpt-5.6-luna"],
    ["some-future-model", "some-future-model"]
  ]) {
    const result = run("node", [SCRIPT, "task", "--model", requested, "diagnose the failing test"], {
      cwd: repo,
      env: buildEnv(binDir)
    });
    assert.equal(result.status, 0, result.stderr);
    assert.equal(readFakeState(statePath).lastTurnStart.model, expected, `requested ${JSON.stringify(requested)}`);
  }
});

test("review normalises --model aliases before starting the review thread", () => {
  const { repo, binDir, statePath } = makeRepo();
  for (const [argv, expected] of [
    [["review", "--model", "sol"], "gpt-5.6-sol"],
    [["review", "-m", "luna-6"], "gpt-6-luna"],
    // The skill forwards "$ARGUMENTS" as one quoted string.
    [["review", "--wait --model astra"], "gpt-6-astra"],
    [["review", "--model", "gpt-5.6-terra"], "gpt-5.6-terra"]
  ]) {
    const result = run("node", [SCRIPT, ...argv], { cwd: repo, env: buildEnv(binDir) });
    assert.equal(result.status, 0, result.stderr);
    assert.equal(readFakeState(statePath).lastThreadStart.model, expected, `argv ${JSON.stringify(argv)}`);
  }
});

test("adversarial-review normalises --model aliases before the review turn", () => {
  const { repo, binDir, statePath } = makeRepo();
  for (const [argv, expected] of [
    [["adversarial-review", "--model", "luna"], "gpt-5.6-luna"],
    [["adversarial-review", "-m", "sol-6", "look", "at", "caching"], "gpt-6-sol"],
    [["adversarial-review", "--wait --model terra-5.6 focus on retries"], "gpt-5.6-terra"]
  ]) {
    const result = run("node", [SCRIPT, ...argv], { cwd: repo, env: buildEnv(binDir) });
    assert.equal(result.status, 0, result.stderr);
    assert.equal(readFakeState(statePath).lastTurnStart.model, expected, `argv ${JSON.stringify(argv)}`);
  }
});

test("usage text documents --model for review, adversarial-review and task", () => {
  const result = run("node", [SCRIPT, "help"], { cwd: ROOT, env: process.env });
  assert.equal(result.status, 0, result.stderr);
  for (const sub of ["review", "adversarial-review", "task"]) {
    const line = result.stdout.split("\n").find((l) => l.includes(`codex-companion.mjs ${sub} `));
    assert.ok(line, `usage must list the ${sub} subcommand`);
    assert.match(line, /--model <model\|alias>/, `usage for ${sub} must document --model`);
  }
});
