// SPDX-License-Identifier: Apache-2.0
// Derived from openai/codex-plugin-cc v1.0.6 (db52e28), Apache-2.0. Modified for rdl-agent-extensions.

import fs from "node:fs";
import os from "node:os";
import path from "node:path";
import { spawnSync } from "node:child_process";

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
    env: options.env,
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
