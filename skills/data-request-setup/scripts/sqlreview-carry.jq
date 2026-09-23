# Carry-forward of human confirmations across scope/review revisions (#348). The one definition of
# "qualifies", included by both `sqlreview.sh publish` (which enforces it) and
# `sqlreview.sh carryforward` (which tells the skills what to carry), so the two cannot drift.
#
# An item qualifies when the previous published document of the same kind has an item with the same
# id in the same list, identical text and rationale, and its governed SQL is unchanged:
#   location null  → the whole SQL is unchanged (SHA evidence), or absent at both revisions
#   location lines → the prior lines in the prior baseline equal the new lines in the current SQL
#                    (a remap is fine; the line count must not change)
# A carried item copies the prior item's confirmed_by, confirmed_at and confirmed_revision and sets
# carried_from_revision to the prior revision.

def cf_sql_lines: if . == null then null elif . == "" then [] else rtrimstr("\n") | split("\n") end;
def cf_range: type == "array" and length == 2 and all(.[]; type == "number" and . >= 1 and . == floor) and .[0] <= .[1];

# Input: a (draft) scope/review document. $ctx:
#   {prior: document|null, base: string|null (prior baseline SQL, only when it is evidence),
#    cur: string|null (current SQL), prior_sha: string ("" = SQL absent/unknown at the prior revision),
#    cur_sha: string ("" = SQL absent now)}
# Output: an array with one row per assumption/limitation object:
#   {kind, id, basis, set} when it qualifies · {kind, id, basis: null, why} when it must be walked.
def carry_rows($ctx):
  . as $d
  | $ctx.prior as $p
  | ($ctx.prior_sha != "" and $ctx.cur_sha != "" and $ctx.prior_sha == $ctx.cur_sha) as $unchanged
  | ($ctx.prior_sha == "" and $ctx.cur_sha == "") as $absent
  | ($ctx.cur | cf_sql_lines) as $c
  | (if $ctx.base != null then ($ctx.base | cf_sql_lines) elif $unchanged then $c else null end) as $b
  | ($p.revision // null) as $pr
  | [ ("assumptions", "limitations") as $k
      | ($d[$k] // [] | if type == "array" then .[] else empty end) | select(type == "object") | . as $i
      | ([($p[$k] // [])[] | select(type == "object" and .id == $i.id)][0]) as $m
      | {kind: $k, id: $i.id}
        + (if $p == null then {why: "no previous published \($d.kind // "document") to carry from"}
           elif $m == null then {why: "no item \($i.id) in \($k) at revision \($pr)"}
           elif $m.text != $i.text then {why: "text differs from revision \($pr)"}
           elif $m.rationale != $i.rationale then {why: "rationale differs from revision \($pr)"}
           elif ($m.location == null) != ($i.location == null) then {why: "location added or removed since revision \($pr)"}
           elif $i.location == null then
             if $unchanged then {basis: "sql-unchanged"}
             elif $absent then {basis: "sql-absent"}
             else {why: "SQL changed since revision \($pr) and the item has no location"} end
           else ($m.location.lines) as $pl | ($i.location.lines) as $nl
             | if ($pl | cf_range | not) or ($nl | cf_range | not) then {why: "location lines are not a valid range"}
               elif ($pl[1] - $pl[0]) != ($nl[1] - $nl[0]) then {why: "governed line count changed since revision \($pr)"}
               elif $b == null or $c == null then {why: "no SQL baseline for revision \($pr) to compare the governed lines with"}
               elif $pl[1] <= ($b | length) and $nl[1] <= ($c | length) and $b[$pl[0] - 1:$pl[1]] == $c[$nl[0] - 1:$nl[1]]
               then {basis: (if $unchanged then "sql-unchanged" else "lines-unchanged" end)}
               else {why: "governed lines changed since revision \($pr)"} end
           end)
      | if has("basis") then
          . + {set: {status: "confirmed", confirmed_by: $m.confirmed_by, confirmed_at: $m.confirmed_at,
                     confirmed_revision: $m.confirmed_revision, carried_from_revision: $pr}}
        else . + {basis: null} end
    ];

# Publish's verdict: one violation line per carried item (carried_from_revision set) that does not
# qualify or does not copy the prior confirmation exactly. $reconfirm_all refuses every carried item.
def carry_violations($ctx; $reconfirm_all):
  carry_rows($ctx) as $rows
  | ("assumptions", "limitations") as $k
  | (.[$k] // [])[] | select(type == "object" and .carried_from_revision != null) | . as $i
  | ([$rows[] | select(.kind == $k and .id == $i.id)][0]) as $r
  | if $reconfirm_all then "\($i.id): --reconfirm-all refuses carried confirmations — re-confirm for this revision"
    elif $r.basis == null then "\($i.id): cannot carry the confirmation forward: \($r.why) — re-confirm for this revision"
    elif ($i | {status, confirmed_by, confirmed_at, confirmed_revision, carried_from_revision}) != $r.set
    then "\($i.id): a carried item must copy confirmed_by, confirmed_at and confirmed_revision from revision \($r.set.carried_from_revision) exactly (sqlreview.sh carryforward prints them)"
    else empty end;
