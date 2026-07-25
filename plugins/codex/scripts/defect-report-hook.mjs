#!/usr/bin/env node
// SPDX-License-Identifier: Apache-2.0

// Advisory hook. Surfaces two things Claude Code would otherwise never see:
// unreported defect markers (reportable) and failed jobs (not reportable).
// Must never block a turn, fail a session, or write to state.json.

import fs from "node:fs";
import process from "node:process";

import { listSurfacedJobs, listUnreportedDefects, markJobSurfaced } from "./lib/defect-log.mjs";
import { loadState } from "./lib/state.mjs";

const COMPANION_MARKER = "codex-companion.mjs";

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

function defectLines(cwd) {
  const markers = listUnreportedDefects(cwd);
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

function failedJobLines(cwd) {
  let jobs = [];
  try {
    jobs = loadState(cwd).jobs ?? [];
  } catch {
    return [];
  }

  const surfaced = new Set(listSurfacedJobs(cwd));
  const lines = [];
  for (const job of jobs) {
    if (job.status !== "failed" || surfaced.has(job.id)) {
      continue;
    }
    const detail = String(job.summary ?? job.errorMessage ?? "no detail recorded").trim();
    lines.push(
      `Codex job ${job.id} failed and was never surfaced: "${detail}". ` +
        `See /codex:result ${job.id}. This is a Codex-side or environment failure, not a plugin ` +
        "defect — tell the user plainly and do not offer to file an issue."
    );
    markJobSurfaced(cwd, job.id);
  }
  return lines;
}

function main() {
  const input = readHookInput();
  if (!isRelevant(input)) {
    return;
  }

  const cwd = input.cwd || process.cwd();
  const lines = [...defectLines(cwd), ...failedJobLines(cwd)];
  if (lines.length === 0) {
    return;
  }

  process.stdout.write(
    `${JSON.stringify(
      {
        hookSpecificOutput: {
          hookEventName: input.hook_event_name ?? "SessionStart",
          additionalContext: lines.join("\n\n")
        }
      },
      null,
      2
    )}\n`
  );
}

try {
  main();
} catch {
  // Advisory only: never fail the session over a nudge.
  process.exitCode = 0;
}
