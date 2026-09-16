// SPDX-License-Identifier: Apache-2.0
// Derived from openai/codex-plugin-cc v1.0.6 (db52e28), Apache-2.0. Modified for rdl-agent-extensions.

import fs from "node:fs";
import os from "node:os";
import path from "node:path";
import test from "node:test";
import assert from "node:assert/strict";

import { makeTempDir } from "./helpers.mjs";
import { ensureStateDir, loadState, readJobFile, resolveJobFile, resolveJobLogFile, resolveStateDir, resolveStateFile, resolveStateRoot, saveState, writeJobFile } from "../../plugins/codex/scripts/lib/state.mjs";

for (const kind of ["state", "job"]) {
  test(`${kind} readers see the previous complete record while an update is being written`, (t) => {
    const workspace = makeTempDir();
    const queued = { id: "task-test", status: "queued" };
    const running = { ...queued, status: "running" };
    const write = (job) => kind === "state"
      ? saveState(workspace, { jobs: [job] })
      : writeJobFile(workspace, job.id, job);
    const read = () => kind === "state"
      ? loadState(workspace).jobs[0]
      : readJobFile(resolveJobFile(workspace, queued.id));
    write(queued);

    // Pause at the actual truncation boundary, making the CI reader/writer race deterministic.
    const originalWrite = fs.writeFileSync;
    let duringWrite;
    t.mock.method(fs, "writeFileSync", (file, data, options) => {
      const fd = fs.openSync(file, "w");
      try {
        duringWrite = read();
        originalWrite(fd, data, options);
      } finally {
        fs.closeSync(fd);
      }
    });

    write(running);
    assert.deepEqual(duringWrite, queued);
    assert.deepEqual(read(), running);
  });
}

test("resolveStateDir uses private per-user storage without Claude plugin data", (t) => {
  const previous = { CLAUDE_PLUGIN_DATA: process.env.CLAUDE_PLUGIN_DATA, XDG_STATE_HOME: process.env.XDG_STATE_HOME };
  t.after(() => {
    for (const [key, value] of Object.entries(previous)) {
      if (value === undefined) delete process.env[key]; else process.env[key] = value;
    }
  });
  delete process.env.CLAUDE_PLUGIN_DATA;
  delete process.env.XDG_STATE_HOME;
  assert.equal(resolveStateRoot(), path.join(os.homedir(), ".local/state/codex-companion"));
  process.env.XDG_STATE_HOME = "relative-state";
  assert.equal(resolveStateRoot(), path.join(os.homedir(), ".local/state/codex-companion"));
  for (const home of ["", "/", "relative-home"]) {
    const mock = t.mock.method(os, "homedir", () => home);
    assert.equal(resolveStateRoot(), path.join(os.userInfo().homedir, ".local/state/codex-companion"));
    mock.mock.restore();
  }
  process.env.XDG_STATE_HOME = makeTempDir();
  const workspace = makeTempDir();
  const stateDir = resolveStateDir(workspace);
  const stateRoot = path.join(process.env.XDG_STATE_HOME, "codex-companion");
  assert.equal(path.dirname(stateDir), stateRoot);
  assert.match(path.basename(stateDir), /.+-[a-f0-9]{16}$/);
  const oldMask = process.umask(0o022);
  t.after(() => process.umask(oldMask));
  saveState(workspace, { jobs: [{ id: "private", prompt: "private input" }] });
  const jobFile = writeJobFile(workspace, "private", { output: "private output" });
  for (const dir of [stateRoot, stateDir, path.dirname(jobFile)]) {
    assert.equal(fs.statSync(dir).mode & 0o777, 0o700);
    assert.equal(fs.statSync(dir).uid, process.getuid());
  }
  for (const file of [resolveStateFile(workspace), jobFile]) {
    assert.equal(fs.statSync(file).mode & 0o777, 0o600);
  }
  fs.chmodSync(stateRoot, 0o755);
  ensureStateDir(workspace);
  assert.equal(fs.statSync(stateRoot).mode & 0o777, 0o700);
  fs.rmSync(stateRoot, { recursive: true });
  const outside = makeTempDir();
  fs.symlinkSync(outside, stateRoot);
  assert.throws(() => ensureStateDir(workspace), /Refusing/);
  assert.deepEqual(fs.readdirSync(outside), []);
});

test("resolveStateDir uses CLAUDE_PLUGIN_DATA when it is provided", () => {
  const workspace = makeTempDir();
  const pluginDataDir = makeTempDir();
  const previousPluginDataDir = process.env.CLAUDE_PLUGIN_DATA;
  process.env.CLAUDE_PLUGIN_DATA = pluginDataDir;

  try {
    const stateDir = resolveStateDir(workspace);

    assert.equal(stateDir.startsWith(path.join(pluginDataDir, "state")), true);
    assert.match(path.basename(stateDir), /.+-[a-f0-9]{16}$/);
    assert.match(
      stateDir,
      new RegExp(`^${path.join(pluginDataDir, "state").replace(/[.*+?^${}()|[\]\\]/g, "\\$&")}`)
    );
  } finally {
    if (previousPluginDataDir == null) {
      delete process.env.CLAUDE_PLUGIN_DATA;
    } else {
      process.env.CLAUDE_PLUGIN_DATA = previousPluginDataDir;
    }
  }
});

test("saveState prunes dropped job artifacts when indexed jobs exceed the cap", () => {
  const workspace = makeTempDir();
  const stateFile = resolveStateFile(workspace);
  fs.mkdirSync(path.dirname(stateFile), { recursive: true });

  const jobs = Array.from({ length: 51 }, (_, index) => {
    const jobId = `job-${index}`;
    const updatedAt = new Date(Date.UTC(2026, 0, 1, 0, index, 0)).toISOString();
    const logFile = resolveJobLogFile(workspace, jobId);
    const jobFile = resolveJobFile(workspace, jobId);
    fs.writeFileSync(logFile, `log ${jobId}\n`, "utf8");
    fs.writeFileSync(jobFile, JSON.stringify({ id: jobId, status: "completed" }, null, 2), "utf8");
    return {
      id: jobId,
      status: "completed",
      logFile,
      updatedAt,
      createdAt: updatedAt
    };
  });

  fs.writeFileSync(
    stateFile,
    `${JSON.stringify(
      {
        version: 1,
        config: { stopReviewGate: false },
        jobs
      },
      null,
      2
    )}\n`,
    "utf8"
  );

  saveState(workspace, {
    version: 1,
    config: { stopReviewGate: false },
    jobs
  });

  const prunedJobFile = resolveJobFile(workspace, "job-0");
  const prunedLogFile = resolveJobLogFile(workspace, "job-0");
  const retainedJobFile = resolveJobFile(workspace, "job-50");
  const retainedLogFile = resolveJobLogFile(workspace, "job-50");
  const jobsDir = path.dirname(prunedJobFile);

  assert.equal(fs.existsSync(retainedJobFile), true);
  assert.equal(fs.existsSync(retainedLogFile), true);

  const savedState = JSON.parse(fs.readFileSync(stateFile, "utf8"));
  assert.equal(savedState.jobs.length, 50);
  assert.deepEqual(
    savedState.jobs.map((job) => job.id),
    Array.from({ length: 50 }, (_, index) => `job-${50 - index}`)
  );
  assert.deepEqual(
    fs.readdirSync(jobsDir).sort(),
    Array.from({ length: 50 }, (_, index) => `job-${index + 1}`)
      .flatMap((jobId) => [`${jobId}.json`, `${jobId}.log`])
      .sort()
  );
});
