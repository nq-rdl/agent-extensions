Advanced .env Patterns with Bitwarden CLI
==========================================

Patterns for common development workflows: multi-environment switching,
CI/CD, team workflows, and integrating with tools that read ``.env`` files.

--------------

Pattern 1: Multi-Environment Switching
---------------------------------------

Store separate items per environment. Switch without file management.

.. code-block:: bash

   # Vault items: myapp-dev, myapp-staging, myapp-prod

   # Load dev
   bwe "myapp-dev"

   # Unload dev, load staging
   bwunload "myapp-dev"
   bwe "myapp-staging"

Naming convention: ``<project>-<env>`` makes ``bwl myapp`` return all
environments sorted together.

--------------

Pattern 2: Generate .env File on Demand (for tools that require files)
-----------------------------------------------------------------------

Some tools (Docker Compose, ``dotenv`` libraries) require an actual ``.env``
file. Generate it on demand from the vault, use it, then delete it.

.. code-block:: bash

   bwdotenv() {
     bwss
     local item="$1"
     local out="${2:-.env}"
     bw get notes "$item" --session "$BW_SESSION" \
       | sed 's/^export //' \
       > "$out"
     >&2 echo "bwdotenv: wrote '$out' (remember to delete after use)"
   }

   # Usage — generate, run, delete
   bwdotenv "myapp-dev"
   docker compose up
   rm .env

**Warning:** Files on disk are less secure than env vars in memory.
Only write to disk when absolutely required by the toolchain.
Never commit the generated ``.env``.

--------------

Pattern 3: CI/CD (GitHub Actions, GitLab CI)
----------------------------------------------

In CI, use the Bitwarden API key login (no interactive password prompt).
Store ``BW_CLIENTID``, ``BW_CLIENTSECRET``, and ``BW_PASSWORD`` as
repository/pipeline secrets in your CI platform.

**GitHub Actions example:**

.. code-block:: yaml

   - name: Install Bitwarden CLI
     run: npm install -g @bitwarden/cli

   - name: Load secrets from Bitwarden
     env:
       BW_CLIENTID: ${{ secrets.BW_CLIENTID }}
       BW_CLIENTSECRET: ${{ secrets.BW_CLIENTSECRET }}
       BW_PASSWORD: ${{ secrets.BW_PASSWORD }}
     run: |
       bw login --apikey
       export BW_SESSION="$(bw unlock --passwordenv BW_PASSWORD --raw)"
       bw get notes "myapp-ci" | sed 's/^export //' >> "$GITHUB_ENV"

The ``>> $GITHUB_ENV`` pattern makes variables available to subsequent steps.

**Note:** This bootstraps Bitwarden with a small set of CI platform secrets.
The tradeoff: you still need 3 CI secrets, but in return you can store
unlimited application secrets in one Bitwarden item.

--------------

Pattern 4: direnv Integration
------------------------------

`direnv <https://direnv.net/>`_ loads ``.envrc`` when you ``cd`` into a directory.
Use it to trigger Bitwarden loading automatically per project.

**.envrc:**

.. code-block:: bash

   # .envrc — committed to git (contains no secrets)
   # Requires: bwss function in ~/.zshrc, bw installed
   if command -v bw &>/dev/null; then
     bwss
     eval "$(bw get notes "myapp-dev" --session "$BW_SESSION")"
   fi

Approve once with ``direnv allow``. Secrets load on ``cd``, unload on ``cd`` out.

**Caution:** This auto-loads secrets on every directory entry. If the
vault is locked you'll be prompted for the master password on every ``cd``.
Better suited for projects with frequent context switching.

--------------

Pattern 5: Storing Structured Credentials as Custom Fields
-----------------------------------------------------------

For credentials with multiple related keys (AWS, database), use a Login item
with custom fields instead of a Secure Note. This lets you retrieve individual
values without parsing.

**Create the item:**

.. code-block:: bash

   bw get template item | jq \
     --arg name "aws-credentials" \
     '.type = 1 | .name = $name |
      .fields = [
        {"name":"AWS_ACCESS_KEY_ID","value":"AKIAIOSFODNN7EXAMPLE","type":1},
        {"name":"AWS_SECRET_ACCESS_KEY","value":"wJalrXUtnFEMI/K7MDENG/bPxRfiCYEXAMPLEKEY","type":1},
        {"name":"AWS_DEFAULT_REGION","value":"eu-west-1","type":0}
      ]' \
     | bw encode | bw create item

**Load all fields into env vars:**

.. code-block:: bash

   load_aws() {
     bwss
     local item
     item="$(bw get item "aws-credentials" --session "$BW_SESSION")"
     eval "$(echo "$item" | jq -r '.fields[] | "export \(.name)=\(.value | @sh)"')"
     >&2 echo "AWS credentials loaded"
   }

--------------

Pattern 6: Syncing Secrets Across Machines
-------------------------------------------

Bitwarden vaults sync automatically. The workflow across machines:

.. code-block:: bash

   # New machine setup
   bw login                              # authenticate once
   export BW_SESSION="$(bw unlock --raw)"
   bw sync                               # pull latest vault
   bwe "myapp-dev"                       # load secrets

No copying `.env` files between machines. Rotate a key once in the vault;
all machines get the new value on next sync.

--------------

Pattern 7: Rotating Secrets
----------------------------

.. code-block:: bash

   # Get existing item, update the notes, save back
   # bwu "myapp-dev" new.env       — updates from a new .env file
   # Or edit inline:

   bwrotate() {
     bwss
     local item_name="$1"
     local field_name="$2"
     local new_value="$3"
     local id
     id="$(bw get item "$item_name" --session "$BW_SESSION" | jq -r '.id')"
     bw get item "$id" --session "$BW_SESSION" \
       | jq --arg f "$field_name" --arg v "$new_value" \
            '(.fields[] | select(.name == $f) | .value) = $v' \
       | bw encode | bw edit item "$id" --session "$BW_SESSION"
     bw sync
   }

   # Usage: bwrotate "github-credentials" "GITHUB_TOKEN" "ghp_newvalue"

--------------

What NOT to Do
--------------

- **Do not** store ``BW_SESSION`` in ``.env``, shell history, or config files.
- **Do not** use ``bw login`` with credentials inline in shell history
  (``bw login email@example.com mysecretpassword``). Use interactive mode.
- **Do not** auto-load secrets at shell startup for all terminals —
  load on-demand per project.
- **Do not** use ``set -x`` / ``bash -x`` in scripts that handle secrets.
- **Do not** ``echo "$BW_SESSION"`` or pipe it through commands that log.
- **Do not** confuse ``bw`` (personal PM) with ``bws`` (Secrets Manager).
