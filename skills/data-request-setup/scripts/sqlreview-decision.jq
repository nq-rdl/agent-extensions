# Advisory attribution heuristic, never a proof of a decision or its authority.
# Explicit provenance is checked at every status. Legacy rationale attribution is
# recognised by roles, capitalised names/handles followed by decision verbs, or
# passive "decided by". No person names are hard-coded.
def decision_source_warnings:
  (.assumptions // [], .limitations // [])[] | select(type == "object")
  | . as $item
  | ((.decided.source // "") | if type == "string" then . else "" end) as $source
  | ((.rationale // "") | if type == "string" then . else "" end) as $rationale
  | ($rationale | test("\\b(requester|researcher|custodian|approver|engineer|analyst)\\b.{0,30}\\b(decided|requested|provided|gave|chose|selected|specified|approved|holds? the approval)\\b|\\b(decided|chosen|specified|requested|approved) by\\b"; "i")
      or test("\\b[A-Z][A-Za-z0-9_-]*( [A-Z][A-Za-z0-9_-]*)? (decided|requested|provided|gave|chose|selected|specified|approved|holds? the approval)\\b")) as $attributed
  | select((($item | has("decided")) or $attributed)
           and (($source | test("\\S") | not) or ($source | test("^\\s*unlinked\\b"; "i"))))
  | {id: (.id // "?"), field: "decided.source", detail: "decision has no linked written source; verify attribution"};
