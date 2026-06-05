---
name: bitwarden
license: CC-BY-4.0
description: >-
  Manage .env files and development secrets using the Bitwarden personal
  Password Manager CLI (bw). Use when the user asks to store, retrieve, or
  inject secrets / API keys / .env variables from Bitwarden. This skill covers
  the PERSONAL password manager only — NOT Bitwarden Secrets Manager. Trigger
  on: "bitwarden .env", "bw CLI secrets", "load API keys from bitwarden",
  "store credentials in bitwarden", "inject env vars from bitwarden".
metadata:
  repo: https://github.com/nq-rdl/agent-skills
---

# Bitwarden Personal PM — .env & Dev Secrets

Use the Bitwarden **personal** Password Manager CLI (`bw`) to store and load
development secrets without ever touching a plaintext `.env` file on disk.

> **CRITICAL DISTINCTION**
> This skill uses the **personal Password Manager** — the `bw` CLI.
> It does **NOT** use Bitwarden Secrets Manager (`bws`).
> See [Password Manager overview](https://bitwarden.com/help/password-manager-overview/) vs
> [Secrets Manager overview](https://bitwarden.com/help/secrets-manager-overview/).

---

## Why Bitwarden for .env?

| Problem | Solution |
|---------|----------|
| Plaintext `.env` files leak into git or logs | Secrets live only in encrypted vault |
| Sharing secrets across machines is risky | Vault syncs automatically — no copying |
| Secrets stay in memory all session | On-demand loading — gone when terminal closes |
| Hard to rotate or audit | One vault item to update, all scripts get fresh value |

---

## Quick-Start: Store & Load in 5 Minutes

### 1. Install & Authenticate

```bash
# Install (choose one)
npm install -g @bitwarden/cli    # npm
brew install bitwarden-cli       # macOS Homebrew
snap install bw                  # Linux Snap

# Log in once (interactive — stores credentials in system keychain)
bw login

# Unlock vault for the session and capture the session key
export BW_SESSION="$(bw unlock --raw)"
```

### 2. Store a Block of .env Variables

Best pattern: store an entire `.env` block as a **Secure Note** in the vault.

```bash
# Store from an existing .env file
bw get template item | jq \
  --rawfile notes .env \
  --arg name "myproject-dev" \
  '.type = 2 | .secureNote.type = 0 | .notes = $notes | .name = $name' \
  | bw encode | bw create item
```

Or store a single credential on a **Login item**'s custom fields:

```bash
bw get template item | jq \
  --arg name "GITHUB_TOKEN" \
  --arg secret "ghp_xxxx" \
  '.type = 1 | .name = $name | .fields = [{"name":"value","value":$secret,"type":1}]' \
  | bw encode | bw create item
```

### 3. Load Secrets into Current Shell

```bash
# Load entire .env block from a Secure Note
eval "$(bw get notes "myproject-dev")"

# Load a single custom field value
export GITHUB_TOKEN="$(bw get item "GITHUB_TOKEN" | jq -r '.fields[] | select(.name=="value") | .value')"

# Load using item ID (faster — no search ambiguity)
export GITHUB_TOKEN="$(bw get notes abc1234-xxxx-xxxx-xxxx-xxxxxxxxxxxx)"
```

---

## Recommended Vault Naming Convention

Use a consistent pattern so `bw list items --search` is predictable:

```
<project>-<env>          # e.g.  myapp-dev, myapp-staging, myapp-prod
<service>-credentials    # e.g.  aws-credentials, github-credentials
```

Example vault layout:

```
myapp-dev          (Secure Note)  — full .env block for local dev
myapp-staging      (Secure Note)  — staging .env block
aws-credentials    (Login)        — AWS_ACCESS_KEY_ID + AWS_SECRET_ACCESS_KEY as custom fields
github-credentials (Login)        — GITHUB_TOKEN as custom field
```

---

## Shell Functions Reference

Add these to `~/.zshrc` or `~/.bashrc`. See [references/shell-functions.rst](references/shell-functions.rst) for the full annotated set.

```bash
# Unlock vault if no active session
bwss() {
  if [[ -z "$BW_SESSION" ]]; then
    export BW_SESSION="$(bw unlock --raw)"
  fi
}

# Load a Secure Note's contents as env vars into current shell
# Usage: bwe "myapp-dev"
bwe() {
  bwss
  eval "$(bw get notes "$1" --session "$BW_SESSION")"
}

# Create a Secure Note from current .env file
# Usage: bwc "myapp-dev"    (reads .env in current dir)
bwc() {
  bwss
  bw get template item \
    | jq --rawfile notes "${2:-.env}" \
         --arg name "$1" \
         '.type = 2 | .secureNote.type = 0 | .notes = $notes | .name = $name' \
    | bw encode | bw create item --session "$BW_SESSION"
}

# Update an existing vault item's notes from current .env file
# Usage: bwu "myapp-dev"
bwu() {
  bwss
  local id
  id="$(bw get item "$1" --session "$BW_SESSION" | jq -r '.id')"
  bw get item "$id" --session "$BW_SESSION" \
    | jq --rawfile notes "${2:-.env}" '.notes = $notes' \
    | bw encode | bw edit item "$id" --session "$BW_SESSION"
}

# List all vault item names (filterable)
# Usage: bwl [filter]
bwl() {
  bwss
  bw list items --search "${1:-}" --session "$BW_SESSION" \
    | jq -r '.[].name' | sort
}

# Delete a vault item by name
# Usage: bwdd "myapp-dev"
bwdd() {
  bwss
  local id
  id="$(bw get item "$1" --session "$BW_SESSION" | jq -r '.id')"
  bw delete item "$id" --session "$BW_SESSION"
}
```

---

## Security Rules

1. **Never export `BW_SESSION` to disk.** It decrypts the entire vault. It lives only in the current shell's memory.
2. **Use item IDs in production scripts** — `bw get notes <UUID>` — not names. Names can have duplicates; the CLI errors on ambiguity.
3. **Store `.env` blocks with `export` prefix** so `eval "$(bw get notes ...)"` populates the current shell.
4. **Avoid `bw unlock` in cron/CI.** Use `--apikey` with `BW_CLIENTID` / `BW_CLIENTSECRET` and `bw unlock --passwordenv`.
5. **Sync before reading stale data**: `bw sync` to pull latest from server.
6. **Do not commit `.env` files** — the whole point. Use `.gitignore`.
7. **Secrets Manager is NOT this.** If someone suggests `bws` commands, that is a different product.

---

## Common Patterns

### Pattern 1: On-Demand Loading (Recommended)

Load secrets into the current terminal only when needed. They disappear when the terminal closes.

```bash
# In .zshrc — define but don't auto-run
autoload -Uz load_myapp_dev
```

```bash
# In ~/.zsh_autoload_functions/load_myapp_dev
load_myapp_dev() {
  bwss
  eval "$(bw get notes "myapp-dev" --session "$BW_SESSION")"
  echo "myapp-dev secrets loaded"
}
```

### Pattern 2: Multiple Environments

Switch contexts cleanly without conflicting env vars:

```bash
bwe "myapp-dev"      # loads dev secrets
# ... work ...
unset $(bw get notes "myapp-dev" | grep -oP '(?<=export )\w+')  # unload

bwe "myapp-staging"  # load staging secrets
```

### Pattern 3: Individual Credential Loading (Gruntwork Pattern)

Store a single token in a Secure Note. Use a named shell function per credential:

```bash
load_github() {
  bwss
  local id='e3e46z6b-a643-4j13-9820-ae4313fg75nd'  # item UUID
  local token
  token="$(bw get notes "$id" --session "$BW_SESSION")"
  export GITHUB_OAUTH_TOKEN="$token"
  export GITHUB_TOKEN="$token"
  export GIT_TOKEN="$token"
}
```

### Pattern 4: Custom Fields for Structured Credentials

Store AWS keys as separate custom fields on a Login item:

```bash
# Retrieve individual fields
export AWS_ACCESS_KEY_ID="$(bw get item "aws-credentials" | jq -r '.fields[] | select(.name=="AWS_ACCESS_KEY_ID") | .value')"
export AWS_SECRET_ACCESS_KEY="$(bw get item "aws-credentials" | jq -r '.fields[] | select(.name=="AWS_SECRET_ACCESS_KEY") | .value')"
```

---

## Reference Files

| File | Contents |
|------|----------|
| [references/cli.rst](references/cli.rst) | Full `bw` CLI command reference — all flags, options, output formats |
| [references/shell-functions.rst](references/shell-functions.rst) | Complete annotated shell function library with security notes |
| [references/env-patterns.rst](references/env-patterns.rst) | Advanced patterns: multi-env, CI/CD, team workflows |

## Example Files

| File | What it does |
|------|-------------|
| [examples/bw-env.sh](examples/bw-env.sh) | Drop-in shell functions for .zshrc / .bashrc |
| [examples/load-github.sh](examples/load-github.sh) | On-demand GitHub token loader (Gruntwork pattern) |
| [examples/bw-env-format.env](examples/bw-env-format.env) | Example .env format suitable for `eval` loading |
