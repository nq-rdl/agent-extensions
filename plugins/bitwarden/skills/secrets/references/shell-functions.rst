Bitwarden Shell Functions Reference
====================================

Complete annotated shell function library for ``.zshrc`` / ``.bashrc``.
All functions assume ``jq`` and ``bw`` are installed and on ``PATH``.

The full drop-in script is at ``examples/bw-env.sh``.

--------------

Session Guard
-------------

Always call this before any ``bw`` command. It unlocks only when no active
session exists in the current shell — avoids redundant password prompts.

.. code-block:: bash

   bwss() {
     if [[ -z "$BW_SESSION" ]]; then
       >&2 echo "bw: vault locked — unlocking..."
       export BW_SESSION="$(bw unlock --raw)"
     fi
   }

Why ``>&2``? Debug/status messages go to stderr so they don't pollute
stdout when the caller is capturing output (e.g., ``val=$(bwss && bw get ...)``).

--------------

Load .env Block from Vault (Core Function)
-------------------------------------------

Loads all variables from a Secure Note into the current shell.

.. code-block:: bash

   # bwe <vault-item-name-or-uuid>
   bwe() {
     bwss
     local notes
     notes="$(bw get notes "$1" --session "$BW_SESSION")"
     if [[ -z "$notes" ]]; then
       >&2 echo "bwe: item '$1' not found or has no notes"
       return 1
     fi
     eval "$notes"
     >&2 echo "bwe: loaded '$1'"
   }

**Requirement:** The Secure Note's content must be lines of:

.. code-block:: bash

   export KEY=value
   export ANOTHER_KEY="value with spaces"

See ``examples/bw-env-format.env`` for the expected format.

--------------

Create Vault Item from .env File
----------------------------------

Stores a .env file as a new Secure Note in the vault.

.. code-block:: bash

   # bwc <vault-item-name> [path-to-env-file]
   # Default env file: .env in current directory
   bwc() {
     bwss
     local name="$1"
     local envfile="${2:-.env}"
     if [[ ! -f "$envfile" ]]; then
       >&2 echo "bwc: file not found: $envfile"
       return 1
     fi
     # Prepend 'export' to any lines that don't already have it
     local notes
     notes="$(awk '/^export /{ print } !/^export /{ print "export " $0 }' "$envfile")"
     bw get template item \
       | jq --arg n "$notes" --arg name "$name" \
            '.type = 2 | .secureNote.type = 0 | .notes = $n | .name = $name' \
       | bw encode | bw create item --session "$BW_SESSION"
   }

--------------

Update Vault Item Notes from .env File
----------------------------------------

Replace the notes on an existing vault item.

.. code-block:: bash

   # bwu <vault-item-name> [path-to-env-file]
   bwu() {
     bwss
     local name="$1"
     local envfile="${2:-.env}"
     if [[ ! -f "$envfile" ]]; then
       >&2 echo "bwu: file not found: $envfile"
       return 1
     fi
     local id
     id="$(bw get item "$name" --session "$BW_SESSION" | jq -r '.id')"
     if [[ -z "$id" || "$id" == "null" ]]; then
       >&2 echo "bwu: item '$name' not found"
       return 1
     fi
     local notes
     notes="$(awk '/^export /{ print } !/^export /{ print "export " $0 }' "$envfile")"
     bw get item "$id" --session "$BW_SESSION" \
       | jq --arg n "$notes" '.notes = $n' \
       | bw encode | bw edit item "$id" --session "$BW_SESSION"
   }

--------------

List Vault Items
-----------------

.. code-block:: bash

   # bwl [search-term]   — list all item names (optionally filtered)
   bwl() {
     bwss
     bw list items --search "${1:-}" --session "$BW_SESSION" \
       | jq -r '.[].name' | sort
   }

   # bwll [search-term]  — list with UUIDs (useful for scripting)
   bwll() {
     bwss
     bw list items --search "${1:-}" --session "$BW_SESSION" \
       | jq -r '.[] | "\(.name)\t\(.id)"' | sort
   }

--------------

Get a Single Custom Field Value
--------------------------------

For Login items with custom fields (not Secure Notes):

.. code-block:: bash

   # bwf <item-name> <field-name>
   bwf() {
     bwss
     bw get item "$1" --session "$BW_SESSION" \
       | jq -r --arg f "$2" '.fields[] | select(.name == $f) | .value'
   }

   # Usage:
   # export GITHUB_TOKEN="$(bwf "github-credentials" "GITHUB_TOKEN")"

--------------

Delete a Vault Item by Name
-----------------------------

.. code-block:: bash

   # bwdd <vault-item-name>   — sends to trash (recoverable)
   bwdd() {
     bwss
     local id
     id="$(bw get item "$1" --session "$BW_SESSION" | jq -r '.id')"
     bw delete item "$id" --session "$BW_SESSION"
     >&2 echo "bwdd: '$1' moved to trash"
   }

--------------

On-Demand Named Loaders (Gruntwork Pattern)
--------------------------------------------

Define per-project functions that are autoloaded but never run at shell startup.
This means secrets are never in memory unless you explicitly call the function.

**~/.zshrc:**

.. code-block:: bash

   fpath=(~/.zsh_autoload_functions "${fpath[@]}")
   autoload -Uz load_github load_myapp_dev load_aws

**~/.zsh_autoload_functions/load_github:**

.. code-block:: bash

   load_github() {
     bwss
     local id="e3e46z6b-a643-4j13-9820-ae4313fg75nd"  # item UUID (use ID not name)
     local token
     token="$(bw get notes "$id" --session "$BW_SESSION")"
     export GITHUB_OAUTH_TOKEN="$token"
     export GITHUB_TOKEN="$token"
     export GIT_TOKEN="$token"
     >&2 echo "GitHub token loaded"
   }

   load_github "$@"

Using the UUID (not the name) prevents breakage if the item is renamed.

--------------

Unloading Secrets
-----------------

Explicitly unset env vars loaded from a Secure Note:

.. code-block:: bash

   # bwunload <vault-item-name>
   bwunload() {
     bwss
     local vars
     vars="$(bw get notes "$1" --session "$BW_SESSION" \
       | grep -oP '(?<=export )\w+')"
     for v in $vars; do
       unset "$v"
     done
     >&2 echo "bwunload: unset vars from '$1'"
   }

--------------

Security Notes
--------------

- ``BW_SESSION`` is a **decryption key** for your entire vault. Never write it
  to disk, log it, or expose it in ``ps`` output. Keep it in memory only.
- Never ``set -x`` (xtrace) when a session key or secret is on the line — it
  will print to stderr/logs.
- Use ``type=1`` (hidden) for custom fields that contain secrets, not ``type=0``
  (text). Hidden fields are masked in the web UI.
- Prefer UUID references (``bw get notes <uuid>``) in permanent scripts to avoid
  breakage from item renames.
