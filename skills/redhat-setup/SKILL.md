---
name: redhat-setup
license: CC-BY-4.0
description: >-
  Check whether this machine can fetch Red Hat documentation and Customer Portal
  content, and when the personal Red Hat offline token is missing, guide the user
  through generating it, storing it (Bitwarden, OS keychain, or a 0600 file),
  loading it, and verifying it — without the secret ever entering the chat. Use
  when a Red Hat fetch reports "no offline token", "subscriber_only",
  "invalid_grant", or when onboarding a teammate to the redhat plugin.
argument-hint: '[--check-only]'
user-invocable: true
allowed-tools: Bash, AskUserQuestion
metadata:
  repo: https://github.com/nq-rdl/agent-extensions
---

# Red Hat docs — setup

Each teammate uses their **own** Red Hat account. The plugin never asks for the token
in conversation: every step below either prompts the user in their own terminal or reads
the secret from a store. **Never ask the user to paste the token here, and never run a
command that would print it.**

## 1. Check

```bash
S="${CLAUDE_PLUGIN_ROOT}/skills/fetch-docs/scripts"
bash "$S/rh-preflight.sh" --json
```

Report OS, fetcher, and `credential` (a source name: `env`, `keychain`, `file`,
`bitwarden`, or `none`). If `fetcher` is `none`, stop: curl must be installed first
(`brew install curl` / `dnf install curl` / `apt install curl`). If `jq` is `no`, same.

If `credential` is not `none`, verify and finish:

```bash
bash "$S/rh-token.sh" --check      # → source=<src> access_token=ok expires_in=900s
```

Exit `4` means Red Hat SSO rejected the token (`invalid_grant`, typically 30 days unused):
continue at step 2 to regenerate. With `--check-only`, stop after reporting.

## 2. Generate (user does this in a browser)

Tell the user, verbatim:

1. Open <https://access.redhat.com/management/api> and log in with **your** Red Hat account.
2. Click **Generate Token**. Copy it now — it is shown once and is not stored by Red Hat.
3. It stays valid as long as it is used at least once every **30 days**; after that,
   regenerate here and re-store it.

## 3. Store — ask once, then give the matching commands

Use `AskUserQuestion` exactly once, options in this order:

- **Bitwarden personal vault (Recommended)** — team standard; syncs across machines.
- **OS keychain** — macOS Keychain or Linux Secret Service; no vault needed.
- **0600 file** — `~/.config/redhat/offline-token`; least preferred (plaintext at rest).

The user runs the store command **in their own terminal** (not via `!`, whose output
lands in the transcript). Give only the chosen block:

**Bitwarden** (the `bitwarden:secrets` pattern — Secure Note named `redhat-credentials`):

```bash
export BW_SESSION="$(bw unlock --raw)"
printf 'Paste offline token: '; IFS= read -rs t; echo
[ -n "$t" ] && bw get template item \
  | jq --rawfile notes <(printf 'export RH_OFFLINE_TOKEN=%s\n' "$t") --arg name redhat-credentials \
       '.type = 2 | .secureNote.type = 0 | .notes = $notes | .name = $name' \
  | bw encode | bw create item >/dev/null && echo stored; unset t
```

Works in bash and zsh (the macOS default). The template goes to `jq` on stdin and the
note text through a process substitution, so the token is never an argument of any
process. If the block is unfamiliar, the equivalent is: create a Secure Note called
`redhat-credentials` whose content is one line, `export RH_OFFLINE_TOKEN=<token>`.

**macOS keychain** (prompts for the secret, keeps it out of shell history):

```bash
security add-generic-password -a "$USER" -s RH_OFFLINE_TOKEN -U -w
```

**Linux Secret Service**:

```bash
secret-tool store --label='Red Hat offline token' service redhat key RH_OFFLINE_TOKEN
```

**0600 file** (bash or zsh — `read -p` is deliberately avoided: zsh reads it as a coprocess
and would silently store an empty file):

```bash
mkdir -p ~/.config/redhat && (umask 077; printf 'Paste offline token: '; IFS= read -rs t; echo; [ -n "$t" ] && printf '%s\n' "$t" > ~/.config/redhat/offline-token && chmod 600 ~/.config/redhat/offline-token && echo stored)
```

## 4. Load

- **Bitwarden**: before launching `claude`, in the shell: `export BW_SESSION="$(bw unlock --raw)"`
  then `eval "$(bw get notes redhat-credentials)"` (or `bwe redhat-credentials` from
  `bitwarden:secrets`). Tool calls inherit that environment. Alternatively leave
  `BW_SESSION` exported and the scripts read the note on demand.
- **Keychain / file**: nothing to load — the scripts resolve them directly.
- Resolution order is `env → keychain → file → bitwarden`; restrict with
  `RH_CRED_SOURCES=env,file` if needed.

## 5. Verify

```bash
bash "$S/rh-token.sh" --check
```

Success prints the source and `expires_in` only. Then hand back to
`/redhat:fetch-docs`. If it prints `invalid_grant`, the pasted token is wrong or
expired — regenerate (step 2) and re-store.
