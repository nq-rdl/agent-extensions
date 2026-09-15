Bitwarden Personal Password Manager CLI Reference
=================================================

This reference covers the ``bw`` CLI — the **personal Password Manager**.
It does NOT cover ``bws`` (Bitwarden Secrets Manager).

Source: https://bitwarden.com/help/cli/

--------------

Authentication
--------------

.. code-block:: bash

   # Interactive login (prompts for email + master password + 2FA)
   bw login

   # Login with API key (non-interactive — for CI)
   bw login --apikey
   # Requires: BW_CLIENTID and BW_CLIENTSECRET env vars

   # Check current auth status
   bw status
   # Returns JSON: { serverUrl, lastSync, userEmail, userId, status }
   # status values: unauthenticated | locked | unlocked

Session Management
------------------

After login, unlock the vault to get a session key:

.. code-block:: bash

   # Interactive unlock — prints session key
   bw unlock

   # Capture session key (most common pattern)
   export BW_SESSION="$(bw unlock --raw)"

   # Non-interactive unlock using an env var for the master password
   export BW_PASSWORD="mypassword"
   export BW_SESSION="$(bw unlock --passwordenv BW_PASSWORD --raw)"

   # Non-interactive unlock from a file
   export BW_SESSION="$(bw unlock --passwordfile /path/to/pwfile --raw)"

   # Pass session inline (single command, no export needed)
   bw get item "myitem" --session "$BW_SESSION"

   # Lock the vault (invalidates session)
   bw lock

   # Logout (removes local data)
   bw logout

Sync
----

Vault data is cached locally. Sync to pull the latest from the server:

.. code-block:: bash

   bw sync                # pull latest from server
   bw sync --last         # print timestamp of last sync

--------------

Retrieving Items (``bw get``)
-----------------------------

.. code-block:: bash

   # Get an item by name or UUID
   bw get item "my-api-key"
   bw get item "abc1234-xxxx-xxxx-xxxx-xxxxxxxxxxxx"

   # Get specific fields directly
   bw get password "my-login-item"
   bw get username "my-login-item"
   bw get uri "my-login-item"
   bw get totp "my-login-item"

   # Get the Notes field of an item (key for .env patterns)
   bw get notes "myapp-dev"
   bw get notes "abc1234-xxxx-xxxx-xxxx-xxxxxxxxxxxx"

   # Get an attachment
   bw get attachment "filename.txt" --itemid "abc1234-..."

   # Get a folder
   bw get folder "Development"

Important flags:
- Use ``--raw`` to suppress extra output (only returns the value)
- Pass ``--session`` to avoid relying on the env var

Listing Items (``bw list``)
---------------------------

.. code-block:: bash

   # List all items
   bw list items

   # Search by name
   bw list items --search "myapp"

   # Filter by folder ID
   bw list items --folderid "folder-uuid"

   # Pretty-print JSON
   bw list items --pretty

   # List just names (jq)
   bw list items | jq -r '.[].name'

   # List names with IDs
   bw list items | jq -r '.[] | "\(.id)\t\(.name)"'

   # List folders
   bw list folders

Creating Items (``bw create``)
------------------------------

The workflow is always: get template → edit with jq → encode → create.

.. code-block:: bash

   # See the item template structure
   bw get template item

   # Create a Secure Note (type=2) from a .env file
   bw get template item \
     | jq --rawfile notes .env \
          --arg name "myapp-dev" \
          '.type = 2 | .secureNote.type = 0 | .notes = $notes | .name = $name' \
     | bw encode | bw create item

   # Create a Login item (type=1) with custom fields
   bw get template item \
     | jq --arg name "GITHUB_TOKEN" \
          --arg secret "ghp_xxxx" \
          '.type = 1 | .name = $name |
           .fields = [{"name":"value","value":$secret,"type":1}]' \
     | bw encode | bw create item

   # Create a folder
   bw get template folder | jq '.name = "Development"' | bw encode | bw create folder

Item Types
~~~~~~~~~~

=====  ============
Type   Description
=====  ============
1      Login
2      Secure Note
3      Card
4      Identity
5      SSH Key
=====  ============

Custom Field Types
~~~~~~~~~~~~~~~~~~

=====  ============
Type   Description
=====  ============
0      Text (visible)
1      Hidden (masked — use for secrets)
2      Boolean
=====  ============

Editing Items (``bw edit``)
----------------------------

.. code-block:: bash

   # Update an item — always get first, modify, then edit
   bw get item "myapp-dev" \
     | jq --rawfile notes .env '.notes = $notes' \
     | bw encode | bw edit item "abc1234-xxxx-xxxx-xxxx-xxxxxxxxxxxx"

Deleting Items (``bw delete``)
-------------------------------

.. code-block:: bash

   # Move to trash (recoverable for 30 days)
   bw delete item "abc1234-xxxx-xxxx-xxxx-xxxxxxxxxxxx"

   # Permanent delete (irreversible)
   bw delete item "abc1234-xxxx-xxxx-xxxx-xxxxxxxxxxxx" --permanent

   # Get item ID from name, then delete
   ID=$(bw get item "myapp-dev" | jq -r '.id')
   bw delete item "$ID"

   # Restore from trash
   bw restore item "abc1234-xxxx-xxxx-xxxx-xxxxxxxxxxxx"

--------------

Global Flags
------------

``--session <key>``
    Pass session key inline instead of using ``$BW_SESSION`` env var.

``--raw``
    Return only the value with no decorative output. Essential for scripting.

``--pretty``
    Pretty-print JSON output.

``--nointeraction``
    Disable interactive prompts. Required for non-interactive/CI use.

``--quiet``
    Suppress stdout (useful in scripts where only exit code matters).

--------------

Environment Variables
---------------------

``BW_SESSION``
    Active session key. Set this after ``bw unlock --raw``.

``BW_CLIENTID`` / ``BW_CLIENTSECRET``
    API key credentials for non-interactive login (``bw login --apikey``).

``BITWARDENCLI_APPDATA_DIR``
    Override config/data directory. Useful for multiple account setups.

``BITWARDENCLI_DEBUG=true``
    Enable verbose debug output.

``NODE_EXTRA_CA_CERTS``
    Path to CA bundle for self-signed certificate environments.

--------------

Useful jq Patterns
------------------

.. code-block:: bash

   # Get notes field (raw, no quotes)
   bw get item "name" | jq -r '.notes'

   # Get a custom field by name
   bw get item "name" | jq -r '.fields[] | select(.name=="MY_KEY") | .value'

   # List all custom field names
   bw get item "name" | jq -r '.fields[].name'

   # Get item ID from name
   bw get item "name" | jq -r '.id'

   # Format name+id table from list
   bw list items | jq -r '.[] | "\(.name)\t\(.id)"'
