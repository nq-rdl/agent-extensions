# Carry-forward of human confirmations across scope/review revisions (#348, #366). The one
# definition of "qualifies", included by both `sqlreview.sh publish` (which enforces it) and
# `sqlreview.sh carryforward` (which tells the skills what to carry), so the two cannot drift.
#
# An item qualifies when the previous published document of the same kind has an item with the same
# id in the same list, identical text, rationale and decided provenance, and one of these holds (the basis):
#   location null  → sql-unchanged      the whole SQL is unchanged (SHA evidence)
#                    sql-absent         the SQL is absent at both revisions
#                    sql-body-unchanged only the leading comment header changed; the rest of the
#                                       file is byte-identical (sr_body_start in sqlreview-lib.sh)
#                    intent-unchanged   scope only: a scope item states intent, not SQL lines, so it
#                                       carries whatever the SQL did; analyse checks the SQL later
#   location lines → the prior lines in the prior baseline equal the new lines in the current SQL
#                    (a remap is fine; the line count must not change): sql-unchanged / lines-unchanged
#   criteria_status rows (scope only) → criteria-unchanged: state, reason, flag and upstream equal the prior row for
#                    the same criterion, and the SQL body is unchanged (see below); after a body change,
#                    criteria-lines-unchanged when the row's location lines are re-located unchanged by the diff
# The decided re-walk rule: after a change, only the items the diff touches are walked. A located item carries
# only when the diff re-locates its range (cf_relocate) with byte-identical lines. Everything that is not walked
# goes into one carry question (carryforward's carry_question). A failed re-proof of the recorded SQL
# ($ctx.reproof_failed) touches every item. An item marked sql_status "not-implemented" carries that mark only.
# A carried item copies the prior item's confirmed_by, confirmed_at and confirmed_revision, sets
# carried_from_revision to the prior revision and carried_basis to the basis (the evidence).
#
# criteria_status rows (scope only, the scaffold's criteria design) carry by `criterion` with basis criteria-unchanged: the
# previous published scope has a row for the same criterion whose state, reason, flag and upstream are equal,
# and the analyst has not reworded or re-confirmed that criterion in answers.intake.json since that revision was recorded
# (the criterion's confirmed_at is not later than the previous scope's recorded_at, the rule that status uses to name a rescope).
# A reworded criterion keeps its id and gets a fresh confirmation, so that time is its revision marker. When it cannot be compared
# (no valid sidecar, an unknown criterion or a stamp that is not UTC) the row is walked
# (an absent reason, flag or upstream equals an absent one, so gaining or dropping an upstream is a
# change, as at publish, R21). A row states what the SQL does, so any SQL body change walks every row, like a
# changed assumption: the engineer confirms or changes each state, never in bulk. An unchanged body carries a
# located row only when the line map re-locates its prior lines to its new lines (cf_lines_kept). The SQL body is unchanged when
# the SQL sha256 is equal at both revisions (an explicit absence at both counts) or only the leading comment header changed. The set fields are the assumption ones minus status (confirmed_by, confirmed_at,
# confirmed_revision, carried_from_revision, carried_basis) plus the prior row's upstream when present;
# a new criterion or a changed row does not qualify and goes to the walk list for fresh confirmation.
# Output rows use kind "criteria_status" and id = the criterion.
#
# A review item that does not qualify only because the SQL changed under it (location null, or a
# location added or removed) is marked bulk: its wording is unchanged, so the skill may put all such
# items to the human in one question, with each item's current location. The answer is a fresh
# confirmation, never a carried one.

def cf_sql_lines: if . == null then null elif . == "" then [] else rtrimstr("\n") | split("\n") end;
def cf_range: type == "array" and length == 2 and all(.[]; type == "number" and . >= 1 and . == floor) and .[0] <= .[1];

# The line map of a zero-context unified diff (diff -U 0 baseline current): the unchanged intervals of the
# baseline with the shift that places them in the current SQL. Shared by remap and the carry rules below, so a
# range that remap cannot re-locate cannot carry either. Zero-length hunk starts name the line BEFORE the edit.
def cf_segments($delta; $blen; $clen):
  [ ($delta | split("\n"))[] | select(startswith("@@ "))
    | capture("^@@ -(?<o>[0-9]+)(,(?<ol>[0-9]+))? \\+(?<n>[0-9]+)(,(?<nl>[0-9]+))? @@")
    | {o: (.o | tonumber), ol: ((.ol // "1") | tonumber), n: (.n | tonumber), nl: ((.nl // "1") | tonumber)} ] as $hunks
  | reduce ($hunks + [{o: ($blen + 1), ol: 1, n: ($clen + 1), nl: 1}])[] as $h
      ({o: 1, n: 1, segments: []};
       ($h.o + (if $h.ol == 0 then 1 else 0 end)) as $start
       | .segments += [{from: .o, to: ($start - 1), shift: (.n - .o)}]
       | .o = ($start + $h.ol)
       | .n = ($h.n + (if $h.nl == 0 then 1 else 0 end) + $h.nl)) | .segments;
# The text of the added and removed lines of the same diff.
def cf_edited($delta): [ ($delta | split("\n"))[2:][] | select(startswith("+") or startswith("-")) | .[1:] ];
# How many times the line slice $s occurs in the line array. Slices are materialised with
# map(.): jq 1.6 can compare two views of one backing array as equal at different offsets.
def cf_count($s):
  . as $lines | ($s | length) as $n | ($s | map(.)) as $m
  | [range(0; ($lines | length) - $n + 1) as $i | select(($lines[$i:$i + $n] | map(.)) == $m)] | length;
# Where the diff places the baseline range $old in the current SQL, or null when it cannot be re-located:
# an edit or an insertion splits the range, or a governed line also occurs in the edit and the governed text
# is not unique in both versions (then more than one alignment is possible).
def cf_relocate($old; $b; $c; $segments; $edited):
  ([ $segments[] | select($old[0] >= .from and $old[1] <= .to) ][0]) as $seg
  | if $seg == null or $old[1] > ($b | length) then null
    else ($b[$old[0] - 1:$old[1]] | map(.)) as $slice
      | if any($slice[]; . as $line | $edited | index($line) != null)
           and (($b | cf_count($slice)) != 1 or ($c | cf_count($slice)) != 1) then null
        else $old | map(. + $seg.shift) end
    end;
# Whether the prior range $pl is re-located by the diff to the draft range $nl with byte-identical lines.
# Without a diff (identical SQL) the lines must be the same range.
def cf_lines_kept($pl; $nl; $b; $c; $delta):
  if $b == null or $c == null then false
  elif ($pl[1] - $pl[0]) != ($nl[1] - $nl[0]) or $pl[1] > ($b | length) or $nl[1] > ($c | length) then false
  elif $b[$pl[0] - 1:$pl[1]] != $c[$nl[0] - 1:$nl[1]] then false
  elif $delta == null then $pl == $nl
  else cf_relocate($pl; $b; $c; cf_segments($delta; $b | length; $c | length); cf_edited($delta)) == $nl end;

# The UTC second of a sidecar or scope stamp, or null for any other format (the status rule, sqlreview-lib.sh sr_next).
def cf_utc: if type == "string" and test("^[0-9]{4}-[0-9]{2}-[0-9]{2}T[0-9]{2}:[0-9]{2}:[0-9]{2}(\\.[0-9]+)?Z$") then .[0:19] else null end;

# criteria_status rows of a scope draft, in carry_rows' output shape (see the header).
# $ctx.criteria is the live sidecar's criteria array, or null when there is no valid schema 2 sidecar.
def carry_criteria_rows($ctx):
  . as $d
  | $ctx.prior as $p
  | ($p.revision // null) as $pr
  | ($ctx.criteria // null) as $cs
  | (($ctx.prior_sha != "" and $ctx.prior_sha == $ctx.cur_sha) or (($ctx.prior_absent // false) and ($ctx.cur_absent // false))
     or ($ctx.body_unchanged // false)) as $body
  | ($ctx.cur | cf_sql_lines) as $cur_lines
  | (if $ctx.base != null then ($ctx.base | cf_sql_lines)
     elif $ctx.prior_sha != "" and $ctx.prior_sha == $ctx.cur_sha then $cur_lines else null end) as $base_lines
  | [ ($d.criteria_status // [] | if type == "array" then .[] else empty end) | select(type == "object") | . as $i
      | ([($p.criteria_status // [] | if type == "array" then .[] else empty end)
          | select(type == "object" and .criterion == $i.criterion)][0]) as $m
      | ([$cs | arrays | .[] | select(type == "object" and .id == $i.criterion)][0]) as $c
      | ($m.location.lines? // null) as $pl | ($i.location.lines? // null) as $nl
      | {kind: "criteria_status", id: $i.criterion, location: ($i.location // null)}
        + (if $ctx.reproof_failed // false then {why: "the recorded SQL cannot be re-proved from git"}
           elif $p == null then {why: "no previous published scope to carry from"}
           elif $m == null then {why: "no row for \($i.criterion) in criteria_status at revision \($pr)"}
           elif $cs == null then {why: "no valid analyst intake (answers.intake.json) to show that \($i.criterion) is unchanged since revision \($pr)"}
           elif $c == null or ($c.confirmed_at | cf_utc) == null or ($p.recorded_at | cf_utc) == null
           then {why: "cannot show that \($i.criterion) is unchanged in answers.intake.json since revision \($pr)"}
           elif ($c.confirmed_at | cf_utc) > ($p.recorded_at | cf_utc)
           then {why: "\($i.criterion) was reworded or re-confirmed in answers.intake.json after revision \($pr): rescope with the engineer and confirm the row afresh"}
           else (["state", "reason", "flag", "upstream"] | map(select($m[.] != $i[.])) | .[0]) as $f
             | if $f != null then {why: "\($f) differs from revision \($pr)"}
               # An unchanged body proves the row only where its location is unchanged too: a location that is
               # added, removed or moved must be proved by the line map, or the row gets a fresh confirmation.
               elif $body then
                 if $pl == null and $nl == null then {basis: "criteria-unchanged"}
                 elif $pl == null or $nl == null then {why: "location added or removed since revision \($pr)"}
                 elif ($pl | cf_range | not) or ($nl | cf_range | not) then {why: "location lines are not a valid range"}
                 elif cf_lines_kept($pl; $nl; $base_lines; $cur_lines; $ctx.delta) then {basis: "criteria-unchanged"}
                 else {why: "the line map cannot prove the location of \($i.criterion) since revision \($pr)"} end
               # The decided re-walk rule: a body change walks only the rows it touches. A row with no
               # location in either revision cannot show that, so it goes into the one carry question as a
               # fresh confirmation (bulk), never a carry.
               elif $pl == null or $nl == null then {why: "the SQL body changed since revision \($pr)", bulk: true}
               elif ($pl | cf_range | not) or ($nl | cf_range | not) then {why: "location lines are not a valid range"}
               elif cf_lines_kept($pl; $nl; $base_lines; $cur_lines; $ctx.delta) then {basis: "criteria-lines-unchanged"}
               else {why: "the change touches the governed lines of \($i.criterion) since revision \($pr)"} end
           end)
      | if has("basis") then
          . + {set: ({confirmed_by: $m.confirmed_by, confirmed_at: $m.confirmed_at,
                     confirmed_revision: $m.confirmed_revision, carried_from_revision: $pr, carried_basis: .basis}
                     + (if $m | has("upstream") then {upstream: $m.upstream} else {} end))}
        else . + {basis: null, bulk: (.bulk // false)} end
    ];

# Input: a (draft) scope/review document. $ctx:
#   {kind: "scope"|"review", prior: document|null,
#    base: string|null (prior baseline SQL, only when it is evidence), cur: string|null (current SQL),
#    prior_sha: string, cur_sha: string ("" means no authenticated SQL hash),
#    prior_absent: boolean, cur_absent: boolean (explicit scope-before-SQL and committed absence),
#    body_unchanged: boolean (baseline and current SQL differ at most in the leading comment header)}
# Output: an array with one row per assumption/limitation object (and, for a scope, per criteria_status row):
#   {kind, id, basis, set} when it qualifies ·
#   {kind, id, basis: null, bulk, why, text, rationale, location} when it must be asked
#   (a criteria_status row has just {kind, id, basis: null, bulk: false, why}).
def carry_rows($ctx):
  . as $d
  | $ctx.prior as $p
  | ($ctx.kind // $d.kind) as $doc
  | ($ctx.prior_sha != "" and $ctx.cur_sha != "" and $ctx.prior_sha == $ctx.cur_sha) as $unchanged
  | (($ctx.prior_absent // false) and ($ctx.cur_absent // false)) as $absent
  | ($unchanged or ($ctx.body_unchanged // false)) as $body
  | ($ctx.cur | cf_sql_lines) as $c
  | (if $ctx.base != null then ($ctx.base | cf_sql_lines) elif $unchanged then $c else null end) as $b
  | ($p.revision // null) as $pr
  | [ ("assumptions", "limitations") as $k
      | ($d[$k] // [] | if type == "array" then .[] else empty end) | select(type == "object") | . as $i
      | ([($p[$k] // [])[] | select(type == "object" and .id == $i.id)][0]) as $m
      | {kind: $k, id: $i.id}
        + (if $ctx.reproof_failed // false then {why: "the recorded SQL cannot be re-proved from git"}
           elif $p == null then {why: "no previous published \($doc // "document") to carry from"}
           elif $m == null then {why: "no item \($i.id) in \($k) at revision \($pr)"}
           elif $m.text != $i.text then {why: "text differs from revision \($pr)"}
           elif $m.rationale != $i.rationale then {why: "rationale differs from revision \($pr)"}
           elif $m.decided != $i.decided then {why: "decided provenance differs from revision \($pr)"}
           elif $m.sql_status != $i.sql_status then {why: "the not-implemented mark differs from revision \($pr)"}
           elif ($m.location == null) != ($i.location == null) then
             {why: "location added or removed since revision \($pr)", bulk: ($doc == "review")}
           elif $i.location == null then
             if $unchanged then {basis: "sql-unchanged"}
             elif $absent then {basis: "sql-absent"}
             elif $body then {basis: "sql-body-unchanged"}
             elif $doc == "scope" then {basis: "intent-unchanged"}
             else {why: "SQL changed since revision \($pr) and the item has no location", bulk: true} end
           else ($m.location.lines) as $pl | ($i.location.lines) as $nl
             | if ($pl | cf_range | not) or ($nl | cf_range | not) then {why: "location lines are not a valid range"}
               elif ($pl[1] - $pl[0]) != ($nl[1] - $nl[0]) then {why: "governed line count changed since revision \($pr)"}
               elif $b == null or $c == null then {why: "no SQL baseline for revision \($pr) to compare the governed lines with"}
               elif $unchanged and $pl[1] <= ($b | length) and $nl[1] <= ($c | length) and $b[$pl[0] - 1:$pl[1]] == $c[$nl[0] - 1:$nl[1]]
               then {basis: "sql-unchanged"}
               # A changed SQL keeps a confirmation only where the diff itself re-locates the range (cf_relocate).
               elif ($unchanged | not) and cf_lines_kept($pl; $nl; $b; $c; $ctx.delta)
               then {basis: "lines-unchanged"}
               else {why: "governed lines changed, or the diff cannot re-locate them, since revision \($pr)"} end
           end)
      | if has("basis") then
          . + {set: ({status: "confirmed", confirmed_by: $m.confirmed_by, confirmed_at: $m.confirmed_at,
                     confirmed_revision: $m.confirmed_revision, carried_from_revision: $pr, carried_basis: .basis}
                     + (if $m | has("upstream") then {upstream: $m.upstream} else {} end)
                     + (if $m | has("decided") then {decided: $m.decided} else {} end))}
        else . + {basis: null, bulk: (.bulk // false), text: $i.text, rationale: $i.rationale, location: $i.location} end
    ]
  + (if $doc == "scope" then carry_criteria_rows($ctx) else [] end);

# The carried_* fields a draft row still holds when carryforward walks or bulks it. A walked row gets a
# fresh confirmation, so these fields must go first: check and publish refuse a fresh row that claims a carry.
# $row is a carry_rows output row; the draft item is found by id (by criterion for a criteria_status row).
def carry_clear($row):
  ((.[$row.kind] // []) | if type == "array" then . else [] end
    | map(select(type == "object" and (if $row.kind == "criteria_status" then .criterion else .id end) == $row.id))
    | .[0] // {}) as $i
  | [("carried_basis", "carried_from_revision") as $f | select($i[$f] != null) | $f];

# Publish's verdict: one violation line per carried item (carried_from_revision set; for a criteria_status
# row, carried_from_revision or carried_basis set) that does not qualify or does not copy the prior confirmation exactly. carried_basis is optional (documents
# written before #366 lack it) but, when present, must name the basis publish proves.
# $reconfirm_all refuses every carried item.
def carry_violations($ctx; $reconfirm_all):
  carry_rows($ctx) as $rows
  | (("assumptions", "limitations") as $k
     | (.[$k] // [])[] | select(type == "object" and .carried_from_revision != null) | . as $i
     | ([$rows[] | select(.kind == $k and .id == $i.id)][0]) as $r
     | if $reconfirm_all then "\($i.id): --reconfirm-all refuses carried confirmations — re-confirm for this revision"
       elif $r.basis == null then "\($i.id): cannot carry the confirmation forward: \($r.why) — re-confirm for this revision"
       elif ($i | {status, confirmed_by, confirmed_at, confirmed_revision, carried_from_revision}) != ($r.set | del(.carried_basis, .upstream, .decided))
       then "\($i.id): a carried item must copy confirmed_by, confirmed_at and confirmed_revision from revision \($r.set.carried_from_revision) exactly (sqlreview.sh carryforward prints them)"
       elif ($r.set.upstream.source == "analyst-intake" or $r.set.upstream.source == "house-default")
            and ($i.upstream != $r.set.upstream or $i.decided != $r.set.decided)
       then "\($i.id): carried \($r.set.upstream.source) must preserve upstream and decision provenance"
       elif ($i | has("carried_basis")) and $i.carried_basis != $r.basis
       then "\($i.id): carried_basis \($i.carried_basis | tojson) does not match the evidence (\($r.basis)); copy the set fields sqlreview.sh carryforward prints"
       else empty end),
    # A criteria_status row claiming a carry is proven the same way, keyed by criterion.
    (if ($ctx.kind // .kind) != "scope" then empty
     else (.criteria_status // [] | if type == "array" then .[] else empty end)
       | select(type == "object" and (.carried_from_revision != null or .carried_basis != null)) | . as $i
       | ([$rows[] | select(.kind == "criteria_status" and .id == $i.criterion)][0]) as $r
       | if $reconfirm_all then "\($i.criterion): --reconfirm-all refuses carried confirmations — re-confirm for this revision"
         elif $r.basis == null then "\($i.criterion): cannot carry the confirmation forward: \($r.why // "no such criterion row") — re-confirm for this revision"
         elif ($i | {confirmed_by, confirmed_at, confirmed_revision, carried_from_revision}) != ($r.set | del(.carried_basis, .upstream))
         then "\($i.criterion): a carried row must copy confirmed_by, confirmed_at and confirmed_revision from revision \($r.set.carried_from_revision) exactly (sqlreview.sh carryforward prints them)"
         elif ($i.upstream // null) != ($r.set.upstream // null)
         then "\($i.criterion): a carried row must keep upstream exactly as at revision \($r.set.carried_from_revision)"
         elif ($i | has("carried_basis")) and $i.carried_basis != $r.basis
         then "\($i.criterion): carried_basis \($i.carried_basis | tojson) does not match the evidence (\($r.basis)); copy the set fields sqlreview.sh carryforward prints"
         else empty end
     end);
