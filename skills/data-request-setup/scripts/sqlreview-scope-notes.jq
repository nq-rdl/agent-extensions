# Factual scope comparison only. Semantic settlement is for bootstrap's source review,
# never inferred from token overlap, IDs in prose, or a confirmed engineer choice.
def scope_notes($questions):
  [ ("assumptions", "limitations") as $kind
    | .[$kind] | to_entries[]
    | .value + {kind: $kind, header_id: ((if $kind == "assumptions" then "HA" else "HL" end) + ((.key + 1) | tostring))}
  ] as $headers
  | . + {scope_check: {
      unmatched_header: [$headers[] | select(.match == null)],
      rationale_differences: [$headers[] | select(.match != null and (.match.rationale_same | not))],
      question_check_basis: "semantic-review-required",
      question_checks: [ $questions.questions[] | select(.applies == "scope" and .status == "open") as $q
        | $headers[] | {question: $q, header: .} ]
    }};
