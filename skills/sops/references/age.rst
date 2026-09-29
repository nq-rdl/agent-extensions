Encrypting with Age
===================

`Age <https://age-encryption.org/>`_ is a simple, modern, and secure tool for encrypting files. It is recommended to use age over PGP if possible.

Generating a Key
----------------

Generate an age identity (private + public key pair) with:

.. code-block:: bash

   mkdir -p "$HOME/.config/sops/age"
   age-keygen -o "$HOME/.config/sops/age/keys.txt"

The **public key** is printed to stderr — copy it into ``--age`` flags or ``.sops.yaml``. The private key is written to ``keys.txt`` and must be kept secret. Only the public key is shared with others.

SOPS looks for ``keys.txt`` at decryption time using the following default paths:

- **Linux**: ``$XDG_CONFIG_HOME/sops/age/keys.txt`` if ``$XDG_CONFIG_HOME`` is set; otherwise ``$HOME/.config/sops/age/keys.txt``
- **macOS**: ``$XDG_CONFIG_HOME/sops/age/keys.txt`` if ``$XDG_CONFIG_HOME`` is set; otherwise ``$HOME/Library/Application Support/sops/age/keys.txt``

Only one of the two paths is searched: when ``$XDG_CONFIG_HOME`` is set, a key in ``$HOME/.config/sops/age/`` is **not** found.

Override the default path with the ``SOPS_AGE_KEY_FILE`` environment variable. SOPS loads every key source, so a missing ``SOPS_AGE_KEY_FILE`` is ignored when another source (e.g. the default ``keys.txt``) holds the key. When no source does, the error names the missing file: ``failed to open SOPS_AGE_KEY_FILE file: open <path>: no such file or directory``.

Encrypting
----------

You can encrypt a file for one or more age recipients (comma separated) using the ``--age`` option or the ``SOPS_AGE_RECIPIENTS`` environment variable:

.. code-block:: bash

   sops encrypt --age age1yt3tfqlfrwdwx0z0ynwplcr6qxcxfaqycuprpmy89nr83ltx74tqdpszlw test.yaml > test.enc.yaml

Decrypting
----------

When decrypting a file with the corresponding identity, SOPS will look for a text file named ``keys.txt`` located in a ``sops`` subdirectory of your user configuration directory.

- **Linux**: Looks for ``keys.txt`` in ``$XDG_CONFIG_HOME/sops/age/keys.txt``; uses ``$HOME/.config/sops/age/keys.txt`` only if ``$XDG_CONFIG_HOME`` is unset.
- **macOS**: Looks for ``keys.txt`` in ``$XDG_CONFIG_HOME/sops/age/keys.txt``; uses ``$HOME/Library/Application Support/sops/age/keys.txt`` only if ``$XDG_CONFIG_HOME`` is unset.

You can override the default lookup by:

- Setting the environment variable ``SOPS_AGE_KEY_FILE``
- Setting the ``SOPS_AGE_KEY`` environment variable directly to the key content
- Providing a command to output the age keys by setting the ``SOPS_AGE_KEY_CMD`` environment variable.

The contents of this key file should be a list of age X25519 identities, one per line. Lines beginning with ``#`` are considered comments and ignored.

Editing in Place
----------------

Open an encrypted file in an editor:

.. code-block:: bash

   sops edit secrets.yaml

SOPS decrypts to a temporary plaintext file in the system temp directory (``$TMPDIR``, usually ``/tmp``; mode ``0600``), opens it in ``$SOPS_EDITOR``, else ``$EDITOR``, else the first of ``vim``, ``nano``, ``vi`` found on ``PATH``. On exit it re-encrypts and deletes the temporary file and its directory. Plaintext therefore touches disk briefly — avoid ``sops edit`` on shared hosts whose temp directory is not private. If the file was not changed, SOPS prints ``File has not changed, exiting.`` and exits with status ``200``.

Using .sops.yaml
----------------

A list of age recipients can be added to ``.sops.yaml`` to make encryption easier for specific paths:

.. code-block:: yaml

   creation_rules:
       - age: >-
           age1s3cqcks5genc6ru8chl0hkkd04zmxvczsvdxq99ekffe4gmvjpzsedk23c,
           age1qe5lxzzeppw5k79vxn3872272sgy224g2nzqlzy3uljs84say3yqgvd0sw

Rotating Recipients
-------------------

After updating ``.sops.yaml`` with new (or removed) age recipients, re-encrypt the data key without touching the underlying plaintext values:

.. code-block:: bash

   sops updatekeys -y secrets.yaml

SOPS re-wraps the symmetric data key against the current set of recipients listed in ``.sops.yaml``. The encrypted values themselves are not re-encrypted — only the encrypted copy of the data key changes. Run ``sops updatekeys -y`` on every file whose recipients you want to update. The caller needs a key that can decrypt the file's current data key.

Without ``-y`` (``--yes``), ``updatekeys`` shows the recipient diff and asks ``Is this okay? (y/n)``. With no terminal attached it reads EOF, leaves the file unchanged, and ``find -exec`` still exits ``0`` — so a non-interactive loop without ``-y`` silently does nothing.

To rotate all files in a directory in one pass:

.. code-block:: bash

   find . -name "*.enc.yaml" -exec sops updatekeys -y {} \;

Encrypting with SSH Keys
------------------------

Encrypting with SSH keys via age is also supported by SOPS. You can use SSH public keys (``ssh-ed25519 AAAA...``, ``ssh-rsa AAAA...``) as age recipients when encrypting a file.

When decrypting a file, SOPS will attempt to source the SSH private key as follows:

- From the path specified in environment variable ``SOPS_AGE_SSH_PRIVATE_KEY_FILE``.
- From the output of the command specified in environment variable ``SOPS_AGE_SSH_PRIVATE_KEY_CMD``. (The output must provide a key that is not password protected.)
- From ``~/.ssh/id_ed25519``.
- From ``~/.ssh/id_rsa``.

*Note: Only ssh-rsa and ssh-ed25519 are supported.*
