Setup remediation and approvals
===============================

Install from canonical sources; do not pipe installers into a shell without
user review:

* Pi: https://pi.dev/ and https://github.com/earendil-works/pi
* Worktrunk and shell integration: https://worktrunk.dev/
* GitHub CLI/auth: https://cli.github.com/manual/gh_auth_login
* jq: https://jqlang.org/download/

CLI verification baseline: pi 0.99.1, wt 0.77.0, verified with installed --help,
pi auth --help and wt switch --help. Pi auth is a command group, not a login
command. Use auth check with --model and --no-refresh. Do not use credential
printing commands. Listing models is catalog inspection, not inference; use
--offline to avoid startup catalog refresh. Readiness checks can resolve
user-configured credential commands; review those configurations if untrusted.
No-refresh prevents OAuth renewal; it cannot make arbitrary user extensions or
credential commands pure. The helper never asks pi to implement a task.

Permission review
-----------------

A Claude Code user may consider an allow entry such as ``Bash(pi -p *)`` in
their user-level permissions.allow. It authorises broad prompts to pi, whose
tools have OS access, so narrow it further to their verified executable/model
or require manual approval instead. Review the exact installed Claude Code
permission syntax before proposing a settings diff. Do not edit settings
without explicit approval. An allow rule may still be denied by the auto-mode
classifier; this is not a guaranteed fix.

After plan confirmation, the user can run ``!bash /absolute/path/to/installed/
pi-dispatch.sh launch ... --confirmed`` in Claude Code, using the exact reviewed
arguments and approved model/state/cap. Ask them to use the helper rather than
bare ``!pi -p``: a bare process has no helper metadata and cannot count towards
its cap or receive reliable status. Export approved PI_DISPATCH_STATE_DIR and
PI_DISPATCH_CAP in that user launch environment too. Do not rerun a denied
launch automatically under a different name.

Default config (no secrets)
--------------------------

With user approval only, write a private config with this shape::

    {"model":"provider/model:high","concurrency":2,"fast":false}

An optional stateDirectory is an absolute private path for this repo. Prefer
omitting it for defaults shared across multiple repos, so owner/repo isolation
is preserved. Read existing JSON before proposing an update; merge keys with
jq, write a temporary file and atomically rename. Do not source JSON as shell.
Do not store API keys, OAuth tokens, permission rules or Worktrunk approvals
here. These are dispatch defaults, not pi's own settings.json.

Fast usage and provenance
-------------------------

Offer fast=false by default; saving true needs explicit consent to increased
plan usage. Only an exact openai-codex model with an advertised priority tier
is verified by the offline Codex catalog check. If the catalog is absent or
priority is not listed, warn and ask instead of assuming support. Dispatch's
fast-check reads models_cache.json under CODEX_HOME (default ~/.codex); setup
may ask the orchestrator to use the installed dispatch helper or inspect that
entry with jq. No app-server is started and no inference call is needed.

Maintainer-supplied orchestrator investigation on 2026-10-01 with pi 0.99.1 /
Codex CLI 0.159.1 found gpt-6.1-sol service_tiers priority named Fast with
"2x speed, increased usage" (other GPT-6/5.x entries: 1.5x–2x); the catalog also
has additional_speed_tiers ["fast"] and default_service_tier null. Pi's internal
serviceTier forwards as service_tier, but no pi CLI flag/setting exposes it.
The bundled dispatch assets/service-tier.mjs uses before_provider_request and
pi -e, a maintainer-approved plain ESM language-policy exception; it is required
for this workflow's Fast mode and does not log payloads.

The orchestrator's live probe accepted priority on openai-codex/gpt-6.1-sol and
rejected fast as "Codex error: Unsupported service_tier: fast". The response
can still echo default (known Codex backend quirk noted in pi's CHANGELOG);
status must say priority (requested), never confirmed. These are supplied
observations, not live checks run by setup. Reverify current catalogs and pi's
`extension example <https://github.com/earendil-works/pi/blob/main/packages/coding-agent/examples/extensions/provider-payload.ts>`_
when being wrong could affect cost. Do not enable this globally in pi settings;
only the confirmed dispatch invocation loads the reviewed extension asset.
