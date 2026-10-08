Committed SQL source and rendering
=================================

SQL review hashes bind exact UTF-8 bytes, including line endings and the final
newline. Generated SQL need not exist in the working tree or any git tree.
``fingerprint`` reconstructs HEAD in a private disposable checkout outside the
repository. Commit the adapter, builder/cohort/spec, configuration and dependency
pins first. Uncommitted source changes are refused; review records under
``.sqlreview/reviews/``, templates, ledger and the store ignore file are exempt.
Ignored generated outputs do not change the source identity.

Project adapter
---------------

Commit a render-only argv array in ``.sqlreview/config.json``::

    {"sql_render": {"command": ["bash", "scripts/render-sql.sh"]}}

The helper executes those arguments directly, without shell interpolation, from
the selected commit's project root, adding
``--sql-path <normalized project-relative path> --output <absolute temporary file>``.
The adapter must use that commit's maintained sources and locked dependencies,
write a regular output file, return zero only on success, and never connect to
a database or run an extract. Do not use an extract CLI that also executes SQL.
Two identical renders are required; differences refuse evidence. Stdout and
stderr are private diagnostics, never the SQL channel or review evidence.

Historical checkout and adapter processes receive an explicit environment:
only the caller's executable-search ``PATH`` is preserved. ``HOME``, ``TMPDIR``
and all XDG configuration/cache/data/state directories point to private temporary
directories; locale is ``C`` and timezone is ``UTC``. Git system/global config
is disabled. Shell startup files, exported functions, Python/Node/runtime
overrides, current-project environment variables, proxies and credentials are
not inherited. Adapters must select their locked runtime through committed argv
and project configuration rather than current environment overrides; executable
tools remain available through ``PATH``. An unavailable locked dependency fails
rendering rather than inheriting a current user's configuration or credentials.

Commit ``sql/provenance.json`` with ``schema: 1`` and a ``requests`` object keyed
by SQL path. Each entry's ``source`` is ``builder``, ``cohort``, ``spec`` or
``hand-written``. Generated entries require the adapter; undeclared entries in
an existing manifest and unknown classifications fail. Hand-written entries
read the committed maintained SQL. Without a manifest, a tracked SQL file is
the legacy compatibility route. Untracked SQL cannot provide durable evidence.
Missing commits, malformed manifests, unsafe paths, replacement refs/grafts,
source symlinks, unavailable adapters/dependencies and missing output all refuse
evidence. An unavailable render never means unchanged or absent.

Manifest hashes
---------------

An optional entry ``sha256`` is checked against the fresh render. Schema-1 legacy
``sha256`` uses ``sha256-canonical-v1``: remove a leading UTF-8 BOM, convert CRLF
to LF, strip trailing LF and append exactly one LF. An optional
``hash_algorithm: "sha256-raw"`` explicitly declares SHA256 of the exact bytes;
``sha256-canonical-v1`` may also be explicit. Unsupported schemas or algorithms
are refused. The manifest's canonical digest is never substituted for the
review's exact-byte ``sql_sha256``. A body digest is separate and cannot
authenticate the complete rendered SQL.

Provenance and shared API
-------------------------

``fingerprint`` returns ``sql_path``, exact-byte ``sql_sha256``,
``sql_body_sha256`` (null for an unparseable header), immutable ``git_commit``,
``git_dirty: false`` and helper-owned ``sql_provenance``::

    {"mode": "rendered", "project_root": "", "commit": "<immutable commit>"}

``mode`` is ``rendered`` or ``tracked``. ``project_root`` is the normalized path
from git top level to the project root, empty at top level. ``commit`` equals
``git_commit``. Scopes before SQL exists may retain a null hash and omit SQL
provenance. Legacy clean records with an immutable commit and full hash can be
reconstructed without the added fields; dirty/null commits require reassessment.
New provenance records require ``git_dirty: false`` during both schema validation
and reconstruction. Legacy records without SQL provenance may omit ``git_dirty``
or use null, but still require an immutable commit and matching full render SHA.

``sr_source_render REF SQL_PATH OUTPUT`` resolves the source ref and sets
``SR_SOURCE_COMMIT``, ``SR_SOURCE_MODE`` and ``SR_SOURCE_PREFIX``.
``sr_source_auth DOC OUTPUT`` reconstructs the recorded commit and verifies the
full SHA before the optional body SHA. Recorded mode and root prefix must match
that reconstruction; a moved root requires reassessment.
``sr_source_clean`` refuses uncommitted source changes. Callers own a trapped
private directory outside the git tree and must check the return code before
using output. Internal checkout and diagnostic files are removed on normal exit
and trapped signals. Neither function writes SQL under ``.sqlreview/``.
