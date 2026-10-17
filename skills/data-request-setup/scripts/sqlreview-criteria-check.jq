# Research-criteria coverage for one scope (spec 017): the rules that need the analyst's sidecar,
# so `sqlreview.sh criteria` runs them and the guard hook's shape check (sqlreview-check.jq) cannot.
# Input: the scope document. Arguments:
#   $intake  `sqlreview.sh intake` output for answers.intake.json at the repository root; it has a
#            `criteria` array only for a valid schema 2 sidecar
#   $others  how many other scopes in the repository carry criteria_status
# Emits one "<id>\t<field>\t<rule>" line per finding ("-" for the document); no output is clean.
# Never a value: a malformed criterion is check's to report, so it is skipped here.
# Run with `jq -L <this directory>` for the criteria vocabulary.
include "sqlreview-criteria";
def well_formed: type == "string" and test("^[NIED][1-9][0-9]*\\z");
def prefix_kind: {"N": "entry_event", "I": "inclusion", "E": "exclusion", "D": "data_element"}[.[0:1]];
def finding($id; $field; $rule): {id: $id, field: $field, rule: $rule};

if has("criteria_status") | not then empty
else
  ($intake.criteria // null) as $criteria
  | (if ($criteria | type) != "array" or ($criteria | length) == 0
     then "-\tcriteria_status\tno-itemised-criteria" else empty end),
    (if $others > 0 then "-\tcriteria_status\towning-scope-ambiguous" else empty end),
    (if ($criteria | type) != "array" or ($criteria | length) == 0 then empty
     else
       (reduce $criteria[] as $c ({}; .[$c.id] = $c)) as $by
       | [.criteria_status | if type == "array" then .[] else empty end
          | select(type == "object" and (.criterion | well_formed))] as $rows
       | ($rows | map(.criterion)) as $stated
       | [ ($criteria | crit_live[] | select(.id as $i | ($stated | index([$i])) == null)
            | finding(.id; "state"; "missing")),
           ($rows[] | .criterion as $id | .state as $s | $by[$id] as $c
            | if $c == null then finding($id; "criterion"; "unknown")
              elif $c.withdrawn != null then finding($id; "state"; "withdrawn")
              elif (crit_states($c.kind) | index([$s])) == null then finding($id; "state"; "not-allowed")
              elif $s == "researcher-applies" and $c.applied_by != "researcher"
              then finding($id; "state"; "researcher-applies-unbased")
              else empty end)
         ]
       | unique
       | sort_by({id, kind: (.id | prefix_kind)} | crit_order)[]
       | "\(.id)\t\(.field)\t\(.rule)"
     end)
end
