// SPDX-License-Identifier: Apache-2.0
// SPDX-FileCopyrightText: 2026 nq-rdl

import fs from "node:fs";
import os from "node:os";
import path from "node:path";
import process from "node:process";
import { spawnSync } from "node:child_process";
import { fileURLToPath, pathToFileURL } from "node:url";

import { resolveStateDir } from "./state.mjs";
import { resolveWorkspaceRoot } from "./workspace.mjs";

const DEFECTS_DIR_NAME = "defects";
const SURFACED_FILE_NAME = "surfaced.json";
const MAX_DEFECTS = 20;
const STDERR_TAIL_LINES = 40;
const STDERR_TAIL_BYTES = 4000;
const MESSAGE_MAX_CHARS = 2000;
const VERSION_PROBE_TIMEOUT_MS = 2000;

// Width of the marker id's intra-millisecond counter. Fixed width so it
// still sorts lexicographically alongside the timestamp.
const SEQUENCE_WIDTH = 4;

const SURFACED_LOCK_NAME = "surfaced.lock";
const SURFACED_MAX_IDS = 100;
const SURFACED_LOCK_RETRY_MS = 10;
// A wall-clock deadline, not an attempt count. An attempt budget is not a time
// budget: the hand-off path below retries without sleeping, so on a loaded
// machine a burst of lock churn burns every attempt in microseconds and the
// caller declines a write it had ample time to make. Measured with a 50-attempt
// budget under a parallel test run: 26 of 80 marks declined. Well inside the
// hooks' 5s timeout.
const SURFACED_LOCK_TIMEOUT_MS = 2000;
const SURFACED_LOCK_STALE_MS = 30000;

// Flags whose values are bounded and non-user-authored (enumerations,
// numbers, generated ids). Everything else is redacted: values can be
// absolute paths, prompt files, or free text. --base is deliberately not
// here — a git ref is arbitrary user text and branch names carry client
// names and ticket ids.
const SAFE_VALUE_FLAGS = new Set([
  "--model",
  "--effort",
  "--job-id",
  "--scope",
  "--timeout-ms",
  "--poll-interval-ms"
]);

// Ids only ever originate from recordDefect's own template
// (`defect-<iso-with-dashes>-<sequence>-<pid>-<random>`): letters, digits,
// hyphens. Anything else — including a path separator or `..` — is
// rejected before it can be joined into a filesystem path.
const DEFECT_ID_PATTERN = /^defect-[A-Za-z0-9-]+$/;

// A token is only treated as a flag if it *looks* like one (`-C`, `--write`,
// `--model=x`). Skills forward the user's whole "$ARGUMENTS" as a single
// token, and documented usage puts flags first — so that token routinely
// starts with `-` while carrying free text. Anything that is not
// flag-shaped falls through to the positional path and is redacted.
const FLAG_PATTERN = /^--?[A-Za-z][A-Za-z0-9-]*$/;

// Same idea for the leading subcommand slot: only a bare subcommand token is
// kept verbatim.
const SUBCOMMAND_PATTERN = /^[a-z][a-z0-9-]*$/;

export function resolveDefectsDir(cwd) {
  // resolveStateDir (via resolveWorkspaceRoot) throws for a non-string,
  // non-nullish cwd. Every other export in this module absorbs that behind a
  // try/catch; this is the one export those functions call unguarded, so it
  // must degrade to a usable fallback instead of throwing itself.
  try {
    return path.join(resolveStateDir(cwd), DEFECTS_DIR_NAME);
  } catch {
    try {
      return path.join(resolveStateDir(process.cwd()), DEFECTS_DIR_NAME);
    } catch {
      return path.join(os.tmpdir(), "codex-companion", DEFECTS_DIR_NAME);
    }
  }
}

function ensureDefectsDir(cwd) {
  const dir = resolveDefectsDir(cwd);
  fs.mkdirSync(dir, { recursive: true });
  return dir;
}

// writeFileSync opens with O_TRUNC and then drains the buffer in a loop, so a
// mid-flight failure (ENOSPC is the realistic one) leaves a truncated file
// behind. Here that is worse than a lost write: markerFiles filters on the
// `defect-`/`.json` name alone, so an unparseable marker is invisible to every
// reader yet still charged against MAX_DEFECTS, and is only reclaimed once
// MAX_DEFECTS strictly newer markers exist. It also lets a concurrent reader
// observe a zero-byte surfaced.json. Write a sibling temp and rename into
// place so a file is either whole or absent. The `.tmp` suffix keeps the temp
// out of markerFiles; the pid keeps concurrent writers off each other's temp.
function writeFileAtomic(file, contents) {
  const temp = `${file}.${process.pid}.tmp`;
  try {
    fs.writeFileSync(temp, contents, "utf8");
    fs.renameSync(temp, file);
  } catch (error) {
    try {
      fs.unlinkSync(temp);
    } catch {
      // Nothing left to reclaim.
    }
    throw error;
  }
}

function splitFlag(token) {
  const index = token.indexOf("=");
  return index === -1 ? [token, null] : [token.slice(0, index), token.slice(index + 1)];
}

export function redactArgv(argv) {
  const tokens = (Array.isArray(argv) ? argv : []).map((value) => String(value));
  const out = [];
  let seenSubcommand = false;
  let passthrough = false;

  for (let index = 0; index < tokens.length; index += 1) {
    const token = tokens[index];

    // `--` ends flag parsing in parseArgs; everything after it is user text.
    if (!passthrough && token === "--") {
      out.push("--");
      passthrough = true;
      continue;
    }

    const [name, inlineValue] = splitFlag(token);
    if (!passthrough && FLAG_PATTERN.test(name)) {
      if (inlineValue !== null) {
        out.push(SAFE_VALUE_FLAGS.has(name) ? `${name}=${inlineValue}` : `${name}=<redacted>`);
        continue;
      }
      out.push(name);
      const next = tokens[index + 1];
      if (next !== undefined && !next.startsWith("-")) {
        out.push(SAFE_VALUE_FLAGS.has(name) ? next : "<redacted>");
        index += 1;
      }
      continue;
    }

    if (!passthrough && !seenSubcommand) {
      seenSubcommand = true;
      out.push(SUBCOMMAND_PATTERN.test(token) ? token : "<redacted>");
      continue;
    }

    out.push("<redacted>");
  }

  return out;
}

// STDERR_TAIL_BYTES is a byte budget, but String.slice counts UTF-16 code
// units — slicing by it keeps 3x the cap for CJK stderr (4000 chars =
// 12,000 bytes) and 2x for Cyrillic or emoji. Trim the UTF-8 buffer
// instead, then walk forward off any continuation byte so the kept tail
// starts on a lead byte and never decodes to a replacement char (each
// stray continuation byte would become a 3-byte U+FFFD and push the result
// back over the cap).
function tailBytes(text) {
  const buffer = Buffer.from(text, "utf8");
  if (buffer.length <= STDERR_TAIL_BYTES) {
    return text;
  }
  let start = buffer.length - STDERR_TAIL_BYTES;
  while (start < buffer.length && (buffer[start] & 0xc0) === 0x80) {
    start += 1;
  }
  return buffer.toString("utf8", start);
}

export function tailText(value) {
  const text = typeof value === "string" ? value : "";
  if (!text) {
    return "";
  }
  return tailBytes(text.split("\n").slice(-STDERR_TAIL_LINES).join("\n"));
}

// A filesystem root (`/`, `C:\`) as "home" would turn every path separator in
// the text into `~`, shredding the diagnostic instead of anonymising it.
function isScrubbableHome(candidate) {
  const normalised = candidate.replace(/\\/g, "/").replace(/\/+$/, "");
  return normalised !== "" && !/^[A-Za-z]:$/.test(normalised);
}

// Every spelling of the home directory worth scrubbing. A single literal
// os.homedir() fails open three ways: HOME set-but-empty (containers,
// systemd units, CI runners) makes it return "" and scrub nothing; Node
// resolves symlinks when loading modules, so a symlinked home renders as its
// realpath in stack frames; and on Windows it is `C:\Users\alice` while an
// ESM frame is `file:///C:/Users/alice/...` — zero overlap.
export function homeCandidates() {
  const roots = [];
  const addRoot = (value) => {
    if (typeof value === "string" && value && path.isAbsolute(value) && isScrubbableHome(value)) {
      roots.push(value);
    }
  };
  addRoot(os.homedir());
  try {
    // Reads the password database rather than HOME, so this still resolves
    // when HOME is set but empty and os.homedir() is "".
    addRoot(os.userInfo().homedir);
  } catch {
    // No passwd entry for the effective uid; other candidates still apply.
  }

  const spellings = new Set();
  for (const root of roots) {
    let real = null;
    try {
      real = fs.realpathSync(root);
    } catch {
      // Home may not exist on disk; the literal spelling still matters.
    }
    for (const form of [root, real]) {
      if (!form || !isScrubbableHome(form)) {
        continue;
      }
      spellings.add(form);
      spellings.add(form.replace(/\\/g, "/"));
      try {
        // file:// frames: `C:\Users\Alice Smith` -> `/C:/Users/Alice%20Smith`.
        spellings.add(pathToFileURL(form).pathname);
      } catch {
        // Not URL-representable; the literal spellings still apply.
      }
    }
  }

  // Longest first so a shorter candidate never eats the prefix of a longer one.
  return [...spellings].sort((a, b) => b.length - a.length);
}

// Conservative by design: only the user's home directory is scrubbed, not
// every absolute path. Plugin-relative paths in a stack trace are the useful
// part of the diagnostic; the home directory name is the part that leaks who
// the user is once a marker is attached to a public GitHub issue.
function scrubHomeDir(value) {
  const text = typeof value === "string" ? value : "";
  if (!text) {
    return text;
  }
  let scrubbed = text;
  for (const home of homeCandidates()) {
    scrubbed = scrubbed.split(home).join("~");
  }
  return scrubbed;
}

function probeVersion(command, args) {
  try {
    const result = spawnSync(command, args, {
      encoding: "utf8",
      timeout: VERSION_PROBE_TIMEOUT_MS,
      windowsHide: true
    });
    if (result.status !== 0) {
      return null;
    }
    return String(result.stdout ?? "").trim().split("\n")[0] || null;
  } catch {
    return null;
  }
}

// Read the plugin's own shipped manifest rather than the repo VERSION file, so
// this resolves in an installed plugin cache as well as in-repo.
function readPluginVersion() {
  try {
    const manifest = path.resolve(
      path.dirname(fileURLToPath(import.meta.url)),
      "..",
      "..",
      ".claude-plugin",
      "plugin.json"
    );
    return JSON.parse(fs.readFileSync(manifest, "utf8")).version ?? null;
  } catch {
    return null;
  }
}

function collectEnvironment(cwd) {
  let repo = null;
  let isGitRepo = false;
  try {
    const workspaceRoot = resolveWorkspaceRoot(cwd);
    repo = path.basename(workspaceRoot) || null;
    isGitRepo = fs.existsSync(path.join(workspaceRoot, ".git"));
  } catch {
    repo = null;
  }

  return {
    node: process.versions.node,
    codex: probeVersion("codex", ["--version"]),
    plugin: readPluginVersion(),
    platform: process.platform,
    release: os.release(),
    // Basename only — never the absolute path.
    repo,
    isGitRepo
  };
}

function markerFiles(dir) {
  return fs
    .readdirSync(dir)
    .filter((name) => name.startsWith("defect-") && name.endsWith(".json"))
    .sort()
    .reverse();
}

function pruneDefects(dir) {
  try {
    for (const stale of markerFiles(dir).slice(MAX_DEFECTS)) {
      for (const candidate of [stale, stale.replace(/\.json$/, ".md")]) {
        try {
          fs.unlinkSync(path.join(dir, candidate));
        } catch {
          // A missing companion report is fine.
        }
      }
    }
  } catch {
    // Pruning is opportunistic.
  }
}

// Intra-millisecond tiebreak. markerFiles sorts by *filename*, so
// newest-first ordering — and the pruning that rides on it — is only as
// precise as the id's millisecond timestamp: two markers written inside the
// same millisecond would otherwise be ordered by their random suffix,
// letting pruning discard the newer one. A fixed-width counter, reset
// whenever the millisecond changes, restores write order within a process.
// The pid segment removes cross-process id collisions — rename (like the
// plain write before it) replaces an existing target silently, so two
// processes hitting the same millisecond *and* the same random suffix would
// destroy a marker with no error. Both segments go after the fixed-width
// ISO timestamp so the lexicographic name sort stays chronological, and the
// counter goes before the pid so within-process order wins.
let lastStamp = "";
let sequence = 0;

function nextDefectId(recordedAt) {
  const stamp = recordedAt.replace(/[:.]/g, "-");
  if (stamp === lastStamp) {
    sequence += 1;
  } else {
    lastStamp = stamp;
    sequence = 0;
  }
  const ordinal = String(sequence).padStart(SEQUENCE_WIDTH, "0");
  return `defect-${stamp}-${ordinal}-${process.pid.toString(36)}-${Math.random()
    .toString(36)
    .slice(2, 8)}`;
}

export function recordDefect(cwd, details = {}) {
  try {
    const dir = ensureDefectsDir(cwd);
    const recordedAt = new Date().toISOString();
    const id = nextDefectId(recordedAt);
    const marker = {
      id,
      recordedAt,
      surface: details.surface ?? "companion",
      // Redaction and home-scrubbing are orthogonal: redactArgv drops unsafe
      // *values*, scrubHomeDir sanitises what survives — the subcommand token
      // and the safe-listed values. Without this, argv is the one field that
      // escapes the scrub that message and stderrTail get below.
      argv: redactArgv(details.argv).map((token) => scrubHomeDir(token)),
      exitCode: details.exitCode ?? 1,
      message: scrubHomeDir(String(details.message ?? "")).slice(0, MESSAGE_MAX_CHARS),
      stderrTail: tailText(scrubHomeDir(details.stderr)),
      // false when no usable home could be resolved (HOME empty and no passwd
      // entry): message/stderrTail may still carry the username, so the
      // reporting surface must not publish this marker unreviewed.
      homeScrubbed: homeCandidates().length > 0,
      jobId: details.jobId ?? null,
      threadId: details.threadId ?? null,
      environment: collectEnvironment(cwd),
      reportedAt: null,
      reportedUrl: null
    };

    const file = path.join(dir, `${id}.json`);
    writeFileAtomic(file, `${JSON.stringify(marker, null, 2)}\n`);
    pruneDefects(dir);
    return file;
  } catch {
    // A reporter that throws while reporting a failure makes things worse.
    return null;
  }
}

export function listDefects(cwd) {
  try {
    const dir = resolveDefectsDir(cwd);
    return markerFiles(dir)
      .map((name) => {
        try {
          return JSON.parse(fs.readFileSync(path.join(dir, name), "utf8"));
        } catch {
          return null;
        }
      })
      .filter(Boolean);
  } catch {
    return [];
  }
}

export function listUnreportedDefects(cwd) {
  return listDefects(cwd).filter((marker) => !marker.reportedAt);
}

export function readDefect(cwd, id) {
  return listDefects(cwd).find((marker) => marker.id === id) ?? null;
}

export function markDefectReported(cwd, id, { url = null } = {}) {
  try {
    if (typeof id !== "string" || !DEFECT_ID_PATTERN.test(id)) {
      // Defense-in-depth: id is caller-supplied and gets joined into a path.
      // Reject anything that isn't the shape recordDefect generates (only
      // letters, digits, hyphens) before it can escape defects/.
      return false;
    }
    const dir = resolveDefectsDir(cwd);
    const file = path.join(dir, `${id}.json`);
    const marker = JSON.parse(fs.readFileSync(file, "utf8"));
    marker.reportedAt = new Date().toISOString();
    marker.reportedUrl = url;
    writeFileAtomic(file, `${JSON.stringify(marker, null, 2)}\n`);
    return true;
  } catch {
    return false;
  }
}

function surfacedFile(cwd) {
  return path.join(resolveDefectsDir(cwd), SURFACED_FILE_NAME);
}

function surfacedLockDir(cwd) {
  return path.join(resolveDefectsDir(cwd), SURFACED_LOCK_NAME);
}

// Blocking sleep with no dependency and no busy-wait. Every caller is a
// short-lived hook process with nothing else on the event loop.
function sleepMs(ms) {
  Atomics.wait(new Int32Array(new SharedArrayBuffer(4)), 0, 0, ms);
}

// mkdir is the stdlib's atomic test-and-set: exactly one process can create a
// directory. The lock matters because this file is rewritten by every hook
// process — SessionStart, SubagentStop and PostToolUse all fire it, so
// parallel subagents routinely interleave. Unlocked, read -> push -> write
// silently drops marks (measured: 59 of 80 across 8 processes), and a dropped
// mark re-announces an advisory the user has already been shown.
function acquireSurfacedLock(cwd) {
  const lock = surfacedLockDir(cwd);
  const deadline = Date.now() + SURFACED_LOCK_TIMEOUT_MS;
  for (;;) {
    try {
      fs.mkdirSync(lock);
      return lock;
    } catch (error) {
      if (error?.code !== "EEXIST") {
        return null;
      }
    }
    if (Date.now() >= deadline) {
      return null;
    }
    try {
      // A hook killed mid-update (the hooks run under a 5s timeout) would
      // otherwise wedge the window permanently.
      if (Date.now() - fs.statSync(lock).mtimeMs > SURFACED_LOCK_STALE_MS) {
        fs.rmdirSync(lock);
        continue;
      }
    } catch {
      // The holder released it between the mkdir and the stat; retry at once.
      continue;
    }
    // Jittered so N waiters woken by the same release do not all re-mkdir on
    // the same tick and starve each other for the whole budget.
    sleepMs(1 + Math.floor(Math.random() * SURFACED_LOCK_RETRY_MS));
  }
}

function releaseSurfacedLock(lock) {
  try {
    fs.rmdirSync(lock);
  } catch {
    // Already broken as stale by another process — nothing to undo.
  }
}

// Reading the window fails in two ways that need opposite handling. ENOENT is
// a genuinely empty window. Anything else is an *unknown* one: a concurrent
// writer or a partial write can leave a zero-byte or half-written file and
// JSON.parse throws on it. Collapsing that to [] is only safe for a reader;
// a read-modify-write would rebuild the file from [] and drop every id
// already recorded.
function readSurfacedWindow(cwd) {
  try {
    const parsed = JSON.parse(fs.readFileSync(surfacedFile(cwd), "utf8"));
    return { known: true, jobIds: Array.isArray(parsed?.jobIds) ? parsed.jobIds : [] };
  } catch (error) {
    return { known: error?.code === "ENOENT", jobIds: [] };
  }
}

export function listSurfacedJobs(cwd) {
  // Lossy on purpose, and non-throwing like every other export here: a reader
  // that mistakes an unknown window for an empty one costs one duplicate
  // nudge, which is strictly better than a hook that throws mid-turn.
  return readSurfacedWindow(cwd).jobIds;
}

function writeSurfacedJobs(cwd, jobIds) {
  writeFileAtomic(surfacedFile(cwd), `${JSON.stringify({ jobIds }, null, 2)}\n`);
}

export function markJobSurfaced(cwd, jobId) {
  return markJobsSurfaced(cwd, [jobId]);
}

// Batched: a cold start with N failed jobs takes one lock and one write, not
// N. This is the ONLY write path for surfaced.json.
export function markJobsSurfaced(cwd, jobIds) {
  const pending = (Array.isArray(jobIds) ? jobIds : [jobIds]).filter(
    (jobId) => typeof jobId === "string" && jobId !== ""
  );
  if (pending.length === 0) {
    return true;
  }

  let lock = null;
  try {
    ensureDefectsDir(cwd);
    lock = acquireSurfacedLock(cwd);
    if (lock === null) {
      // Re-announcing an advisory is noise; rewriting the window from a stale
      // snapshot loses notifications outright. Prefer the noisy failure.
      return false;
    }

    const { known, jobIds: existing } = readSurfacedWindow(cwd);
    if (!known) {
      // Never rebuild the file from a window we could not read: that is how a
      // 100-id window becomes a 1-id one and every still-failed job gets
      // re-announced. A file that stays unreadable is recovered by deleting
      // it — ENOENT is a clean empty window.
      return false;
    }

    const seen = new Set(existing);
    const added = [];
    for (const jobId of pending) {
      if (seen.has(jobId)) {
        continue;
      }
      seen.add(jobId);
      added.push(jobId);
    }
    if (added.length === 0) {
      return true;
    }

    writeSurfacedJobs(cwd, [...existing, ...added].slice(-SURFACED_MAX_IDS));
    return true;
  } catch {
    return false;
  } finally {
    if (lock !== null) {
      releaseSurfacedLock(lock);
    }
  }
}
