# Codex and prompting family review (#305–#310)

This record follows the pilot protocol in epic #312. It covers the `codex`
plugin skills (`codex-*`, `gpt-5-6-prompting`) and the `prompting` plugin's
`opus-5-5-prompting`. Issues: #305 (gpt-5-6-prompting duplication), #306
(codex-cli-runtime description), #307 (review versus adversarial review),
#308 (runtime/model guide/prompting provenance, codex-report-defect), #309
(codex-result-handling and codex-cli-runtime decision records) and #310
(codex-rescue argument, resume and model/effort ownership).

The tasks, invariants, prompts and expected outcomes below were recorded
**before** any skill edit, at source revision `4817a19`.

## Scope notes

- PR #291 removed the named `codex:codex-rescue` agent and all skill preloads.
  The upstream agent is now `skills/codex-rescue/references/subagent.rst`, an
  optional worker outline. The main agent normally runs the rescue workflow
  itself and reads `codex:cli-runtime` directly. #309 item 3 ("remove a preload
  only when …") and #310's preload wording are re-scoped to that form.
- The vendored companion runtime lives in `plugins/codex/scripts/` (packaged
  as-is; there are no `skills/codex-*/scripts/`). It is the authority for every
  command contract below. This review does not change the runtime or `hooks/`.
- Upstream is `openai/codex-plugin-cc` at `db52e28` (v1.0.6), fetched with
  `gh api` on 2026-09-29 for comparison.

## Baseline sizes

`asctl repo-check --size-report` built from `4817a19`. Approximate tokens are
body bytes / 4, not measured model usage. Description length is the parsed
(folded) YAML string.

| Skill | Body lines | Approx. tokens | References | Description chars |
|---|---|---|---|---|
| opus-5-5-prompting | 112 | 1726 | 1 | 480 |
| codex-adversarial-review | 83 | 1128 | 1 | 81 |
| codex-review | 78 | 1043 | 1 | 47 |
| codex-model-guide | 74 | 1514 | 0 | 140 |
| codex-rescue | 74 | 1226 | 2 | 103 |
| gpt-5-6-prompting | 56 | 1094 | 3 | 143 |
| codex-setup | 53 | 471 | 1 | 90 |
| codex-cli-runtime | 50 | 1018 | 0 | 101 |
| codex-status | 36 | 367 | 1 | 83 |
| codex-result | 34 | 343 | 1 | 72 |
| codex-cancel | 29 | 271 | 1 | 56 |
| codex-report-defect | 29 | 313 | 2 | 106 |
| codex-transfer | 29 | 280 | 1 | 70 |
| codex-result-handling | 21 | 431 | 0 | 69 |

Every body is far below the 300-line target. Size is not the problem in this
family; contradictions between owners are.

## Runtime facts checked before edits

Local host: Linux, Node v22.23.1, `codex-cli 0.158.0`. No request was sent to
OpenAI; the model catalog was read from the local cache
`~/.codex/models_cache.json` (`fetched_at` 2026-09-29T05:17Z,
`client_version` 0.158.0).

| Claim (file) | Check | Result |
|---|---|---|
| `review` rejects focus text (codex-review) | `validateNativeReviewRequest` in `codex-companion.mjs` | True: throws and names `/codex:adversarial-review` |
| Adversarial review keeps focus text (codex-adversarial-review) | `buildAdversarialReviewPrompt` interpolates `USER_FOCUS` | True |
| Both reviews share target selection | `handleReviewCommand` → `resolveReviewTarget` for both | True: `auto`, `working-tree`, `branch`, `--base` |
| "staged-only or unstaged-only scope requires $codex:adversarial-review" (codex-review `references/codex.rst`) | `resolveReviewTarget` | **False**: both reviews reject `--scope staged/unstaged` ("Unsupported review scope") |
| `task` accepts `--wait` | `handleTask` boolean options | **No**: `--wait` is not an option of `task`, so it becomes prompt text; stripping it is required |
| `task` accepts `--background` | `handleTask` | Yes (companion-side detached worker); the Claude skills use the host's background shell instead (upstream design, retained) |
| `task` accepts `--resume` | `handleTask` | Yes, as an alias of `--resume-last`; `--fresh` is also parsed |
| `--resume-last` with no resumable thread | `executeTaskRun` → `resolveLatestTrackedTaskThread` | Fails: "No previous Codex task thread was found for this repository." |
| Phrase-based resume ("continue", "keep going") adds `--resume-last` (codex-cli-runtime, subagent.rst) | Combined with the rescue skill's `task-resume-candidate` check | **Conflict**: when the candidate check reports `available: false`, the phrase rule still adds `--resume-last`, which then fails |
| "If the Bash call fails … return nothing" (codex-cli-runtime) | Main agent now executes it directly (post-#291) | **Conflict** with codex-rescue ("tell the user to run `/codex:setup`") and codex-result-handling ("include the most actionable stderr lines") |
| Model aliases resolved by the companion | `MODEL_ALIASES`, `normalizeRequestedModel` | True; natural phrases such as "luna 6" still need mapping by the caller |
| `codex proto` removed | `codex help proto` | True: "unrecognized subcommand 'proto'" |
| `codex app-server` subcommands `daemon|proxy|generate-ts|generate-json-schema` | `codex app-server --help` | True on 0.158.0 |
| `codex exec` has `--json`, `--output-schema`, `--ephemeral` | `codex exec --help` | True on 0.158.0 |
| Approval policies `untrusted | on-request | never` (codex-cli-runtime) | `codex --help` | **Stale**: 0.158.0 lists `on-request` and `never` only. The companion always passes `approvalPolicy: "never"` over app-server and never calls `codex exec` |
| Companion runtime requirement | `getCodexAvailability` | Runs `codex --version` and `codex app-server --help` |
| Model catalog rows (codex-model-guide) | local cache | Defaults and `ultra` column match; spark absent |
| API prices and "relative cost signal" (codex-model-guide) | — | No maintained source or verification process in the repo (#308) |
| `text.verbosity` advice (gpt-5-6-prompting) | OpenAI "Prompting guidance for GPT-5.6 Sol", <https://developers.openai.com/api/docs/guides/prompt-guidance-gpt-5p6>, fetched 2026-09-29 | API parameter. The companion `task` exposes no verbosity control, so it is not actionable in `codex:rescue` |
| Migration callouts `prompt_cache_options`, `reasoning.context`, `reasoning.mode: "pro"` (gpt-5-6-prompting) | Same guide | Not in the guide; API-level, not reachable through the companion |
| "Keep effort baseline, test one lower" (gpt-5-6-prompting) | Same guide | Supported |
| Draft field list (codex-report-defect `reporting.rst`) | `recordDefect`, `codex-defects.mjs show` | Matches the current marker, but restates the runtime's `environment` sub-structure |

## Invariants

These must survive. "Where" names the owner after the change.

### Review commands (#307)

| ID | Invariant | Where |
|---|---|---|
| RV-1 | Both reviews are review-only; return companion stdout verbatim; no fixes | both SKILL.md |
| RV-2 | Shared mechanics: `--wait` foreground, `--background` host background task, otherwise size estimate + one question; arguments passed through unchanged as one string | both SKILL.md |
| RV-3 | Shared target selection: auto / working-tree / branch / `--base`; neither supports staged-only or unstaged-only | both SKILL.md and Codex entrypoints |
| RV-4 | `/codex:review` is native review only and rejects focus text; its error names adversarial review | codex-review |
| RV-5 | `/codex:adversarial-review` accepts and preserves focus text and challenges approach, design and assumptions | codex-adversarial-review |
| RV-6 | Distinct command name, description, argument hint, framing and labels | both |
| RV-7 | `review_model` applies to native review only (marked unverified against a live backend) | codex-review, codex-model-guide |

### Rescue and runtime (#309, #310)

| ID | Invariant | Where |
|---|---|---|
| RS-1 | Exactly one `task` call; forwarder only; no repo inspection or own solution | codex-cli-runtime |
| RS-2 | Strip `--wait`/`--background` before `task` (`--wait` would become prompt text) | codex-cli-runtime |
| RS-3 | Pass `--model`/`--effort` through only when the user asked; map spoken model words; no GPT-6 Terra; one owner for the alias table | codex-model-guide (table), rescue (phrases) |
| RS-4 | `--resume` → `--resume-last`; `--fresh` → none; ask once when a candidate exists | codex-rescue, codex-cli-runtime |
| RS-5 | `--write` for authorized edit requests; read-only for review/diagnosis/research; resuming does not authorize edits | codex-cli-runtime |
| RS-6 | On failure: no substitute answer, no Claude-side implementation, actionable stderr, `/codex:setup` for install/auth | codex-result-handling, codex-cli-runtime |
| RS-7 | After review findings, stop and ask before any fix | codex-result-handling |

### Prompting and model guide (#305, #308)

| ID | Invariant | Where |
|---|---|---|
| PR-1 | Companion-specific constraints: one task per run, output contract, one autonomy policy, grounding/verification blocks, `task --resume-last` for follow-ups with delta only | gpt-5-6-prompting |
| PR-2 | Built-in review commands own review prompts | gpt-5-6-prompting |
| MG-1 | Alias table (bare names = GPT-5.6; explicit GPT-6 forms; no GPT-6 Terra) agrees with `MODEL_ALIASES` | codex-model-guide |
| MG-2 | Live catalog (`codex debug models`) is the authority; tested versions are provenance, not support | codex-model-guide |
| MG-3 | Per-model default efforts, `ultra` availability, no `minimal`, `pro` is not an effort | codex-model-guide |
| RD-1 | Report-defect: verdict gate, privacy gate (`homeScrubbed`), no secrets, show draft before filing, `--body-file`, mark-reported only after success | reporting.rst |

## Behavioural protocol

**Harness.** `claude -p` (Claude Code 2.1.284) with `--plugin-dir` pointing at a
temporary copy of `plugins/codex/`: **orig** exported from `4817a19`, **rev**
regenerated from this branch. A fake `codex` executable from
`tests/codex/fake-codex-fixture.mjs` is first on `PATH`, so no request reaches
OpenAI and no paid Codex job runs; it records the `turn/start` model, effort and
prompt. Each run uses a fresh throwaway git repository with one committed file
and one uncommitted change, a private `CLAUDE_PLUGIN_DATA`, and
`--setting-sources local` so the user's installed `codex` plugin is not loaded.
Model `claude-sonnet-5`, `--output-format stream-json --verbose`,
`--permission-mode dontAsk`.

**Observed per run.** Skill calls, every `Bash` command (the companion
invocation and its arguments), `Read`/`Grep`/`Edit` calls, the fake Codex's
recorded model/effort/prompt, the final reply, cost.

| Case | Kind | Prompt | Expected |
|---|---|---|---|
| R1 | normal | `/codex:review --wait` | one `review` call with `--wait` kept; reply is the companion output verbatim; no edits |
| R2 | gotcha RV-4 | `/codex:review --wait focus on error handling` | `review` called with the focus text unchanged; runtime error returned; the agent does not silently drop the focus text or run adversarial review on its own |
| R3 | normal RV-5 | `/codex:adversarial-review --wait focus on error handling` | focus text reaches Codex (fake prompt contains it); verbatim output; no edits |
| X1 | model/effort | `/codex:rescue --wait --effort high use luna 6 to diagnose why the app crashes on empty input` | one `task`; model `gpt-6-luna`; effort `high`; no `--wait` in the prompt; no `--write` |
| X2 | write scope | `/codex:rescue --fresh fix the crash on empty input in src/app.js` | `--write`; no `--resume-last`; `--fresh` not in prompt text |
| X3 | gotcha RS-4 | `/codex:rescue keep going` (no earlier Codex job) | candidate check reports none; no `--resume-last` (so no "No previous Codex task thread" failure); a fresh task or a question about what to do |
| X4 | blocked RS-6 | `/codex:rescue --wait diagnose the crash` with Codex logged out | failure reported with `/codex:setup`; no substitute diagnosis; no repository reads |

## Rubric application (skill-audit, applied from the checkout)

Recorded before edits from `skills/skill-audit/SKILL.md`:

- **codex-review / codex-adversarial-review** — CRITICAL (Codex host only):
  `codex-review/references/codex.rst` says staged-only/unstaged-only scope
  "requires $codex:adversarial-review", which the runtime rejects. MINOR: the
  shared execution rules are duplicated across both files by design (each is
  loaded alone). Recommendation: fix the false route; retain the duplication.
- **codex-cli-runtime** — MODERATE: "return nothing" on failure contradicts two
  sibling owners now that the main agent runs it. MODERATE: phrase-based
  `--resume-last` fails when no candidate exists. MODERATE: "Codex CLI facts"
  pinned to 0.144.6 with one stale value; none of them is used by the
  forwarder. MINOR: decorative version pin in the description (#306).
- **codex-rescue** — MODERATE: the alias mapping appears in the SKILL.md, in
  codex-cli-runtime and in the outline; the main agent loads the first two
  together.
- **codex-result-handling** — MINOR: no incoming route (upstream had none
  either; it relies on model invocation). Its failure and post-review rules are
  the only owner of RS-6/RS-7.
- **codex-model-guide** — MODERATE: prices and a "relative cost signal" with no
  maintenance process (#308). Otherwise verified.
- **gpt-5-6-prompting** — MODERATE: `text.verbosity` guidance is not actionable
  through the companion; the migration section lists API features that the
  canonical guide does not mention and the companion cannot use.
- **codex-report-defect** — MINOR: restates the runtime's environment structure.
- **opus-5-5-prompting** — description 480 characters (editorial target 400);
  has `compatibility`, a dated verification and a verify-canonical guard.
- **codex-setup / status / result / cancel / transfer** — no finding.
