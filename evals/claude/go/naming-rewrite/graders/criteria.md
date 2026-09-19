---
type: llm
---

Judge only the identifiers in the rewritten Go code, not the formatting or the explanation around it.

PASS if all of these hold:
- The type no longer repeats the package name: it is not `AccountHTTPClient` or `AccountHttpClient` (for example `HTTPClient` or `Client`), and the constructor follows suit (for example `New` or `NewHTTPClient`).
- Initialisms keep uniform case: `HTTP`, `URL`/`url`, and `ID`/`id` — never `Http`, `Url`, or `Id`.
- No identifier contains an underscore.

FAIL if any of those conditions is broken, or if no rewritten code is shown.
