
import { describe, it, expect, afterAll } from "bun:test";
import { resolve } from "path";
import { runGemini } from "../src/gemini.js";
import { writeFileSync, chmodSync, rmSync } from "fs";

const FAKE_BINARY = resolve(import.meta.dir, "fake-gemini-junk.sh");

describe("spawnGemini with trailing junk", () => {
  afterAll(() => {
    delete process.env.GEMINI_BINARY;
    try { rmSync(FAKE_BINARY); } catch {}
  });

  it("should fail if there is trailing junk after JSON", async () => {
    writeFileSync(FAKE_BINARY, `#!/usr/bin/env bash
echo '{"session_id":"fake","response":"ok","stats":{}}'
echo "Extra junk"
exit 0
`, "utf-8");
    chmodSync(FAKE_BINARY, 0o755);

    process.env.GEMINI_BINARY = FAKE_BINARY;
    
    // This is expected to fail with the current implementation
    await expect(runGemini("test")).rejects.toThrow(/Failed to parse Gemini CLI output/);
  });
});
