// SPDX-License-Identifier: Apache-2.0
// SPDX-FileCopyrightText: 2026 nq-rdl
//
// Regression: git hooks export GIT_DIR / GIT_WORK_TREE / GIT_INDEX_FILE. When the
// lefthook pre-push job ran these tests with that env, their git calls hit the real
// repository: "init" commits, moved branches, stray refs and rewritten user.* config.
// This runs git-heavy suites with the hook env pointed at a decoy repo and asserts
// the decoy is untouched. It fails without the scrub in helpers.mjs.

import crypto from "node:crypto";
import fs from "node:fs";
import path from "node:path";
import process from "node:process";
import test from "node:test";
import assert from "node:assert/strict";
import { spawnSync } from "node:child_process";
import { fileURLToPath, pathToFileURL } from "node:url";

import { GIT_LOCAL_ENV_VARS, initGitRepo, makeTempDir, run, scrubGitEnv } from "./helpers.mjs";

const HERE = path.dirname(fileURLToPath(import.meta.url));
const ROOT = path.resolve(HERE, "..", "..");
// Suites that create temp repos through helpers.mjs, the companion runtime, and the
// fake codex fixture.
const GIT_HEAVY_SUITES = ["git.test.mjs", "model-aliases.test.mjs"];

function makeDecoyRepo() {
  const decoy = makeTempDir("codex-git-env-decoy-");
  initGitRepo(decoy);
  fs.writeFileSync(path.join(decoy, "decoy.txt"), "decoy\n");
  run("git", ["add", "decoy.txt"], { cwd: decoy });
  run("git", ["commit", "-m", "decoy"], { cwd: decoy });
  // Drop the identity initGitRepo set so a leaked `git config user.name` shows up.
  run("git", ["config", "--unset", "user.name"], { cwd: decoy });
  run("git", ["config", "--unset", "user.email"], { cwd: decoy });
  return decoy;
}

function snapshot(decoy) {
  const git = (...args) => run("git", ["-C", decoy, ...args]).stdout;
  const gitDir = path.join(decoy, ".git");
  const hash = (file) =>
    fs.existsSync(file) ? crypto.createHash("sha256").update(fs.readFileSync(file)).digest("hex") : null;
  return {
    refs: git("for-each-ref", "--format=%(refname) %(objectname)"),
    head: fs.readFileSync(path.join(gitDir, "HEAD"), "utf8"),
    config: fs.readFileSync(path.join(gitDir, "config"), "utf8"),
    index: hash(path.join(gitDir, "index")),
    status: git("status", "--porcelain", "--untracked-files=all"),
    objects: git("count-objects", "-v")
  };
}

test("scrubGitEnv removes every repository-local git variable and keeps the rest", () => {
  const env = Object.fromEntries(GIT_LOCAL_ENV_VARS.map((key) => [key, "/decoy"]));
  Object.assign(env, { GIT_CONFIG_KEY_0: "user.name", GIT_CONFIG_VALUE_0: "x", GIT_AUTHOR_NAME: "keep", PATH: "/bin" });
  assert.deepEqual(scrubGitEnv(env), { GIT_AUTHOR_NAME: "keep", PATH: "/bin" });
});

// run() scrubs the env it is given, so the leaky children below use spawnSync directly.
function spawnWithEnv(args, options) {
  return spawnSync(process.execPath, args, { ...options, encoding: "utf8", shell: false, windowsHide: true });
}

test("importing helpers.mjs clears inherited git and host-session variables", () => {
  const decoy = makeDecoyRepo();
  const watched = ["GIT_DIR", "GIT_WORK_TREE", "CODEX_COMPANION_SESSION_ID", "CLAUDE_PLUGIN_DATA"];
  const probe =
    `import(${JSON.stringify(pathToFileURL(path.join(HERE, "helpers.mjs")).href)})` +
    `.then(() => process.stdout.write(JSON.stringify(${JSON.stringify(watched)}.filter((k) => k in process.env))))`;
  const result = spawnWithEnv(["--input-type=module", "-e", probe], {
    cwd: decoy,
    env: {
      ...process.env,
      GIT_DIR: path.join(decoy, ".git"),
      GIT_WORK_TREE: decoy,
      CODEX_COMPANION_SESSION_ID: "leaked-session",
      CLAUDE_PLUGIN_DATA: decoy
    }
  });
  assert.equal(result.status, 0, result.stderr);
  assert.deepEqual(JSON.parse(result.stdout), []);
});

test("git-heavy suites leave the repository named by a leaked hook env untouched", () => {
  const decoy = makeDecoyRepo();
  const before = snapshot(decoy);

  // Simulate the env git exports into a pre-push hook from a linked worktree.
  const hookEnv = {
    ...process.env,
    GIT_DIR: path.join(decoy, ".git"),
    GIT_WORK_TREE: decoy,
    GIT_INDEX_FILE: path.join(decoy, ".git", "index"),
    GIT_PREFIX: ""
  };
  delete hookEnv.NODE_TEST_CONTEXT;
  const suites = GIT_HEAVY_SUITES.map((name) => path.join(HERE, name));
  const result = spawnWithEnv(["--test", ...suites], { cwd: ROOT, env: hookEnv });

  const after = snapshot(decoy);
  assert.deepEqual(after, before, "a test wrote to the repository named by GIT_DIR");
  assert.equal(result.status, 0, `${result.stdout}\n${result.stderr}`);
});
