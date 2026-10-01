// SPDX-License-Identifier: Apache-2.0
// SPDX-FileCopyrightText: 2026 nq-rdl
// Test-only ownership and bounded teardown; no production lifecycle changes.

import net from "node:net";
import path from "node:path";
import { spawnSync } from "node:child_process";
import { parseBrokerEndpoint } from "../../plugins/codex/scripts/lib/broker-endpoint.mjs";
import { teardownBrokerSession } from "../../plugins/codex/scripts/lib/broker-lifecycle.mjs";

export function findTestBrokers(roots) {
  // ps is available on both supported platforms (Linux and macOS). Do not use
  // broker.json: tests can remove the cwd, replace state, or use a private data dir.
  const result = spawnSync("ps", ["-axww", "-o", "pid=,stat=,command="], { encoding: "utf8" });
  if (result.error || result.status !== 0) {
    throw new Error(`Cannot inspect test brokers: ${result.error ?? result.stderr}`);
  }
  return result.stdout.split("\n").flatMap((line) => {
    const match = line.match(/^\s*(\d+)\s+(\S+)\s+\S+ .*\/app-server-broker[.]mjs serve --endpoint (.+?) --cwd (.+?) --pid-file (.+)$/);
    if (!match || match[2].startsWith("Z")) return [];
    const [, pid, , endpoint, cwd, pidFile] = match;
    if (!roots.some((root) => cwd === root || cwd.startsWith(`${root}${path.sep}`))) return [];
    return [{ pid: Number(pid), endpoint, cwd, pidFile }];
  });
}

function shutdown(endpoint) {
  return new Promise((resolve) => {
    let socket;
    const finish = () => {
      clearTimeout(timer);
      socket?.destroy();
      resolve();
    };
    const timer = setTimeout(finish, 750);
    try {
      socket = net.createConnection({ path: parseBrokerEndpoint(endpoint).path });
      socket.on("connect", () => socket.write(`${JSON.stringify({ id: 1, method: "broker/shutdown", params: {} })}\n`));
      socket.on("data", finish);
      socket.on("error", finish);
      socket.on("close", finish);
    } catch {
      finish();
    }
  });
}

function signalOwned(roots, signal) {
  // Recheck ownership immediately before signalling; never kill from stale state
  // or a global temp-dir prefix shared with other test runs.
  for (const { pid } of findTestBrokers(roots)) {
    try {
      process.kill(pid, signal);
    } catch (error) {
      if (error.code !== "ESRCH") throw error;
    }
  }
}

async function waitForExit(roots) {
  const deadline = Date.now() + 1500;
  while (findTestBrokers(roots).length && Date.now() < deadline) {
    await new Promise((resolve) => setTimeout(resolve, 50));
  }
}

export async function cleanupTestBrokers(roots) {
  const brokers = findTestBrokers(roots);
  await Promise.all(brokers.map(({ endpoint }) => shutdown(endpoint)));
  await waitForExit(roots);
  signalOwned(roots, "SIGTERM");
  await waitForExit(roots);
  signalOwned(roots, "SIGKILL");
  await waitForExit(roots);
  const remaining = findTestBrokers(roots);
  if (remaining.length) throw new Error(`Leaked test brokers: ${JSON.stringify(remaining)}`);
  for (const broker of brokers) {
    teardownBrokerSession({
      ...broker,
      sessionDir: path.dirname(broker.pidFile),
      logFile: path.join(path.dirname(broker.pidFile), "broker.log")
    });
  }
}

// exit cannot await RPC or polling. This is only a best-effort fallback for an
// explicit process.exit(); the normal node:test after hook handles shutdown.
export function killTestBrokersOnExit(roots) {
  signalOwned(roots, "SIGKILL");
}
