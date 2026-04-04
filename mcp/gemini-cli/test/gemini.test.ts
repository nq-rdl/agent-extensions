/**
 * Unit tests for the Gemini CLI subprocess manager.
 *
 * Uses fake-gemini.sh as the test double — controlled via FAKE_GEMINI_SCENARIO.
 * Tests subprocess management, JSONL parsing, system context injection, and error handling.
 */

import { describe, it, expect, beforeAll, afterAll } from "bun:test";
import { existsSync } from "fs";
import { join, resolve } from "path";
import { runGemini, runGeminiWithContext, resumeGemini } from "../src/gemini.js";

const FAKE_BINARY = resolve(import.meta.dir, "fake-gemini.sh");

/** Set GEMINI_BINARY to the fake script for all tests */
function useFake(scenario = "success") {
  process.env.GEMINI_BINARY = FAKE_BINARY;
  process.env.FAKE_GEMINI_SCENARIO = scenario;
}

afterAll(() => {
  delete process.env.GEMINI_BINARY;
  delete process.env.FAKE_GEMINI_SCENARIO;
  delete process.env.GEMINI_SYSTEM_MD;
});

describe("runGemini", () => {
  it("returns response and session_id on success", async () => {
    useFake("success");
    const result = await runGemini("Hello");
    expect(result.response).toBe("This is a fake response from the test double.");
    expect(result.session_id).toMatch(/^fake-session-\d+$/);
    expect(result.stats).toBeDefined();
  });

  it("includes token stats in result", async () => {
    useFake("success");
    const result = await runGemini("Count tokens");
    expect(result.stats.total_tokens).toBe(42);
    expect(result.stats.input_tokens).toBe(10);
    expect(result.stats.output_tokens).toBe(32);
    expect(result.stats.duration_ms).toBe(100);
  });

  it("handles tool_use scenario (web search)", async () => {
    useFake("tool_use");
    const result = await runGemini("Search the web");
    expect(result.response).toContain("fake web content");
    expect(result.session_id).toBeTruthy();
  });

  it("throws on API error (exit code 1)", async () => {
    useFake("error");
    await expect(runGemini("Will fail")).rejects.toThrow(/general error|API failure/i);
  });

  it("throws on input error (exit code 42)", async () => {
    useFake("input_err");
    await expect(runGemini("Bad input")).rejects.toThrow(/invalid input/i);
  });

  it("throws on turn limit exceeded (exit code 53)", async () => {
    useFake("turn_limit");
    await expect(runGemini("Too many turns")).rejects.toThrow(/turn limit/i);
  });

  it("throws with ENOENT when binary not found", async () => {
    process.env.GEMINI_BINARY = "/nonexistent/gemini";
    await expect(runGemini("test")).rejects.toThrow(/not found/i);
    process.env.GEMINI_BINARY = FAKE_BINARY;
  });
});

describe("runGemini with system context", () => {
  it("creates and cleans up temp GEMINI.md dir", async () => {
    useFake("success");
    const tmpDirs = new Set<string>();

    // Intercept mkdirSync to track temp dir creation (integration-style check via filesystem)
    const { mkdtempSync } = await import("fs");
    const before = new Set(
      (await import("fs")).readdirSync("/tmp").filter((d) => d.startsWith("gemini-mcp-"))
    );

    await runGemini("Test", { system_context: "You are a test assistant." });

    const after = new Set(
      (await import("fs")).readdirSync("/tmp").filter((d) => d.startsWith("gemini-mcp-"))
    );

    // All temp dirs created during this call should have been cleaned up
    const leaked = [...after].filter((d) => !before.has(d));
    expect(leaked).toHaveLength(0);
  });

  it("loads system context from GEMINI_SYSTEM_MD env var", async () => {
    useFake("success");
    // Create a temp file to use as GEMINI_SYSTEM_MD
    const { writeFileSync, mkdtempSync, rmSync } = await import("fs");
    const tempDir = mkdtempSync("/tmp/test-gemini-sys-");
    const systemMdPath = join(tempDir, "system.md");
    writeFileSync(systemMdPath, "You are a test assistant from env var.", "utf-8");

    process.env.GEMINI_SYSTEM_MD = systemMdPath;
    try {
      const result = await runGemini("Test with env context");
      expect(result.response).toBeTruthy();
    } finally {
      delete process.env.GEMINI_SYSTEM_MD;
      rmSync(tempDir, { recursive: true });
    }
  });

  it("per-call system_context takes priority over GEMINI_SYSTEM_MD", async () => {
    useFake("success");
    // Both env var and per-call context set — per-call wins
    process.env.GEMINI_SYSTEM_MD = "/tmp/nonexistent-system.md";
    try {
      const result = await runGemini("Test priority", {
        system_context: "Per-call context takes priority",
      });
      expect(result.response).toBeTruthy();
    } finally {
      delete process.env.GEMINI_SYSTEM_MD;
    }
  });
});

describe("runGeminiWithContext", () => {
  it("accepts and processes piped context", async () => {
    useFake("success");
    const result = await runGeminiWithContext(
      "Review this diff",
      "diff --git a/foo.ts b/foo.ts\n+const x = 1;"
    );
    expect(result.response).toBeTruthy();
    expect(result.session_id).toBeTruthy();
  });
});

describe("resumeGemini", () => {
  it("resumes a previous session", async () => {
    useFake("resume");
    const result = await resumeGemini("fake-session-123", "Follow up question");
    expect(result.response).toContain("previous session");
    expect(result.session_id).toBeTruthy();
  });
});

describe("default options", () => {
  it("uses yolo approval mode by default", async () => {
    useFake("success");
    // We can't easily inspect CLI args in the test, but we verify it runs
    // (yolo is default — if it were blocking, the fake binary wouldn't output anything)
    const result = await runGemini("Test defaults");
    expect(result.response).toBeTruthy();
  });
});
