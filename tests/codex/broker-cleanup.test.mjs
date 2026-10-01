// SPDX-License-Identifier: Apache-2.0
// SPDX-FileCopyrightText: 2026 nq-rdl
import fs from "node:fs";
import path from "node:path";
import test from "node:test";
import assert from "node:assert/strict";
import { fileURLToPath } from "node:url";
import { makeTempDir, run } from "./helpers.mjs";
import { cleanupTestBrokers, findTestBrokers } from "./broker-cleanup.mjs";
import { buildEnv, installFakeCodex } from "./fake-codex-fixture.mjs";
import { ensureBrokerSession } from "../../plugins/codex/scripts/lib/broker-lifecycle.mjs";

const FIXTURE = fileURLToPath(new URL("./broker-cleanup-fixture.mjs", import.meta.url));

for (const mode of ["normal", "failure", "deleted", "unresponsive", "exit"]) {
  test(`file teardown leaves no live brokers (${mode})`, async () => {
    const tempRoot = makeTempDir();
    const manifest = path.join(tempRoot, "session.json");
    const env = {
      ...process.env,
      TMPDIR: tempRoot,
      BROKER_CLEANUP_MODE: mode,
      BROKER_CLEANUP_MANIFEST: manifest
    };
    delete env.NODE_TEST_CONTEXT;
    const result = run(process.execPath, ["--test", FIXTURE], { env });
    try {
      assert.equal(result.status, mode === "failure" ? 1 : 0, `${result.stdout}\n${result.stderr}`);
      assert.ok(fs.existsSync(manifest), "fixture must actually start a broker");
      // The exit hook cannot wait for SIGKILL to be reaped by the OS.
      const deadline = Date.now() + 2000;
      while (findTestBrokers([tempRoot]).length && Date.now() < deadline) {
        await new Promise((resolve) => setTimeout(resolve, 50));
      }
      assert.deepEqual(findTestBrokers([tempRoot]), [], "detached broker survived the test file");
      if (mode !== "exit") {
        const session = JSON.parse(fs.readFileSync(manifest, "utf8"));
        assert.equal(fs.existsSync(session.sessionDir), false, "broker socket/log directory leaked");
        assert.equal(fs.existsSync(session.root), false, "workspace was not removed after teardown");
      }
    } finally {
      await cleanupTestBrokers([tempRoot]);
    }
  });
}

test("cleanup affects only explicitly owned cwd roots, not other brokers", async () => {
  const cwd = makeTempDir();
  const bin = makeTempDir();
  installFakeCodex(bin);
  const session = await ensureBrokerSession(cwd, { env: buildEnv(bin) });
  assert.ok(session);
  assert.equal(findTestBrokers([cwd])[0]?.pid, session.pid, "guard detects a real live broker");
  await cleanupTestBrokers([`${cwd}-not-owned`]);
  assert.equal(findTestBrokers([cwd])[0]?.pid, session.pid, "similar cwd prefix must not grant ownership");
  await cleanupTestBrokers([cwd]);
  assert.deepEqual(findTestBrokers([cwd]), []);
  // Cleanup is safe to repeat, including already-exited sessions.
  await cleanupTestBrokers([cwd]);
});
