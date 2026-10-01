---
name: codex-model-guide
license: Apache-2.0
description: Internal guide for selecting a Codex model and reasoning effort (GPT-5.6 Sol/Terra/Luna, GPT-6 Astra/Sol/Luna) when delegating work to Codex
user-invocable: false
metadata:
  repo: https://github.com/nq-rdl/agent-extensions
---

<!--
SPDX-License-Identifier: Apache-2.0
Derived from openai/codex-plugin-cc v1.0.6 (db52e28), Apache-2.0. Modified for rdl-agent-extensions.
-->

# Codex Model Guide

The delegation decision guide used by Claude Code and the `codex:rescue` executor when picking a Codex model and effort. A process spawned by Codex cannot load Claude Code skills, so this guidance applies on the Claude Code side, before invoking the companion.

## Verify against the live catalog first

`codex debug models` is the authority for what is actually available in the installed Codex. When a value below differs from `codex debug models`, trust the live catalog and prefer it over this static table. The catalog is server-fetched, so defaults can change without a CLI upgrade.

Provenance, not a supported-version range: GPT-5.6 rows recorded against Codex CLI 0.144.6. GPT-6 rows recorded against Codex CLI 0.156.1 (nq-rdl/agent-extensions#393) and re-checked on 0.157.0. All rows re-checked on 2026-09-29 against the model catalog cached by `codex-cli 0.158.0`.

## Models and aliases

The companion maps each alias to its full id (`MODEL_ALIASES` in `scripts/codex-companion.mjs`). Aliases are case-insensitive. Any other value passes through to Codex unchanged.

| Aliases (`--model`) | Full id | Default effort | `ultra` | Position |
|---|---|---|---|---|
| `sol`, `sol-5.6` | `gpt-5.6-sol` | low | yes | GPT-5.6 flagship; deepest reasoning |
| `terra`, `terra-5.6` | `gpt-5.6-terra` | medium | yes | GPT-5.6 balanced default |
| `luna`, `luna-5.6` | `gpt-5.6-luna` | medium | no | GPT-5.6 fast / cheap |
| `astra`, `astra-6` | `gpt-6-astra` | medium | yes | GPT-6 frontier tier |
| `sol-6` | `gpt-6-sol` | medium | yes | GPT-6 workhorse for coding |
| `luna-6` | `gpt-6-luna` | medium | no | GPT-6 fast / cheap |
| `spark` | `gpt-5.3-codex-spark` | — | — | Unverified: absent from `codex debug models` on 0.157.0 and 0.158.0 |

Alias decision:
- Bare `sol`, `terra`, and `luna` mean **GPT-5.6**. No GPT-5.6 account restriction is recorded here (compare the GPT-6 caveats below). There is **no** `gpt-6-terra`, so a GPT-6 meaning for bare names would split the family.
- The catalog now describes the GPT-5.6 models as "Older…". Bare aliases still map to GPT-5.6 by design; use `sol-6` (or `luna-6`, `astra`) for GPT-6.
- GPT-6 needs an explicit form: `sol-6`, `luna-6`, or `astra` (`astra` exists only in GPT-6). Use `sol-5.6`, `terra-5.6`, or `luna-5.6` to state GPT-5.6 without ambiguity.
- `terra-6` is not an alias. Do not map it to another model.
- `gpt-5.6` (bare) is not a companion alias and is absent from the local catalog; it passes through unchanged. There is **no** `gpt-5.6-codex`.
- GPT-5.6: Codex harness context 272,000 tokens. GPT-6: Codex harness context 272,000 tokens (`context_window`, `codex debug models` on 0.157.0 and 0.158.0). API limits are not recorded here.
- Positions paraphrase the `codex debug models` descriptions. No price, benchmark, or capability claim is made here; check OpenAI's current pricing when cost matters.

## GPT-6 availability caveats

- A third-party report says the backend accepts GPT-6 Sol and Luna from ChatGPT-account sign-ins only on Codex CLI >= 0.155.0 ([bman654/clodex#267](https://github.com/bman654/clodex/pull/267)). Older clients are rejected.
- nq-rdl/agent-extensions#392 (CLI 0.156.1, ChatGPT sign-in): native review on `gpt-6-luna` failed with `The 'gpt-6-luna' model is not supported when using Codex with a ChatGPT account`. Adversarial review on the same default succeeded. GPT-6 task runs on a ChatGPT account are untested.
- If Codex rejects a GPT-6 model, report the rejection to the user and suggest the GPT-5.6 alias (for example `luna-5.6`). Do not retry automatically, with this or any other model.

## Reasoning effort ladder

`low | medium | high | xhigh | max` on every model above. `ultra` ("maximum reasoning with automatic task delegation" — multi-agent) is available where the table says yes: **not on either Luna**. It is costly. There is **no** `minimal` in the current catalog.

Per-model defaults (a real gotcha):
- **`gpt-5.6-sol` defaults to `low`.** If you want deep reasoning from GPT-5.6 Sol, set effort explicitly. `gpt-6-sol` defaults to `medium`.
- Every other model defaults to `medium`. nq-rdl/agent-extensions#393 recorded `gpt-6-astra` at `low` on 0.156.1; 0.157.0 reports `medium`. Check `codex debug models` when it matters.

`pro` is **not** a Codex effort — it is the API's `reasoning.mode: "pro"`, independent of effort. Do not pass `pro` as `--effort`.

No account-plan gating is asserted beyond the caveats above; there is no authoritative source for it. `codex debug models` is the live authority for what is listed, not for what an account may run.

## Review commands

`/codex:review` and `/codex:adversarial-review` accept `--model <model|alias>` for one run. For a persistent native-review model, set `review_model` in `~/.codex/config.toml` ([config reference](https://learn.chatgpt.com/docs/config-file/config-reference)). Per that reference it overrides the session model for native review. `--model` sets the session model, so a set `review_model` takes precedence on `/codex:review` (per the Codex config reference). Live pilot on 2026-09-30 with CLI 0.159.1 (nq-rdl/agent-extensions#430) confirmed precedence in a persisted app-server probe and `codex exec review`; a rejected-model sentinel corroborated Codex's selection of `review_model` on the companion path; the companion's ephemeral native review does not expose the reviewer model in stdout. It does not apply to `/codex:adversarial-review`, which runs an ordinary turn on `model`.

## Task → model / effort mapping

| Task | Model | Effort |
|---|---|---|
| Quick fix, small bounded edit | `luna` | medium |
| Default day-to-day work | `terra` | medium |
| Deep review / tricky diagnosis | `sol` | high (or `xhigh`) |
| Large autonomous multi-step run | `sol` | `max` or `ultra` |

Use a GPT-6 alias only when the user asks for GPT-6 or names a GPT-6 model.

Defaults: leave `--model` and `--effort` unset unless the user asks or the task clearly warrants a change — the companion honors the user's `config.toml`. Escalate effort before switching to a bigger model; a tighter prompt (see `codex:prompting`) often beats more reasoning.
