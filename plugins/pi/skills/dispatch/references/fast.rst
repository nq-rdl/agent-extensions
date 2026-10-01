Opt-in GPT Fast mode
====================

Fast is OFF unless the user requests ``/pi:dispatch --fast TARGET`` or approves
saving ``fast: true`` as a dispatch default. Parse --fast/--no-fast as workflow
options before passing the remaining target to resolve. --no-fast overrides an
approved Fast default; never treat a provider credential or inherited environment
variable as approval for increased usage. Include the choice and cost in the
plan confirmation. Fast does not relax the concurrency cap.

The helper flag is not a pi CLI flag: pi 0.99.1 has no service-tier CLI option
or setting. The shipped ``assets/service-tier.mjs`` is loaded explicitly with
``pi -e`` only for Fast launches. This small, dependency-free plain ESM asset
is a maintainer-approved language-policy exception, not a new TypeScript helper.
Pi already supplies its Node runtime. No global pi settings are edited.

Catalog check and consent
-------------------------

Before launch, run ``fast-check openai-codex/<exact-model>:<thinking>`` and show
the result. It reads ``${CODEX_HOME:-$HOME/.codex}/models_cache.json`` offline,
matching models[].slug (or id) and service_tiers[].id == priority. It does not
start Codex/app-server or refresh the cache. A cache is a snapshot, not proof of
live entitlement or availability. If the user already has app-server model/list
output, inspect that model's service_tiers too; do not start a paid call to test it.

``listed`` means the cache entry advertises priority; still confirm increased
plan usage. ``not-listed``, ``unavailable`` or ``unreadable`` means warn and ASK,
not silently proceed. Offer normal mode or let the user inspect/update their
catalog. The launcher refuses these unknown/negative checks by default. Only
if the user explicitly authorises an unverified priority request for this exact
model may the orchestrator add ``--fast-unverified`` in addition to --fast and
--confirmed. That override is an attestation of extra consent, never inferred
from general task confirmation. Other providers/fuzzy model names are refused.

Example after confirming a listed model and increased usage::

    bash "$S/pi-dispatch.sh" launch UNIT.json "$WORKTREE" PROMPT "$MODEL" --confirmed --fast

The runner adds ``-e <installed-skill>/assets/service-tier.mjs`` and exports
``PI_DISPATCH_SERVICE_TIER=priority`` to pi. Normal launches add neither and
unset any inherited PI_DISPATCH_SERVICE_TIER. On a resumed invocation, select
Fast again explicitly; metadata records the mode of this invocation, not a
session-wide entitlement. No payload contents are logged by the extension.

The extension accepts only priority; unsupported values (including fast) produce
a fixed stderr warning and leave requests untouched. It requires ctx.model's
provider openai-codex, a Responses API (openai-codex-responses/openai-responses),
an object payload whose model agrees with ctx.model.id, array input, string
instructions, and no chat-completions messages field. All other requests are
unchanged. The event has no provider field, so ambiguous/nested calls whose
model does not match are deliberately left untouched. It returns a shallow
payload copy with service_tier: priority, never a credential or request log.
Other user extensions could later override it; it is a request, not enforcement.

Launch metadata and status report ``service_tier: "priority (requested)"``,
fast=true and the catalog snapshot result. They must NOT claim Fast is confirmed
or measure speed from the provider's tier echo. Normal mode is reported as off;
it does not override the provider's own defaults or unrelated user extensions.

Verification provenance — 2026-10-01
-----------------------------------

Orchestrator investigation supplied by the maintainer, using pi 0.99.1 and
Codex CLI 0.159.1 (not new live tests by this implementation worker):

* Codex models_cache.json and app-server model/list expose per-model
  service_tiers. gpt-6.1-sol lists
  {"id":"priority","name":"Fast","description":"2x speed, increased usage"}.
  Other GPT-6/5.x models also list priority (1.5x–2x). The catalog contains
  additional_speed_tiers: ["fast"] and default_service_tier: null; these are
  NOT instructions to send service_tier: fast or to enable Fast by default.
* Pi's openai-codex provider forwards internal serviceTier as body service_tier,
  but exposes no CLI flag/setting for it. before_provider_request can replace
  the payload; see the `canonical example <https://github.com/earendil-works/pi/blob/main/packages/coding-agent/examples/extensions/provider-payload.ts>`_
  and `extension API <https://github.com/earendil-works/pi/blob/main/packages/coding-agent/docs/extensions.md>`_.
  Unlike that logging example, this asset never logs payloads.
* The orchestrator's live check accepted service_tier: priority for
  openai-codex/gpt-6.1-sol, and rejected service_tier: fast with
  "Codex error: Unsupported service_tier: fast". The backend echoes
  service_tier: default even when priority was requested (known quirk noted in
  pi's CHANGELOG). The echo cannot prove whether Fast was applied.

Verify this fast-moving contract against installed pi/provider source and the
selected model's current catalog when being wrong would affect cost or usage.
Live verification needs separate explicit authorisation, isolation, a call/budget
cap and credential cleanup. Offline tests prove request construction only.
