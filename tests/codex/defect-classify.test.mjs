// SPDX-License-Identifier: Apache-2.0

import test from "node:test";
import assert from "node:assert/strict";

import { classifyDefect, resolveAuthCrossCheck } from "../../plugins/codex/scripts/lib/defect-classify.mjs";

// Messages taken verbatim from the throw sites they represent.
const NOT_A_DEFECT = [
  ["codex-companion.mjs:265", "Codex CLI is not installed or is missing required runtime support."],
  ["codex-companion.mjs:232", "Choose either --enable-review-gate or --disable-review-gate."],
  ["codex-companion.mjs:790", "Choose either --resume/--resume-last or --fresh."],
  ["codex-companion.mjs:913", "`status --wait` requires a job id."],
  ["codex-companion.mjs:290", "This `/codex:review` target is not supported by the built-in reviewer."],
  ["codex-companion.mjs:353", "Task task-abc is still running. Use /codex:status before continuing it."],
  ["codex-companion.mjs:486", "No previous Codex task thread was found for this repository."],
  ["codex-companion.mjs:492", "Provide a prompt, a prompt file, piped stdin, or use --resume-last."],
  ["lib/codex.mjs:1129", "A prompt is required for this Codex run."],
  ["lib/git.mjs:82", "git is not installed. Install Git and retry."],
  ["lib/git.mjs:85", "This command must run inside a Git repository."],
  ["lib/claude-session-transfer.mjs:37", "Claude session file not found: /tmp/x.jsonl"]
];

for (const [site, message] of NOT_A_DEFECT) {
  test(`${site} is not a defect`, () => {
    assert.equal(classifyDefect({ message }).verdict, "not-a-defect");
  });
}

const CANDIDATE_DEFECT = [
  ["codex-companion.mjs:854", "Missing required --job-id for task-worker."],
  ["codex-companion.mjs:861", "No stored job found for task-abc."],
  ["codex-companion.mjs:866", "Stored job task-abc is missing its task request payload."],
  ["codex-companion.mjs:1075", "Unknown subcommand: taks"],
  ["lib/args.mjs:39", "Missing value for --model"],
  ["lib/app-server.mjs:88", "codex app-server client is closed."],
  ["lib/app-server.mjs:329", "codex app-server broker connection is not connected."],
  ["lib/broker-endpoint.mjs:40", "Unsupported broker endpoint: tcp://nope"],
  ["unanticipated", "TypeError: Cannot read properties of undefined (reading 'threadId')"]
];

for (const [site, message] of CANDIDATE_DEFECT) {
  test(`${site} is a candidate defect`, () => {
    assert.equal(classifyDefect({ message }).verdict, "candidate-defect");
  });
}

test("an unrecognised message defaults to candidate, not to not-a-defect", () => {
  const verdict = classifyDefect({ message: "something nobody has ever seen before" });

  assert.equal(verdict.verdict, "candidate-defect");
  assert.equal(verdict.cause, "unclassified");
});

test("the observed auth failure defers to a setup cross-check", () => {
  const verdict = classifyDefect({
    message:
      "Your access token could not be refreshed because your refresh token was already used. Please log out and sign in again."
  });

  assert.equal(verdict.verdict, "needs-cross-check");
  assert.equal(verdict.cause, "auth");
  assert.equal(verdict.needsSetupCrossCheck, true);
});

test("rate limiting is not a defect", () => {
  const rateLimitMessage = classifyDefect({ message: "429 rate limit exceeded" });
  assert.equal(rateLimitMessage.verdict, "not-a-defect");
  assert.equal(rateLimitMessage.cause, "rate-limit");

  const usageLimitMessage = classifyDefect({ message: "You have hit your usage limit." });
  assert.equal(usageLimitMessage.verdict, "not-a-defect");
  assert.equal(usageLimitMessage.cause, "rate-limit");
});

test("a bare 429 with status-code context is a rate limit, not a defect", () => {
  const httpForm = classifyDefect({ message: "Request failed: HTTP 429" });
  assert.equal(httpForm.verdict, "not-a-defect");
  assert.equal(httpForm.cause, "rate-limit");

  const statusCodeForm = classifyDefect({ message: "Request failed with status code 429" });
  assert.equal(statusCodeForm.verdict, "not-a-defect");
  assert.equal(statusCodeForm.cause, "rate-limit");
});

test("a bare 429 without status-code context is a candidate defect, not a rate limit", () => {
  // A stack-frame column number can contain "429" with no HTTP status in
  // sight; the rate-limit rule must not fire on it.
  const stackFrame = classifyDefect({
    message: "TypeError: Cannot read properties of undefined\n    at run (/x/codex.mjs:429:12)"
  });
  assert.equal(stackFrame.verdict, "candidate-defect");
  assert.notEqual(stackFrame.cause, "rate-limit");

  // V8's JSON.parse error message embeds a character offset, not a status code.
  const jsonOffset = classifyDefect({ message: "Unexpected token < in JSON at position 429" });
  assert.equal(jsonOffset.verdict, "candidate-defect");
  assert.notEqual(jsonOffset.cause, "rate-limit");
});

test("classifyDefect also inspects the stderr tail", () => {
  const verdict = classifyDefect({ message: "", stderrTail: "codex error: git is not installed. Install Git and retry." });

  assert.equal(verdict.verdict, "not-a-defect");
});

test("auth cross-check: setup reporting ready makes the readiness check the defect", () => {
  const ready = resolveAuthCrossCheck(true);
  assert.equal(ready.verdict, "candidate-defect");
  assert.equal(ready.cause, "readiness-check-disagreement");

  const notReady = resolveAuthCrossCheck(false);
  assert.equal(notReady.verdict, "not-a-defect");
  assert.equal(notReady.cause, "auth");
  assert.match(notReady.remedy, /\/codex:setup/);
});

test("classifyDefect tolerates missing and non-string input", () => {
  assert.equal(classifyDefect().verdict, "candidate-defect");
  assert.equal(classifyDefect({ message: null, stderrTail: undefined }).verdict, "candidate-defect");
});
