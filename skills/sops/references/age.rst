Encrypting with Age
===================

`Age <https://age-encryption.org/>`_ is a simple, modern, and secure tool for encrypting files. It is recommended to use age over PGP if possible.

Encrypting
----------

You can encrypt a file for one or more age recipients (comma separated) using the ``--age`` option or the ``SOPS_AGE_RECIPIENTS`` environment variable:

.. code-block:: bash

   sops encrypt --age age1yt3tfqlfrwdwx0z0ynwplcr6qxcxfaqycuprpmy89nr83ltx74tqdpszlw test.yaml > test.enc.yaml

Decrypting
----------

When decrypting a file with the corresponding identity, SOPS will look for a text file named ``keys.txt`` located in a ``sops`` subdirectory of your user configuration directory.

- **Linux**: Looks for ``keys.txt`` in ``$XDG_CONFIG_HOME/sops/age/keys.txt``; falls back to ``$HOME/.config/sops/age/keys.txt``.
- **macOS**: Looks for ``keys.txt`` in ``$XDG_CONFIG_HOME/sops/age/keys.txt``; falls back to ``$HOME/Library/Application Support/sops/age/keys.txt``.

You can override the default lookup by:

- Setting the environment variable ``SOPS_AGE_KEY_FILE``
- Setting the ``SOPS_AGE_KEY`` environment variable directly to the key content
- Providing a command to output the age keys by setting the ``SOPS_AGE_KEY_CMD`` environment variable.

The contents of this key file should be a list of age X25519 identities, one per line. Lines beginning with ``#`` are considered comments and ignored.

Using .sops.yaml
----------------

A list of age recipients can be added to ``.sops.yaml`` to make encryption easier for specific paths:

.. code-block:: yaml

   creation_rules:
       - age: >-
           age1s3cqcks5genc6ru8chl0hkkd04zmxvczsvdxq99ekffe4gmvjpzsedk23c,
           age1qe5lxzzeppw5k79vxn3872272sgy224g2nzqlzy3uljs84say3yqgvd0sw

Encrypting with SSH Keys
------------------------

Encrypting with SSH keys via age is also supported by SOPS. You can use SSH public keys (``ssh-ed25519 AAAA...``, ``ssh-rsa AAAA...``) as age recipients when encrypting a file.

When decrypting a file, SOPS will attempt to source the SSH private key as follows:

- From the path specified in environment variable ``SOPS_AGE_SSH_PRIVATE_KEY_FILE``.
- From the output of the command specified in environment variable ``SOPS_AGE_SSH_PRIVATE_KEY_CMD``. (The output must provide a key that is not password protected.)
- From ``~/.ssh/id_ed25519``.
- From ``~/.ssh/id_rsa``.

*Note: Only ssh-rsa and ssh-ed25519 are supported.*
