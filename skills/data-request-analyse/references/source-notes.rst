Inspect rendered header notes
=============================

Run this self-contained command from the project root, with ``S`` set to the
installed setup scripts and ``SLUG`` set to the review slug. It reconstructs HEAD
from clean committed sources; generated SQL need not exist in the project.
Inspect the emitted notes before the shell removes its private directory.

.. code-block:: bash

    bash -s -- "$S" "<sql path>" --against ".sqlreview/reviews/$SLUG/review.draft.json" <<'SH'
    set -e
    S="$1"; SQL_PATH="$2"; shift 2
    . "$S/sqlreview-lib.sh"
    SR_ROOT="$(sr_find_root)" || exit 3
    T="$(mktemp -d /tmp/sqlreview-notes.XXXXXX)" || exit 2
    trap 'rm -rf "$T"' EXIT
    trap 'exit 130' INT
    trap 'exit 143' TERM HUP
    sr_source_clean || exit $?
    sr_source_render HEAD "$SQL_PATH" "$T/current.sql" || exit $?
    bash "$S/sqlreview.sh" notes "$T/current.sql" "$@" || exit $?
    SH

For the initial scope comparison, replace ``review.draft.json`` with ``scope.json``;
omit both ``--against`` and its argument when no scope exists. For unchanged-SQL
completion, use the published ``review.json``. Before publication, use the confirmed
``review.draft.json``. To assess named dated header decisions, add
``--confirmed-by "<human handle>"`` before ``<<'SH'``; establish that intended human
handle explicitly first. Keep the draft's original ``sql_path`` so header evidence
is assessed against maintained source history, rather than the temporary path.

Output includes ``present``, header ``lines``, and assumption/limitation candidates
with ``text``, ``rationale`` and ``match``. With ``--confirmed-by``, it also includes
``header_carry_over`` and ``header_walk``. A malformed header returns 4: report its
line and continue the human review without those candidates. Rendering or source
failures require resolution; never substitute an old working SQL file. The trapped
directory is removed on success, failure and signals, and no SQL enters the review store.
