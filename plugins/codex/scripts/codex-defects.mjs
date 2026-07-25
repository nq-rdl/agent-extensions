#!/usr/bin/env node
// SPDX-License-Identifier: Apache-2.0

// Callable surface over the defect log, for /codex:report-defect. A markdown
// skill cannot read a JSON marker or update bookkeeping on its own. This lives
// outside codex-companion.mjs so the vendored delta stays at one line.

import process from "node:process";

import { classifyDefect } from "./lib/defect-classify.mjs";
import {
  listDefects,
  listUnreportedDefects,
  markDefectReported,
  readDefect,
  resolveDefectsDir
} from "./lib/defect-log.mjs";

function parseArgs(argv) {
  const options = { _: [] };
  for (let index = 0; index < argv.length; index += 1) {
    const token = argv[index];
    if (!token.startsWith("--")) {
      options._.push(token);
      continue;
    }
    const name = token.slice(2);
    if (name === "json" || name === "all" || name === "latest") {
      options[name] = true;
      continue;
    }
    options[name] = argv[index + 1] ?? "";
    index += 1;
  }
  return options;
}

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
  const [subcommand, ...rest] = process.argv.slice(2);
  const options = parseArgs(rest);
  const cwd = options.cwd || process.cwd();

  switch (subcommand) {
    case "list": {
      const markers = options.all ? listDefects(cwd) : listUnreportedDefects(cwd);
      emit({ defects: markers.map(summarise) });
      return;
    }
    case "show": {
      const marker = options.latest ? (listUnreportedDefects(cwd)[0] ?? listDefects(cwd)[0]) : readDefect(cwd, options._[0]);
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
      const id = options._[0];
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
}

main();
