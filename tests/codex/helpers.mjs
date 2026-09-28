// SPDX-License-Identifier: Apache-2.0
// Derived from openai/codex-plugin-cc v1.0.6 (db52e28), Apache-2.0. Modified for rdl-agent-extensions.

import fs from "node:fs";
import os from "node:os";
import path from "node:path";
import process from "node:process";
import { spawnSync } from "node:child_process";

// Git exports GIT_DIR (and, depending on the hook, GIT_WORK_TREE, GIT_INDEX_FILE,
// GIT_PREFIX, ...) into hooks, e.g. when pushing from a linked worktree. Inherited,
// they redirect every git call these tests make -- through run(), through the
// companion runtime, through the fake codex fixture -- from the temp repos to the
// real repository, rewriting its refs, HEAD, index and config. Strip the
// repository-local variables (`git rev-parse --local-env-vars`) from this process
// as soon as any test imports this module, and from every env run() spawns with.
export const GIT_LOCAL_ENV_VARS = Object.freeze([
  "GIT_ALTERNATE_OBJECT_DIRECTORIES",
  "GIT_CONFIG",
  "GIT_CONFIG_PARAMETERS",
  "GIT_CONFIG_COUNT",
  "GIT_OBJECT_DIRECTORY",
  "GIT_DIR",
  "GIT_WORK_TREE",
  "GIT_IMPLICIT_WORK_TREE",
  "GIT_GRAFT_FILE",
  "GIT_INDEX_FILE",
  "GIT_NO_REPLACE_OBJECTS",
  "GIT_REPLACE_REF_BASE",
  "GIT_PREFIX",
  "GIT_SHALLOW_FILE",
  "GIT_COMMON_DIR"
]);

export function scrubGitEnv(env) {
  for (const key of Object.keys(env)) {
    if (GIT_LOCAL_ENV_VARS.includes(key) || /^GIT_CONFIG_(KEY|VALUE)_\d+$/.test(key)) {
      delete env[key];
    }
  }
  return env;
}

// A test run started from a Claude Code session (e.g. an agent's git push) also
// inherits the companion's session variables. They point job state at the real
// plugin data dir and filter status/result by the live session, so tests that do
// not set them explicitly would read and write the user's real jobs.
export function scrubHostSessionEnv(env) {
  for (const key of Object.keys(env)) {
    if (key === "CLAUDE_PLUGIN_DATA" || key === "CLAUDE_ENV_FILE" || key.startsWith("CODEX_COMPANION_")) {
      delete env[key];
    }
  }
  return env;
}

scrubGitEnv(process.env);
scrubHostSessionEnv(process.env);

export function makeTempDir(prefix = "codex-plugin-test-") {
  return fs.mkdtempSync(path.join(os.tmpdir(), prefix));
}

export function writeExecutable(filePath, source) {
  fs.writeFileSync(filePath, source, { encoding: "utf8", mode: 0o755 });
}

// Never spawns through a shell. Callers hand this helper environment-derived
// absolute paths -- the repo root off import.meta.url, process.execPath, mkdtemp
// dirs -- and a shell would re-parse those on spaces and metacharacters. The
// commands used here (node, git, bash, process.execPath) are all directly
// executable, so there is nothing to gain from a shell and no `shell` option to
// override: shell interpretation is not a per-call decision.
export function run(command, args, options = {}) {
  return spawnSync(command, args, {
    cwd: options.cwd,
    env: scrubGitEnv({ ...(options.env ?? process.env) }),
    encoding: "utf8",
    input: options.input,
    shell: false,
    windowsHide: true
  });
}

export function initGitRepo(cwd) {
  run("git", ["init", "-b", "main"], { cwd });
  run("git", ["config", "user.name", "Codex Plugin Tests"], { cwd });
  run("git", ["config", "user.email", "tests@example.com"], { cwd });
  run("git", ["config", "commit.gpgsign", "false"], { cwd });
  run("git", ["config", "tag.gpgsign", "false"], { cwd });
}
