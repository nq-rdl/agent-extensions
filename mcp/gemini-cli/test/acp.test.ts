/**
 * Unit tests for ACP (Agent Communication Protocol) persistent sessions.
 *
 * Uses fake-gemini-acp.sh as the test double — a long-running process that
 * speaks JSON-RPC 2.0 over stdin/stdout, controlled via FAKE_ACP_SCENARIO.
 */

import { describe, it, expect, afterEach, afterAll } from "bun:test";
import { resolve } from "path";
import { acpAsk, acpShutdownAll, acpGetSession } from "../src/acpClient.js";

const FAKE_ACP_BINARY = resolve(import.meta.dir, "fake-gemini-acp.sh");

function useFakeAcp(scenario = "success") {
  process.env.GEMINI_BINARY = FAKE_ACP_BINARY;
  process.env.FAKE_ACP_SCENARIO = scenario;
}

afterEach(async () => {
  await acpShutdownAll();
});

afterAll(() => {
  delete process.env.GEMINI_BINARY;
  delete process.env.FAKE_ACP_SCENARIO;
});

describe("acpAsk", () => {
  it("returns answer and turn number on first call", async () => {
    useFakeAcp("success");
    const result = await acpAsk("What is 2+2?", {});
    expect(result.answer).toContain("Fake ACP response for turn 1");
    expect(result.session_id).toBe("fake-acp-session-001");
    expect(result.turn).toBe(1);
    expect(result.usage).toBeDefined();
    expect(result.usage.totalTokens).toBe(40);
  });

  it("maintains turn counter across calls", async () => {
    useFakeAcp("success");
    const r1 = await acpAsk("First question", {});
    expect(r1.turn).toBe(1);

    const r2 = await acpAsk("Follow up", {});
    expect(r2.turn).toBe(2);
    expect(r2.session_id).toBe("fake-acp-session-001");
  });

  it("supports named sessions", async () => {
    useFakeAcp("success");
    const r1 = await acpAsk("Question for supervisor", { session_name: "supervisor" });
    expect(r1.turn).toBe(1);
    expect(r1.session_id).toBe("fake-acp-session-001");

    // Different named session gets its own subprocess
    const r2 = await acpAsk("Question for checker", { session_name: "checker" });
    expect(r2.turn).toBe(1); // new session starts at turn 1
  });

  it("reuses same session for default name", async () => {
    useFakeAcp("success");
    await acpAsk("First", {});
    const session = acpGetSession("default");
    expect(session).toBeDefined();
    expect(session!.turn).toBe(1);

    await acpAsk("Second", {});
    expect(acpGetSession("default")!.turn).toBe(2);
  });

  it("prepends context to question when provided", async () => {
    useFakeAcp("success");
    const result = await acpAsk("Does this match?", { context: "Some context data" });
    expect(result.answer).toBeTruthy();
    expect(result.turn).toBe(1);
  });

  it("throws on JSON-RPC error response", async () => {
    useFakeAcp("error");
    await expect(acpAsk("Will fail", {})).rejects.toThrow(/Model unavailable/i);
  });
});

describe("acpShutdownAll", () => {
  it("cleans up all sessions", async () => {
    useFakeAcp("success");
    await acpAsk("Create session", {});
    expect(acpGetSession("default")).toBeDefined();

    await acpShutdownAll();
    expect(acpGetSession("default")).toBeUndefined();
  });
});
