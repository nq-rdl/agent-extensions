// SPDX-License-Identifier: Apache-2.0

import fs from "node:fs";
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

// A fake `node` that answers the wrapper's single version probe with
// `major minor` and, when exec'd on the hook script, streams stdin through and
// exits with `exitCode`. The wrapper deliberately issues one `-p` rather than
// two — a second Node start-up costs ~40ms on every hook invocation — so this
// stub answers any `-p` with the pair rather than matching on the expression.
function fakeNode(major, minor, exitCode = 0) {
  return `#!/bin/sh
case "$1" in
  -p)
    echo "${major} ${minor}"
    ;;
  *)
    while IFS= read -r line; do printf '%s\n' "$line"; done
    exit ${exitCode}
    ;;
esac
`;
}

// A `node` that exists but whose version probe yields nothing usable. Without
// the wrapper's parse guard this dies inside `[ "$major" -lt 18 ]` under
// `set -e`, exiting non-zero with no explanation of what the user must install.
function fakeNodeWithUnusableProbe() {
  return `#!/bin/sh
case "$1" in
  -p) echo "" ;;
  *)  exit 0 ;;
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

  test(`${name} wrapper reports the preflight message when the version probe is unusable`, () => {
    const binDir = makeTempDir();
    writeExecutable(path.join(binDir, "node"), fakeNodeWithUnusableProbe());

    const result = runWrapper(wrapperPath, binDir, "");

    assert.equal(result.status, 1);
    assert.equal(
      result.stderr.trim(),
      NODE_PREFLIGHT_MESSAGE,
      "an unparseable probe must name the requirement, not exit bare from `set -e`"
    );
  });
}

// ── Installed-copy runtime checks (#311) ────────────────────────────────────
// Copy ONLY plugins/codex into a cache path that contains spaces, run from an
// unrelated working directory, and execute the command strings from the
// installed hooks/hooks.json the way Claude Code's shell form does: once with
// the placeholder left for the shell to expand from the exported
// CLAUDE_PLUGIN_ROOT, and once textually substituted first. The fake `node`
// proves which script the wrapper exec'd, that stdin arrived, and that the
// child's exit status is returned unchanged.
function installCodexCopy() {
  const tmp = makeTempDir("codex hook install ");
  const root = path.join(tmp, "plugin cache", "codex");
  fs.cpSync(PLUGIN_ROOT, root, { recursive: true });
  const cwd = path.join(tmp, "unrelated cwd");
  fs.mkdirSync(cwd);
  return { root, cwd, bin: makeTempDir() };
}

function installedCommands(root) {
  const config = JSON.parse(fs.readFileSync(path.join(root, "hooks", "hooks.json"), "utf8"));
  const commands = new Set();
  for (const groups of Object.values(config.hooks)) {
    for (const group of groups) {
      for (const hook of group.hooks) commands.add(hook.command);
    }
  }
  return [...commands];
}

function fakeNodeRecordingScript(exitCode) {
  return `#!/bin/sh
case "$1" in
  -p) echo "22 1" ;;
  *)
    [ -f "$1" ] || { printf 'script not found: %s\\n' "$1" >&2; exit 97; }
    printf 'SCRIPT=%s\\n' "$1"
    while IFS= read -r line; do printf '%s\\n' "$line"; done
    exit ${exitCode}
    ;;
esac
`;
}

function runShellForm(command, { root, cwd, bin }, substitute, input) {
  const text = substitute ? command.split("${CLAUDE_PLUGIN_ROOT}").join(root) : command;
  return run("/bin/sh", ["-c", text], {
    cwd,
    env: { PATH: bin, HOME: cwd, CLAUDE_PLUGIN_ROOT: root },
    input
  });
}

test("installed codex hooks keep executable wrappers", () => {
  const { root } = installCodexCopy();
  for (const name of ["codex-session-lifecycle.sh", "codex-stop-review-gate.sh", "codex-defect-report.sh"]) {
    const mode = fs.statSync(path.join(root, "scripts", name)).mode;
    assert.ok(mode & 0o100, `${name} must stay executable in the installed copy`);
  }
});

for (const substitute of [false, true]) {
  const form = substitute ? "textually substituted" : "shell-expanded";
  test(`installed codex hook commands run from a spaced path (${form})`, () => {
    const install = installCodexCopy();
    writeExecutable(path.join(install.bin, "node"), fakeNodeRecordingScript(7));
    const commands = installedCommands(install.root);
    assert.equal(commands.length, 3);
    for (const command of commands) {
      const result = runShellForm(command, install, substitute, "PING\n");
      assert.equal(result.status, 7, `${command}: ${result.stderr}`);
      assert.match(result.stdout, /PING/, "stdin must reach the exec'd hook");
      const script = /SCRIPT=(.*)/.exec(result.stdout)[1];
      assert.ok(script.startsWith(install.root + path.sep), `exec'd ${script} outside the installed copy`);
    }
  });
}

for (const [label, source] of [
  ["missing", null],
  ["old", fakeNode(18, 17, 0)],
  ["unparseable", fakeNodeWithUnusableProbe()]
]) {
  test(`installed codex hook commands report ${label} Node.js from a spaced path`, () => {
    const install = installCodexCopy();
    if (source) writeExecutable(path.join(install.bin, "node"), source);
    for (const command of installedCommands(install.root)) {
      const result = runShellForm(command, install, false, "");
      assert.equal(result.status, 1, command);
      assert.equal(result.stderr.trim(), NODE_PREFLIGHT_MESSAGE, command);
    }
  });
}

test("the three wrappers share one Node.js preflight and one owned minimum", () => {
  const extract = (file) => {
    const text = fs.readFileSync(file, "utf8");
    return text.slice(text.indexOf("codex_require_node() {"), text.indexOf("\ncodex_require_node\n"));
  };
  const [first, ...rest] = WRAPPERS.map(([, file]) => extract(file));
  assert.ok(first.includes(">=18.18.0") && first.includes('"$minor" -lt 18'), "minimum must be 18.18");
  for (const body of rest) assert.equal(body, first, "preflight bodies must stay byte-identical");
});
