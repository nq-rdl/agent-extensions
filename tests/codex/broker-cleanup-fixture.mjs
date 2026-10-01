// SPDX-License-Identifier: Apache-2.0
// SPDX-FileCopyrightText: 2026 nq-rdl
// Invoked explicitly by broker-cleanup.test.mjs, never by the suite glob.
import fs from "node:fs";
import path from "node:path";
import test from "node:test";
import assert from "node:assert/strict";
import { makeTempDir } from "./helpers.mjs";
import { buildEnv, installFakeCodex } from "./fake-codex-fixture.mjs";
import { ensureBrokerSession } from "../../plugins/codex/scripts/lib/broker-lifecycle.mjs";

const mode = process.env.BROKER_CLEANUP_MODE;
test("start a detached broker owned by this file", async () => {
  const root = makeTempDir("codex-plugin-test-with spaces-");
  const cwd = path.join(root, "nested workspace");
  fs.mkdirSync(cwd);
  const bin = makeTempDir();
  installFakeCodex(bin);
  const session = await ensureBrokerSession(cwd, { env: buildEnv(bin) });
  assert.ok(session);
  fs.writeFileSync(process.env.BROKER_CLEANUP_MANIFEST, JSON.stringify({ ...session, cwd, root }));
  if (mode === "deleted") fs.rmSync(root, { recursive: true });
  if (mode === "unresponsive") process.kill(session.pid, "SIGSTOP");
  if (mode === "exit") process.exit(0);
  assert.notEqual(mode, "failure", "intentional failure to exercise after teardown");
});
