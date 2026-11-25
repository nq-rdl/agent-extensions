# Turns query-builder's script manifest (pypika_queries.script_format.describe_script, as JSON) into the
# record stream that `notes` reads (the one _notes_scan prints), so one parser serves both readers (#585).
# Run as `jq -r -L DIR --argjson awk RECORDS -f sqlreview-manifest.jq MANIFEST`, where RECORDS is the jq grammar's
# own records as an array of arrays, or null when that grammar rejected the header.
#
# The manifest names no line numbers. They come from the jq grammar's records, and only where the two readers
# agree on every item of the section. Where they differ the lines are empty, so the item can be neither
# carried nor decided from its header position, and the difference is listed under `disagreements`.
# A record "D", message follows for each disagreement (the caller moves them into the JSON).
def kind_of: if . == "assumption" then "assumptions" elif . == "limitation" then "limitations" else null end;
def want: if . == "assumption" then "rationale" else "consequence" end;
def detail($n):
  ($n.details | map(select(.[0] == ($n.section | want)))) as $d
  | if ([$n.details[] | .[0]] | map(select(. != ($n.section | want))) | length) > 0
    then error("\($n.id): detail label is not \($n.section | want): (only that detail is read)")
    elif ($d | length) > 1 then error("\($n.id): second \($n.section | want): for one item")
    elif ($d | length) == 1 then $d[0][1] else null end;
(.format_version) as $fv
| if $fv != 1 then error("script format version \($fv) is not understood; this helper reads version 1") else . end
| [.notes[] | select(.section != "input")] as $notes
| ($awk // []) as $a
| [ ("assumptions", "limitations") as $k
    | [$notes[] | select((.section | kind_of) == $k) | {k: $k, text, rationale: detail(.)}] as $lib
    | [$a[] | select(.[0] == "I" and .[1] == $k)] as $mine
    | ($awk == null) as $nogrammar
    | (($lib | length) == ($mine | length)
       and ([range(0; $lib | length)] | all(. as $i | $lib[$i].text == $mine[$i][4]
            and $lib[$i].rationale == (if $mine[$i][5] == "1" then $mine[$i][6] else null end)))) as $same
    | {k: $k, lib: $lib, mine: $mine, ok: (($nogrammar | not) and $same), nogrammar: $nogrammar}
  ] as $kinds
# The jq grammar found items the library did not: a header the format does not allow in that place (after a SET
# line, a banner or CRLF line ends, say) would otherwise read as "no header", the failure of #567. Stop instead.
| ([$kinds[] | select((.nogrammar | not) and (.mine | length) > (.lib | length))
     | "\(.k): the jq grammar read \(.mine | length) item(s) and the library \(.lib | length)"]) as $missed
| if ($missed | length) > 0 then error("the query-builder reader does not find notes that the header grammar finds (" + ($missed | join("; ")) + "); the header may not follow docs/SCRIPT_FORMAT.md") else . end
| ([$kinds[] | select(.ok | not) | .k] | length) as $bad
| [ $kinds[] | select(.ok | not)
    | if .nogrammar then "\(.k): the jq grammar rejected the header, so line numbers are unavailable"
      else "\(.k): the jq grammar read \(.mine | length) item(s) and the library \(.lib | length), or their text differs" end
  ] as $why
| ([$a[] | select(.[0] == "H")][0]) as $h
| ( $kinds[]
    | . as $kd
    | range(0; .lib | length) as $i
    | ["I", $kd.k,
       (if $kd.ok then $kd.mine[$i][2] else "" end),
       (if $kd.ok then $kd.mine[$i][3] else "" end),
       $kd.lib[$i].text, (if $kd.lib[$i].rationale == null then "0" else "1" end), ($kd.lib[$i].rationale // "")]
    | join("\u001f") ),
  ( if (.notes | length) > 0 then
      (["H"] + (if $bad == 0 and $h != null then [$h[1], $h[2]] else ["", ""] end) | join("\u001f"))
    else empty end ),
  ( $why[] | "D\u001f" + . )
