Encrypting using HashiCorp Vault
=================================

SOPS can use HashiCorp Vault as a backend for encryption via Vault's transit engine.

Setup
-----

First, ensure you have a transit engine enabled in Vault. It is suggested to create a transit engine specifically for SOPS.

.. code-block:: bash

   # Enable the transit secrets engine
   vault secrets enable -path=sops transit

   # Create keys
   vault write sops/keys/firstkey type=rsa-4096
   vault write sops/keys/secondkey type=rsa-2048
   vault write sops/keys/thirdkey type=chacha20-poly1305

Authentication
--------------

SOPS uses the standard Vault client libraries, so it honours the same authentication mechanisms as the ``vault`` CLI. Both encrypt **and** decrypt operations require a reachable Vault instance with a valid credential.

**Token-based auth (most common):**

.. code-block:: bash

   export VAULT_ADDR=http://vault.example.com:8200
   export VAULT_TOKEN=s.xxxxxxxxxxxx

If ``VAULT_TOKEN`` is not set, the Vault client falls back to the token stored in ``~/.vault-token`` (written by ``vault login``).

**AppRole auth:**

.. code-block:: bash

   # Obtain a token from AppRole credentials
   vault write auth/approle/login \
     role_id=<ROLE_ID> \
     secret_id=<SECRET_ID>

   # Export the client_token from the response
   export VAULT_TOKEN=<client_token>

The ``VAULT_ADDR``, ``VAULT_TOKEN``, and any TLS-related environment variables (``VAULT_CACERT``, ``VAULT_SKIP_VERIFY``) must be available at **both** encrypt and decrypt time — not just when the file is first created.

Encrypting via CLI
------------------

You can encrypt a file using the HashiCorp Vault transit engine directly from the CLI. ``sops encrypt`` writes to **stdout** by default — redirect to a file or use ``-i`` to overwrite the source in place:

.. code-block:: bash

   export VAULT_ADDR=http://127.0.0.1:8200
   export VAULT_TOKEN=... # Only needed if not already logged in

   # Redirect to a new file (recommended — keeps the original):
   sops encrypt --hc-vault-transit $VAULT_ADDR/v1/sops/keys/firstkey vault_example.yml > vault_example.enc.yml

   # Or encrypt in place:
   sops encrypt -i --hc-vault-transit $VAULT_ADDR/v1/sops/keys/firstkey vault_example.yml

Using .sops.yaml
----------------

A HashiCorp Vault transit URI can be added to ``.sops.yaml`` to specify rules:

.. code-block:: yaml

   creation_rules:
       - path_regex: \.dev\.yaml$
         hc_vault_transit_uri: "http://127.0.0.1:8200/v1/sops/keys/secondkey"
       - path_regex: \.prod\.yaml$
         hc_vault_transit_uri: "http://127.0.0.1:8200/v1/sops/keys/thirdkey"

Then you can encrypt your target file simply, since SOPS will apply the correct ``hc_vault_transit_uri``:

.. code-block:: bash

   sops encrypt --verbose prod/raw.yaml > prod/encrypted.yaml

Rotating Keys
-------------

After changing recipients in ``.sops.yaml``, re-encrypt the data key with the current Vault transit key:

.. code-block:: bash

   sops updatekeys prod/encrypted.yaml

This re-wraps the symmetric data key against the new Vault transit URI without re-encrypting the underlying values.

**Rotating the Vault transit key itself** (cryptographic rotation) is a separate operation performed in Vault:

.. code-block:: bash

   vault write -f sops/keys/firstkey/rotate

After a Vault key rotation, Vault uses the new key version for new encrypt operations but can still decrypt data encrypted with older versions (controlled by ``min_decryption_version``). To clean up old key versions and enforce a minimum version, see the `Vault Transit Secrets Engine documentation <https://developer.hashicorp.com/vault/docs/secrets/transit>`_ — do not set ``min_decryption_version`` higher than the version used to encrypt your oldest file without first running ``sops updatekeys`` on all affected files.
