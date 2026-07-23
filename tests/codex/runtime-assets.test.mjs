import fs from "node:fs";
import path from "node:path";
import test from "node:test";
import assert from "node:assert/strict";
import { fileURLToPath } from "node:url";

import { loadPromptTemplate, interpolateTemplate } from "../../plugins/codex/scripts/lib/prompts.mjs";

const ROOT = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..", "..");
const PLUGIN_ROOT = path.join(ROOT, "plugins", "codex");
const SCHEMA_PATH = path.join(PLUGIN_ROOT, "schemas", "review-output.schema.json");

test("adversarial-review prompt template loads and frames a challenge review", () => {
  const template = loadPromptTemplate(PLUGIN_ROOT, "adversarial-review");
  assert.ok(template.trim().length > 0, "template must not be empty");
  assert.match(template, /adversarial/i);
});

test("stop-review-gate prompt interpolates the Claude response block", () => {
  const template = loadPromptTemplate(PLUGIN_ROOT, "stop-review-gate");
  assert.match(template, /\{\{CLAUDE_RESPONSE_BLOCK\}\}/, "placeholder must be present pre-interpolation");

  const filled = interpolateTemplate(template, { CLAUDE_RESPONSE_BLOCK: "PREV-TURN-MARKER" });
  assert.match(filled, /PREV-TURN-MARKER/);
  assert.doesNotMatch(filled, /\{\{CLAUDE_RESPONSE_BLOCK\}\}/, "placeholder must be consumed");
});

test("review-output schema is valid JSON with the expected review contract", () => {
  const schema = JSON.parse(fs.readFileSync(SCHEMA_PATH, "utf8"));
  assert.equal(schema.type, "object");
  assert.deepEqual(schema.required, ["verdict", "summary", "findings", "next_steps"]);
});
