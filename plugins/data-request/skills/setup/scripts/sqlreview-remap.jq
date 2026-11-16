# Draft-only remap (#438). Unified diff's unchanged intervals are the line map;
# never search for a matching slice (repeated SQL can make that a false proof).
# If a governed line also occurs in an edit, the diff alignment is ambiguous:
# conservatively leave that range for the human, even if diff chose to keep it.
# One exception: the whole governed text occurs exactly once in the baseline and exactly
# once in the current SQL. Then only one alignment exists, so a shared line such as a
# repeated GO separator does not block the remap. The diff still supplies the offset.
# Inputs: authenticated $prior/$base, frozen $cur, zero-context $delta.
include "sqlreview-carry";

def remap_valid:
  type == "object"
  and all((.assumptions, .limitations); type == "array" and all(.[];
    type == "object" and (.id | type == "string") and
    (.location == null or ((.location | type == "object") and (.location.lines | cf_range))))
    and (map(.id) | length == (unique | length)))
  and ((.logic // []) | type == "array" and all(.[];
    type == "object" and (.step | type == "number" and . >= 1 and . == floor) and (.lines | cf_range))
    and (map(.step) | length == (unique | length)))
  # A criteria_status row may record the SQL lines that apply it (the decided re-walk rule).
  and ((.criteria_status // []) | type == "array" and all(.[];
    type == "object" and (.location == null or ((.location | type == "object") and (.location.lines | cf_range)))));

def remap_ranges:
  [ ("assumptions", "limitations") as $k | .[$k] | to_entries[]
    | select(.value.location != null)
    | {kind: $k, id: .value.id, path: [$k, .key, "location", "lines"], lines: .value.location.lines} ]
  + [ (.logic // []) | to_entries[]
      | {kind: "logic", id: .value.step, path: ["logic", .key, "lines"], lines: .value.lines} ]
  + [ (.criteria_status // []) | to_entries[] | select(.value.location != null)
      | {kind: "criteria_status", id: .value.criterion, path: ["criteria_status", .key, "location", "lines"],
         lines: .value.location.lines} ];

def remap_result:
  ($base | cf_sql_lines) as $b | ($cur | cf_sql_lines) as $c
  | cf_segments($delta; $b | length; $c | length) as $segments
  | cf_edited($delta) as $edited
  | . as $draft
  | [ remap_ranges[] | . as $r
      | ([ $prior[0] | remap_ranges[] | select(.kind == $r.kind and .id == $r.id) ]) as $matches
      | ($matches[0].lines) as $old
      | if ($matches | length) != 1 then . + {why: "no unique range in the published baseline"}
        elif $old[1] > ($b | length) then . + {why: "published range is outside the baseline"}
        else ([ $segments[] | select($old[0] >= .from and $old[1] <= .to) ][0]) as $segment
          | if $segment == null then . + {why: "governed lines changed or an insertion splits the range"}
            else ($old | map(. + $segment.shift)) as $new
              | ($b[$old[0] - 1:$old[1]] | map(.)) as $slice
              | if any($slice[]; . as $line | $edited | index($line) != null)
                   and (($b | cf_count($slice)) != 1 or ($c | cf_count($slice)) != 1)
                then . + {why: "ambiguous alignment: governed text also occurs in the edit"}
                elif $r.lines != $old and $r.lines != $new then . + {why: "draft range differs from both baseline and computed range; keep the manual edit"}
                elif $b[$old[0] - 1:$old[1]] != $c[$new[0] - 1:$new[1]] then error("diff map does not preserve governed bytes")
                else . + {old: $old, new: $new} end
            end
        end ] as $rows
  | {draft: (reduce ($rows[] | select(has("new"))) as $r ($draft; setpath($r.path; $r.new))),
     report: {document: .kind, prior_revision: $prior[0].revision,
       remapped: [$rows[] | select(has("new")) | {kind, id, from: .old, to: .new}],
       walk: [$rows[] | select(has("why")) | {kind, id, lines, why}]}};
