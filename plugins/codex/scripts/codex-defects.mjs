#!/usr/bin/env node
// SPDX-License-Identifier: Apache-2.0

// Callable surface over the defect log, for /codex:report-defect. A markdown
// skill cannot read a JSON marker or update bookkeeping on its own. This lives
// outside codex-companion.mjs so the vendored delta stays at one line.

import path from "node:path";
import process from "node:process";

import { classifyDefect } from "./lib/defect-classify.mjs";
import { parseArgs } from "./lib/args.mjs";
import {
  listDefects,
  listUnreportedDefects,
  markDefectReported,
  readDefect,
  resolveDefectsDir
} from "./lib/defect-log.mjs";

const ARG_CONFIG = {
  valueOptions: ["cwd", "url"],
  booleanOptions: ["json", "all", "latest"]
};

function summarise(marker) {
  const classification = classifyDefect(marker);
  return {
    id: marker.id,
    recordedAt: marker.recordedAt,
    surface: marker.surface,
    message: marker.message,
    verdict: classification.verdict,
    cause: classification.cause
  };
}

function emit(payload) {
  process.stdout.write(`${JSON.stringify(payload, null, 2)}\n`);
}

function main() {
  try {
    const [subcommand, ...rest] = process.argv.slice(2);
    const { options, positionals } = parseArgs(rest, ARG_CONFIG);
    const cwd = options.cwd ? path.resolve(process.cwd(), options.cwd) : process.cwd();

    switch (subcommand) {
      case "list": {
        const markers = options.all ? listDefects(cwd) : listUnreportedDefects(cwd);
        emit({ defects: markers.map(summarise) });
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
          classification: classifyDefect(marker),
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
