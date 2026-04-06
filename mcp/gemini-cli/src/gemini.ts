/**
 * Subprocess manager for Gemini CLI headless mode.
 *
 * Spawns `gemini -p <prompt> --output-format json` and parses the single
 * JSON response object: { session_id, response, stats }.
 *
 * Key design choices:
 * - Uses `--output-format json` (not `stream-json`) — the JSON format already
 *   includes `session_id` at the top level, so no JSONL parsing is needed
 * - Defaults to `--approval-mode yolo` and `--sandbox` for safe headless operation
 * - System context is injected via a temporary GEMINI.md + `--include-directories`
 * - Binary path is configurable via `GEMINI_BINARY` for test injection
 * - Default model configurable via `GEMINI_DEFAULT_MODEL` (e.g. "gemini-3-flash-preview")
 */

import { spawn } from "child_process";
import { randomUUID } from "crypto";
import { mkdirSync, writeFileSync, rmSync, readFileSync, existsSync } from "fs";
import { join } from "path";
import type { GeminiOptions, GeminiResult } from "./types.js";

/**
 * Named model presets → real Gemini CLI model IDs.
 * Keeps tool callers from having to remember full model strings.
 */
const MODEL_ALIASES: Record<string, string> = {
  fast:    "gemini-3-flash-preview",
  quality: "gemini-3.1-pro-preview",
};

/** Resolve a preset alias or pass through a full model ID unchanged. */
function resolveModel(model: string): string {
  return MODEL_ALIASES[model] ?? model;
}

/** Exit code meanings from Gemini CLI */
const EXIT_CODE_MESSAGES: Record<number, string> = {
  1: "Gemini CLI returned a general error or API failure",
  42: "Gemini CLI received invalid input (bad prompt or arguments)",
  52: "Gemini CLI configuration error — check $HOME/.gemini/settings.json permissions",
  53: "Gemini CLI turn limit exceeded — break your task into smaller pieces",
};

/** Default timeout: 5 minutes */
const DEFAULT_TIMEOUT_MS = 300_000;

/**
 * Run a prompt headlessly and return the response, session ID, and stats.
 * Uses `--output-format stream-json` to capture the session ID for multi-turn support.
 */
export async function runGemini(
  prompt: string,
  options: GeminiOptions = {}
): Promise<GeminiResult> {
  const args = buildArgs(prompt, options);
  const contextDir = await prepareSystemContext(options.system_context);

  if (contextDir) {
    args.push("--include-directories", contextDir);
  }

  try {
    return await spawnGemini(args, {
      cwd: options.cwd,
      timeoutMs: options.timeout_ms ?? DEFAULT_TIMEOUT_MS,
    });
  } finally {
    if (contextDir) cleanupContextDir(contextDir);
  }
}

/**
 * Run a prompt with piped context (file contents, diffs, logs, etc.).
 * The context is written to the process's stdin.
 */
export async function runGeminiWithContext(
  prompt: string,
  context: string,
  options: GeminiOptions = {}
): Promise<GeminiResult> {
  const args = buildArgs(prompt, options);
  const contextDir = await prepareSystemContext(options.system_context);

  if (contextDir) {
    args.push("--include-directories", contextDir);
  }

  try {
    return await spawnGemini(args, {
      cwd: options.cwd,
      timeoutMs: options.timeout_ms ?? DEFAULT_TIMEOUT_MS,
      stdin: context,
    });
  } finally {
    if (contextDir) cleanupContextDir(contextDir);
  }
}

/**
 * Continue a previous session using `--resume <session_id>`.
 */
export async function resumeGemini(
  sessionId: string,
  prompt: string,
  options: GeminiOptions = {}
): Promise<GeminiResult> {
  const args = buildArgs(prompt, { ...options, session_id: sessionId });
  const contextDir = await prepareSystemContext(options.system_context);

  if (contextDir) {
    args.push("--include-directories", contextDir);
  }

  try {
    return await spawnGemini(args, {
      cwd: options.cwd,
      timeoutMs: options.timeout_ms ?? DEFAULT_TIMEOUT_MS,
    });
  } finally {
    if (contextDir) cleanupContextDir(contextDir);
  }
}

/**
 * Build the CLI argument array for a gemini invocation.
 * Uses `--output-format json` — the JSON format includes session_id at the top level.
 */
function buildArgs(prompt: string, options: GeminiOptions): string[] {
  // Fallback chain: caller → GEMINI_DEFAULT_MODEL env var → gemini-3-flash-preview
  // "auto" is intentionally not the fallback — it routes to cheapest model.
  const defaultModel = process.env.GEMINI_DEFAULT_MODEL ?? "gemini-3-flash-preview";
  const {
    model = defaultModel,
    approval_mode = "yolo",
    sandbox = false,   // Default false: --sandbox sets HOME=/home/node which breaks most setups
    allowed_tools,
    session_id,
  } = options;

  const args: string[] = [
    "--prompt", prompt,
    "--output-format", "json",
    "--model", resolveModel(model),
    "--approval-mode", approval_mode,
  ];

  if (sandbox) {
    args.push("--sandbox");
  }

  if (session_id) {
    args.push("--resume", session_id);
  }

  if (allowed_tools && allowed_tools.length > 0) {
    args.push("--allowed-tools", allowed_tools.join(","));
  }

  return args;
}

/**
 * Write system context to a temporary GEMINI.md file.
 * Returns the temp directory path, or null if no context is needed.
 *
 * Priority: per-call `system_context` > `GEMINI_SYSTEM_MD` env var > none
 */
async function prepareSystemContext(
  systemContext?: string
): Promise<string | null> {
  // Per-call context takes priority
  let content = systemContext;

  // Fall back to env var pointing to a default GEMINI.md file
  if (!content) {
    const envPath = process.env.GEMINI_SYSTEM_MD;
    if (envPath && existsSync(envPath)) {
      content = readFileSync(envPath, "utf-8");
    }
  }

  if (!content) return null;

  const tempDir = join("/tmp", `gemini-mcp-${randomUUID()}`);
  mkdirSync(tempDir, { recursive: true });
  writeFileSync(join(tempDir, "GEMINI.md"), content, "utf-8");
  return tempDir;
}

/**
 * Remove the temporary context directory.
 */
function cleanupContextDir(dir: string): void {
  try {
    rmSync(dir, { recursive: true, force: true });
  } catch {
    // Best-effort cleanup — don't throw
  }
}

/**
 * Normalize Gemini CLI stats into a flat structure.
 *
 * The real CLI outputs nested per-model breakdowns:
 *   stats.models["gemini-3-flash-preview"].tokens.{ input, candidates, total, cached }
 *   stats.models["gemini-3-flash-preview"].api.{ totalLatencyMs }
 *
 * Aggregate these into the flat GeminiStats fields so callers always get
 * total_tokens, input_tokens, output_tokens, cached, and duration_ms at the top level.
 */
function normalizeStats(raw: Record<string, unknown> | undefined): import("./types.js").GeminiStats {
  if (!raw) return {};

  // Aggregate across all models (there's usually only one, but handle multiple)
  let totalTokens = 0, inputTokens = 0, outputTokens = 0, cachedTokens = 0, latencyMs = 0;
  const models = raw.models as Record<string, Record<string, Record<string, number>>> | undefined;

  if (models) {
    for (const model of Object.values(models)) {
      const tokens = model.tokens ?? {};
      const api = model.api ?? {};
      totalTokens  += tokens.total      ?? tokens.totalTokens   ?? 0;
      inputTokens  += tokens.input      ?? tokens.inputTokens   ?? tokens.prompt ?? 0;
      outputTokens += tokens.candidates ?? tokens.outputTokens  ?? 0;
      cachedTokens += tokens.cached     ?? 0;
      latencyMs    += (api as Record<string, number>).totalLatencyMs ?? 0;
    }
  }

  return {
    // Flat aggregate fields (populated from models breakdown)
    total_tokens:  totalTokens  || (raw.total_tokens  as number)  || undefined,
    input_tokens:  inputTokens  || (raw.input_tokens  as number)  || undefined,
    output_tokens: outputTokens || (raw.output_tokens as number)  || undefined,
    cached:        cachedTokens || (raw.cached        as number)  || undefined,
    duration_ms:   latencyMs    || (raw.duration_ms   as number)  || undefined,
    tool_calls:    (raw.tool_calls as number) || undefined,
    // Keep raw nested breakdown for full detail
    models:        raw.models as Record<string, unknown> | undefined,
    tools:         raw.tools,
    files:         raw.files,
  };
}

interface SpawnOptions {
  cwd?: string;
  timeoutMs: number;
  stdin?: string;
}

/**
 * Spawn the gemini binary with `--output-format json`, collect stdout, and parse result.
 *
 * The JSON output format returns a single object:
 *   { session_id: string, response: string, stats: { models: {...}, tools: {...}, files: {...} } }
 *
 * Note: Gemini CLI writes MCP status lines and other non-JSON output to stderr.
 * We capture stdout only and strip any stray non-JSON prefix lines.
 */
async function spawnGemini(
  args: string[],
  { cwd, timeoutMs, stdin }: SpawnOptions
): Promise<GeminiResult> {
  const binary = process.env.GEMINI_BINARY ?? "gemini";

  if (cwd !== undefined && !existsSync(cwd)) {
    throw new Error(`cwd does not exist: ${cwd}`);
  }

  return new Promise((resolve, reject) => {
    const proc = spawn(binary, args, {
      cwd: cwd ?? process.cwd(),
      stdio: ["pipe", "pipe", "pipe"],
      // Pass through HOME so Gemini CLI finds ~/.gemini/settings.json correctly
      env: { ...process.env },
    });

    // Write piped context to stdin if provided
    if (stdin !== undefined) {
      proc.stdin.write(stdin, "utf-8");
    }
    proc.stdin.end();

    let stdoutBuf = "";
    let stderrOutput = "";

    proc.stdout.on("data", (chunk: Buffer) => {
      stdoutBuf += chunk.toString("utf-8");
    });

    proc.stderr.on("data", (chunk: Buffer) => {
      stderrOutput += chunk.toString("utf-8");
    });

    const timer = setTimeout(() => {
      proc.kill("SIGTERM");
      reject(new Error(`Gemini CLI timed out after ${timeoutMs}ms`));
    }, timeoutMs);

    proc.on("close", (code) => {
      clearTimeout(timer);

      if (code === 0) {
        // Find the JSON object in stdout (skip any prefix status lines)
        const jsonStart = stdoutBuf.indexOf("{");
        if (jsonStart === -1) {
          reject(new Error("Gemini CLI returned no JSON output"));
          return;
        }
        try {
          const parsed = JSON.parse(stdoutBuf.slice(jsonStart));
          resolve({
            response: parsed.response ?? "",
            session_id: parsed.session_id ?? "",
            stats: normalizeStats(parsed.stats),
          });
        } catch {
          reject(new Error(`Failed to parse Gemini CLI output: ${stdoutBuf.slice(0, 200)}`));
        }
      } else {
        const message =
          EXIT_CODE_MESSAGES[code ?? 1] ??
          `Gemini CLI exited with code ${code}`;
        const detail = stderrOutput.trim()
          ? `\nDetails: ${stderrOutput.trim()}`
          : "";
        reject(new Error(`${message}${detail}`));
      }
    });

    proc.on("error", (err) => {
      clearTimeout(timer);
      if ((err as NodeJS.ErrnoException).code === "ENOENT") {
        reject(
          new Error(
            `Gemini CLI not found. Install it with: npm install -g @google/gemini-cli\n` +
            `Or set GEMINI_BINARY to the path of the gemini binary.`
          )
        );
      } else {
        reject(err);
      }
    });
  });
}
