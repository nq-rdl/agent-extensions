// SPDX-License-Identifier: Apache-2.0
// SPDX-FileCopyrightText: 2026 nq-rdl

import fs from "node:fs";
import os from "node:os";
import path from "node:path";
import process from "node:process";
import test from "node:test";
import assert from "node:assert/strict";
import { spawn } from "node:child_process";

import { makeTempDir, run } from "./helpers.mjs";
import {
  resolveJobLogFile,
  resolveJobsDir,
  saveState,
  writeJobFile
} from "../../plugins/codex/scripts/lib/state.mjs";
import {
  homeCandidates,
  listDefects,
  listSurfacedJobs,
  listUnreportedDefects,
  markDefectReported,
  markJobSurfaced,
  markJobsSurfaced,
  readDefect,
  recordDefect,
  redactArgv,
  resolveDefectsDir,
  tailText
} from "../../plugins/codex/scripts/lib/defect-log.mjs";

const DEFECT_LOG_URL = new URL(
  "../../plugins/codex/scripts/lib/defect-log.mjs",
  import.meta.url
).href;

test("resolveDefectsDir is a sibling of the jobs dir, not a child", () => {
  const workspace = makeTempDir();
  const defectsDir = resolveDefectsDir(workspace);
  const jobsDir = resolveJobsDir(workspace);

  assert.equal(path.dirname(defectsDir), path.dirname(jobsDir));
  assert.equal(path.basename(defectsDir), "defects");
  assert.equal(defectsDir.startsWith(jobsDir), false, "must not nest under jobs/");
});

test("a marker survives job pruning that deletes every job", () => {
  const workspace = makeTempDir();
  const markerPath = recordDefect(workspace, { message: "boom" });
  assert.equal(
    path.dirname(markerPath),
    resolveDefectsDir(workspace),
    "recordDefect must return a path inside this workspace's defects dir"
  );

  // Give the pruner something to delete. saveState only unlinks job files for
  // jobs present in the *previous* state, and recordDefect writes no state.json
  // -- so without this seeding the pruning below is a no-op and the marker
  // would "survive" an operation that never ran.
  const jobFile = writeJobFile(workspace, "task-1", { id: "task-1" });
  const logFile = resolveJobLogFile(workspace, "task-1");
  fs.writeFileSync(logFile, "codex stdout\n", "utf8");
  saveState(workspace, { config: {}, jobs: [{ id: "task-1", status: "completed", logFile }] });
  assert.equal(fs.existsSync(jobFile), true, "precondition: the job file exists before pruning");

  // Simulate cleanupSessionJobs: save state with no jobs at all.
  saveState(workspace, { config: {}, jobs: [] });

  assert.equal(fs.existsSync(jobFile), false, "the job file must actually be pruned");
  assert.equal(fs.existsSync(logFile), false, "the job log must actually be pruned");
  assert.deepEqual(fs.readdirSync(resolveJobsDir(workspace)), [], "jobs/ must be empty after pruning");
  assert.equal(fs.existsSync(markerPath), true, "defect marker must outlive job pruning");
  assert.equal(listDefects(workspace).length, 1);
});

test("redactArgv keeps the subcommand and flag names but drops prompt text", () => {
  const redacted = redactArgv(["task", "refactor the billing module", "--write", "--model", "gpt-5.6-sol"]);

  assert.deepEqual(redacted, ["task", "<redacted>", "--write", "--model", "gpt-5.6-sol"]);
  assert.equal(redacted.includes("refactor the billing module"), false);
});

test("redactArgv redacts values of flags not on the safe list", () => {
  assert.deepEqual(redactArgv(["task", "--cwd", "/home/someone/secret-project"]), ["task", "--cwd", "<redacted>"]);
  assert.deepEqual(redactArgv(["status", "--job-id=task-abc"]), ["status", "--job-id=task-abc"]);
  assert.deepEqual(redactArgv(["transfer", "--source=/home/someone/x.jsonl"]), ["transfer", "--source=<redacted>"]);
  assert.deepEqual(redactArgv(["review", "--base", "feature/ACME-1234-billing"]), ["review", "--base", "<redacted>"]);
});

test("redactArgv redacts a single \"$ARGUMENTS\" blob that merely starts with a dash", () => {
  assert.deepEqual(
    redactArgv(["task", "--background write a migration plan, api key sk-live-abc123XYZ"]),
    ["task", "<redacted>"]
  );
  assert.deepEqual(
    redactArgv(["adversarial-review", "-- audit the ACME-Corp auth flow"]),
    ["adversarial-review", "<redacted>"]
  );
  assert.deepEqual(
    redactArgv(["adversarial-review", "-check that DB_PASSWORD=hunter2 is unused"]),
    ["adversarial-review", "<redacted>"]
  );
  assert.deepEqual(redactArgv(["/home/me/blob --evil"]), ["<redacted>"]);
});

test("redactArgv redacts a flag value that itself starts with a dash", () => {
  assert.deepEqual(
    redactArgv(["task", "--cwd", "-/home/alice/clients/acme"]),
    ["task", "--cwd", "<redacted>"]
  );
});

test("redactArgv stops trusting flags after the -- passthrough separator", () => {
  assert.deepEqual(
    redactArgv(["task", "--", "--model", "/home/me/secret"]),
    ["task", "--", "<redacted>", "<redacted>"]
  );
});

test("recordDefect never writes positional prompt text into the marker", () => {
  const workspace = makeTempDir();
  const secret = "PROPRIETARY-PROMPT-TEXT";
  const markerPath = recordDefect(workspace, { argv: ["task", secret], message: "failed" });

  assert.equal(fs.readFileSync(markerPath, "utf8").includes(secret), false);
});

test("tailText keeps only the last 40 lines", () => {
  const tail = tailText(Array.from({ length: 100 }, (_, i) => `line${i}`).join("\n"));

  assert.equal(tail.split("\n").length, 40);
  assert.equal(tail.split("\n")[0], "line60");
  assert.equal(tail.includes("line59"), false);
});

test("tailText caps the tail at 4 KB of UTF-8, not 4000 UTF-16 code units", () => {
  // STDERR_TAIL_BYTES is measured with Buffer.byteLength but a String.slice
  // cap counts UTF-16 code units: 4000 units is 8000 bytes of emoji or
  // Cyrillic and 12,000 bytes of CJK. Byte-slicing must also land on a
  // character boundary -- Buffer's decoder turns each stray continuation byte
  // into a 3-byte U+FFFD, pushing a mid-sequence tail back over the cap.
  for (const sample of ["a".repeat(20000), "漢".repeat(9000), "\u{1F600}".repeat(4000), "б".repeat(5000)]) {
    const tail = tailText(sample);
    const bytes = Buffer.byteLength(tail, "utf8");

    assert.ok(bytes <= 4000, `tail is ${bytes} bytes, over the 4000-byte cap`);
    // Guard the other direction: a cap that threw most of the tail away would
    // also satisfy the assertion above. CJK lands at 3999 (a 3-byte char
    // cannot fit in the last byte); everything else lands at exactly 4000.
    assert.ok(bytes > 3997, `expected a nearly-full tail, got ${bytes} bytes`);
    assert.equal(tail.includes("�"), false, "truncation must land on a character boundary");
    assert.equal(sample.endsWith(tail), true, "must keep the tail, not the head");
  }
});

test("tailText applies the 40-line cap before the 4 KB byte cap", () => {
  // 100 lines of 60 CJK chars: the 40-line slice alone is ~7.3 KB, so the byte
  // cap has to bite second and win.
  const wide = Array.from({ length: 100 }, (_, i) => `${"漢".repeat(60)}${i}`).join("\n");
  const tail = tailText(wide);

  assert.ok(Buffer.byteLength(tail, "utf8") <= 4000);
  assert.ok(tail.split("\n").length <= 40);
  assert.equal(wide.endsWith(tail), true);
  assert.equal(tail.includes("�"), false);
});

test("tailText leaves an under-cap tail byte-identical", () => {
  const short = "Error: boom\n  at frame";
  assert.equal(tailText(short), short);

  const exact = "a".repeat(4000);
  assert.equal(tailText(exact), exact, "a tail exactly at the cap must not be trimmed");

  assert.equal(tailText(`${"X".repeat(10000)}TAIL_MARKER`).endsWith("TAIL_MARKER"), true);

  const mixed = tailText("a漢\u{1F600}".repeat(9000));
  assert.ok(Buffer.byteLength(mixed, "utf8") <= 4000);
  assert.equal(mixed.includes("�"), false, "must not split a surrogate pair");
  assert.equal(JSON.parse(JSON.stringify(mixed)), mixed, "must round-trip through JSON");
});

test("recordDefect returns null instead of throwing when the dir cannot be written", () => {
  const workspace = makeTempDir();
  const defectsDir = resolveDefectsDir(workspace);
  fs.mkdirSync(path.dirname(defectsDir), { recursive: true });
  // Occupy the defects path with a FILE so mkdirSync must fail.
  fs.writeFileSync(defectsDir, "not a directory", "utf8");

  assert.equal(recordDefect(workspace, { message: "boom" }), null);
});

test("a marker write that fails mid-flight leaves no unparseable marker behind", { skip: process.platform === "win32" }, () => {
  const workspace = makeTempDir();
  const source = `import { recordDefect } from ${JSON.stringify(DEFECT_LOG_URL)};
recordDefect(${JSON.stringify(workspace)}, { message: "x".repeat(2000), stderr: "y".repeat(3000) });`;
  // ulimit -f makes the marker write fail partway, the same way ENOSPC does.
  run("bash", ["-c", `ulimit -f 1; exec ${JSON.stringify(process.execPath)} --input-type=module -e ${JSON.stringify(source)}`], { env: process.env });

  const dir = resolveDefectsDir(workspace);
  const markers = fs.existsSync(dir)
    ? fs.readdirSync(dir).filter((n) => n.startsWith("defect-") && n.endsWith(".json"))
    : [];
  assert.deepEqual(markers, [], "a failed write must not leave a marker that counts against MAX_DEFECTS");
});

test("pruning retains only the newest 20 markers", () => {
  const workspace = makeTempDir();
  for (let i = 0; i < 25; i += 1) {
    recordDefect(workspace, { message: `boom ${i}` });
  }

  // Assert identity, not just cardinality: pin which 20 survive (the newest,
  // boom 5..boom 24, newest first) so a reversed sort that pruned the newest
  // 20 instead of the oldest 5 would fail this test even though it still
  // leaves exactly 20 markers on disk.
  const retained = listDefects(workspace).map((marker) => marker.message);
  assert.deepEqual(retained, Array.from({ length: 20 }, (_, i) => `boom ${24 - i}`));
  for (let i = 0; i < 5; i += 1) {
    assert.equal(retained.includes(`boom ${i}`), false, `boom ${i} must be pruned`);
  }
});

test("marker order survives 25 writes inside a single millisecond", () => {
  const workspace = makeTempDir();

  // markerFiles sorts by *filename*, so the id -- not the wall clock -- has to
  // carry write order. Freezing the clock collapses all 25 markers into one
  // millisecond: without the sequence counter the random suffix decides the
  // order, and pruning discards an arbitrary five markers rather than the
  // oldest five.
  const realToISOString = Date.prototype.toISOString;
  Date.prototype.toISOString = () => "2026-07-27T12:00:00.000Z";
  try {
    for (let i = 0; i < 25; i += 1) {
      recordDefect(workspace, { message: `boom ${i}` });
    }
  } finally {
    Date.prototype.toISOString = realToISOString;
  }

  const retained = listDefects(workspace).map((marker) => marker.message);
  assert.deepEqual(retained, Array.from({ length: 20 }, (_, i) => `boom ${24 - i}`));
});

test("listUnreportedDefects excludes markers carrying reportedAt", () => {
  const workspace = makeTempDir();
  recordDefect(workspace, { message: "first" });
  const second = listDefects(workspace)[0];

  assert.equal(markDefectReported(workspace, second.id, { url: "https://example.test/1" }), true);

  assert.equal(listUnreportedDefects(workspace).length, 0);
  assert.equal(readDefect(workspace, second.id).reportedUrl, "https://example.test/1");
});

test("surfaced-job bookkeeping lives in defects/, keyed by job id", () => {
  const workspace = makeTempDir();

  assert.deepEqual(listSurfacedJobs(workspace), []);
  assert.equal(markJobSurfaced(workspace, "task-abc"), true);
  assert.deepEqual(listSurfacedJobs(workspace), ["task-abc"]);

  // Idempotent: marking twice must not duplicate.
  markJobSurfaced(workspace, "task-abc");
  assert.deepEqual(listSurfacedJobs(workspace), ["task-abc"]);
  assert.equal(fs.existsSync(path.join(resolveDefectsDir(workspace), "surfaced.json")), true);
});

test("an unreadable surfaced window is never rebuilt from empty", () => {
  const workspace = makeTempDir();
  const file = path.join(resolveDefectsDir(workspace), "surfaced.json");

  // 1. Torn read: writeFileSync's O_TRUNC instant, modelled as a zero-byte file.
  markJobsSurfaced(workspace, Array.from({ length: 100 }, (_, i) => `task-${i}`));
  fs.writeFileSync(file, "", "utf8");
  assert.equal(markJobSurfaced(workspace, "task-new"), false);
  assert.equal(fs.readFileSync(file, "utf8"), "", "an unreadable window must not be overwritten");

  // 2. Half-written prefix.
  fs.writeFileSync(file, '{\n  "jobIds": [\n    "task-0",\n    "task-', "utf8");
  const before = fs.readFileSync(file, "utf8");
  assert.equal(markJobSurfaced(workspace, "task-new"), false);
  assert.equal(fs.readFileSync(file, "utf8"), before);

  // 3. The reader stays lossy and non-throwing -- guards against a future
  //    contributor making listSurfacedJobs rethrow, which would unwind through
  //    the hook and silence its whole payload.
  assert.doesNotThrow(() => listSurfacedJobs(workspace));
  assert.deepEqual(listSurfacedJobs(workspace), []);

  // 4. ENOENT is the documented recovery: a clean empty window that self-heals.
  fs.unlinkSync(file);
  assert.equal(markJobSurfaced(workspace, "task-new"), true);
  assert.deepEqual(listSurfacedJobs(workspace), ["task-new"]);
});

test("markJobsSurfaced merges in one write and honours the 100-id window", () => {
  const workspace = makeTempDir();

  assert.equal(markJobsSurfaced(workspace, ["a", "b", "c"]), true);
  assert.deepEqual(listSurfacedJobs(workspace), ["a", "b", "c"]);

  assert.equal(markJobsSurfaced(workspace, ["b", "d"]), true);
  assert.deepEqual(listSurfacedJobs(workspace), ["a", "b", "c", "d"]);

  const wide = makeTempDir();
  markJobsSurfaced(wide, Array.from({ length: 120 }, (_, i) => `job-${i}`));
  const window = listSurfacedJobs(wide);
  assert.equal(window.length, 100);
  assert.equal(window[0], "job-20");
});

test("concurrent hook processes do not lose each other's marks", async () => {
  const workspace = makeTempDir();
  // Retry on `false`. Under 8-way contention acquireSurfacedLock occasionally
  // burns its whole retry budget and *declines* to write -- that is the
  // documented noisy failure, not a lost mark, and a caller is expected to see
  // it. Retrying isolates the invariant this test is actually for: a mark that
  // was accepted must never be clobbered by another process's
  // read-modify-write. Measured over 10 runs: 80/80 every time as written, and
  // 15-23/80 with the lock removed -- so the retry costs the test nothing.
  const source = `import(${JSON.stringify(DEFECT_LOG_URL)}).then((m) => {
    for (let i = 0; i < 10; i += 1) {
      for (let attempt = 0; attempt < 20; attempt += 1) {
        if (m.markJobSurfaced(process.argv[1], process.argv[2] + "-" + i)) break;
      }
    }
  })`;

  await Promise.all(
    Array.from(
      { length: 8 },
      (_unused, worker) =>
        new Promise((resolve, reject) => {
          const child = spawn(process.execPath, ["-e", source, workspace, `worker${worker}`], {
            stdio: "ignore"
          });
          child.on("error", reject);
          child.on("exit", resolve);
        })
    )
  );

  assert.equal(listSurfacedJobs(workspace).length, 80);
});

test("resolveDefectsDir never throws, even for a malformed cwd", () => {
  // resolveStateDir (via resolveWorkspaceRoot -> path operations) throws
  // TypeError for a non-string, non-nullish cwd. Every exported function here
  // must be incapable of throwing, including this one.
  for (const badCwd of [123, {}, []]) {
    assert.doesNotThrow(() => resolveDefectsDir(badCwd));
    assert.equal(typeof resolveDefectsDir(badCwd), "string");
  }
});

test("markDefectReported rejects ids that don't match recordDefect's shape", () => {
  const workspace = makeTempDir();
  recordDefect(workspace, { message: "first" });

  assert.equal(
    markDefectReported(workspace, "../../../../etc/passwd", { url: "https://example.test" }),
    false
  );
  assert.equal(
    markDefectReported(workspace, "../defects/../../secret", { url: "https://example.test" }),
    false
  );
  assert.equal(markDefectReported(workspace, "not-a-defect-id-at-all", { url: "https://example.test" }), false);
  assert.equal(markDefectReported(workspace, 123, { url: "https://example.test" }), false);

  // The four negatives above are all rejected by the `defect-` prefix (or the
  // typeof guard), so none of them exercises the `[A-Za-z0-9-]` class that is
  // what actually blocks traversal. The two below carry the prefix and are
  // rejected only by that class, so each pins an observable side effect.

  // 1. Escape defects/ entirely. `defect-..` is a literal segment, so it costs
  //    one `..` to pop it and one more to leave defects/.
  const stateDir = path.dirname(resolveDefectsDir(workspace));
  const canary = path.join(stateDir, "canary.json");
  fs.writeFileSync(canary, `${JSON.stringify({ untouched: true })}\n`, "utf8");
  assert.equal(
    markDefectReported(workspace, "defect-../../../canary", { url: "https://example.test" }),
    false
  );
  assert.deepEqual(JSON.parse(fs.readFileSync(canary, "utf8")), { untouched: true });

  // 2. A separator that normalizes straight back onto a real marker. The target
  //    exists, so a missing file cannot mask a loosened pattern.
  const real = listDefects(workspace)[0];
  assert.equal(
    markDefectReported(workspace, `defect-x/../${real.id}`, { url: "https://example.test" }),
    false
  );
  assert.equal(readDefect(workspace, real.id).reportedAt, null);

  // A real id, generated by recordDefect itself, must still work.
  assert.equal(markDefectReported(workspace, real.id, { url: "https://example.test" }), true);
});

test("recordDefect scrubs the user's home directory out of message and stderrTail", () => {
  const workspace = makeTempDir();
  const home = os.homedir();
  const markerPath = recordDefect(workspace, {
    message: `boom at ${home}/secret-project/index.js`,
    stderr: `Error: Claude session file not found: ${home}/.claude/projects/foo/bar.jsonl\n    at ${home}/plugins/codex/scripts/lib/claude-session-transfer.mjs:37:11`
  });

  const marker = JSON.parse(fs.readFileSync(markerPath, "utf8"));
  assert.equal(marker.message.includes(home), false);
  assert.equal(marker.message, "boom at ~/secret-project/index.js");
  assert.equal(marker.stderrTail.includes(home), false);
  assert.match(marker.stderrTail, /^Error: Claude session file not found: ~\/\.claude\/projects\/foo\/bar\.jsonl/);
  assert.match(marker.stderrTail, /at ~\/plugins\/codex\/scripts\/lib\/claude-session-transfer\.mjs:37:11$/);
});

test("recordDefect scrubs the user's home directory out of argv", () => {
  const workspace = makeTempDir();
  const home = os.homedir();
  // redactArgv already drops every unsafe *value*, so the only argv slots that
  // reach the marker verbatim are the subcommand token, the flag names, and the
  // safe-listed values. --job-id is on that safe list, so its value is what the
  // home scrub has to catch -- argv is otherwise the one field that escapes the
  // scrub message and stderrTail get.
  const markerPath = recordDefect(workspace, {
    argv: ["status", "--job-id", `${home}/clients/ACME/notes.md`, "--model", "gpt-5.6-sol"],
    message: "Unknown subcommand"
  });
  const raw = fs.readFileSync(markerPath, "utf8");
  const marker = JSON.parse(raw);
  assert.deepEqual(marker.argv, ["status", "--job-id", "~/clients/ACME/notes.md", "--model", "gpt-5.6-sol"]);
  assert.equal(raw.includes(home), false, "no marker field may carry the raw home path");
});

test("homeCandidates never yields a filesystem root", () => {
  const entries = homeCandidates();
  for (const entry of entries) {
    assert.equal(typeof entry, "string");
    assert.notEqual(entry, "");
    assert.notEqual(entry, "/");
    assert.equal(/^[A-Za-z]:[/\\]?$/.test(entry), false, `${entry} is a drive root`);
  }
  assert.equal(
    entries.every((v, i, a) => i === 0 || a[i - 1].length >= v.length),
    true,
    "candidates must be longest-first so a short one never eats a long one's prefix"
  );
});

test("homeScrubbed is true on a normal run", () => {
  const workspace = makeTempDir();
  const marker = JSON.parse(fs.readFileSync(recordDefect(workspace, { message: "boom" }), "utf8"));
  assert.equal(marker.homeScrubbed, true);
});

test("recordDefect still scrubs home when HOME is set but empty", { skip: process.platform === "win32" }, () => {
  const workspace = makeTempDir();
  const probeDir = makeTempDir();
  const probe = path.join(probeDir, "probe.mjs");
  fs.writeFileSync(
    probe,
    `import { recordDefect } from ${JSON.stringify(DEFECT_LOG_URL)};
import os from "node:os";
process.stdout.write(String(recordDefect(${JSON.stringify(workspace)}, { message: \`boom at \${os.userInfo().homedir}/secret/index.js\` })));`,
    "utf8"
  );

  const result = run(process.execPath, [probe], { env: { ...process.env, HOME: "" } });
  const marker = JSON.parse(fs.readFileSync(result.stdout.trim(), "utf8"));

  assert.equal(marker.message.includes(os.userInfo().homedir), false);
  assert.equal(marker.message, "boom at ~/secret/index.js");
  assert.equal(marker.homeScrubbed, true);
});

test("HOME=/ does not shred every path separator", { skip: process.platform === "win32" }, () => {
  const workspace = makeTempDir();
  const probeDir = makeTempDir();
  const probe = path.join(probeDir, "probe-root-home.mjs");
  const message = "Error: ENOENT /usr/lib/node_modules/codex/bin.js";
  fs.writeFileSync(
    probe,
    `import { recordDefect } from ${JSON.stringify(DEFECT_LOG_URL)};
process.stdout.write(String(recordDefect(${JSON.stringify(workspace)}, { message: ${JSON.stringify(message)} })));`,
    "utf8"
  );

  const result = run(process.execPath, [probe], { env: { ...process.env, HOME: "/" } });
  const marker = JSON.parse(fs.readFileSync(result.stdout.trim(), "utf8"));

  assert.equal(marker.message, message, "a root home must not turn every separator into ~");
  assert.equal(marker.message.includes("~"), false);
});
