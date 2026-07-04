Canonical spec-kit Extension Sources — Validation
=================================================

spec-kit evolves fast (v0.12.x, near-daily releases; extension schema_version
"1.0"). A remembered field name or CLI flag can be a release stale. When
correctness depends on a detail you are not certain of, **fetch the page below
and read the current wording** instead of asserting from memory.

Keep full URLs here; cite docs *by name and section* at the point of use.

Primary
-------

- Extensions reference (rendered):
  https://github.github.io/spec-kit/reference/extensions.html
- Development Guide (manifest schema, validation rules, minimal example,
  .extensionignore):
  https://raw.githubusercontent.com/github/spec-kit/main/extensions/EXTENSION-DEVELOPMENT-GUIDE.md
- Official scaffold (mirror this):
  https://github.com/github/spec-kit/tree/main/extensions/template
- API reference (Python classes, hook events):
  https://raw.githubusercontent.com/github/spec-kit/main/extensions/EXTENSION-API-REFERENCE.md

Context
-------

- Extensions system overview & catalog format:
  https://github.com/github/spec-kit/tree/main/extensions
- Install (the uv footgun):
  https://github.github.io/spec-kit/installation.html

Version pin
-----------

Schema ``schema_version: "1.0"``; facts verified against release line v0.12.x on
2026-07-04. Re-check the Development Guide before emitting a manifest.
