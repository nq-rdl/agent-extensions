Committed SQL source and rendering
=================================

.. contents::
   :local:

SQL review hashes bind exact UTF-8 bytes, including line endings and the final
newline. Generated SQL need not exist in the working tree or any git tree.
``fingerprint`` reconstructs HEAD in a private disposable checkout outside the
repository. Commit the adapter, builder/cohort/spec, configuration and dependency
pins first. Uncommitted source changes are refused; review records under
``.sqlreview/reviews/``, templates, ledger and the store ignore file are exempt.
Ignored generated outputs do not change the source identity.

Accepted paths
--------------

Only reviewed request SQL under ``sql/v<N>/`` is read into ``.sqlreview/``. The
directory name must match ``v[0-9]+([.-][0-9]+)*`` (``sql/v1/``, ``sql/v2.1/``,
``sql/v3-1/``), the scaffold's rule. ``slug``, ``fingerprint``, ``snapshot``,
``notes`` and ``intake``, the new path of ``move``, and the ``sql_path`` of a draft
or record, refuse any path under ``data/`` and any path under ``sql/`` outside such a
directory, such as ``sql/<name>/`` pipeline SQL, because those files can hold
researcher-supplied values that must never reach Git. Other paths inside the project are
unaffected. ``move OLD NEW`` accepts a refused OLD path, which is only the key of
an existing record and is never read, so records bound to such a path can move
into a reviewed directory.

The path is canonicalised before the check: ``..`` and symlinks are resolved
relative to the project root, so ``sql/v1/../pipeline_a/q.sql`` and a link from
``sql/v1/`` into ``data/`` are refused. A path that cannot be resolved (a symlink
loop, say) or that resolves outside the project is refused; copy a file from outside
the project root into ``sql/v<N>/`` first. Only ``notes`` also accepts a render the helper itself wrote
(``sr_source_render``, ``materialize``), marked by a ``FILE.sqlreview-render`` SHA-256
file, which is what the analyse, bootstrap and explain recipes pass it. A file with
more than one hard link is refused, since a link may lead to ``data/``. Every file argument
(``check``, ``lint``, ``ledger``, ``carryover``, ``carryforward``, ``remap``, ``publish``,
``publish-questions``, ``intake``, ``notes --against/--questions``, and the files given to
``release.sh`` and ``recurring-decisions.sh``) follows the same rules. The command exits 2
with a message that names the rule and the path as given, never file content,
and writes nothing under ``.sqlreview/``.

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


Temporary SQL for workflow inspection
-------------------------------------

Run from the project root with ``S`` set to the installed setup scripts. For a
SQL-bound draft, authenticate its recorded full SHA before comparing with HEAD::

    bash -s -- "$S" ".sqlreview/reviews/$SLUG/scope.draft.json" "<sql path>" <<'SH'
      set -e
      S="$1"; DRAFT="$2"; SQL_PATH="$3"
      . "$S/sqlreview-lib.sh"
      SR_ROOT="$(sr_find_root)" || exit 3
      T="$(mktemp -d /tmp/sqlreview-inspect.XXXXXX)" || exit 2
      trap 'rm -rf "$T"' EXIT
      trap 'exit 130' INT
      trap 'exit 143' TERM HUP
      sr_source_auth "$DRAFT" "$T/recorded.sql" || exit $?
      sr_source_clean || exit $?
      sr_source_render HEAD "$SQL_PATH" "$T/current.sql" || exit $?
      diff -u "$T/recorded.sql" "$T/current.sql"
    SH

For a fresh review without an SQL-bound draft, omit ``sr_source_auth`` and the
diff; inspect ``$T/current.sql`` inside that same shell before its cleanup.
Never save those bytes under ``.sqlreview/``. Return 6 means historical evidence
is unavailable or nonreproducible; return 2 means an operational/path failure.
Both require resolution before publication. Do not infer unchanged or SQL absent.

``publish`` authenticates recorded and current renders before atomically writing
scope/review JSON. Only advancing human revisions save the previous JSON at
``history/<kind>/<revision>.json``. Header-only updates preserve the original SHA,
commit and confirmations with helper-owned ``header_revisions``. ``snapshot``
verifies the published review only; it does not store SQL. ``materialize SLUG
scope|review REVISION OUTPUT`` authenticates that exact recorded revision, writes
to an absolute external temporary path and leaves deletion to the caller. Explain
must not substitute HEAD for an unavailable recorded revision. Missing historical
evidence requires reassessment. Generated fresh header-decision carry requires
proved maintained-source and rendered-header history; otherwise confirm normally.
