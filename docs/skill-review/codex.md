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

---

Everything below was recorded **after** the edits (`d2a85be`).

## Tests written first

`tests/test_codex_skill_contracts.py` (new, 17 tests) and two new assertions in
`tests/test_codex_model_aliases.py` were written before the skill edits and
failed against `2f025f2`: 21 failures in the new file (staged/unstaged route,
focus-text rerun, `--wait` as prompt text, write default, phrase-based
resume, "return nothing", version pin, stale approval list, runtime
requirement, `text.verbosity`, API-only migration fields, source citation,
report-defect environment structure) and 2 in the alias file (prices, alias
mapping duplicated into codex-cli-runtime). Four tests passed before and are
kept as regression guards (adversarial focus preserved, result-handling
rules, companion-specific prompting blocks, report-defect gates). The alias
test now reads the model-guide table by header name instead of column index,
so removing the price column does not silently shift its assertions. After
the edits all pass, together with the existing suites (see "Validators").

## What changed

| Skill | Change | Invariants |
|---|---|---|
| codex-review | Focus text: pass it, return the runtime's rejection, do not drop it and rerun, do not switch commands unasked. States that adversarial review shares the targets | RV-2, RV-3, RV-4 |
| codex-review `references/codex.rst` | Removed the false "staged-only or unstaged-only scope requires $codex:adversarial-review" | RV-3 |
| codex-adversarial-review `references/codex.rst` | States the shared targets and preserved focus text | RV-3, RV-5 |
| codex-rescue | One "Forwarded command" block (the rules the main agent needs, in the skill it always loads); `--wait` never forwarded, with the reason; `--write` only for edit requests; continuation without a thread is not forwarded; failure reporting | RS-2, RS-4, RS-5, RS-6 |
| codex-rescue `references/codex.rst` | Same no-thread and failure rules for the Codex host (write scope was already correct there) | RS-4, RS-6 |
| codex-rescue `references/subagent.rst` | Write scope, no phrase-based resume, failure returned to the parent instead of "return nothing" | RS-4, RS-5, RS-6 |
| codex-cli-runtime | Description pin removed; alias mapping deferred to rescue/model-guide; write scope; no phrase-based resume (with the runtime error it causes); `--wait` reason; "Codex CLI facts" replaced by the checked runtime requirement and a dated tested version; failure reporting | RS-1 to RS-6 |
| codex-model-guide | Price column and "relative cost signal" removed; unverified API limits and "`gpt-5.6` aliases to Sol" removed (not in `MODEL_ALIASES` or the catalog); provenance separated from support; rows re-checked against the 0.158.0 catalog cache | MG-1 to MG-3 |
| gpt-5-6-prompting | Source URL and verification date; `text.verbosity` instruction replaced by "length goes in the output contract; the companion has no verbosity parameter"; API-only migration callouts removed; effort migration reworded to match the guide | PR-1, PR-2 |
| gpt-5-6-prompting references | Same `text.verbosity` correction in `prompt-blocks.rst` and `codex-prompt-antipatterns.rst` | PR-1 |
| codex-report-defect `references/reporting.rst` | Draft list names the marker's fields and copies `environment` as emitted; the CLI owns structure, redaction and scrubbing | RD-1 |

Local deltas from upstream `db52e28`, recorded for any future refresh: the
write-scope wording (upstream defaults to `--write`; this catalog and its Codex
entrypoint add it only for edit requests), the removal of phrase-based
`--resume-last`, failure reporting instead of "return nothing", and the
no-thread continuation rule. Upstream's resume phrase rule has the same
failure mode (`task-resume-candidate` reports none, the phrase rule adds
`--resume-last`, the runtime fails).

## After sizes

| Skill | Body lines | Approx. tokens | Description chars |
|---|---|---|---|
| codex-rescue | 74 → 83 | 1226 → 1461 | 103 |
| codex-review | 78 → 78 | 1043 → 1110 | 47 |
| codex-model-guide | 74 → 73 | 1514 → 1505 | 140 |
| gpt-5-6-prompting | 56 → 57 | 1094 → 1143 | 143 |
| codex-cli-runtime | 50 → 45 | 1018 → 1019 | 101 → 85 |
| others | unchanged | | |

codex-rescue grew by about 235 approximate tokens. The runs below show why
this is a net saving: with the forwarded command in the skill it always loads,
the model loaded codex-cli-runtime (about 1,000 tokens) in 1 of 8 rescue runs,
against 6 of 8 before.

## Behavioural results

**Conditions.** Claude Code 2.1.284, model `claude-sonnet-5` (default effort),
Linux, OAuth login, fake Codex (no OpenAI calls). Orig = plugin tree at
`4817a19`; rev = plugin tree regenerated at `d2a85be`. `--setting-sources
local` loaded only the inline `codex` plugin plus built-ins (checked in the
`init` event). Deviation from the recorded protocol: the first orig runs of
R3/X2/X3/X4 were blocked because the model appended `; echo "EXIT:$?"` to the
Node preflight, which `Bash(node:*)` does not match; `Bash(echo:*)` was added
and those cases rerun. X4 was first run with the fake's `logged-out` mode,
which does not make `task` fail; it was switched to `auth-run-fails`. The
blocked runs are kept as a side observation: all four stopped and asked for
permission; one (X2) offered to fix the file itself, but only as a question.

**Grading.** Deterministic, from `stream-json` and the fake Codex state: the
companion command line (subcommand, flags, task text), the model/effort/prompt
the fake Codex received, whether `src/app.js` changed, and the final reply.

| Case | Version | Runs | Result | Notes |
|---|---|---|---|---|
| R1 native review | orig / rev | 1 / 1 | pass / pass | `review "--wait"`, verbatim output |
| R2 focus text on native review | orig | 3 | **1 fail**, 2 pass | r1 reran `review "--wait"` without the focus text and presented that review as the answer |
| | rev | 3 | 3 pass | returned the runtime's rejection; no rerun |
| R3 adversarial focus | orig / rev | 3 / 3 | focus reached Codex 3/3 · 3/3; verbatim final reply 2/3 · 2/3 | one run per version ended with a pointer to "the output above" instead of the output; not affected by this change |
| X1 model/effort | orig / rev | 1 / 1 | pass / pass | `--model gpt-6-luna --effort high`, no `--wait`, no `--write` |
| X2 fix request | orig / rev | 1 / 1 | pass / pass | `--write`, `--fresh` stripped |
| X3 "keep going", no thread | orig | 3 | **3 fail** | forwarded the bare text "keep going" to a fresh Codex task with `--write` |
| | rev | 3 | 3 pass | reported that no thread exists and asked what Codex should do; no task call |
| X4 diagnose, Codex auth fails | orig | 3 | `/codex:setup` 3/3; **`--wait` in task text 2/3; `--write` on a diagnosis 1/3** | no substitute answer in any run |
| | rev | 3 | 3 pass | no `--wait`, no `--write`, `/codex:setup`, no substitute answer |

The phrase-based `--resume-last` conflict predicted before the edits was not
observed: in X3 the original model ignored the phrase rule and started a fresh
write-enabled task instead. Both are wrong for a request with nothing to
continue.

Loaded content and cost (input tokens include the system prompt and every
turn, so they are a coarse proxy):

| Cases | Version | codex:cli-runtime loads | Median input tokens per case | Cost (USD) |
|---|---|---|---|---|
| X1–X4 | orig | 6 of 8 | 113k–194k | 0.93 |
| X1–X4 | rev | 1 of 8 | 113k–150k | 0.82 |
| R1–R3 | orig / rev | 0 / 0 | 110k–111k | 0.67 / 0.67 |

No run read a reference file, called `codex:result-handling`, or edited the
repository. Total for the codex harness: 35 runs, USD 3.56 (including the
blocked runs).

### Prompting plugin eval (opus-5-5-prompting)

The existing suite `evals/claude/prompting` was run once on the working tree
(`opus-5-5-prompting` is unchanged by this work) with
`scripts/eval-claude-plugin.sh prompting --model claude-sonnet-5
--judge-model claude-haiku-4-5 --threshold 0.8`, default with/without
ablation, 5 runs per arm, `EVAL_MAX_COST_USD=4`. Exit 0. This is the first
recorded score for the suite.

| Case | With | Without | Δ | Cost (USD) | Notes |
|---|---|---|---|---|---|
| migrate-thinking-disabled | 1.00 | 1.00 | 0.00 | 2.16 | Saturated. The without arm cost about 4× more per run ($0.32–0.40 against $0.07–0.09), consistent with the model looking the facts up elsewhere; the built-in `claude-api` skill is present in both arms |
| unattended-early-stop | 1.00 | 0.10 | +0.90 | 1.61 | Without the plugin: 0.00–0.25; two runs hit the 6-turn limit |

The `skill-fired` indicator fired in 10 of 10 with-plugin runs, which is the
routing evidence for keeping the 480-character description. Total USD 3.77.

Paid model spend for this review: USD 7.33 (codex harness 3.56, prompting
eval 3.77).

## Decision records (#309)

### codex-result-handling: retain

- **Published invocation:** `codex:result-handling` (model-invocable only;
  `user-invocable: false`). Bundle `codex`, leaf `result-handling`; Codex
  package copy under `dist/codex/plugins/codex/skills/result-handling/`.
- **Incoming routes:** none in this catalog. Upstream `db52e28` had none either
  (its rescue agent preloaded `codex-cli-runtime` and `gpt-5-4-prompting`
  only), so #291 did not remove a route to it.
- **Behaviour it owns:** no substitute answer and no Claude-side implementation
  after a failed rescue; stop after review findings and ask before fixing;
  `/codex:setup` for auth; preserve Codex's structure, evidence boundaries and
  file:line references.
- **Evidence:** it was not loaded in any of the 35 runs. The failure and
  no-substitute rules that matter for rescue now also sit in codex-rescue and
  codex-cli-runtime, and every rev failure run (X4) behaved correctly without
  it. The review commands carry their own "do not fix" rule.
- **Decision:** retain unchanged. The overlap is intentional repetition in
  independently loaded context. Consolidation would remove a public
  model-invocable capability (presenting helper output such as a
  `/codex:result` payload) without a replacement, and no consumer task showed
  harm. A later removal needs a with/without-skill task on `/codex:result`
  output first.
- **Network/runtime:** none. **Grouping impact:** none.

### codex-cli-runtime: retain, corrected

- **Published invocation:** `codex:cli-runtime` (model-invocable only). Read by
  `codex:rescue` (direct execution) and named in the rescue worker outline.
- **Resume behaviour versus the companion:** the companion accepts `--resume`
  (alias of `--resume-last`) and `--fresh`; `--resume-last` fails when no
  tracked thread exists for this session. The rescue skill asks when a
  candidate exists; phrasing alone no longer adds `--resume-last`.
- **`--wait` stripping:** required, because `task` does not parse `--wait`.
  `--background` is also stripped: the companion supports a detached worker,
  but the skill uses the host's background task (upstream design, retained).
- **Pass-through:** `--model`, `--effort`, `--resume`/`--fresh` routing; the
  task text is otherwise unchanged.
- **Model/effort ownership:** the companion resolves aliases
  (`MODEL_ALIASES`); codex-model-guide owns the table; codex-rescue owns the
  spoken-form mapping; codex-cli-runtime defers to both. The worker outline
  keeps its own table because a worker may receive only the outline; its
  agreement with the runtime is enforced by `tests/test_codex_model_aliases.py`.
- **Evidence:** X1–X4 above. With the forwarded command in codex-rescue, the
  runtime skill is rarely loaded in direct execution; it remains the contract
  for delegated workers and the record of the rationale.
- **Decision:** retain, with the corrections above. No preload exists to
  remove (#291).

## Per-issue dispositions

| Issue | Candidate | Disposition | Evidence |
|---|---|---|---|
| #305 | gpt-5-6-prompting: companion-specific constraints | Retained | PR-1/PR-2 guard tests; recipes unchanged |
| #305 | gpt-5-6-prompting: `text.verbosity` guidance | Changed | Companion has no verbosity control (test); OpenAI guide fetched 2026-09-29 |
| #305 | gpt-5-6-prompting: duplicated migration prose and API-only callouts | Changed (removed) | Not in the canonical guide; not reachable through `task` |
| #305 | gpt-5-6-prompting: XML-tag convention, recipes, references | Retained with reason | The vendored adversarial prompt and upstream companion prompts use XML blocks; the guide does not contradict it |
| #306 | codex-cli-runtime description | Changed | Pin removed (101 → 85 characters); the skill is read by name from codex-rescue |
| #307 | Shared execution mechanics | Retained | Identical wait/background/size rules, target selection, verbatim output, review-only scope |
| #307 | Public contract differences | Retained and documented | RV-4 to RV-6; runtime `validateNativeReviewRequest`, `buildAdversarialReviewPrompt` |
| #307 | False staged/unstaged route in the codex-review Codex entrypoint | Separate factual fix | `resolveReviewTarget` rejects both scopes for both commands |
| #307 | Focus text on native review | Changed | R2 orig 1/3 silent rerun; rev 0/3 |
| #308 | codex-model-guide prices and relative cost | Changed (removed) | No maintained source; test forbids price columns |
| #308 | codex-model-guide provenance vs support | Changed | Provenance line; re-checked against the 0.158.0 catalog cache |
| #308 | codex-model-guide model disambiguation | Retained | Alias table and decision unchanged; alias tests pass |
| #308 | codex-model-guide unverified API limits and bare `gpt-5.6` claim | Separate factual fix | Not in `MODEL_ALIASES` or the local catalog |
| #308 | codex-cli-runtime CLI facts | Changed | `untrusted` absent on 0.158.0; the companion never calls `codex exec` |
| #308 | codex-report-defect payload structure | Changed | The runtime owns structure; a test checks that named fields exist in `recordDefect` |
| #308 | codex-report-defect reporting fields and redaction gates | Retained | Gate tests |
| #309 | codex-result-handling | Retained (decision record) | Above |
| #309 | codex-cli-runtime | Retained, corrected (decision record) | Above |
| #310 | codex-rescue argument semantics (`--wait`, `--background`, flags out of task text) | Changed | X4 orig leaked `--wait` 2/3; rev 0/3 |
| #310 | codex-rescue resume semantics | Changed | X3 orig 3/3 forwarded "keep going"; rev 0/3 |
| #310 | codex-rescue write scope | Changed | X4 orig `--write` on a diagnosis 1/3; rev 0/3; X2 keeps `--write` |
| #310 | codex-rescue model/effort ownership | Changed | Owners above; X1 passes in both versions |
| #310 | Delegation outline (subagent.rst) | Changed | Failure returned to the parent; no universal one-turn rule added |
| — | opus-5-5-prompting size, provenance, guard | Retained | 112 body lines; `compatibility` with a dated source; verify-canonical guard present. Claims spot-checked 2026-09-29 against the [Opus 5.5 prompting guide](https://platform.claude.com/docs/en/build-with-claude/prompt-engineering/prompting-claude-opus-5-5), [effort docs](https://platform.claude.com/docs/en/build-with-claude/effort) and [preserved thinking](https://platform.claude.com/docs/en/build-with-claude/preserved-thinking): default `medium`, 128,000 `max_tokens`, `mid-conversation-output-config-2026-07-01`, `thinking-display-updates-2026-08-18`, `mid-conversation-system-clear-at-2026-08-21`, the 2026-08-31 400 cutoff |
| — | opus-5-5-prompting description (480 characters) | Retained with reason | Over the 400-character editorial target, under the hard limit. It lists the symptoms that route migration and harness problems, and the eval's `skill-fired` indicator fired in every with-plugin run. Trimming it without a routing comparison is not justified |
| — | codex-setup, status, result, cancel, transfer | Retained | No candidate in #305–#310; rubric found nothing |

## Rubric disagreements

- The rubric scores size first. This family is small; its defects were
  contradictions between owners and one false route. Adding 9 lines to
  codex-rescue reduced the content actually loaded.
- The rubric would flag the repeated review mechanics in the two review skills
  as duplication. They are kept: each command loads alone, and #307 asks for
  identical shared mechanics.

## Validators

Run on `d2a85be`: `pixi run bash scripts/validate-plugins.sh` (exit 0);
`pixi run python3 -m unittest discover -s tests -p 'test_*.py'` (1055 tests,
OK); `asctl repo-check` (117 skills, exit 0); `node --test
tests/codex/*.test.mjs` (223 pass, 0 fail); `generate_manifests.py --check`,
`generate_bundles_doc.py --check`, `generate_eval_graders.py --check`,
`check_bundle_refs.py`, `check_exposure.py`, `check_grouping.py`,
`check_consistency.py`, `sync-plugins.sh --check` (all exit 0).

## Limitations

- One model and one host; 1–3 runs per case. X1, X2 and R1 ran once per
  version because both versions passed and the cases did not discriminate.
- The fake Codex proves the command contract, not Codex's answers. No real
  Codex task, review or login was run (no paid Codex jobs, no OpenAI calls).
- The Codex-host entrypoints (`references/codex.rst`) were checked by tests and
  reading only; no Codex-host behavioural run was made.
- The original stubbed review did not verify `review_model` precedence.
  The [#430 live pilot](codex-live-430.md) now confirms it in persisted
  app-server and `codex exec review` runs and records the companion's
  ephemeral-review observability limit.
- Human answers and question cancellation remain untested. The #430 pilot
  exercises unavailable interaction in `claude -p`, explicit runtime resume
  and job cancellation; none substitutes for a human answering the review
  wait/background or rescue continue/new-thread question.
- The model catalog came from the local cache written by the installed CLI on
  the same day; `codex debug models` itself was not run.
