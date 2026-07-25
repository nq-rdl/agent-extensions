// SPDX-License-Identifier: Apache-2.0

import fs from "node:fs";
import os from "node:os";
import path from "node:path";
import process from "node:process";
import { spawnSync } from "node:child_process";
import { fileURLToPath } from "node:url";

import { resolveStateDir } from "./state.mjs";
import { resolveWorkspaceRoot } from "./workspace.mjs";

const DEFECTS_DIR_NAME = "defects";
const SURFACED_FILE_NAME = "surfaced.json";
const MAX_DEFECTS = 20;
const STDERR_TAIL_LINES = 40;
const STDERR_TAIL_BYTES = 4000;
const MESSAGE_MAX_CHARS = 2000;
const VERSION_PROBE_TIMEOUT_MS = 2000;

// Flags whose values are safe to keep verbatim. Everything else is redacted:
// values can be absolute paths, prompt files, or free text.
const SAFE_VALUE_FLAGS = new Set([
  "--model",
  "--effort",
  "--job-id",
  "--scope",
  "--base",
  "--timeout-ms",
  "--poll-interval-ms"
]);

// Ids only ever originate from recordDefect's own template
// (`defect-<iso-with-dashes>-<random>`): letters, digits, hyphens. Anything
// else — including a path separator or `..` — is rejected before it can be
// joined into a filesystem path.
const DEFECT_ID_PATTERN = /^defect-[A-Za-z0-9-]+$/;

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

function splitFlag(token) {
  const index = token.indexOf("=");
  return index === -1 ? [token, null] : [token.slice(0, index), token.slice(index + 1)];
}

export function redactArgv(argv) {
  const tokens = (Array.isArray(argv) ? argv : []).map((value) => String(value));
  const out = [];
  let seenSubcommand = false;

  for (let index = 0; index < tokens.length; index += 1) {
    const token = tokens[index];

    if (token.startsWith("-")) {
      const [name, inlineValue] = splitFlag(token);
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

    if (!seenSubcommand) {
      out.push(token);
      seenSubcommand = true;
      continue;
    }

    out.push("<redacted>");
  }

  return out;
}

export function tailText(value) {
  const text = typeof value === "string" ? value : "";
  if (!text) {
    return "";
  }
  let tail = text.split("\n").slice(-STDERR_TAIL_LINES).join("\n");
  if (Buffer.byteLength(tail, "utf8") > STDERR_TAIL_BYTES) {
    tail = tail.slice(-STDERR_TAIL_BYTES);
  }
  return tail;
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
  const home = os.homedir();
  return home ? text.split(home).join("~") : text;
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

export function recordDefect(cwd, details = {}) {
  try {
    const dir = ensureDefectsDir(cwd);
    const recordedAt = new Date().toISOString();
    const id = `defect-${recordedAt.replace(/[:.]/g, "-")}-${Math.random().toString(36).slice(2, 8)}`;
    const marker = {
      id,
      recordedAt,
      surface: details.surface ?? "companion",
      argv: redactArgv(details.argv),
      exitCode: details.exitCode ?? 1,
      message: scrubHomeDir(String(details.message ?? "")).slice(0, MESSAGE_MAX_CHARS),
      stderrTail: tailText(scrubHomeDir(details.stderr)),
      jobId: details.jobId ?? null,
      threadId: details.threadId ?? null,
      environment: collectEnvironment(cwd),
      reportedAt: null,
      reportedUrl: null
    };

    const file = path.join(dir, `${id}.json`);
    fs.writeFileSync(file, `${JSON.stringify(marker, null, 2)}\n`, "utf8");
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
    fs.writeFileSync(file, `${JSON.stringify(marker, null, 2)}\n`, "utf8");
    return true;
  } catch {
    return false;
  }
}

function surfacedFile(cwd) {
  return path.join(resolveDefectsDir(cwd), SURFACED_FILE_NAME);
}

export function listSurfacedJobs(cwd) {
  try {
    const parsed = JSON.parse(fs.readFileSync(surfacedFile(cwd), "utf8"));
    return Array.isArray(parsed.jobIds) ? parsed.jobIds : [];
  } catch {
    return [];
  }
}

export function markJobSurfaced(cwd, jobId) {
  try {
    ensureDefectsDir(cwd);
    const jobIds = listSurfacedJobs(cwd);
    if (jobIds.includes(jobId)) {
      return true;
    }
    jobIds.push(jobId);
    fs.writeFileSync(
      surfacedFile(cwd),
      `${JSON.stringify({ jobIds: jobIds.slice(-100) }, null, 2)}\n`,
      "utf8"
    );
    return true;
  } catch {
    return false;
  }
}
