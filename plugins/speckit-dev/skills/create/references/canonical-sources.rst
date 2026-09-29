Canonical spec-kit Extension Sources — Where to Verify
======================================================

spec-kit evolves fast (v0.12.0 to v1.0.12 shipped between late June and September
2026; extension schema_version "1.0"). A remembered field name or CLI flag can be a release stale. When
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
- Install (PyPI ``specify-cli`` or a pinned GitHub tag; both official):
  https://github.github.io/spec-kit/installation.html

Version pin
-----------

Schema ``schema_version: "1.0"``. First written against the v0.12.x line
(2026-07-04); re-checked on 2026-09-29 against source at v0.12.0, v0.14.0,
v0.15.0, v0.16.2, v1.0.0 and v1.0.12 (latest release). Releases between those
tags were not read, and nothing here was tested by running the installer.
Re-check the Development Guide before emitting a manifest.
