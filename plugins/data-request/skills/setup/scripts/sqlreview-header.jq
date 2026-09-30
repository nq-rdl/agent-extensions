# #431: evidence for a fresh human carry-all question, never automatic confirmation.
def hd_lines: rtrimstr("\n") | split("\n");
def hd_origin:
  (try capture("^Engineer decision \\((?<by>[A-Za-z0-9][A-Za-z0-9_-]*), (?<at>[0-9T:Z.-]+)\\)(?:, flagged for the data analyst)?$") catch null)
  // (try capture("^Engineer decision by (?<by>[A-Za-z0-9][A-Za-z0-9_-]*) on (?<at>[0-9T:Z.-]+)$") catch null) // null;
def hd_time:
  . as $date
  | if test("^[0-9]{4}-[0-9]{2}-[0-9]{2}$") then . + "T00:00:00Z" else . end
  | . as $iso | try (fromdateiso8601 as $epoch
    | if ($epoch | strftime("%Y-%m-%dT%H:%M:%SZ")) == $iso then {epoch:$epoch, date:$date[0:10], precision:(if ($date|length)==10 then "date" else "instant" end)} else null end) catch null;
def hd_header($kind; $item):
  [(.notes[$kind] // [])[] | select(.text == $item.text and .rationale == $item.rationale)] | length == 1;
# Bind filter arguments before changing input. Only a unique exact range at the same
# body-relative offset is evidence. The prefix must also survive: a relocated matching
# snippet elsewhere is not a line-history proof. Header growth alone may shift lines.
def hd_range($sql; $start; $offset; $prefix; $excerpt):
  $sql as $s | $start as $b | $offset as $o | $prefix as $p | $excerpt as $e
  | if $s == null or $b < 1 then false
    else $s[$b-1:$b-1+$o+($e|length)] == $p
      and ([range($b-1; ($s|length)) as $n | select($s[$n:$n+($e|length)] == $e)] | length == 1)
    end;
def header_candidates($doc; $sql; $actor; $path; $sha; $safe; $start; $history):
  . as $notes | ($sql | hd_lines) as $lines
  | [("assumptions", "limitations") as $kind | ($doc[$kind] // [])[] | . as $item
      | [$notes[$kind][] | select(.text == $item.text and .rationale == $item.rationale)] as $matches
      | ($item.rationale | if type == "string" then hd_origin else null end) as $origin
      | ($origin.at // "" | hd_time) as $time
      | ($item.location.lines // []) as $range
      | {kind:$kind, id:$item.id, text:$item.text, rationale:$item.rationale, location:$item.location}
      + if ($matches | length) != 1 then {why:"header text or rationale differs, or the match is ambiguous"}
        elif $origin == null or $time == null then {why:"no valid named dated engineer decision"}
        elif $time.epoch > now then {why:"decision date is in the future"}
        elif $actor == "" or $origin.by != $actor then {why:"named decider does not match the actual review confirmer"}
        elif $doc.sql_path != $path or $doc.sql_sha256 != $sha then {why:"draft SQL identity or fingerprint differs"}
        elif $safe != true then {why:"missing, shallow, relevant merge/rename or inconsistent git history"}
        elif ($range | type) != "array" or ($range | length) != 2 or
             ($range | all(.[]; type == "number" and . >= 1 and . == floor) | not) or
             $range[0] < $start or $range[0] > $range[1] or $range[1] > ($lines|length) then {why:"no proven governed SQL line range"}
        # Materialise slices: jq 1.6 can compare two views of one backing array
        # as equal despite differing offsets, defeating uniqueness checks.
        else ($lines[$range[0]-1:$range[1]] | map(.)) as $excerpt
          | ($range[0] - $start) as $offset
          | ($lines[$start-1:$range[1]] | map(.)) as $prefix
          | ([$history | to_entries[] | select(.value | hd_header($kind; $item))][0]) as $entry
          | $entry.value as $first
          | (if $entry == null then [] else $history[$entry.key:] end) as $later
          | if $first == null then {why:"decision header has no committed source"}
            elif (if $time.precision == "date" then ($first.at | strftime("%Y-%m-%d")) > $time.date else $first.at > $time.epoch end)
              then {why:"first committed decision source is after the decision date"}
            elif $first.at > now then {why:"committed decision source is in the future"}
            # Entry failures before this decision's first source are irrelevant. Ancestry
            # availability stays global; source/subsequent merges, renames and times do not.
            elif ($later | all(.[]; .safe == true) | not) or
                 (all(range(1; ($later|length)); . as $n | $later[$n].at >= $later[$n-1].at) | not)
              then {why:"invalid source or subsequent relevant merge/rename or inconsistent git history"}
            elif ($later | all(.[]; hd_header($kind; $item) and hd_range(.sql; .body_start; $offset; $prefix; $excerpt)) | not)
              or (hd_range($lines; $start; $offset; $prefix; $excerpt) | not) then {why:"header wording or governed SQL changed since the recorded decision source"}
            else {by:$origin.by, role:"engineer", at:$origin.at,
                  source:"git:\($first.commit):\($path)#L\($first.notes[$kind][] | select(.text == $item.text and .rationale == $item.rationale) | .lines[0])"} as $decided
              | if ($item | has("decided")) and $item.decided != $decided then {why:"decision provenance differs from the recorded header source"}
                else {basis:"header-decision", decided:$decided,
                      evidence:{commit:$first.commit, committed_at:($first.at | todateiso8601), precision:$time.precision,
                                sql_path:$path, header_lines:$matches[0].lines}} end
            end
        end
    ] as $rows
  | . + {header_carry_over:[$rows[] | select(.basis == "header-decision")], header_walk:[$rows[] | select(.basis == null)]};
