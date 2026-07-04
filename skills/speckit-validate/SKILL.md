---
name: speckit-validate
license: CC-BY-4.0
compatibility: "spec-kit >=0.12 (extension schema_version 1.0); re-verify at github.github.io/spec-kit"
description: >-
  Lint an existing GitHub spec-kit extension against the real manifest schema and
  validation rules, and report pass/fail per rule. Use when checking a spec-kit
  extension before install/publish, debugging a `specify extension add` rejection,
  auditing extension.yml / commands/*.md, or when the user runs /speckit-dev:validate.
  Mirrors the checks spec-kit's ExtensionManifest performs at install time.
argument-hint: "Path to the extension directory to validate (e.g. ./my-extension)"
user-invocable: true
metadata:
  repo: https://github.com/nq-rdl/agent-extensions
---

# Validate a spec-kit extension

> **Verify-canonical guard.** Rules below are pinned to schema `1.0` / v0.12.x
> (verified 2026-07-04). Before failing a manifest on a rule, confirm against
> `references/validation-rules.rst` and the live
> [development guide](https://raw.githubusercontent.com/github/spec-kit/main/extensions/EXTENSION-DEVELOPMENT-GUIDE.md).

## User input

`$ARGUMENTS` = path to the extension directory (contains `extension.yml`).

## Checklist — run every rule, report PASS/FAIL each

**Manifest structure**
- [ ] `extension.yml` parses as YAML.
- [ ] Top-level `schema_version`, `extension`, `requires`, `provides` all present.
- [ ] `schema_version == "1.0"` exactly.

**extension block**
- [ ] `id`, `name`, `version`, `description` present.
- [ ] `id` matches `^[a-z0-9-]+$`.
- [ ] `version` is strict `X.Y.Z` (PEP-440-parseable; warn if it uses a
      pre-release/loose form even though `packaging` accepts it).
- [ ] if `effect` present → `read-only` or `read-write`.

**requires**
- [ ] `requires.speckit_version` present and a valid specifier.

**provides**
- [ ] at least one command OR one hook.
- [ ] every `commands[].name` matches `^speckit\.[a-z0-9-]+\.[a-z0-9-]+$` and the
      middle segment equals `extension.id`.
- [ ] every `commands[].file` is a relative path that exists (no `..`, not absolute).
- [ ] each referenced command file has frontmatter `description`.
- [ ] if `provides.config[]` present → each `template` file exists.

**hooks**
- [ ] every hook event name is one of the 18 documented `before_/after_` × phase names (an unrecognized name isn't bound to any stage, so the hook silently never fires).
- [ ] each entry has a non-empty `command`; `priority` (if present) is an int ≥ 1.

Report a compact table: rule → PASS/FAIL → offending value. End with an overall
verdict and the exact fixes.

## Canonical sources

See `references/validation-rules.rst` and `references/canonical-sources.rst`.
