/**
 * ACP (Agent Communication Protocol) client for persistent Gemini sessions.
 *
 * Manages long-lived `gemini --acp` subprocesses that speak JSON-RPC 2.0 over
 * stdin/stdout. Each named session is a separate subprocess with full conversation
 * context preserved across calls.
 *
 * Key design:
 * - Lazy init: subprocess spawned on first acpAsk() call
 * - Singleton per session_name: one subprocess per named slot
 * - Turn counter: tracks conversation depth per session
 * - Graceful shutdown: SIGTERM all subprocesses via acpShutdownAll()
 */

import { spawn, type ChildProcess } from "child_process";
import { createInterface, type Interface as ReadlineInterface } from "readline";
import { mkdirSync, writeFileSync, rmSync } from "fs";
import { join } from "path";
import { randomUUID } from "crypto";
import type {
  JsonRpcRequest,
  JsonRpcMessage,
  AcpPromptResult,
  AcpAskResult,
  AcpSessionOptions,
} from "./types.js";

interface AcpSession {
  proc: ChildProcess;
  reader: ReadlineInterface;
  sessionId: string;
  turn: number;
  model: string;
  nextId: number;
  contextDir: string | null;
  /** Pending response resolvers keyed by JSON-RPC request id */
  pending: Map<number, { resolve: (msg: JsonRpcMessage) => void; reject: (err: Error) => void }>;
  /** Accumulated text from session/update notifications for current prompt */
  chunks: string[];
}

const sessions = new Map<string, AcpSession>();

const MODEL_ALIASES: Record<string, string> = {
  fast: "gemini-3-flash-preview",
  quality: "gemini-3.1-pro-preview",
};

function resolveModel(model: string): string {
  return MODEL_ALIASES[model] ?? model;
}

/**
 * Send a JSON-RPC request and wait for the matching response.
 */
function sendRequest(
  session: AcpSession,
  method: string,
  params?: Record<string, unknown>
): Promise<JsonRpcMessage> {
  const id = session.nextId++;
  const request: JsonRpcRequest = { jsonrpc: "2.0", id, method, params };

  return new Promise((resolve, reject) => {
    session.pending.set(id, { resolve, reject });
    session.proc.stdin!.write(JSON.stringify(request) + "\n", "utf-8");
  });
}

/**
 * Process an incoming JSON-RPC line from the ACP subprocess.
 */
function handleLine(session: AcpSession, line: string): void {
  if (!line.trim()) return;

  let msg: JsonRpcMessage;
  try {
    msg = JSON.parse(line);
  } catch {
    return; // Skip non-JSON lines (stderr leaking into stdout, etc.)
  }

  // Notification (no id) — accumulate text chunks
  if (!("id" in msg) && "method" in msg) {
    if (msg.method === "session/update") {
      const params = msg.params as { update?: { text?: string } } | undefined;
      if (params?.update?.text) {
        session.chunks.push(params.update.text);
      }
    }
    return;
  }

  // Response (has id) — resolve the pending promise
  if ("id" in msg && msg.id !== undefined) {
    const pending = session.pending.get(msg.id as number);
    if (pending) {
      session.pending.delete(msg.id as number);
      pending.resolve(msg);
    }
  }
}

/**
 * Spawn a new ACP subprocess and perform the initialize + session/new handshake.
 */
async function createSession(
  name: string,
  opts: AcpSessionOptions
): Promise<AcpSession> {
  const binary = process.env.GEMINI_BINARY ?? "gemini";
  const model = resolveModel(opts.model ?? process.env.GEMINI_DEFAULT_MODEL ?? "gemini-3-flash-preview");

  const args = ["--acp", "--model", model, "--yolo"];

  // System context injection
  let contextDir: string | null = null;
  if (opts.system_context) {
    contextDir = join("/tmp", `gemini-acp-${randomUUID()}`);
    mkdirSync(contextDir, { recursive: true });
    writeFileSync(join(contextDir, "GEMINI.md"), opts.system_context, "utf-8");
    args.push("--include-directories", contextDir);
  }

  const proc = spawn(binary, args, {
    cwd: opts.cwd ?? process.cwd(),
    stdio: ["pipe", "pipe", "pipe"],
    env: { ...process.env },
  });

  const reader = createInterface({ input: proc.stdout! });
  const session: AcpSession = {
    proc,
    reader,
    sessionId: "",
    turn: 0,
    model,
    nextId: 1,
    contextDir,
    pending: new Map(),
    chunks: [],
  };

  // Wire up line-by-line reading
  reader.on("line", (line) => handleLine(session, line));

  // Handle subprocess crash — only clean up if this session is still registered
  proc.on("exit", (code) => {
    // Reject all pending requests
    for (const [, { reject }] of session.pending) {
      reject(new Error(`ACP subprocess exited with code ${code}`));
    }
    session.pending.clear();
    // Only remove from map if this session is still the active one for this name
    if (sessions.get(name) === session) {
      sessions.delete(name);
    }
    if (session.contextDir) {
      try { rmSync(session.contextDir, { recursive: true, force: true }); } catch { /* best-effort */ }
    }
  });

  // Ignore stderr (Gemini CLI writes status/progress there)
  proc.stderr!.on("data", () => {});

  sessions.set(name, session);

  // Handshake: initialize
  const initResp = await sendRequest(session, "initialize", { clientCapabilities: {} });
  if ("error" in initResp) {
    throw new Error(`ACP initialize failed: ${(initResp as any).error.message}`);
  }

  // Handshake: session/new
  const newResp = await sendRequest(session, "session/new", { cwd: opts.cwd ?? process.cwd() });
  if ("error" in newResp) {
    throw new Error(`ACP session/new failed: ${(newResp as any).error.message}`);
  }
  session.sessionId = ((newResp as any).result as Record<string, unknown>).sessionId as string;

  return session;
}

/**
 * Get an existing session by name (for inspection/testing).
 */
export function acpGetSession(name: string): { turn: number; sessionId: string } | undefined {
  const s = sessions.get(name);
  if (!s) return undefined;
  return { turn: s.turn, sessionId: s.sessionId };
}

/**
 * Send a prompt to a persistent ACP session. Creates the session on first call.
 */
export async function acpAsk(
  question: string,
  opts: AcpSessionOptions & { session_name?: string; context?: string }
): Promise<AcpAskResult> {
  const name = opts.session_name ?? "default";
  let session = sessions.get(name);

  if (!session) {
    session = await createSession(name, opts);
  }

  // Clear chunks for this turn
  session.chunks = [];

  // Prepend context if provided
  const prompt = opts.context ? `${opts.context}\n\n${question}` : question;

  const resp = await sendRequest(session, "session/prompt", {
    sessionId: session.sessionId,
    prompt,
  });

  if ("error" in resp) {
    throw new Error(`ACP prompt failed: ${(resp as any).error.message}`);
  }

  session.turn++;

  const result = (resp as any).result as AcpPromptResult;
  const answer = session.chunks.join("");

  return {
    answer,
    session_id: session.sessionId,
    turn: session.turn,
    usage: result.usage ?? {},
  };
}

/**
 * Gracefully shut down all ACP sessions. Called on MCP server exit.
 */
export async function acpShutdownAll(): Promise<void> {
  for (const [name, session] of sessions) {
    try {
      session.reader.close();
      session.proc.kill("SIGTERM");
    } catch { /* best-effort */ }
    if (session.contextDir) {
      try { rmSync(session.contextDir, { recursive: true, force: true }); } catch { /* best-effort */ }
    }
  }
  sessions.clear();
}
