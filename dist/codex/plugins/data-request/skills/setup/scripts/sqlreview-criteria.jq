# Research-criteria vocabulary (the scaffold's criteria design): the one definition of criterion kinds, id shape, states
# per kind and display order, so the intake, check, coverage, scope-renderer and release scripts
# cannot drift. A def-only module: no top-level program.
#
# Load it by pointing jq at this directory and including it (the way sqlreview-slug.jq is):
#   jq -L "$SR_SCRIPT_DIR" 'include "sqlreview-criteria"; ...'
#
# Criteria are objects `{id, kind, ...}`. Ids are `^[NIED][1-9][0-9]*$` and the prefix names the
# kind: N entry_event, I inclusion, E exclusion, D data_element.
#
#   crit_kinds              the kinds, in display order
#   <kind> | crit_prefix    the id prefix for a kind (null for an unknown kind)
#   <criterion> | crit_id_ok  true when `id` is well formed and its prefix matches `kind`
#   crit_states($kind)      the allowed scope states for a kind ([] for an unknown kind)
#   crit_all_states         the union of every kind's states, first occurrence order
#   crit_reason_required    the states that need a `reason`
#   <criterion> | crit_order  sort key for `sort_by(crit_order)`: kind order, then numeric id
#                           (so E10 follows E2)
#   <id> | crit_kind_of_id  the kind an id prefix names (null for anything else)
#   <status row> | crit_status_order  crit_order for a scope `criteria_status` row, which carries
#                           `criterion` (the id) but no `kind`: the kind comes from the id prefix
#   <criteria> | crit_live  the criteria without `withdrawn`
def crit_kinds: ["entry_event", "inclusion", "exclusion", "data_element"];
def crit_prefix:
  if type == "string" then {"entry_event": "N", "inclusion": "I", "exclusion": "E", "data_element": "D"}[.] else null end;
def crit_id_ok:
  (.kind | crit_prefix) as $p
  | .id as $id
  | ($id | type) == "string" and $p != null
    and ($id | test("^[NIED][1-9][0-9]*\\z")) and $id[0:1] == $p;
def crit_states($kind):
  if $kind == "entry_event" then ["applied", "not-doable"]
  elif $kind == "inclusion" or $kind == "exclusion" then
    ["applied", "partially-applied", "flagged", "not-applied", "researcher-applies", "not-doable"]
  elif $kind == "data_element" then ["delivered", "not-delivered", "not-doable"]
  else [] end;
def crit_all_states:
  reduce (crit_kinds[] as $k | crit_states($k)[]) as $s ([]; if any(.[]; . == $s) then . else . + [$s] end);
def crit_reason_required: ["partially-applied", "not-applied", "not-delivered", "not-doable"];
def crit_order:
  .kind as $k | .id as $id
  | [((crit_kinds | index([$k])) // 99), ((try ($id[1:] | tonumber) catch 0) // 0)];
def crit_kind_of_id:
  if type == "string" then {"N": "entry_event", "I": "inclusion", "E": "exclusion", "D": "data_element"}[.[0:1]] else null end;
def crit_status_order: {id: .criterion, kind: (.criterion | crit_kind_of_id)} | crit_order;
def crit_live: map(select(.withdrawn == null));
