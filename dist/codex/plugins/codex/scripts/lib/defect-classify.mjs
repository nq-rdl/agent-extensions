// SPDX-License-Identifier: Apache-2.0
// SPDX-FileCopyrightText: 2026 nq-rdl

// The classification guard. Deliberately an ALLOWLIST of usage and environment
// causes: everything unrecognised falls through to "candidate-defect" so the
// guard fails toward a human review rather than toward silence. A denylist of
// known-benign strings was tried first and failed open on the very first real
// error encountered (a consumed OAuth refresh token).

const USAGE_AND_ENVIRONMENT = [
  {
    cause: "codex-missing",
    pattern: /Codex CLI is not installed/i,
    remedy: "Install the Codex CLI (`npm install -g @openai/codex`), then run `/codex:setup`."
  },
  {
    cause: "flag-misuse",
    pattern: /Choose either --|requires a job id/i,
    remedy: "Re-run with only one of the conflicting flags, or supply the required job id."
  },
  {
    cause: "unsupported-review-target",
    pattern: /is not supported by the built-in reviewer/i,
    remedy: "Retry with `/codex:adversarial-review` for custom targeting."
  },
  {
    cause: "job-already-running",
    pattern: /is still running\. Use \/codex:status/i,
    remedy: "Wait for the running job, or cancel it with `/codex:cancel`."
  },
  {
    cause: "nothing-to-resume",
    pattern: /No previous Codex task thread was found/i,
    remedy: "Start a fresh run instead of resuming."
  },
  {
    cause: "no-prompt",
    pattern: /Provide a prompt, a prompt file, piped stdin|A prompt is required for this Codex run/i,
    remedy: "Supply a prompt, a prompt file, or piped stdin."
  },
  {
    cause: "git-environment",
    pattern: /git is not installed|must run inside a Git repository/i,
    remedy: "Install Git, or run the command inside a Git repository."
  },
  {
    cause: "transfer-source",
    pattern: /Could not identify the current Claude transcript|Claude session (source must be|file not found)|can import Claude sessions only from/i,
    remedy: "Pass a valid `--source <path-to-claude-jsonl>`."
  },
  {
    cause: "rate-limit",
    // Both bare tokens here are fail-opens, and this is the one verdict that
    // discards the marker outright. A bare `\b429\b` matches a stack-frame
    // column number (e.g. "codex.mjs:429:12") or a JSON.parse error offset
    // (V8's "... in JSON at position 429") just as readily as an HTTP 429. A
    // bare `\bquota\b` is worse: `message` carries user-supplied git refs and
    // raw git stderr through formatCommandFailure, so a `--base quota-fix` or
    // a checkout under `/srv/quota/` would discard a genuine crash as "wait
    // for the limit to reset". Both tokens therefore require adjacent limit
    // language. `insufficient_quota` is spelled out because `_` is a word
    // character, so `\bquota\b` never fires inside OpenAI's error code.
    pattern:
      /rate limit|usage limit|insufficient_quota|\b(?:exceeded|exhausted|insufficient|out of)\b[^.\n]{0,32}\bquota\b|\bquota\b[^.\n]{0,32}\b(?:exceeded|exhausted|reached)\b|\b(?:status(?: code)?|http)\s+429\b/i,
    remedy: "Wait for the limit to reset and retry."
  }
];

// Auth is special: it is only benign if the readiness check agrees, so it is
// the one verdict a marker cannot settle alone. resolveAuthCrossCheck turns it
// into a terminal verdict; codex-defects.mjs applies it against a live setup
// probe, so no caller ever surfaces "needs-cross-check".
//
// A bare `\b401\b` carries the same fail-open as the bare `\b429\b` rejected
// above, and for the same reason: stderrTail is a V8 stack, so it matches any
// frame at line or column 401 — reachable in lib/codex.mjs, codex-companion.mjs
// and lib/render.mjs alike — as well as V8's "... in JSON at position 401".
// Require the same explicit status-code context. Genuine 401s still match on
// `unauthorized`, which every real "401 Unauthorized" carries.
const AUTH_PATTERN =
  /refresh token|access token|log ?out and sign in|not logged in|unauthorized|\b(?:status(?: code)?|http)\s+401\b/i;

export function classifyDefect({ message = "", stderrTail = "" } = {}) {
  const haystack = `${typeof message === "string" ? message : ""}\n${
    typeof stderrTail === "string" ? stderrTail : ""
  }`;

  for (const rule of USAGE_AND_ENVIRONMENT) {
    if (rule.pattern.test(haystack)) {
      return {
        verdict: "not-a-defect",
        cause: rule.cause,
        remedy: rule.remedy,
        needsSetupCrossCheck: false
      };
    }
  }

  if (AUTH_PATTERN.test(haystack)) {
    return {
      verdict: "needs-cross-check",
      cause: "auth",
      remedy: "Pending the `/codex:setup` readiness cross-check — `/codex:report-defect` resolves it before reporting.",
      needsSetupCrossCheck: true
    };
  }

  return {
    verdict: "candidate-defect",
    cause: "unclassified",
    remedy: "Report via `/codex:report-defect`.",
    needsSetupCrossCheck: false
  };
}

export function resolveAuthCrossCheck(setupReady) {
  if (setupReady) {
    return {
      verdict: "candidate-defect",
      cause: "readiness-check-disagreement",
      remedy:
        "Report this: every Codex turn fails on auth while the readiness check reports ready, so the check is validating stored credentials rather than a usable token.",
      needsSetupCrossCheck: false
    };
  }

  return {
    verdict: "not-a-defect",
    cause: "auth",
    remedy: "Re-authenticate with `codex login`, then confirm with `/codex:setup`.",
    needsSetupCrossCheck: false
  };
}
