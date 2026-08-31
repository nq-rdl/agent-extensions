---
license: CC-BY-4.0
description: >-
  Fetch Red Hat product documentation and Customer Portal knowledge base (KCS)
  content — including subscriber-only solutions — using the user's own Red Hat
  offline token and curl/wget, on macOS or Linux. Use when the user gives a
  docs.redhat.com or access.redhat.com URL, a KCS solution/article id, or asks
  to look something up in Red Hat documentation, OpenShift docs, Ansible
  Automation Platform docs, or the Red Hat knowledge base. Do NOT use WebFetch
  or defuddle on these hosts — they get an Akamai 403 or a login-gated page.
argument-hint: '<docs.redhat.com URL | access.redhat.com/solutions/<id> | kcs:<id> | search:<terms>>'
user-invocable: true
compatibility: >-
  Customer Portal search API (api.access.redhat.com/support/search/kcs) and
  Red Hat SSO offline-token exchange as of 2026-08; source-repo layouts of
  ansible/aap-docs (2.x branches) and openshift/openshift-docs (enterprise-4.x).
  Needs curl (or wget) and jq; gh optional (raises GitHub API rate limits).
metadata:
  repo: https://github.com/nq-rdl/agent-extensions
---

# Red Hat docs — fetch by the route that works

Red Hat's documentation is public but **`docs.redhat.com` returns HTTP 403 to every
non-browser client** (Akamai bot fingerprinting — no User-Agent or header trick changes
it, and evading it is out of scope). Subscriber-only knowledge base content needs the
person's **own** Red Hat account. This skill's scripts pick the working route for you.

| Target | Route | Credential |
|---|---|---|
| `docs.redhat.com/…/html/<book>/<page>#anchor` (also the legacy `access.redhat.com/documentation/<locale>/…` form) | The product's **open-source doc repo on GitHub** (AsciiDoc) | none |
| `access.redhat.com/solutions/<id>`, `/articles/<id>`, `kcs:<id>` | Customer Portal **KCS search API** with `fq=id:` + Bearer token | offline token |
| `search:<terms>` | KCS search API (metadata is public) | none |
| `docs-text:<docs URL>` | *Experimental* — the KCS index's stored page text (keyed by page URL; `#anchor` ignored); only route for closed-source products (RHEL) | offline token |

## Do this

```bash
S="${CLAUDE_PLUGIN_ROOT}/skills/fetch-docs/scripts"     # canonical in-repo: skills/redhat-docs-fetch/scripts
bash "$S/rh-preflight.sh"                                # OS, fetcher, credential source (never the value)
bash "$S/rh-fetch.sh" 'https://docs.redhat.com/en/documentation/red_hat_ansible_automation_platform/2.5/html/operating_ansible_automation_platform/assembly-configure-egress-proxy#proc-set-community-remote'
bash "$S/rh-fetch.sh" --includes '<docs URL>'            # inline first-level include:: modules
bash "$S/rh-fetch.sh" kcs:7137578                        # Markdown: Environment/Issue/Resolution/Root Cause/…
bash "$S/rh-fetch.sh" --kind Solution --rows 5 'search:automation hub proxy 403'
bash "$S/rh-token.sh" --check                            # source=… access_token=ok expires_in=900s
```

Exit codes: `3` = no credential, not entitled, or the offline token was rejected (30-day
idle expiry — the message says to regenerate) → tell the user to run **`/redhat:setup`**;
`4` = unresolvable (unknown product/slug) → say so and offer `search:` / `docs-text:` /
a browser. Render AsciiDoc to Markdown yourself; keep the `// source:` provenance line
in your answer.

## Non-obvious facts the scripts encode (don't work around them)

- **URL → source file.** AAP: `ansible/aap-docs`, branch = version (`2.5`), files under
  `downstream/{assemblies,modules}/`; the page slug and every `#anchor` are **file names**
  (`proc-set-community-remote.adoc`) whose `[id=…]` equals the anchor. OpenShift:
  `openshift/openshift-docs`, branch `enterprise-<ver>`; the page slug is the assembly
  file name located via `_topic_maps/_topic_map.yml` (nested `Dir`/`File`), modules under
  `modules/`, and anchors are `<module-file>_{context}` — the script strips the suffix to
  find the module (so `html-single/…/index#anchor` URLs resolve too). Satellite builds from `theforeman/foreman-documentation`
  (`guides/doc-<Title>/`, `BUILD=satellite`). **RHEL has no public source.**
  Details: `references/source-repos.rst`.
- **No "get solution by id" endpoint exists.** The `resource_uri` the API returns
  (`/rs/solutions/<id>`) is the decommissioned Strata API (HTTP 410). The body comes from
  the search endpoint filtered by id. `references/customer-portal-api.rst`.
- **A bad Bearer token is silently ignored**: HTTP 200 with the literal string
  `"subscriber_only"` in the body fields. `rh-fetch.sh` treats that as *not authenticated*
  (exit 3); never conclude "the content is empty".
- **`access.redhat.com` HTML redirects to a `/ja/` locale from some networks** regardless
  of `Accept-Language`, cookies, or an explicit `/en/` path, and the page body is
  login-gated anyway. Use `view_uri` for provenance only; the API is the content route.
- **Credentials never transit the model.** `rh-token.sh` resolves the offline token from
  `RH_OFFLINE_TOKEN` → OS keychain → 0600 file → Bitwarden (`bw`, item
  `redhat-credentials`), exchanges it at Red Hat SSO (`client_id=rhsm-api`,
  `grant_type=refresh_token`) for a 15-minute access token cached 0600, and hands curl a
  `-K` config. Never `echo` the token, never put it in argv, never ask the user to paste
  it into the chat. Offline tokens die after **30 days unused** → `invalid_grant` → the
  script says to regenerate; hand the user to `/redhat:setup`.
- **Platform**: `curl` first, `wget` fallback (absent on stock macOS and many servers);
  scripts run on bash 3.2. `references/platform-notes.rst`.

## Verify against the canonical source when being wrong would mislead

Version-specific procedures change between branches: fetch the branch that matches the
user's product version (the script derives it from the URL) and quote the `// source:`
line. For API behaviour, Red Hat's own page is
<https://access.redhat.com/articles/3626371> (Getting started with Red Hat APIs).

## Reference files

| File | Contents |
|---|---|
| [references/source-repos.rst](references/source-repos.rst) | Verified docs.redhat.com → GitHub map, URL→path recipes, closed products |
| [references/customer-portal-api.rst](references/customer-portal-api.rst) | KCS search endpoint, params, fields, auth flow, the 410/`subscriber_only`/locale gotchas |
| [references/platform-notes.rst](references/platform-notes.rst) | macOS vs Linux differences the scripts account for |

## Scripts

| File | What it does |
|---|---|
| [scripts/rh-preflight.sh](scripts/rh-preflight.sh) | OS / fetcher / jq / gh / bw / credential-source report (`--json`, `--require-cred`) |
| [scripts/rh-token.sh](scripts/rh-token.sh) | Offline token → cached access token; `--check`, `--curl-config`, `--clear` |
| [scripts/rh-fetch.sh](scripts/rh-fetch.sh) | Route + fetch: docs URL, solution/article/`kcs:` id, `search:`, `docs-text:` |
| [scripts/rh-lib.sh](scripts/rh-lib.sh) | Shared helpers (credential resolution, curl/wget abstraction) |
