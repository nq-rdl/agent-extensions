#!/usr/bin/env node
// SPDX-License-Identifier: Apache-2.0
// SPDX-FileCopyrightText: 2026 nq-rdl

// Callable surface over the defect log, for /codex:report-defect. A markdown
// skill cannot read a JSON marker or update bookkeeping on its own. Keeping it
// out of codex-companion.mjs holds that vendored file's defect delta to one
// recordDefect import plus a guarded block in main().catch(). The only other
// vendored file this feature touches is lib/workspace.mjs, which had to stop
// returning an empty workspace root before per-workspace state was safe to
// write concurrently.

import path from "node:path";
import process from "node:process";

import { classifyDefect, resolveAuthCrossCheck } from "./lib/defect-classify.mjs";
import { parseArgs } from "./lib/args.mjs";
import {
  listDefects,
  listUnreportedDefects,
  markDefectReported,
  readDefect,
  resolveDefectsDir
} from "./lib/defect-log.mjs";

// Every subcommand emits JSON unconditionally — the only caller is the
// /codex:report-defect skill, which parses it — so `--json` changes nothing.
// It stays declared anyway: parseArgs pushes unrecognised long flags into
// positionals, so dropping it would make a `--json` typed out of habit (every
// codex-companion.mjs subcommand takes one) read as a marker id under `show`.
const ARG_CONFIG = {
  valueOptions: ["cwd", "url"],
  booleanOptions: ["json", "all", "latest"]
};

// Auth is the one verdict a marker cannot settle alone: the same error is
// benign when the user really is logged out, and a plugin defect when the
// readiness check insists the session is fine. Probe live state once per
// invocation, and only when a marker asks for it — `list` over ordinary
// markers must not pay for an app-server handshake.
let setupProbe = null;

function probeSetupStatus(cwd) {
  if (!setupProbe) {
    // Deferred import so the common path never loads the app-server stack.
    setupProbe = import("./lib/codex.mjs").then(({ getCodexAuthStatus }) => getCodexAuthStatus(cwd));
  }
  return setupProbe;
}

async function classify(marker, cwd) {
  const classification = classifyDefect(marker);
  if (!classification.needsSetupCrossCheck) {
    return classification;
  }

  // Mirrors buildSetupReport's `ready`: node is a given inside this process, so
  // Codex availability plus a live login is the whole check.
  const status = await probeSetupStatus(cwd);
  return resolveAuthCrossCheck(Boolean(status.available && status.loggedIn));
}

async function summarise(marker, cwd) {
  const classification = await classify(marker, cwd);
  return {
    id: marker.id,
    recordedAt: marker.recordedAt,
    surface: marker.surface,
    message: marker.message,
    // `!== false` so markers written before the field existed read as scrubbed
    // rather than as spurious warnings. false means the marker may still carry
    // the user's username and must not be published unreviewed.
    homeScrubbed: marker.homeScrubbed !== false,
    verdict: classification.verdict,
    cause: classification.cause
  };
}

function emit(payload) {
  process.stdout.write(`${JSON.stringify(payload, null, 2)}\n`);
}

async function main() {
  try {
    const [subcommand, ...rest] = process.argv.slice(2);
    const { options, positionals } = parseArgs(rest, ARG_CONFIG);
    const cwd = options.cwd ? path.resolve(process.cwd(), options.cwd) : process.cwd();

    switch (subcommand) {
      case "list": {
        const markers = options.all ? listDefects(cwd) : listUnreportedDefects(cwd);
        emit({ defects: await Promise.all(markers.map((marker) => summarise(marker, cwd))) });
        return;
      }
      case "show": {
        const marker = options.latest
          ? (listUnreportedDefects(cwd)[0] ?? listDefects(cwd)[0])
          : readDefect(cwd, positionals[0]);
        if (!marker) {
          process.stderr.write("Defect marker not found.\n");
          process.exitCode = 1;
          return;
        }
        emit({
          ...marker,
          classification: await classify(marker, cwd),
          // The skill writes its <id>.md report alongside the marker.
          defectsDir: resolveDefectsDir(cwd)
        });
        return;
      }
      case "mark-reported": {
        const id = positionals[0];
        if (!id) {
          process.stderr.write("mark-reported requires a defect id.\n");
          process.exitCode = 1;
          return;
        }
        if (!markDefectReported(cwd, id, { url: options.url ?? null })) {
          process.stderr.write(`Could not mark ${id} as reported.\n`);
          process.exitCode = 1;
          return;
        }
        emit({ ok: true, id, url: options.url ?? null });
        return;
      }
      default:
        process.stderr.write(`Unknown subcommand: ${subcommand ?? "(none)"}\n`);
        process.exitCode = 1;
    }
  } catch (error) {
    // parseArgs throws on a missing value (e.g. a trailing `--url` with
    // nothing after it). Surface just the message, not a raw stack trace —
    // process.exitCode (not process.exit()) so stdout still flushes for the
    // skill to parse.
    process.stderr.write(`${error.message}\n`);
    process.exitCode = 1;
  }
}

main();
