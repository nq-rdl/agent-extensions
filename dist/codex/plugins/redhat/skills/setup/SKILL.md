---
name: setup
license: CC-BY-4.0
description: Check whether this machine can fetch Red Hat documentation and Customer
  Portal content, and when the personal Red Hat offline token is missing, guide the
  user through generating it, storing it (Bitwarden, OS keychain, or a 0600 file),
  loading it, and verifying it – without the secret ever entering the chat. Use when
  a Red Hat fetch reports "no offline token", "subscriber_only", "invalid_grant",
  or when onboarding a teammate to the redhat plugin.
compatibility: Red Hat SSO offline tokens from access.redhat.com/management/api (30-day
  idle expiry) as of 2026-08; Bitwarden CLI 2026.8.0 (source-verified sync/list/get/create/edit
  contract); macOS security(1) keychain; libsecret secret-tool on Linux; jq >= 1.6
  (`--rawfile`); bash or zsh for the paste prompts.
metadata:
  repo: https://github.com/nq-rdl/agent-extensions
---

## Codex execution

Before shell examples, set PLUGIN_ROOT to the absolute installed plugin directory: two parent directories above this SKILL.md’s containing skill directory. Derive it from the loaded file path, never the working directory. This variable is not automatically supplied to ordinary shell tools. Quote it in commands.

# Red Hat docs – setup

Each teammate uses their **own** Red Hat account. The plugin never asks for the token
in conversation: every step below either prompts the user in their own terminal or reads
the secret from a store. **Never ask the user to paste the token here, and never run a
command that would print it.**

Before changing or relying on Bitwarden CLI behavior, verify the installed version against
the [official CLI documentation](https://bitwarden.com/help/cli/) and the
[pinned lookup implementation](https://github.com/bitwarden/clients/blob/cli-v2026.8.0/apps/cli/src/commands/get.command.ts).
The offline tests use shims; they do not replace verification against the installed CLI.

## 1. Check

```bash
S="${PLUGIN_ROOT}/skills/fetch-docs/scripts"
bash "$S/rh-preflight.sh" --json
```

Report OS, fetcher, `bw`, and `credential` (a source name: `env`, `keychain`, `file`,
`bitwarden`, or `none`). If `fetcher` is `none`, stop: curl must be installed first
(`brew install curl` / `dnf install curl` / `apt install curl`). If `jq` is `no`, same.
If `bw` is `no`, say so beside the Bitwarden option in step 3 (still list it first).

If `credential` is not `none`, verify and finish:

```bash
bash "$S/rh-token.sh" --check      # → source=<src> access_token=ok expires_in=900s
```

Exit `4` means Red Hat SSO rejected the token (`invalid_grant`, typically 30 days unused):
continue at step 2 to regenerate.

Exit `3` here means the source was found but yields no token (a `redhat-credentials` note
without an `RH_OFFLINE_TOKEN=` line or with an empty value, or a token file whose first line
is blank – only line 1 is read): skip step 2 if the user still has their token and re-store
it at step 3 with the same source.

With `--check-only`, stop after this step whatever `credential` says.

## 2. Generate (user does this in a browser)

Tell the user, verbatim:

1. Open <https://access.redhat.com/management/api> and log in with **your** Red Hat account.
2. Click **Generate Token**. Copy it now – it is shown once and is not stored by Red Hat.
3. It stays valid as long as it is used at least once every **30 days**; after that,
   regenerate here and re-store it.

## 3. Store – ask once, then give the matching commands

Use `the host user-question tool` exactly once, options in this order:

- **Bitwarden personal vault (Recommended)** – team standard; syncs across machines.
- **OS keychain** – macOS Keychain or Linux Secret Service; no vault needed.
- **0600 file** – `${XDG_CONFIG_HOME:-$HOME/.config}/redhat/offline-token` (or `$RH_OFFLINE_TOKEN_FILE`);
  least preferred (plaintext at rest).

The user runs the store command **in their own terminal** (not via `!`, whose output
lands in the transcript). Give only the chosen block:

**Bitwarden** (the `bitwarden:secrets` pattern – Secure Note named `redhat-credentials`):

```bash
s="$(bw unlock --raw)"; [ -n "$s" ] && export BW_SESSION="$s"; unset s
if [ -z "${BW_SESSION:-}" ] || ! bw sync >/dev/null; then echo "unlock or sync failed – fix that, then re-run" >&2; else
  # get notes and list --search use the same basic search, including names and note contents
  if ! items="$(bw list items --search redhat-credentials 2>/dev/null)"; then
    echo "vault lookup failed – fix that, then re-run" >&2
  elif ! hits="$(printf '%s' "$items" | jq -ecs '
    if length != 1 or (.[0] | type) != "array" then error("expected one item array")
    else .[0] | map(
      if (.id | type) != "string" or .id == "" or (.name | type) != "string"
      then error("invalid item") else {id, name} end) end' 2>/dev/null)"; then
    echo "vault lookup returned invalid data – fix that, then re-run" >&2
  elif ! count="$(printf '%s' "$hits" | jq -er 'length')" \
    || ! id="$(printf '%s' "$hits" | jq -r '.[] | select(.name == "redhat-credentials") | .id')" \
    || ! names="$(printf '%s' "$hits" | jq -r '[.[].name] | join(", ")')"; then
    echo "vault lookup filter failed – fix that, then re-run" >&2
  elif [ "$count" -gt 1 ]; then
    echo "more than one note matches 'redhat-credentials' ($names) – keep exactly one, named redhat-credentials, then re-run" >&2
  elif [ -n "$names" ] && [ -z "$id" ]; then
    echo "a note named '$names' would shadow 'redhat-credentials' – rename it to redhat-credentials (or delete it), then re-run" >&2
  else
    printf 'Paste offline token: '; IFS= read -rs t; echo
    if [ -n "$t" ] && [ -n "$id" ]; then
      bw get item "$id" | jq --rawfile notes <(printf 'export RH_OFFLINE_TOKEN=%s\n' "$t") '.notes = $notes' \
        | bw encode | bw edit item "$id" >/dev/null && echo updated
    elif [ -n "$t" ]; then
      bw get template item \
        | jq --rawfile notes <(printf 'export RH_OFFLINE_TOKEN=%s\n' "$t") --arg name redhat-credentials \
             '.type = 2 | .secureNote.type = 0 | .notes = $notes | .name = $name' \
        | bw encode | bw create item >/dev/null && echo stored
    fi
  fi
fi; unset t id hits names items count
```

Works in bash and zsh (the macOS default). The template goes to `jq` on stdin and the
note text through a process substitution, so the token is never an argument of any
process. An unavailable session, failed sync, failed lookup, or invalid lookup JSON stops
the block before it asks for the token or writes to the vault. Re-running
(a regenerated token) **edits the existing note in place**. The block refuses when the vault
returns more than one search result, or a result not named exactly `redhat-credentials`.
Bitwarden 2026.8.0 searches names, notes, and other indexed fields, so even a differently
named item mentioning `redhat-credentials` can make the lookup ambiguous. Remove the
matching text from unrelated items or rename the intended note, then retry. If the block
is unfamiliar, the equivalent is: create (or update) a Secure Note called `redhat-credentials` whose content is
one line, `export RH_OFFLINE_TOKEN=<token>`.

**macOS keychain** (prompts for the secret, keeps it out of shell history):

```bash
security add-generic-password -a "$USER" -s RH_OFFLINE_TOKEN -U -w
```

**Linux Secret Service** (prompts for the secret, keeps it out of shell history):

```bash
secret-tool store --label='Red Hat offline token' service redhat key RH_OFFLINE_TOKEN
```

**0600 file** (bash or zsh – `read -p` is deliberately avoided: zsh reads it as a coprocess
and would silently store an empty file):

```bash
d="${XDG_CONFIG_HOME:-$HOME/.config}/redhat" && mkdir -p "$d" && (umask 077; printf 'Paste offline token: '; IFS= read -rs t; echo; [ -n "$t" ] && printf '%s\n' "$t" > "$d/offline-token" && chmod 600 "$d/offline-token" && echo "stored in $d/offline-token")
```

The path honours `XDG_CONFIG_HOME` because the scripts resolve the same
`${XDG_CONFIG_HOME:-$HOME/.config}/redhat/offline-token` (or `RH_OFFLINE_TOKEN_FILE`).

## 4. Load

- **Bitwarden**: before launching `claude`, in the shell: `export BW_SESSION="$(bw unlock --raw)"`
  then `eval "$(bw get notes redhat-credentials)"` (or `bwe redhat-credentials` from
  `bitwarden:secrets`). Tool calls inherit that environment. Alternatively leave
  `BW_SESSION` exported and the scripts read the note on demand.
- **Keychain / file**: nothing to load – the scripts resolve them directly.
- Resolution order is `env → keychain → file → bitwarden`; restrict with
  `RH_CRED_SOURCES=env,file` if needed.

## 5. Verify

```bash
bash "$S/rh-token.sh" --check
```

`--check` always performs a fresh exchange (it never reports a cached access token), so
it verifies the token that was just stored. Success prints the source and `expires_in`
only. Then hand back to `$redhat:fetch-docs`. If it prints `invalid_grant`, the pasted
token is wrong or expired – regenerate (step 2) and re-store.

If it exits `3`, first confirm storage completed: Bitwarden must report `stored` or
`updated`, the file block must report `stored in ...`, and the keychain command must
finish successfully. An empty paste, cancelled prompt, or failed write means step 3
must be retried; do not diagnose a session problem until storage succeeds.

Then read the message. "No Red Hat offline token found" means no usable credential
was found; after successful storage, check visibility to this session: for Bitwarden,
`BW_SESSION` (or the `bwe`-loaded `RH_OFFLINE_TOKEN`)
must be in the environment `claude` was launched from – finish step 4 in that shell and
restart `claude`, or have the user run the same `rh-token.sh --check` in the terminal where
the vault is unlocked (give the expanded `$S` path; `CLAUDE_PLUGIN_ROOT` is not set there; it
prints only the source and `expires_in`); for a file, `HOME`/`XDG_CONFIG_HOME` must match the
path step 3 printed; for the Linux keychain, the Secret Service must be reachable from this
session. "returned an empty token" means the store was found but holds no usable line –
re-store at step 3.
