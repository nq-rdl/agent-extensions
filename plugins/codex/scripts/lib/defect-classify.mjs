// SPDX-License-Identifier: Apache-2.0

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
    pattern: /rate limit|usage limit|\bquota\b|\b429\b/i,
    remedy: "Wait for the limit to reset and retry."
  }
];

// Auth is special: it is only benign if the readiness check agrees. See
// resolveAuthCrossCheck.
const AUTH_PATTERN =
  /refresh token|access token|log ?out and sign in|not logged in|unauthorized|\b401\b/i;

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
      remedy: "Run `codex-companion.mjs setup --json` and apply resolveAuthCrossCheck.",
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
        "Report this: every Codex turn fails on auth while the readiness check reports ready, so the check is validating stored credentials rather than a usable token."
    };
  }

  return {
    verdict: "not-a-defect",
    cause: "auth",
    remedy: "Re-authenticate with `codex login`, then confirm with `/codex:setup`."
  };
}
