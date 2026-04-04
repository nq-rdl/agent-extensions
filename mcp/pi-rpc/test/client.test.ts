import { afterEach, describe, expect, it } from "bun:test";

const originalFetch = globalThis.fetch;
const originalServerUrl = process.env.PI_SERVER_URL;

function restoreEnv() {
  if (originalServerUrl === undefined) {
    delete process.env.PI_SERVER_URL;
    return;
  }

  process.env.PI_SERVER_URL = originalServerUrl;
}

async function loadClientModule(tag: string) {
  return import(`../src/client.ts?${tag}`);
}

afterEach(() => {
  globalThis.fetch = originalFetch;
  restoreEnv();
});

describe("pi-rpc client", () => {
  it("posts Create requests to the default endpoint", async () => {
    delete process.env.PI_SERVER_URL;

    const calls: Array<{ input: string | URL | Request; init?: RequestInit }> = [];
    globalThis.fetch = (async (input: string | URL | Request, init?: RequestInit) => {
      calls.push({ input, init });
      return new Response(
        JSON.stringify({ sessionId: "sess-1", state: "SESSION_STATE_IDLE" }),
        { status: 200, headers: { "Content-Type": "application/json" } }
      );
    }) as unknown as typeof fetch;

    const { piCreate } = await loadClientModule(`default-${Date.now()}`);
    const result = await piCreate("openai-codex", "gpt-5.4", "/tmp/project", "low");

    expect(result).toEqual({ sessionId: "sess-1", state: "SESSION_STATE_IDLE" });
    expect(calls).toHaveLength(1);
    expect(calls[0]?.input).toBe("http://localhost:4097/pirpc.v1.SessionService/Create");
    expect(calls[0]?.init?.method).toBe("POST");
    expect(calls[0]?.init?.headers).toEqual({ "Content-Type": "application/json" });
    expect(calls[0]?.init?.body).toBe(
      JSON.stringify({
        provider: "openai-codex",
        model: "gpt-5.4",
        cwd: "/tmp/project",
        thinkingLevel: "low",
      })
    );
  });

  it("normalizes a custom server URL before posting", async () => {
    process.env.PI_SERVER_URL = "http://pi.example.test:5000/";

    const calls: Array<{ input: string | URL | Request; init?: RequestInit }> = [];
    globalThis.fetch = (async (input: string | URL | Request, init?: RequestInit) => {
      calls.push({ input, init });
      return new Response(JSON.stringify({ sessions: [] }), {
        status: 200,
        headers: { "Content-Type": "application/json" },
      });
    }) as unknown as typeof fetch;

    const { piList } = await loadClientModule(`custom-${Date.now()}`);
    const result = await piList();

    expect(result).toEqual({ sessions: [] });
    expect(calls).toHaveLength(1);
    expect(calls[0]?.input).toBe("http://pi.example.test:5000/pirpc.v1.SessionService/List");
    expect(calls[0]?.init?.body).toBe("{}");
  });

  it("includes the response body when requests fail", async () => {
    delete process.env.PI_SERVER_URL;

    globalThis.fetch = (async () => {
      return new Response("backend offline", { status: 503, statusText: "Service Unavailable" });
    }) as unknown as typeof fetch;

    const { piPrompt } = await loadClientModule(`error-${Date.now()}`);

    await expect(piPrompt("sess-1", "hello")).rejects.toThrow(
      "pi-rpc Prompt failed (503): backend offline"
    );
  });
});
