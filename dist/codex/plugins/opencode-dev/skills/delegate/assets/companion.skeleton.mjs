// companion.skeleton.mjs — minimal CC→OpenCode serve+SDK companion.
// Verify SDK signatures against opencode-dev:sdk + GET /doc before shipping.
// Connect-only: the caller provisions the server, credentials and permission policy.
// Node 18+. No auto-approval or permission overrides are added here.

import { spawn } from "node:child_process";
import { randomUUID } from "node:crypto";
import { readFileSync, writeFileSync, existsSync, mkdirSync, renameSync, rmdirSync } from "node:fs";
import { fileURLToPath } from "node:url";
import { createOpencodeClient } from "@opencode-ai/sdk";

const SELF = fileURLToPath(import.meta.url);
const CACHE_DIR = `${process.env.HOME}/.cache/cc-opencode`;
const STORE = `${CACHE_DIR}/jobs.json`;
const LOCK = `${STORE}.lock`;
const BASE_URL = process.env.OPENCODE_BASE_URL ?? "http://localhost:4096";
const client = () => createOpencodeClient({ baseUrl: BASE_URL });
const load = () => (existsSync(STORE) ? JSON.parse(readFileSync(STORE, "utf8")) : {});
const running = (job) => job?.status === "running";
const errorRecord = (error) => ({
  name: error?.name ?? "Error",
  message: error?.data?.message ?? error?.message ?? String(error),
});

// Readers see atomic snapshots. Writers serialize read/modify/write, including
// result publication, so another job or a late worker cannot erase cancellation.
// This small skeleton fails visibly on a stale lock; production crash recovery,
// remote-request timeouts and job retention remain deployment responsibilities.
async function update(id, change) {
  mkdirSync(CACHE_DIR, { recursive: true });
  const deadline = Date.now() + 5000;
  while (true) {
    try { mkdirSync(LOCK); break; }
    catch (error) {
      if (error.code !== "EEXIST") throw error;
      if (Date.now() >= deadline) throw new Error(`job store lock timed out: ${LOCK}`);
      await new Promise((resolve) => setTimeout(resolve, 10));
    }
  }
  try {
    const jobs = load();
    const next = change(jobs[id]); // synchronous: never hold the lock over SDK calls
    if (next) {
      jobs[id] = next;
      const temporary = `${STORE}.${process.pid}.tmp`;
      writeFileSync(temporary, JSON.stringify(jobs, null, 2));
      renameSync(temporary, STORE);
    }
    return next ?? jobs[id];
  } finally { rmdirSync(LOCK); }
}

function resultFile(job, result) {
  const temporary = `${job.logFile}.${process.pid}.tmp`;
  writeFileSync(temporary, JSON.stringify(result, null, 2));
  renameSync(temporary, job.logFile);
}
async function finish(id, status, result) {
  return update(id, (job) => {
    if (!running(job)) return; // cancellation/another terminal state wins
    resultFile(job, result); // publish result before advertising terminal status
    return { ...job, status, phase: status === "done" ? "complete" : "failed",
      ...(result.error ? { error: result.error } : {}) };
  });
}
function responseData(response) {
  if (response?.error) throw response.error; // default SDK errors are returned
  if (response?.data == null) throw new Error("missing SDK response data");
  return response.data;
}

async function abortSession(id, sessionID, connected) {
  // Creation may finish after cancellation: retain the new remote session id.
  await update(id, (job) => {
    if (job?.status !== "cancelled") return;
    const next = { ...job, sessionID };
    resultFile(next, { status: "cancelled", sessionID, ...(job.error ? { error: job.error } : {}) });
    return next;
  });
  try { responseData(await (connected ?? client()).session.abort({ path: { id: sessionID } })); }
  catch (error) {
    const failure = errorRecord(error);
    await update(id, (job) => {
      if (job?.status !== "cancelled") return;
      const next = { ...job, error: failure };
      resultFile(next, { status: "cancelled", sessionID, error: failure });
      return next;
    });
    throw error;
  }
}

async function task(request) {
  const id = `job_${randomUUID()}`;
  const logFile = `${CACHE_DIR}/${id}.log`;
  // Persist dispatch BEFORE starting the worker. The parent only patches pid;
  // it never writes a stale copy of the worker's phase/status/session/result.
  await update(id, () => ({ id, status: "running", phase: "dispatched", logFile, request }));
  try {
    const child = spawn(process.execPath, [SELF, "__worker", id, logFile, request], {
      detached: true,
      stdio: "ignore",
    });
    child.once("error", (error) => {
      finish(id, "failed", { error: errorRecord(error) }).catch(console.error);
    });
    child.unref(); // REQUIRED: worker outlives this fast tool call
    await update(id, (job) => ({ ...job, pid: child.pid }));
  } catch (error) { await finish(id, "failed", { error: errorRecord(error) }); }
  console.log(JSON.stringify({ id }));
}

async function worker(id, _logFile, request) {
  let sessionID;
  try {
    const initial = await update(id, (job) => running(job)
      ? { ...job, pid: process.pid, phase: "creating" } : undefined);
    if (!running(initial)) return;
    const c = client();
    const created = responseData(await c.session.create({ body: {} }));
    sessionID = created.id;
    if (typeof sessionID !== "string" || !sessionID) throw new Error("missing session id");
    const current = await update(id, (job) => running(job)
      ? { ...job, sessionID, phase: "prompting" } : undefined);
    if (!running(current)) {
      await abortSession(id, sessionID, c);
      return;
    }
    const result = responseData(await c.session.prompt({ path: { id: sessionID },
      body: { parts: [{ type: "text", text: request }] } }));
    if (result.info?.error) throw result.info.error; // assistant errors also resolve
    if (!result.info || !Array.isArray(result.parts)) throw new Error("missing prompt message data");
    await finish(id, "done", { sessionID, result });
  } catch (error) {
    await finish(id, "failed", { ...(sessionID ? { sessionID } : {}), error: errorRecord(error) });
  }
}

function status(id) { console.log(JSON.stringify(load()[id] ?? { error: "unknown job" })); }
function result(id) {
  const job = load()[id];
  if (!job) { console.log(JSON.stringify({ error: "unknown job" })); return; }
  console.log(existsSync(job.logFile) ? readFileSync(job.logFile, "utf8") : "(no result yet)");
}

async function cancel(id) {
  let claimed = false;
  const job = await update(id, (current) => {
    if (!running(current)) return;
    claimed = true;
    const next = { ...current, status: "cancelled", phase: "cancelled" };
    resultFile(next, { status: "cancelled", ...(next.sessionID ? { sessionID: next.sessionID } : {}) });
    return next;
  });
  if (!job) { console.log(JSON.stringify({ error: "unknown job" })); return; }
  if (!claimed) return; // idempotent; completed and failed jobs stay terminal
  try {
    if (job.sessionID) await abortSession(id, job.sessionID);
    // A create in flight can still return after cancellation: let the worker
    // see the terminal record and abort that new session without prompting it.
    // Before it starts, the worker sees cancellation and exits immediately.
  } catch (error) {
    console.error(JSON.stringify(errorRecord(error)));
    process.exitCode = 1; // cancellation recorded; remote abort was unsuccessful
  }
}

const [verb, ...args] = process.argv.slice(2);
const verbs = { task: () => task(args.join(" ")), status: () => status(args[0]),
  result: () => result(args[0]), cancel: () => cancel(args[0]),
  __worker: () => worker(args[0], args[1], args.slice(2).join(" ")) };
await (verbs[verb] ?? (() => { console.error("usage: companion.mjs task|status|result|cancel"); process.exit(1); }))();
