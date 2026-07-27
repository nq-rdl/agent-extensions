#!/usr/bin/env node
// SPDX-License-Identifier: Apache-2.0
// SPDX-FileCopyrightText: 2026 nq-rdl

// Advisory hook. Surfaces two things Claude Code would otherwise never see:
// unreported defect markers (reportable) and failed jobs (not reportable).
// Must never block a turn, fail a session, or write to state.json.

import fs from "node:fs";
import process from "node:process";

import { classifyDefect } from "./lib/defect-classify.mjs";
import { listSurfacedJobs, listUnreportedDefects, markJobsSurfaced } from "./lib/defect-log.mjs";
import { loadState } from "./lib/state.mjs";

const COMPANION_MARKER = "codex-companion.mjs";
// A failed job's summary is firstMeaningfulLine(rawOutput) — Codex-side text
// with no length bound — so cap it here the way the companion caps its own.
const DETAIL_MAX_CHARS = 200;
// additionalContext over ~10k chars is spilled to a file and replaced by a
// preview, so a cold start against a full 50-job state must not emit one line
// per job. The remainder keep their unsurfaced state and return on a later turn.
const MAX_FAILED_JOB_LINES = 5;

// Mirrors codex-companion.mjs's shorten(): collapse whitespace, ellipsis.
function shorten(text, limit) {
  const normalized = String(text ?? "").trim().replace(/\s+/g, " ");
  if (normalized.length <= limit) {
    return normalized;
  }
  return `${normalized.slice(0, limit - 3)}...`;
}

function readHookInput() {
  try {
    const raw = fs.readFileSync(0, "utf8").trim();
    return raw ? JSON.parse(raw) : {};
  } catch {
    return {};
  }
}

// PostToolUse fires on every Bash call; only codex-companion invocations are ours.
function isRelevant(input) {
  if (input.hook_event_name !== "PostToolUse") {
    return true;
  }
  return String(input.tool_input?.command ?? "").includes(COMPANION_MARKER);
}

// recordDefect fires on every companion throw, so the log holds benign usage
// errors too — a flag typo, a missing Git install. Those stay on disk for
// `codex-defects.mjs list`, but must never open an issue-filing workflow, so
// the nudge is gated on the classifier. "needs-cross-check" (auth) stays in:
// settling it needs a `setup` probe this hook must not spawn on every fire,
// so the skill makes that call.
function defectLines(cwd) {
  const markers = listUnreportedDefects(cwd).filter(
    (marker) => classifyDefect(marker).verdict !== "not-a-defect"
  );
  if (markers.length === 0) {
    return [];
  }
  const newest = markers[0];
  const extra = markers.length > 1 ? ` (${markers.length - 1} older also unreported)` : "";
  return [
    `Codex plugin defect recorded: ${newest.id}${extra} — "${newest.message}". ` +
      "Run /codex:report-defect to review the evidence and decide whether to file it against " +
      "nq-rdl/agent-extensions. Do not file anything without showing the user the draft first."
  ];
}

// Returns the lines to emit plus the ids they name. Marking deliberately does
// not happen here: there is no un-surface path, so an id must not be committed
// until its advisory has actually reached Claude Code (see main).
function failedJobLines(cwd) {
  let jobs = [];
  try {
    jobs = loadState(cwd).jobs ?? [];
  } catch {
    return { lines: [], jobIds: [] };
  }

  const surfaced = new Set(listSurfacedJobs(cwd));
  // state.mjs stores jobs newest-first, so the head of pending is the newest.
  const pending = jobs.filter((job) => job.status === "failed" && !surfaced.has(job.id));
  const lines = [];
  const jobIds = [];

  for (const job of pending.slice(0, MAX_FAILED_JOB_LINES)) {
    const detail = shorten(job.summary ?? job.errorMessage, DETAIL_MAX_CHARS) || "no detail recorded";
    lines.push(
      `Codex job ${job.id} failed and was never surfaced: "${detail}". ` +
        `See /codex:result ${job.id}. This is a Codex-side or environment failure, not a plugin ` +
        "defect — tell the user plainly and do not offer to file an issue."
    );
    jobIds.push(job.id);
  }

  const remaining = pending.length - jobIds.length;
  if (remaining > 0) {
    lines.push(
      `${remaining} older failed Codex job(s) are also unsurfaced; they follow on a later turn.`
    );
  }

  return { lines, jobIds };
}

function main() {
  const input = readHookInput();
  // Claude Code always names the event on stdin. Without it we can neither
  // honour the PostToolUse command filter below nor label hookSpecificOutput
  // with an event Claude Code will accept — and a mislabelled block is dropped
  // after the marks have already been consumed, losing the nudge for good.
  // Unparseable in, silence out.
  if (typeof input.hook_event_name !== "string" || input.hook_event_name === "") {
    return;
  }
  if (!isRelevant(input)) {
    return;
  }

  const cwd = input.cwd || process.cwd();
  const failed = failedJobLines(cwd);
  const lines = [...defectLines(cwd), ...failed.lines];
  if (lines.length === 0) {
    return;
  }

  const payload = `${JSON.stringify(
    {
      hookSpecificOutput: {
        hookEventName: input.hook_event_name,
        additionalContext: lines.join("\n\n")
      }
    },
    null,
    2
  )}\n`;

  // Commit the marks only once the payload has actually been flushed. There is
  // no un-surface path, so a mark written ahead of a write that errors — or of
  // a hook killed on its 5s timeout, whose stdout is discarded — is a
  // permanently lost notification. The write callback runs after the flush.
  process.stdout.write(payload, (error) => {
    if (error || failed.jobIds.length === 0) {
      return;
    }
    try {
      markJobsSurfaced(cwd, failed.jobIds);
    } catch {
      // Advisory only: the nudge was already delivered.
    }
  });
}

try {
  main();
} catch {
  // Advisory only: never fail the session over a nudge.
  process.exitCode = 0;
}
