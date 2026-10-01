# Codex live integration pilot (#430)

Follow-up to the [stubbed family review](codex.md), #312 and #320. Recorded
2026-09-30, 22:14–22:18 UTC at source revision
`c64b3c1371ebc0c6112004baafbf94fa499443ea`. No runtime code or model-tier
policy changed; #201 remains separate. Two distinguishing persisted probes
were added on 2026-10-01 at `c1986ff6`, using the same CLI/runtime versions.
Human question answers/cancellation remain unexecuted: [follow-up #475](https://github.com/nq-rdl/agent-extensions/issues/475).

## Protocol and evidence boundaries

Before editing skills, run the installed companion against live Codex with:
no model, a configured default, a native-review override, and an adversarial
control. Exercise explicit resume, cancellation and unavailable interaction.
A human answering or cancelling a Claude question is unavailable in this
headless session: record that gap, never substitute scripted prompt text for
an actual answer.

Versions for **every case below**: Linux, Node v22.23.1, Codex CLI 0.159.1,
Claude Code 2.1.286, companion from the source revision above (marketplace
manifest 0.36.2; vendored upstream v1.0.6/db52e28 plus catalog changes).
Codex used authenticated ChatGPT sign-in. Claude used `claude-sonnet-5`.

All live working directories were disposable git repositories under
`/tmp/pi-issue-430/<case>/repo`, with one committed `value.js` exporting `1`
and an uncommitted change to `2`. Each case had a private `CODEX_HOME` with
only a copy of authentication and the specified `config.toml`, and a private
`CLAUDE_PLUGIN_DATA`. The resume case reused its own configured repository
and completed thread. No live Codex ran against the catalog checkout.

An observational Node wrapper forwarded the real Codex binary unchanged,
recording app-server JSONL requests/responses to scratch files. It did not
invent responses or answer questions. Requests used `approvalPolicy: never`
and read-only sandboxes. Model evidence comes from `thread/start` responses,
`turn_context` session metadata, or a backend rejection, **not from asking
the model its name**. Native reviews spawn a separate reviewer: the parent
thread model is not proof of the reviewer model.

Scratch logs and authentication were kept outside the checkout and are removed
after delivery; only trimmed, non-secret evidence is recorded here. A CLI warning about inability to create
PATH helper aliases under `/tmp` did not prevent completion. Fresh Codex homes
also acquired CLI-managed plugin/cache files; these were not catalog installs.
There were 15 top-level live invocations (13 Codex runs, including one rejected
model and one interrupted turn, and two Claude runs). Availability, candidate,
status and cancel commands are not additional model requests. One run per
case: this is a small integration check, not a reliability benchmark.

## Commands, actual models and responses

Below, `C` is the absolute path to `plugins/codex/scripts/codex-companion.mjs`
in this worktree, `P` is the absolute path to `plugins/codex`, and `Q` is:
`Reply exactly PILOT_OK. Do not use tools or change files.`
All commands execute inside the disposable repository, with the private homes
above; review arguments are intentionally passed as **one string**.

| Case | Config and command | Actual model evidence | Response / outcome |
|---|---|---|---|
| absent | Empty config; `node "$C" task "$Q" --json` | `thread/start.result.model` and session `turn_context.model`: `gpt-6.1-sol` | `status: 0`, `rawOutput: PILOT_OK`, `touchedFiles: []` |
| configured | `model = "gpt-5.6-luna"`; same task command, no model flag | Response and turn context: `gpt-5.6-luna` | Same successful `PILOT_OK` |
| native-default | Luna config; `node "$C" review '--wait --json'` | Parent Luna; actual ephemeral reviewer **not exposed** | Status 0: “The change only updates the exported constant from 1 to 2, with no repository evidence indicating this violates an expected behavior.” |
| native-override | Luna config plus `review_model = "gpt-5.6-sol"`; `node "$C" review '--wait --model luna --json'` | Parent Luna; actual ephemeral reviewer **not exposed** | Status 0: “The only change updates the exported constant from 1 to 2, with no evidence of affected callers, tests, or repository-specific invariants.” |
| adversarial-override | Same Sol review override; `node "$C" adversarial-review '--wait --model luna --json'` | Thread response Luna; ordinary `turn/start.model: gpt-5.6-luna` | `verdict: approve`, `findings: []`; “No substantive, repository-grounded risk identified…” |
| native-persist | Same override; `node probe-review.mjs` (recipe below) | **Reviewer** turn context: `gpt-5.6-sol`, source `subagent: review`; parent Luna | “The only change updates an exported constant from 1 to 2. No concrete defect or affected invariant is evident…” |
| native-persist-explicit-luna (originally native-persist-default) | Luna config without review override; probe explicitly sets session model Luna, matching config | Reviewer turn context: `gpt-5.6-luna`; does not distinguish config default from explicit selection | “The change only updates the exported constant from 1 to 2, with no apparent correctness issue…” |
| native-config-null | Luna config, no `review_model`; `node probe-review.mjs null` | `thread/start.model: null`; parent and reviewer child resolve to `gpt-5.6-luna` | Exit 0: “The change only updates the exported constant from 1 to 2, with no identifiable correctness issue in the available repository context.” |
| native-explicit-terra | Luna config, no `review_model`; `node probe-review.mjs gpt-5.6-terra` | Explicit session Terra; parent and reviewer child: `gpt-5.6-terra`, not configured Luna | Exit 0: “The sole change updates the exported constant value and introduces no apparent correctness issue.” |
| exec-native | Luna + Sol override; `codex exec review --uncommitted --json` | Reviewer turn context: `gpt-5.6-sol` | “The only change updates the exported constant from 1 to 2, with no surrounding code, tests, or documented invariant indicating that this introduces a defect.” |
| native-sentinel | Luna + `review_model = "pilot-unavailable-model"`; `node "$C" review '--wait --model luna --json'` | Warning and backend error name `pilot-unavailable-model`: for this companion-launched ephemeral native review with explicit `thread/start.model: gpt-5.6-luna`, Codex selected `review_model` for the review turn (**attempt only; no successful completion**) | Exit 1; helper says “Reviewer failed to output a response.” No retry |
| explicit-resume | Configured case: `printf 'Reply exactly RESUME_OK. Do not use tools or change files.\n' \| node "$C" task --resume --json` | Same thread `<configured-thread-id>`; turn context Luna | `status: 0`, `rawOutput: RESUME_OK`, `touchedFiles: []` |
| cancellation | Luna config; `node "$C" task --background --json 'Read-only: mentally enumerate 200 distinct short greetings and return the full list. Do not use tools or change files.'`, then `node "$C" cancel <jobId> --json` after `turn/started` | Thread selected Luna; cancelled before a completed turn/context/usage record | `status: cancelled`, `turnInterruptAttempted: true`, `turnInterrupted: true`; status confirms `pid: null`, `write: false` |
| unavailable-review | Empty config; Claude command below, initially without `Bash(echo:*)` | Claude Sonnet 5; **no Codex model used** | Preflight permission denial; stops without review |
| unavailable-review-retry | Same Claude command with undeclared extra `Bash(echo:*)` grant | Claude Sonnet 5; **no Codex model used** | Preflight and size check proceed only under widened grants; question unavailable; asks in text and stops without launching review |

Guide gap: the absent-config server default `gpt-6.1-sol` is absent from
`codex:model-guide` and its alias table; [#477](https://github.com/nq-rdl/agent-extensions/issues/477)
tracks that factual coverage gap without changing the table or #201 policy.

### Trimmed request/response evidence

Absent-model task:

```json
{"method":"thread/start","params":{"model":null,"approvalPolicy":"never","sandbox":"read-only","ephemeral":false}}
{"result":{"model":"gpt-6.1-sol"}}
{"method":"turn/start","params":{"model":null,"effort":null,"input":[{"type":"text","text":"Reply exactly PILOT_OK. Do not use tools or change files."}]}}
```

Configured task sends the same null model fields; Codex resolves them to Luna.
The resume candidate reported `available: true` for the completed configured
thread. Explicit `--resume` sent `thread/resume` for that thread, followed by a
read-only turn with the piped delta; `--resume` was not prompt text. This proves
stdin task input and the explicit resume contract, **not a question answer**.

Native override sends `thread/start.model: gpt-5.6-luna`, then:

```json
{"method":"review/start","params":{"delivery":"inline","target":{"type":"uncommittedChanges"}}}
```

The original persisted probe explicitly set session Luna even without a
`review_model`, so its default-labelled case did not distinguish configuration
inheritance from explicit selection. The two 2026-10-01 probes now do: with
config Luna and no review override, `thread/start.model: null` resolves both
parent and reviewer to Luna, while explicit `gpt-5.6-terra` resolves both to
Terra. Each review child's `session_meta.source` is `subagent: review`, and its
`turn_context.model` is the corresponding model. Usage below is the child's
final cumulative `token_count`, not the parent's. The original companion
`native-default` run did omit `--model`, but its ephemeral reviewer model was
not directly observable.

The Sol-override persisted probe's child session (not its parent) records:

```json
{"type":"session_meta","payload":{"source":{"subagent":"review"},"cli_version":"0.159.1"}}
{"type":"turn_context","payload":{"model":"gpt-5.6-sol","approval_policy":"never","sandbox_policy":{"type":"read-only"}}}
```

The companion sentinel run reports on the wire; the warning precedes
`turn/started` and corroborates Codex's selection of the configured reviewer:

```text
warning: Model metadata for `pilot-unavailable-model` not found. Defaulting to fallback metadata; this can degrade performance and cause issues.
error: The 'pilot-unavailable-model' model is not supported when using Codex with a ChatGPT account.
willRetry: false
turn/completed: status failed
```

The helper's stdout hides that actionable backend reason behind “Reviewer
failed to output a response.” This is an observed diagnostic limitation,
not fixed here: changing vendored error rendering is separate from verifying
precedence. No model substitution or automatic retry was performed.

Cancellation recorded `turn/interrupt` for the live thread/turn and an empty
successful RPC result. This is runtime **job** cancellation, not cancelling
an `AskUserQuestion` selection. No tool permission was used as edit authority;
no `--write` was supplied and all repositories retained only the pilot's
original one-line change (the cancellation case also has `launch.json`, written
by the harness to retain the queued job ID).

## Usage and cost

Counts below are final cumulative totals per run, except resume which is the
new turn's delta. Cached input is a subset of input; reasoning is a subset of
output. No cache-write tokens were reported. Codex exposes tokens, not a dollar
charge for this ChatGPT session: **USD cost unknown**, not zero. Do not infer
API prices or a model-tier policy from these numbers.

| Case | Input | Cached input | Output | Reasoning output | USD |
|---|---:|---:|---:|---:|---|
| absent | 14,198 | 12,288 | 8 | 0 | unknown |
| configured | 11,529 | 9,984 | 8 | 0 | unknown |
| native-default / native-override | not exposed | — | — | — | unknown |
| adversarial-override | 25,175 | 18,944 | 317 | 101 | unknown |
| native-persist | 20,332 | 12,928 | 362 | 57 | unknown |
| native-persist-explicit-luna | 20,391 | 11,776 | 415 | 132 | unknown |
| native-config-null | 27,551 | 20,480 | 472 | 125 | unknown |
| native-explicit-terra | 27,167 | 22,528 | 406 | 67 | unknown |
| exec-native | 20,101 | 13,696 | 349 | 39 | unknown |
| native-sentinel / cancellation | not exposed | — | — | — | unknown |
| explicit-resume | 14,293 | 11,008 | 17 | 8 | unknown |
| unavailable-review | 4 | 56,931 | 468 | 17 | 0.0867022 |
| unavailable-review-retry | 8 | 133,468 | 775 | 236 | 0.1290676 |

Codex task/adversarial counts come from `thread/tokenUsage/updated`; persisted
native counts come from the review child's last `event_msg/token_count`, not
parent usage. In particular, `codex exec review` printed a parent
`turn.completed.usage` of all zeroes: **that is not the review's usage**.
Claude also reported cache-creation input of 17,657 / 23,652 tokens respectively
and total reported USD 0.2157698 across the two runs. These are CLI-reported
list-cost values, not independently reconciled billing.

## Unavailable interaction and remaining human checks

The headless retry reached the question boundary only with a grant wider than
the shipped skill. The command below adds `--strict-mcp-config` for hardened
reproduction; **both historical runs omitted that flag**:

```bash
claude -p --plugin-dir "$P" --setting-sources local --strict-mcp-config --model claude-sonnet-5 \
  --permission-mode dontAsk \
  --allowedTools 'Bash(node:*)' 'Bash(git:*)' 'Bash(echo:*)' Read Glob Grep AskUserQuestion \
  --output-format stream-json --verbose --max-turns 8 '/codex:review'
```

Both runs appended `echo "...EXIT:$?"` to the shipped Node preflight, and the
retry also chained echo separators into the git size check. The skill declares
`Bash(node:*)` and `Bash(git:*)`, **not `Bash(echo:*)`**. The shipped grants denied
the composed preflight; the retry needed an undeclared extra echo grant to reach
the size check (`1 file changed, 1 insertion(+), 1 deletion(-)`). This is a
missing capability/permission-contract gap under #430, not shipped-contract
success. [#476](https://github.com/nq-rdl/agent-extensions/issues/476) tracks exact-command/status
handling versus deliberate allowed-tools review; this PR does not change grants.

The original runs were not isolated from claude.ai connectors: init listed
Gmail, Slack and Google Drive, and ToolSearch surfaced Slack tools. No connector
operation executed; `dontAsk` prevented use. `--setting-sources local` alone did
not isolate them. The strict-MCP reproduction above is not a new tested result;
verify connector absence in init before running it. Tool search for
`AskUserQuestion` returned “No matching deferred tools found.” Final reply:

```text
The change is tiny (1 file, +1/-1 in value.js), so I'd recommend waiting…
Would you like me to:
1. Wait for results (Recommended)
2. Run in background
```

No companion review call or Codex request followed. This confirms a conservative
stop for unavailable interaction on this run. It does not prove an interactive
question was displayed, answered or cancelled. The first run's suggested
manual companion command would bypass the host's selection question; it was
not executed as a purported answer.

**Remaining manual steps (not passes):** in an interactive terminal, create a
fresh fixture using the setup below and run
`claude --plugin-dir "$P" --setting-sources local --strict-mcp-config`. Leave normal permissions
in place; approve only the necessary read-only preflight/companion commands.

1. Enter `/codex:review`. Select **Wait for results**; check exactly one native
   review, unchanged argument string, verbatim output, no fixes. Repeat in a
   new Claude session selecting **Run in background**; check host background
   launch and no foreground polling.
2. In a fresh session enter `/codex:rescue --fresh --wait Reply exactly PILOT_OK. Do not use tools or change files.`
   Then `/codex:rescue Reply exactly RESUME_OK. Do not use tools or change files.`
   Select **Continue current Codex thread**. Verify same thread, delta-only
   prompt, no `--write`. Repeat selecting **Start a new Codex thread**, verifying
   a new thread and no `--resume-last`.
3. Repeat each question and press Escape to dismiss/cancel (record the actual
   UI outcome; exit with Ctrl-C if needed). Verify **no task/review launches
   after cancellation**, and no assumed authorization or fallback answer.
4. Record versions, selections, session model/usage and trimmed host tool
   request/response evidence. These checks need a human and are not covered by
   stdin resume or the job-cancellation run.

## Reproduction setup and persisted reviewer probe

Use a new directory for every independent case. Do not reuse the catalog as
`cwd` or change the user's real Codex configuration:

```bash
P=/absolute/path/to/agent-extensions/plugins/codex
C="$P/scripts/codex-companion.mjs"
export P
root=$(mktemp -d "${TMPDIR:-/tmp}/codex-430.XXXXXX")
trap 'rm -rf "$root"' EXIT
mkdir -p "$root/repo" "$root/home" "$root/data"
cp "$HOME/.codex/auth.json" "$root/home/auth.json"
chmod 600 "$root/home/auth.json"
export CODEX_HOME="$root/home" CLAUDE_PLUGIN_DATA="$root/data"
unset CODEX_COMPANION_APP_SERVER_ENDPOINT CODEX_COMPANION_SESSION_ID
# Write only the chosen case's config; use an empty file for absent model.
printf 'model = "gpt-5.6-luna"\nreview_model = "gpt-5.6-sol"\n' > "$CODEX_HOME/config.toml"
cd "$root/repo"
git init -q; git config user.name Pilot; git config user.email pilot@example.com
printf 'export const value = 1;\n' > value.js
git add value.js; git commit -qm baseline
printf 'export const value = 2;\n' > value.js
```

The copied credentials **must be removed**: exit the reproduction shell to run
the trap, or explicitly `cd /; rm -rf "$root"` after collecting scrubbed evidence.
Do not publish authentication, untrimmed wire logs or private local paths.

### Observational wire recorder

Save the original recorder as `$root/codex-wrapper.mjs` (no local paths needed):

```javascript
import { spawn } from 'node:child_process';
import fs from 'node:fs';
const args = process.argv.slice(2);
const child = spawn(process.env.REAL_CODEX, args, { stdio: ['pipe', 'pipe', 'pipe'] });
function record(direction, chunk) {
  fs.appendFileSync(process.env.WIRE_LOG,
    JSON.stringify({ direction, text: chunk.toString() }) + '\n');
}
process.stdin.on('data', chunk => {
  if (args[0] === 'app-server') record('request', chunk);
  child.stdin.write(chunk);
});
process.stdin.on('end', () => child.stdin.end());
child.stdout.on('data', chunk => {
  if (args[0] === 'app-server') record('response', chunk);
  process.stdout.write(chunk);
});
child.stderr.pipe(process.stderr);
child.on('exit', code => process.exit(code ?? 1));
for (const signal of ['SIGTERM', 'SIGINT']) {
  process.on(signal, () => child.kill(signal));
}
```

Resolve the real binary **before** prepending the shim, to avoid recursion:

```bash
export REAL_CODEX="$(command -v codex)" WIRE_LOG="$root/wire.jsonl"
export WIRE_WRAPPER="$root/codex-wrapper.mjs"
mkdir -p "$root/bin"
printf '#!/bin/sh\nexec node "$WIRE_WRAPPER" "$@"\n' > "$root/bin/codex"
chmod +x "$root/bin/codex"
export PATH="$root/bin:$PATH"
```

Each recorded line contains `direction` and a raw text chunk. Reassemble chunks
per direction, then split JSONL; chunks need not coincide with message lines.
Keep the recorder enabled through runtime availability checks and model calls.
It forwards stderr without recording it and never answers server/user questions.

### Persisted probe

The persisted probe used the vendored app-server client but deliberately changed
`ephemeral` to `false` to expose reviewer metadata. It is **not an exact companion
run**. Save this as `$root/probe-review.mjs` (outside the fixture repo), then run
`node "$root/probe-review.mjs"` from the fixture (explicit Luna, as in the original
probe). For the distinguishing runs use `node "$root/probe-review.mjs" null`
and `node "$root/probe-review.mjs" gpt-5.6-terra`, each with Luna config and **no**
`review_model`:

```javascript
const { CodexAppServerClient } = await import(
  `${process.env.P}/scripts/lib/app-server.mjs`
);
const client = await CodexAppServerClient.connect(process.cwd());
let done;
const finished = new Promise(resolve => { done = resolve; });
client.setNotificationHandler(message => {
  console.log(JSON.stringify(message));
  if (message.method === 'turn/completed') done();
});
const response = await client.request('thread/start', {
  cwd: process.cwd(),
  model: process.argv[2] === 'null' ? null : (process.argv[2] ?? 'gpt-5.6-luna'),
  approvalPolicy: 'never',
  sandbox: 'read-only', ephemeral: false
});
console.log(JSON.stringify({ threadStart: response }));
console.log(JSON.stringify({ reviewStart: await client.request('review/start', {
  threadId: response.thread.id, delivery: 'inline',
  target: { type: 'uncommittedChanges' }
}) }));
await finished;
await client.close();
```

Export `P` before running the probe. Inspect the review child's JSONL under
`$CODEX_HOME/sessions/` for `session_meta.source.subagent: review`,
`turn_context.model`, and the last `event_msg` with `type: token_count`.
Do not report the parent's model or zero usage as the reviewer's.

## Decision

Replace the blanket “not verified against a live backend” text with dated,
bounded evidence: configured model inheritance works; `review_model` wins over
the native session model on CLI 0.159.1; adversarial review uses the ordinary
turn model. Successful ephemeral companion native runs still do not directly
expose reviewer model/usage. Retain the explicit human-question limitation.
No retry, model-tier, authorization, resume or argument contract was changed.
The content regression guard was updated first (19 tests: one expected failure),
then passed after the evidence wording and generated target refresh.

Validation results are tracked in PR #471 rather than this evidence record.
Deterministic tests do not close the human-question gap in #475.
