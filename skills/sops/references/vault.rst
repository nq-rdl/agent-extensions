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

Encrypting via CLI
------------------

You can encrypt a file using the HashiCorp Vault transit engine directly from the CLI:

.. code-block:: bash

   export VAULT_ADDR=http://127.0.0.1:8200
   export VAULT_TOKEN=... # Only needed if not already logged in

   sops encrypt --hc-vault-transit $VAULT_ADDR/v1/sops/keys/firstkey vault_example.yml

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
