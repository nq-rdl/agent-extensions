---
description: Internal guide for selecting a Codex model and reasoning effort (GPT-5.6 Sol/Terra/Luna) when delegating work to Codex
user-invocable: false
---

<!--
SPDX-License-Identifier: Apache-2.0
Derived from openai/codex-plugin-cc v1.0.6 (db52e28), Apache-2.0. Modified for rdl-agent-extensions.
-->

# Codex Model Guide

The delegation decision guide used by Claude Code and the `codex:codex-rescue` subagent when picking a Codex model and effort. A process spawned by Codex cannot load Claude Code skills, so this guidance applies on the Claude Code side, before invoking the companion.

## Verify against the live catalog first

`codex debug models` is the authority for what is actually available in the installed Codex. When a value below differs from `codex debug models`, trust the live catalog and prefer it over this static table. Pin: recorded against Codex CLI 0.144.6.

## Models (GPT-5.6 family)

| Alias (`--model`) | Full id | API price in/out (per 1M tok) | Position |
|---|---|---|---|
| `sol` | `gpt-5.6-sol` | $5 / $30 | Flagship; deepest reasoning |
| `terra` | `gpt-5.6-terra` | $2.50 / $15 | Balanced default |
| `luna` | `gpt-5.6-luna` | $1 / $6 | Fast / cheap |

- `gpt-5.6` (bare) aliases to Sol.
- `spark` aliases to `gpt-5.3-codex-spark` (still live).
- There is **no** `gpt-5.6-codex`.
- Context: API 1.05M in / 128K out; Codex harness context 272,000 tokens.
- Prices are OpenAI API input/output rates per million tokens. A ChatGPT-subscription Codex user is not necessarily billed these amounts; treat them as relative cost signal, not a quote.

## Reasoning effort ladder

`low | medium | high | xhigh | max` on all three models. `ultra` ("maximum reasoning with automatic task delegation" — multi-agent) is available on **Sol and Terra only**, and is costly. There is **no** `minimal` in the current catalog.

Per-model defaults (a real gotcha):
- **Sol defaults to `low`.** If you want deep reasoning from Sol, set effort explicitly.
- **Terra and Luna default to `medium`.**

`pro` is **not** a Codex effort — it is the API's `reasoning.mode: "pro"`, independent of effort. Do not pass `pro` as `--effort`.

No account-plan gating is asserted here; there is no reachable authoritative source for it. `codex debug models` is the live authority.

## Task → model / effort mapping

| Task | Model | Effort |
|---|---|---|
| Quick fix, small bounded edit | `luna` | medium |
| Default day-to-day work | `terra` | medium |
| Deep review / tricky diagnosis | `sol` | high (or `xhigh`) |
| Large autonomous multi-step run | `sol` | `max` or `ultra` |

Defaults: leave `--model` and `--effort` unset unless the user asks or the task clearly warrants a change — the companion honors the user's `config.toml`. Escalate effort before switching to a bigger model; a tighter prompt (see `codex:prompting`) often beats more reasoning.
