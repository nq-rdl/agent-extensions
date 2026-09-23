# Path-derived review slugs: the one definition, included by sqlreview-check.jq (check's
# slug/sql_path binding) and by sr_slug in sqlreview-lib.sh (`jq -L <scripts dir>`), so the two
# cannot drift. Input: a project-relative path. Both encodings strip a trailing `.sql`, split on
# `/`, write an empty component as `%00`, percent-encode each component (@uri plus ~ ' ! ( ) *,
# so only A-Za-z0-9 - _ . stay literal) and join the components with `__`.
#
# path_slug (readable, #353): `_` stays literal unless it is next to another `_` or at the start
# or end of its component (then `%5F`); `.` stays literal except a component's leading dot
# (`%2E`), so no slug or component is `.`, `..` or dot-leading.
# legacy_path_slug (before #353): every `_` is `%5F` and every `.` is `%2E`.
#
# Injective: `%` is always escaped and no encoded component contains `__` or starts or ends with
# `_`, so every `__` in a slug is a separator; splitting on `__` and percent-decoding each
# component recovers the path stem. The same decoder inverts legacy slugs, so a legacy slug can
# never equal the readable slug of a different path. Only the `.sql` strip is lossy: `x` and
# `x.sql` share a slug under both encodings (pre-existing; `slug` reports the binding conflict).
def _sr_escape: @uri | gsub("~"; "%7E") | gsub("'"; "%27") | gsub("[!]"; "%21") | gsub("[(]"; "%28") | gsub("[)]"; "%29") | gsub("[*]"; "%2A");
def _sr_components: sub("\\.sql$"; "") | if . == "" then [""] else split("/") end;
def _sr_readable:
  explode as $c | ($c | length) as $n
  | [range(0; $n) as $i | $c[$i] as $ch
     | if $ch == 95 and ($i == 0 or $i == $n - 1 or $c[$i - 1] == 95 or $c[$i + 1] == 95) then "%5F"
       elif $ch == 46 and $i == 0 then "%2E"
       else [$ch] | implode end]
  | join("");
def path_slug: _sr_components | map(if . == "" then "%00" else _sr_escape | _sr_readable end) | join("__");
def legacy_path_slug: _sr_components | map(if . == "" then "%00" else _sr_escape | gsub("_"; "%5F") | gsub("\\."; "%2E") end) | join("__");
