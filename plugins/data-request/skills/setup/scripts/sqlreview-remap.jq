# Draft-only remap (#438). Unified diff's unchanged intervals are the line map;
# never search for a matching slice (repeated SQL can make that a false proof).
# If a governed line also occurs in an edit, the diff alignment is ambiguous:
# conservatively leave that range for the human, even if diff chose to keep it.
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
    and (map(.step) | length == (unique | length)));

def remap_ranges:
  [ ("assumptions", "limitations") as $k | .[$k] | to_entries[]
    | select(.value.location != null)
    | {kind: $k, id: .value.id, path: [$k, .key, "location", "lines"], lines: .value.location.lines} ]
  + [ (.logic // []) | to_entries[]
      | {kind: "logic", id: .value.step, path: ["logic", .key, "lines"], lines: .value.lines} ];

def remap_result:
  ($base | cf_sql_lines) as $b | ($cur | cf_sql_lines) as $c
  | ($delta | split("\n")) as $diff
  | [ $diff[] | select(startswith("@@ "))
      | capture("^@@ -(?<o>[0-9]+)(,(?<ol>[0-9]+))? \\+(?<n>[0-9]+)(,(?<nl>[0-9]+))? @@")
      | {o: (.o | tonumber), ol: ((.ol // "1") | tonumber),
         n: (.n | tonumber), nl: ((.nl // "1") | tonumber)} ] as $hunks
  # Zero-length hunk starts name the line BEFORE the insertion/deletion.
  | (reduce ($hunks + [{o: (($b | length) + 1), ol: 1, n: (($c | length) + 1), nl: 1}])[] as $h
      ({o: 1, n: 1, segments: []};
       ($h.o + (if $h.ol == 0 then 1 else 0 end)) as $start
       | .segments += [{from: .o, to: ($start - 1), shift: (.n - .o)}]
       | .o = ($start + $h.ol)
       | .n = ($h.n + (if $h.nl == 0 then 1 else 0 end) + $h.nl)) | .segments) as $segments
  | [ $diff[2:][] | select(startswith("+") or startswith("-")) | .[1:] ] as $edited
  | . as $draft
  | [ remap_ranges[] | . as $r
      | ([ $prior[0] | remap_ranges[] | select(.kind == $r.kind and .id == $r.id) ]) as $matches
      | ($matches[0].lines) as $old
      | if ($matches | length) != 1 then . + {why: "no unique range in the published baseline"}
        elif $old[1] > ($b | length) then . + {why: "published range is outside the baseline"}
        else ([ $segments[] | select($old[0] >= .from and $old[1] <= .to) ][0]) as $segment
          | if $segment == null then . + {why: "governed lines changed or an insertion splits the range"}
            else ($old | map(. + $segment.shift)) as $new
              | if any($b[$old[0] - 1:$old[1]][]; . as $line | $edited | index($line) != null)
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
