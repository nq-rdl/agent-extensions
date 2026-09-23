# Build the {{placeholder}} -> text map for rendering a scope/review document into its template.
# Input: the document; $cfgs[0] (jq --slurpfile cfgs config.json): the project's config. Every value is a string.
def lines(l): if l == null then "—" elif (l | type) == "array" then (l | map(tostring) | join("-")) else (l | tostring) end;
def named_list(a): if (a | length) == 0 then "_none_" else (a | map("- **\(.name // "?")** — \(.description // "")") | join("\n")) end;
def str_list(a): if (a | length) == 0 then "_none_" else (a | map("- " + (if type == "object" then (.question // .text // tostring) else tostring end)) | join("\n")) end;
def cell: tostring | gsub("\\|"; "&#124;") | gsub("[\r\n]+"; "<br>");
def table(a; heading):
  if (a | length) == 0 then "_none recorded_"
  else "| ID | \(heading) | Rationale | Lines | Confirmed by | Revision |\n|---|---|---|---|---|---|\n"
       + (a | map("| \(.id | cell) | \(.text | cell) | \(.rationale // "" | cell) | \(lines(.location.lines) | cell) | \(.confirmed_by // "" | cell) | \((.confirmed_revision // "" | tostring) + (if .carried_from_revision != null then " (carried)" else "" end) | cell) |") | join("\n"))
  end;
def steps(a): if (a | length) == 0 then "_none_" else (a | map("\(.step). **\(.title // "")** (lines \(lines(.lines))) — \(.description // "")") | join("\n")) end;
def changes(a): if (a | length) == 0 then "_none_" else (a | map("- r\(.revision) — \(.at // "") — \(.by // ""): \(.summary // "")") | join("\n")) end;
$cfgs[0] as $cfg |
{
  recurring: ((.recurring // false) | tostring),
  definition_lift_candidate: (($cfg.definitions.lift_candidate // "") | tostring),
  lifts_list: ((.lifts // []) | if length == 0 then "_none recorded_" else map(
    "## \(.id): \(.need)\n\nClassification: \(.classification // "unclassified") · status: \(.status)\n\nLibrary: \(.library) @ \(.pinned_version)\n\nInspected: \(.looked_in | map(.path + " @ " + .revision) | join(", "))\n\nShortfall: \(.shortfall)\n\nWorkaround: `\(.workaround.file)` lines \(lines(.workaround.lines))\n\nIssue: \(.issue_url // "none")\n\nConfirmed: \(.confirmed_by // "pending") · \(.confirmed_at // "") · revision \(.confirmed_revision // "")"
  ) | join("\n\n") end),
  title: ((.title // .slug) | tostring),
  slug: (.slug | tostring),
  sql_path: (.sql_path | tostring),
  revision: (.revision | tostring),
  recorded_at: ((.recorded_at // "") | tostring),
  recorded_by: ((.recorded_by // "") | tostring),
  git_commit: ((.git_commit // "n/a") | tostring),
  sql_sha256: ((.sql_sha256 // "n/a") | tostring),
  purpose: ((.purpose // "") | tostring),
  intent: ((.intent // "") | tostring),
  grain: ((.grain // "") | tostring),
  inputs_list: named_list(.inputs // []),
  outputs_list: named_list(.outputs // []),
  logic_steps: steps(.logic // []),
  assumptions_table: table(.assumptions // []; "Assumption"),
  limitations_table: table(.limitations // []; "Limitation"),
  open_questions_list: str_list(.open_questions // []),
  changes_list: changes(.changes // []),
  definition_assumption: (($cfg.definitions.assumption // "") | tostring),
  definition_limitation: (($cfg.definitions.limitation // "") | tostring),
  role_engineer: (($cfg.roles.engineer // "Data Engineer") | tostring),
  role_analyst: (($cfg.roles.analyst // "Data Analyst") | tostring)
}
