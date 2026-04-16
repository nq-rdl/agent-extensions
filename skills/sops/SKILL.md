---
name: sops
description: >-
  Encrypt and decrypt files using SOPS (Secrets OPerationS).
  Trigger when the user asks to encrypt .env files, config files,
  or secrets using SOPS + Age or SOPS + HashiCorp Vault.
license: MIT
metadata:
  repo: https://github.com/nq-rdl/agent-skills
---

# SOPS Encryption Skill

This skill teaches how to encrypt and decrypt files using [SOPS](https://github.com/getsops/sops). SOPS supports YAML, JSON, ENV, INI, and BINARY formats. It supports various KMS backends. This skill focuses on encrypting with **Age** and **HashiCorp Vault**.

## When to use this skill

- The user wants to encrypt secrets for infrastructure as code, CI/CD, or deployment.
- The user explicitly mentions SOPS, Age, or HashiCorp Vault for encryption.
- The user asks to encrypt an `.env`, `.yaml`, or `.json` file containing sensitive data.

## The Encryption Flow

1. **Identify the format**: Ensure the file to be encrypted is in a supported format (YAML, JSON, ENV, INI) so SOPS can extract keys and only encrypt leaf values.
2. **Choose the backend**: Follow the user's instructions to use either Age or HashiCorp Vault.
3. **Execute**: Use the `sops` CLI tool to perform the encryption.

## Best Practices

- Always keep the file extension the same so SOPS knows how to decrypt it (e.g. `sops encrypt -i myfile.json`).
- If you need to change the extension after encryption, provide `--input-type` and `--output-type`.
- The SOPS CLI works by encrypting leaf values, not keys. This means the diffs in Git will be readable!
- Top-level arrays in YAML/JSON are not supported. Put arrays inside an object (e.g. `{"data": [...]}`).

## Reference Guides

- [Encrypting with Age](references/age.rst)
- [Encrypting with HashiCorp Vault](references/vault.rst)
