// companion.skeleton.mjs — minimal CC→OpenCode delegation companion.
//
// Anchored on the verifiable drive path: `opencode serve` + `@opencode-ai/sdk`
// (`createOpencodeClient`). This is the OpenCode analog of codex-plugin-cc's
// persistent-connection companion. The CC-facing surface (verbs below) is the same
// regardless of transport — to use `opencode acp` or `opencode run` instead, swap
// only the connect()/start()/cancel() bodies.
//
// VERIFY before relying on signatures: SDK method arg shapes are generated from the
// server's OpenAPI spec (`GET http://localhost:4096/doc`) — see the `opencode-dev:sdk`
// skill. Pins: @opencode-ai/sdk; node 18+.

import { spawn } from "node:child_process";
import { readFileSync, writeFileSync, existsSync, mkdirSync } from "node:fs";
import { fileURLToPath } from "node:url";
import { createOpencodeClient } from "@opencode-ai/sdk";

const SELF = fileURLToPath(import.meta.url); // node 18+ has no import.meta.filename
const CACHE_DIR = `${process.env.HOME}/.cache/cc-opencode`;
const STORE = `${CACHE_DIR}/jobs.json`;
const BASE_URL = process.env.OPENCODE_BASE_URL ?? "http://localhost:4096";

const client = () =>
  createOpencodeClient({ baseUrl: BASE_URL }); // connect-only; assumes `opencode serve` is up

// --- job store: {id,status,phase,pid,logFile,sessionID,request} ----------------
const load = () => (existsSync(STORE) ? JSON.parse(readFileSync(STORE, "utf8")) : {});
const save = (jobs) => { mkdirSync(CACHE_DIR, { recursive: true }); writeFileSync(STORE, JSON.stringify(jobs, null, 2)); };
const put = (job) => { const j = load(); j[job.id] = job; save(j); };

// --- verbs ---------------------------------------------------------------------
async function task(request) {
  const id = `job_${Date.now()}`;
  const logFile = `${CACHE_DIR}/${id}.log`;
  // Spawn the worker TRULY detached so it outlives this fast CC tool call.
  const child = spawn(process.execPath, [SELF, "__worker", id, logFile, request], {
    detached: true,
    stdio: "ignore",
  });
  child.unref(); // REQUIRED — without unref the job is not detached.
  put({ id, status: "running", phase: "dispatched", pid: child.pid, logFile, request });
  console.log(JSON.stringify({ id }));
}

async function worker(id, logFile, request) {
  const c = client();
  // Verify these signatures against `opencode-dev:sdk` + GET /doc before shipping.
  const created = await c.session.create({ body: {} });             // {data}-wrapped response
  const sessionID = created.data.id;
  put({ ...load()[id], sessionID, phase: "prompting" });
  await c.session.prompt({ path: { id: sessionID }, body: { parts: [{ type: "text", text: request }] } });
  put({ ...load()[id], status: "done", phase: "complete" });
  writeFileSync(logFile, JSON.stringify({ sessionID }, null, 2));
}

function status(id) { console.log(JSON.stringify(load()[id] ?? { error: "unknown job" })); }
function result(id) {
  const j = load()[id];
  if (!j) { console.log(JSON.stringify({ error: "unknown job" })); return; }
  console.log(existsSync(j.logFile) ? readFileSync(j.logFile, "utf8") : "(no result yet)");
}

async function cancel(id) {
  const j = load()[id];
  if (!j) { console.log(JSON.stringify({ error: "unknown job" })); return; }
  if (j.sessionID) await client().session.abort({ path: { id: j.sessionID } }); // serve+SDK cancel
  else if (j.pid) try { process.kill(j.pid); } catch {}                          // run-path cancel
  put({ ...j, status: "cancelled" });
}

// --- dispatch ------------------------------------------------------------------
const [verb, ...args] = process.argv.slice(2);
const verbs = { task: () => task(args.join(" ")), status: () => status(args[0]),
  result: () => result(args[0]), cancel: () => cancel(args[0]),
  __worker: () => worker(args[0], args[1], args.slice(2).join(" ")) };
await (verbs[verb] ?? (() => { console.error(`usage: companion.mjs task|status|result|cancel`); process.exit(1); }))();
