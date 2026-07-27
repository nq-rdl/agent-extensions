// SPDX-License-Identifier: Apache-2.0

import path from "node:path";
import test from "node:test";
import assert from "node:assert/strict";
import { fileURLToPath } from "node:url";

import { makeTempDir, run, writeExecutable } from "./helpers.mjs";

const ROOT = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..", "..");
const PLUGIN_ROOT = path.join(ROOT, "plugins", "codex");
const SESSION_WRAPPER = path.join(PLUGIN_ROOT, "scripts", "codex-session-lifecycle.sh");
const STOP_WRAPPER = path.join(PLUGIN_ROOT, "scripts", "codex-stop-review-gate.sh");
const DEFECT_WRAPPER = path.join(PLUGIN_ROOT, "scripts", "codex-defect-report.sh");

const NODE_PREFLIGHT_MESSAGE =
  "Codex plugin requires Node.js >=18.18.0; install or upgrade Node: https://nodejs.org/en/download";

const WRAPPERS = [
  ["session-lifecycle", SESSION_WRAPPER],
  ["stop-review-gate", STOP_WRAPPER],
  ["defect-report", DEFECT_WRAPPER]
];

// A fake `node` that answers the wrapper's version probes with `major.minor` and,
// when exec'd on the hook script, streams stdin through and exits with `exitCode`.
function fakeNode(major, minor, exitCode = 0) {
  return `#!/bin/sh
case "$1" in
  -p)
    case "$2" in
      *'[0]'*) echo ${major} ;;
      *'[1]'*) echo ${minor} ;;
      *) echo "" ;;
    esac
    ;;
  *)
    while IFS= read -r line; do printf '%s\n' "$line"; done
    exit ${exitCode}
    ;;
esac
`;
}

// Run a wrapper by absolute path so the kernel honours its `#!/bin/sh` shebang
// regardless of the child PATH; only `node` needs to be resolved from PATH.
function runWrapper(wrapperPath, binDir, input) {
  return run(wrapperPath, [], {
    env: { ...process.env, PATH: binDir, CLAUDE_PLUGIN_ROOT: PLUGIN_ROOT },
    input
  });
}

for (const [name, wrapperPath] of WRAPPERS) {
  test(`${name} wrapper passes stdin through and preserves the child exit status`, () => {
    const binDir = makeTempDir();
    writeExecutable(path.join(binDir, "node"), fakeNode(20, 0, 7));

    const result = runWrapper(wrapperPath, binDir, "PING\n");

    assert.equal(result.status, 7, "exit status of the exec'd node must pass through");
    assert.match(result.stdout, /PING/, "stdin must reach the exec'd node unchanged");
  });

  test(`${name} wrapper reports the exact preflight message when node is missing`, () => {
    const binDir = makeTempDir(); // deliberately empty: no node on PATH

    const result = runWrapper(wrapperPath, binDir, "");

    assert.equal(result.status, 1);
    assert.equal(result.stderr.trim(), NODE_PREFLIGHT_MESSAGE);
  });

  test(`${name} wrapper rejects a Node.js older than 18.18.0`, () => {
    const binDir = makeTempDir();
    writeExecutable(path.join(binDir, "node"), fakeNode(16, 20, 0));

    const result = runWrapper(wrapperPath, binDir, "");

    assert.equal(result.status, 1);
    assert.equal(result.stderr.trim(), NODE_PREFLIGHT_MESSAGE);
  });

  test(`${name} wrapper rejects 18.x below the 18.18 floor`, () => {
    const binDir = makeTempDir();
    writeExecutable(path.join(binDir, "node"), fakeNode(18, 17, 0));

    const result = runWrapper(wrapperPath, binDir, "");

    assert.equal(result.status, 1);
    assert.equal(result.stderr.trim(), NODE_PREFLIGHT_MESSAGE);
  });
}
