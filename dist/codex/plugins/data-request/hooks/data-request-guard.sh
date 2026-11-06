#!/usr/bin/env bash
# PreToolUse guard (data-request plugin), matchers Write|Edit and Read|Grep|Glob. Read, Grep and Glob are denied for paths
# under data/00_raw/ (researcher-supplied cohort files; *.dvc and .gitignore pass), for a Grep or Glob rooted at or above it
# (no path means the cwd) and for a glob or pattern that could name it. They pass everywhere else. Write|Edit fire
# only for paths under a .sqlreview/ directory; everything else passes silently. Decisions via
# permissionDecision JSON:
#   reviews/*/review.json, scope.json   Write → content run through `sqlreview.sh check`:
#                                        every assumption/limitation must carry a complete
#                                        confirmation record for the current revision, else deny
#                                        (the violations and the AskUserQuestion step are named);
#                                        carried confirmations → deny (only publish can prove them)
#                                       Edit  → deny (a fragment cannot be validated; Write the whole file)
#   reviews/*/review.md, scope.md       deny  (rendered from the JSON by `sqlreview.sh render`)
#   ledger.json                         deny  (triage entries use validated atomic ledger set)
#   config.json                         ask   (config changes go through /data-request:setup)
#   releases/*/release.json             Write → content run through `release.sh check`; Edit → deny
#   releases/*/release.md               deny  (rendered from the record by `release.sh render`)
#   reviews/*/explain.json              Write → its `by` must be a handle, not an email (#419); Edit → deny
#   amendments/<request>.json           Write → content run through `release.sh amend-check`; Edit → deny
#   reviews/*/*.draft.json, templates/*   pass
#   any name ending .sql .csv .tsv .parquet .xlsx .xls (case and trailing blanks or dots ignored), except under templates/   deny
#                                       (the store holds JSON, hashes and commits only, #505)
# This is an invariant check, not proof that a human answered: it makes "forgot to ask" a denied
# tool call with the offending ids named, and leaves a fabricated confirmation auditable in the
# recorded document. Bash heredocs into .sqlreview/ are out of its reach by design (guardrail, not sandbox).
# The checker is resolved via CLAUDE_PLUGIN_ROOT, then relative to this hook's own plugin copy,
# then the canonical skills/ tree; when none is found the guard DENIES — a missing guardrail must
# not silently pass. JSON in/out via jq, falling back to python3 for the event; neither present,
# or malformed stdin → no-op when a parser is available.
set -u
command -v jq >/dev/null 2>&1 || command -v python3 >/dev/null 2>&1 || {
  printf '%s\n' '{"hookSpecificOutput":{"hookEventName":"PreToolUse","permissionDecision":"deny","permissionDecisionReason":"SQL Review guard requires jq; no event parser is available. Install jq before writing."}}'
  exit 0
}
input="$(cat 2>/dev/null)" || exit 0
[ -n "$input" ] || exit 0

field() { # <.dotted.path> → string value from $input, or empty
  if command -v jq >/dev/null 2>&1; then
    printf '%s' "$input" | jq -r "$1 // empty" 2>/dev/null
  else
    printf '%s' "$input" | python3 -c 'import json,sys
try: d = json.load(sys.stdin)
except Exception: sys.exit(0)
for k in sys.argv[1].strip(".").split("."):
    d = d.get(k) if isinstance(d, dict) else None
sys.stdout.write(d if isinstance(d, str) else "")' "$1" 2>/dev/null
  fi
}
decide() { # <allow|deny|ask> <reason>
  if command -v jq >/dev/null 2>&1; then
    jq -nc --arg d "$1" --arg r "$2" '{hookSpecificOutput:{hookEventName:"PreToolUse",permissionDecision:$d,permissionDecisionReason:$r}}'
  else
    python3 -c 'import json,sys; print(json.dumps({"hookSpecificOutput":{"hookEventName":"PreToolUse","permissionDecision":sys.argv[1],"permissionDecisionReason":sys.argv[2]}}))' "$1" "$2"
  fi
  exit 0
}

tool="$(field .tool_name)"
# A shell command substitution trims trailing newlines and a later step can split on blanks, so a control
# character in a path-like field could change what the checks below see. Test the raw JSON values first,
# for every field that names a path or a glob (a Grep pattern is a regex and may hold a tab or newline), and fail closed.
# The content fields are not tested.
case "$tool" in Write|Edit|Read|Grep|Glob|NotebookEdit)
  if command -v jq >/dev/null 2>&1; then
    printf '%s' "$input" | jq -e '[.cwd, .tool_input.file_path, .tool_input.path, .tool_input.glob, (if .tool_name == "Glob" then .tool_input.pattern else null end), .tool_input.notebook_path] | any(.[]; type == "string" and any(explode[]; . < 32 or . == 127))' >/dev/null 2>&1 && ctl=1 || ctl=0
  else
    printf '%s' "$input" | python3 -c 'import json,re,sys
try: d = json.load(sys.stdin)
except Exception: sys.exit(1)
t = d.get("tool_input") if isinstance(d.get("tool_input"), dict) else {}
v = [d.get("cwd")] + [t.get(k) for k in ("file_path", "path", "glob", "notebook_path")] + ([t.get("pattern")] if d.get("tool_name") == "Glob" else [])
sys.exit(0 if any(isinstance(x, str) and re.search("[\\x00-\\x1f\\x7f]", x) for x in v) else 1)' && ctl=1 || ctl=0
  fi
  [ "$ctl" = 0 ] || decide deny "A path, search root or search filter in this call contains a control character (a newline, tab or similar), so the guard cannot check it safely. Use a path without control characters."
esac
case "$tool" in
  Write|Edit|Read) path="$(field .tool_input.file_path)" ;;
  Grep|Glob) path="$(field .tool_input.path)" ;;  # the search root; no path means the cwd
  *) exit 0 ;;
esac
raw_denied="Reading or searching data/00_raw/ is denied: a researcher-supplied cohort file holds identifiers, and the runner loads it into a temp table at run time. Never read or search it, copy a value from it, or print one. For its shape read conf/base/supplied/<name>.template.csv (header only); for a load problem use the reason codes, row numbers and column names the runner reports (no value appears in them). Only a genuine small DVC pointer (*.dvc) or .gitignore file can be Read."
above_denied="A Grep or Glob rooted at or above data/00_raw/ (or above a project that holds it, or holding a link into it) can reach researcher-supplied identifiers, so it is denied. Pass a path inside one project that excludes data/, such as skills/ or src/. Never search data/00_raw/."
lc() { printf '%s' "$1" | tr '[:upper:]' '[:lower:]'; }
NL='
'
# One rule decides every raw-data question. For each governing project, RAW_LEX is <project>/data/00_raw as
# written and RAW_PHYS is its physical path (resolved, even when 00_raw or data is a symlink).
#   Read target, Grep or Glob root  denied when its lexical OR physical path is at or under RAW_LEX or RAW_PHYS.
#   Grep or Glob root               also denied when it is an ancestor of RAW_LEX or RAW_PHYS, when a bounded search
#                                   under it finds a data/00_raw entry of ANY type, or when that search finds a
#                                   symbolic link whose resolved target is at, under or above a RAW_PHYS, holds
#                                   data/00_raw, or is one.
#   Grep glob, Glob pattern         denied when a path segment of it could be 00_raw (GLOB_RAW_AWK below).
# A governing project is any directory, from the target's lexical and physical path and from the cwd up, that
# holds a data/00_raw entry of any type (a dangling link counts).
# A glob is checked as text because it can reach the directory from a root above it. It is expanded (braces),
# split into segments and matched against the name 00_raw, ignoring case and trailing blanks and dots. It is
# denied only when a segment after a data/ or **/ boundary, or a segment with a literal character at the start,
# could match that name. So *draw*.py and Drawing*.md pass; data/00_r[a]w/*, data/0?_raw/* and **/00_RAW/** do not.
GLOB_RAW_AWK='
function gm(p, pi, s, si,   c, ch, k, e, start, cl, neg, hit, lo, hi) {
  while (pi <= length(p)) {
    c = substr(p, pi, 1)
    if (c == "*") {
      while (substr(p, pi + 1, 1) == "*") pi++
      pi++
      if (pi > length(p)) return 1
      for (k = si; k <= length(s) + 1; k++) if (gm(p, pi, s, k)) return 1
      return 0
    }
    if (si > length(s)) return 0
    ch = substr(s, si, 1)
    if (c == "?") { pi++; si++; continue }
    if (c == "\\") { c = substr(p, pi + 1, 1); pi += 2; if (c != ch) return 0; si++; continue }
    if (c == "[") {
      e = pi + 1; neg = 0
      if (substr(p, e, 1) == "!" || substr(p, e, 1) == "^") { neg = 1; e++ }
      start = e; cl = 0
      for (k = start + 1; k <= length(p); k++) if (substr(p, k, 1) == "]") { cl = k; break }
      if (cl == 0) { if (c != ch) return 0; pi++; si++; continue }
      hit = 0; k = start
      while (k < cl) {
        lo = substr(p, k, 1)
        if (substr(p, k + 1, 1) == "-" && k + 2 < cl) { hi = substr(p, k + 2, 1); if (ch >= lo && ch <= hi) hit = 1; k += 3 }
        else { if (ch == lo) hit = 1; k++ }
      }
      if (hit == neg) return 0
      pi = cl + 1; si++; continue
    }
    if (c != ch) return 0
    pi++; si++
  }
  return si > length(s)
}
function names(seg, target,   t) { t = seg; sub(/[ .]+$/, "", t); return gm(seg, 1, target, 1) || gm(t, 1, target, 1) }
function add(str) { if (++nout > 256) { over = 1; return } OUT[nout] = str }
function expand(str,   i, c, d, s, e, pre, inner, post, cur) {
  if (over) return
  s = index(str, "{")
  if (s == 0) { add(str); return }
  d = 0; e = 0
  for (i = s; i <= length(str); i++) { c = substr(str, i, 1); if (c == "{") d++; else if (c == "}") { d--; if (d == 0) { e = i; break } } }
  if (e == 0) { gsub(/[{}]/, "", str); add(str); return }
  pre = substr(str, 1, s - 1); inner = substr(str, s + 1, e - s - 1); post = substr(str, e + 1)
  d = 0; cur = ""
  for (i = 1; i <= length(inner); i++) {
    c = substr(inner, i, 1)
    if (c == "{") d++; else if (c == "}") d--
    if (c == "," && d == 0) { expand(pre cur post); cur = "" } else cur = cur c
  }
  expand(pre cur post)
}
function haslit(x,   i) { for (i = 1; i <= length(x); i++) if (index("*?[]{}!^,\\", substr(x, i, 1)) == 0) return 1; return 0 }
BEGIN {
  f = tolower(ENVIRON["GLOB_TEXT"])
  if (index(f, "[:") || index(f, "[.") || index(f, "[=")) { print "DENY"; exit }
  sub(/^!+/, "", f)
  expand(f)
  if (over) { print "DENY"; exit }
  for (a = 1; a <= nout; a++) {
    n = split(OUT[a], parts, "/"); m = 0
    for (i = 1; i <= n; i++) if (parts[i] != "" && parts[i] != ".") seg[++m] = parts[i]
    for (i = 1; i <= m; i++) {
      if (!names(seg[i], "00_raw")) continue
      if (i > 1) { if (names(seg[i - 1], "data") || seg[i - 1] == "**") { print "DENY"; exit } }
      else if (haslit(seg[i])) { print "DENY"; exit }
    }
    split("", seg)
  }
  print "OK"
}'
case "$tool" in Grep) filter="$(field .tool_input.glob)" ;; Glob) filter="$(field .tool_input.pattern)" ;; *) filter="" ;; esac
if [ -n "$filter" ]; then
  filter_lc="$(lc "$filter")"
  filter_reason="A Grep glob or Glob pattern with a path segment that could be 00_raw (a literal, or a wildcard that can match it), with .., or starting at an absolute path could reach data/00_raw/, so it is denied. Pass a literal path under skills/ or src/ and a plain filter such as *.py."
  case "$filter_lc" in *..*|/*|'~'*) decide deny "$filter_reason" ;; esac
  [ "$(GLOB_TEXT="$filter_lc" awk "$GLOB_RAW_AWK" </dev/null 2>/dev/null)" = OK ] || decide deny "$filter_reason"
fi
case "$tool" in Grep|Glob) [ -n "$path" ] || path="." ;; esac  # no path means the cwd
[ -n "$path" ] || exit 0
cwd="$(field .cwd)"; [ -n "$cwd" ] || cwd="$(pwd -P)"
case "$path" in /*) abs="$path" ;; *) abs="$cwd/$path" ;; esac
# Physical directory with every character kept: command substitution trims trailing newlines, so a sentinel
# protects the name. A newline anywhere in a resolved name is refused, because the line-based cleanup below
# could misread it. Sets PHYS.
physdir() {
  local o
  o="$(cd -P -- "$1" 2>/dev/null && pwd -P && printf x)" || return 1
  o="${o%x}"; PHYS="${o%$'\n'}"
  case "$PHYS" in *$'\n'*) decide deny "A resolved directory name contains a newline, so the guard cannot rule out data/00_raw/. Use a path without a newline." ;; esac
}
normalize_path() {
  awk -F/ '{ n=0; for (i=1;i<=NF;i++) { if ($i==""||$i==".") continue; if ($i=="..") { if (n>0) n--; continue }; p[++n]=$i }; o=""; for (i=1;i<=n;i++) o=o "/" p[i]; print (o==""?"/":o) }'
}
# Physical path of an absolute path: the existing parent via cd -P (so a ".." after a symlinked directory is
# followed on disk), then the final component's symlink chain. A loop or a chain over 20 hops is denied, never
# allowed. A name that does not exist yet keeps its absent suffix. Sets RPHYS.
resolve_phys() {
  local p="$1" hops=0 parent suffix target
  while :; do
    parent="$(dirname "$p")"; suffix="$(basename "$p")"
    while [ ! -d "$parent" ] && [ "$parent" != / ]; do suffix="$(basename "$parent")/$suffix"; parent="$(dirname "$parent")"; done
    if physdir "$parent"; then p="$PHYS/$suffix"; else break; fi
    p="$(printf '%s\n' "$p" | normalize_path)"
    [ -L "$p" ] || break
    hops=$((hops + 1))
    [ "$hops" -le 20 ] || decide deny "Read guard could not resolve a symlink chain (loop or over 20 links), so it cannot rule out data/00_raw/. Read the non-symlink path."
    target="$(readlink -- "$p" 2>/dev/null; printf x)"; target="${target%x}"; target="${target%$'\n'}"
    case "$target" in *$'\n'*) decide deny "A symlink target contains a newline, so the guard cannot rule out data/00_raw/. Read the non-symlink path." ;; esac
    [ -n "$target" ] || break
    case "$target" in /*) p="$target" ;; *) p="$(dirname "$p")/$target" ;; esac
  done
  RPHYS="$p"
}
under() { case "$1/" in "${2%/}/"*) return 0 ;; esac; return 1; }  # <path> <dir>: the path is the dir or is below it
case "$tool" in Read|Grep|Glob)
  # Researcher-supplied cohort files live under data/00_raw/ (DVC, gitignored) and hold identifiers. The runner
  # loads them at run time; an agent never reads one. Covers the Read tool and Grep and Glob (root and filter);
  # Bash is the scaffold child's hook.
  # The path cleanup reads one line at a time, so a newline inside a path could hide data/00_raw/. Fail closed.
  case "$abs$cwd" in *$'\n'*) decide deny "The path or working directory contains a newline, so the guard cannot rule out data/00_raw/. Use a path without a newline." ;; esac
  raw_lexical="$(printf '%s\n' "$abs" | normalize_path)"
  resolve_phys "$abs"; raw_physical="$RPHYS"
  cwd_lexical="$(printf '%s\n' "$cwd" | normalize_path)"
  cwd_physical="$cwd_lexical"; ! physdir "$cwd_lexical" || cwd_physical="$PHYS"
  # The governing projects: each directory, from the target and from the cwd up, that holds data/00_raw.
  projects=""
  for start in "$raw_lexical" "$raw_physical" "$cwd_lexical" "$cwd_physical"; do
    d="$start"
    while :; do
      if [ -e "$d/data/00_raw" ] || [ -L "$d/data/00_raw" ]; then
        case "$NL$projects" in *"$NL$d$NL"*) ;; *) projects="$projects$d$NL" ;; esac
      fi
      [ -n "$d" ] && [ "$d" != / ] || break
      d="${d%/*}"; [ -n "$d" ] || d=/
    done
  done
  raws=""  # RAW_LEX and RAW_PHYS of every project, one per line
  while IFS= read -r d; do
    [ -n "$d" ] || continue
    resolve_phys "${d%/}/data/00_raw"
    raws="$raws${d%/}/data/00_raw$NL$RPHYS$NL"
  done <<EOF
$projects
EOF
  in_raw=false
  while IFS= read -r r; do
    [ -n "$r" ] || continue
    if under "$raw_lexical" "$r" || under "$raw_physical" "$r"; then in_raw=true; fi
  done <<EOF
$raws
EOF
  # The textual rule covers a project the walk cannot see (a directory that does not exist yet). It is
  # case-insensitive, since a case-insensitive volume resolves data/00_RAW to the real directory.
  for candidate in "$raw_lexical" "$raw_physical"; do
    case "$candidate" in */[dD][aA][tT][aA]/00_[rR][aA][wW]|*/[dD][aA][tT][aA]/00_[rR][aA][wW]/*) in_raw=true ;; esac
  done
  if [ "$in_raw" = true ]; then
    # DVC pointers and ignore rules hold hashes and rules, not values, so a Read of a genuine one passes. The name
    # alone proves nothing: it must be a regular, non-symlink, small file whose content looks like what it
    # claims. Grep and Glob never pass by suffix.
    ok=false
    case "$(lc "$(basename "$raw_lexical")")" in
      *.dvc|.gitignore)
        if [ "$tool" = Read ] && [ -f "$raw_physical" ] && [ ! -L "$abs" ] && [ ! -L "$raw_lexical" ] &&
           [ "$(basename "$raw_lexical")" = "$(basename "$raw_physical")" ]; then
          size="$(wc -c < "$raw_physical" 2>/dev/null | tr -d ' ')"
          if [ -n "$size" ] && [ "$size" -le 65536 ]; then
            case "$raw_physical" in
              */.gitignore) ok=true ;;
              *) if grep -Eq '^outs:[[:space:]]*$' "$raw_physical" &&
                    grep -Eq '^[[:space:]-]*path:' "$raw_physical" &&
                    grep -Eq '^[[:space:]-]*(md5|hash|etag):' "$raw_physical" &&
                    ! grep -Evq '^([[:space:]]*(#.*)?|[A-Za-z_0-9]+:[[:space:]]*[^[:space:]]*|[[:space:]-]+[A-Za-z_0-9]+:[[:space:]]*[^[:space:]].*|[[:space:]]+[A-Za-z_0-9]+:[[:space:]]*)$' "$raw_physical"; then ok=true; fi ;;
            esac
          fi
        fi ;;
    esac
    [ "$ok" = true ] || decide deny "$raw_denied"
    exit 0
  fi
  if [ "$tool" = Grep ] || [ "$tool" = Glob ]; then
    # The root is above data/00_raw/: the project root, data/, a parent, or the directory above a symlinked
    # 00_raw's real files.
    while IFS= read -r r; do
      [ -n "$r" ] || continue
      if under "$r" "$raw_lexical" || under "$r" "$raw_physical"; then decide deny "$above_denied"; fi
    done <<EOF
$raws
EOF
    # A root further above a project that is not on the cwd chain would pass the checks above, so look beneath
    # the root, to a fixed depth that keeps the guard fast: 6 levels cover a project up to 4 directories below
    # the root. A root higher than that is not searched deeper, which is the stated limit. One walk lists every
    # data/00_raw entry of any type (a directory, a file, a link) and every symbolic link, and a link is
    # resolved. More than 200 links is refused, because the guard cannot resolve them all quickly.
    if [ -d "$raw_physical" ]; then
      links=0
      while IFS= read -r -d '' entry; do
        case "$entry" in */[dD][aA][tT][aA]/00_[rR][aA][wW]) decide deny "$above_denied" ;; esac
        links=$((links + 1))
        [ "$links" -le 200 ] || decide deny "A Grep or Glob root holds more than 200 symbolic links, so the guard cannot rule out a link into data/00_raw/. Pass a narrower path, such as skills/ or src/."
        resolve_phys "$entry"; target="$RPHYS"
        case "$target" in */[dD][aA][tT][aA]/00_[rR][aA][wW]|*/[dD][aA][tT][aA]/00_[rR][aA][wW]/*) decide deny "$above_denied" ;; esac
        if [ -d "$target" ]; then
          if [ -e "$target/data/00_raw" ] || [ -L "$target/data/00_raw" ]; then decide deny "$above_denied"; fi
          case "$target" in */[dD][aA][tT][aA]) if [ -e "$target/00_raw" ] || [ -L "$target/00_raw" ]; then decide deny "$above_denied"; fi ;; esac
        fi
        while IFS= read -r r; do
          [ -n "$r" ] || continue
          if under "$target" "$r" || under "$r" "$target"; then decide deny "$above_denied"; fi
        done <<EOF
$raws
EOF
      done < <(find "$raw_physical" -maxdepth 6 \( -name .git -o -name node_modules \) -prune -o \( \( -iname 00_raw -ipath '*/data/00_raw' \) -o -type l \) -print0 2>/dev/null)
    fi
  fi
  exit 0 ;;
esac
# Resolve existing parents before lexical cleanup: aliases can lead into .sqlreview,
# and symlink/.. must follow filesystem semantics. Keep absent suffixes for new files.
lexical_abs="$abs"
[ ! -L "$abs" ] || decide deny "SQL Review guard cannot validate a symlink file alias. Use the non-symlink destination path."
parent="$(dirname "$abs")"; suffix="$(basename "$abs")"
while [ ! -d "$parent" ] && [ "$parent" != / ]; do
  suffix="$(basename "$parent")/$suffix"
  parent="$(dirname "$parent")"
done
physdir "$parent" ||
  decide deny "SQL Review guard cannot resolve the destination's existing parent directory."
physical_parent="$PHYS"
abs="$physical_parent/$suffix"
# Collapse absent suffixes. Physical protection wins; retain lexical protection
# too when .sqlreview itself points outside the child.
abs="$(printf '%s\n' "$abs" | normalize_path)"
lexical_abs="$(printf '%s\n' "$lexical_abs" | normalize_path)"
case "$abs" in
  */.sqlreview/*) ;;
  *) case "$lexical_abs" in */.sqlreview/*) abs="$lexical_abs" ;; esac ;;
esac
# Resolve once for both ledger coverage and authoritative record validation.
here="$(cd "$(dirname "$0")" 2>/dev/null && pwd -P)"
checker=""
for c in "${CLAUDE_PLUGIN_ROOT:-/nonexistent}/skills/setup/scripts/sqlreview.sh" \
         "$here/../skills/setup/scripts/sqlreview.sh" \
         "$here/../skills/data-request-setup/scripts/sqlreview.sh"; do
  [ -f "$c" ] && { checker="$c"; break; }
done
# Experimental narrow direct-call detector. Default off, including schema-1 configs.
case "$abs" in
  *.py|*.sql)
    project="$(dirname "$abs")"
    while [ "$project" != / ] && [ ! -d "$project/.sqlreview" ]; do project="$(dirname "$project")"; done
    if command -v jq >/dev/null 2>&1 &&
       jq -e '.guard.require_lift_for_string_sql == true' "$project/.sqlreview/config.json" >/dev/null 2>&1; then
      if [ "$tool" = Write ]; then proposed="$(field .tool_input.content)"; else proposed="$(field .tool_input.new_string)"; fi
      if printf '%s\n' "$proposed" | grep -Ei '(execute|executemany|query|read_sql)[[:space:]]*\(' |
         grep -Ei '(select|with|insert|update|delete|merge)[[:space:]]' |
         grep -Eq "\\([[:space:]]*([fF][rR]?|[rR][fF])[\"']|[\"'][[:space:]]*\\+"; then
        [ -n "$checker" ] || decide deny "Lift guard cannot find sqlreview.sh; reinstall the data-request plugin."
        covered=false
        for ledger in "$project"/.sqlreview/reviews/*/lifts.json; do
          [ -f "$ledger" ] && [ ! -L "$ledger" ] || continue
          bash "$checker" check "$ledger" >/dev/null 2>&1 || continue
          if jq -e --arg slug "$(basename "$(dirname "$ledger")")" --arg p "${abs#"$project"/}" '.slug == $slug and any(.lifts[]; .workaround.file == $p and
            (.status == "candidate" or .status == "confirmed" or .status == "filed" or .status == "released" or .status == "recomposed"))' "$ledger" >/dev/null; then covered=true; break; fi
        done
        [ "$covered" = true ] || decide deny "Record a pinned-library lift candidate for ${abs#"$project"/} before string-built SQL. Publish the pipeline ledger with sqlreview.sh publish <slug> lifts <draft>."
      fi
    fi ;;
esac
case "$abs" in
  */.sqlreview/*) rel="${abs##*/.sqlreview/}" ;;
  *) exit 0 ;;
esac
# Some volumes ignore trailing blanks and dots, so review.json. and "review.json " name review.json there. Trim them
# from the whole name once, so every check below (the SQL and table files, and each authoritative document) sees the
# same name.
while :; do case "$rel" in *[" ."]) rel="${rel%?}" ;; *) break ;; esac; done

# The store holds JSON records, never SQL or tabular copies (#505). Fold case, then refuse a SQL or table file
# anywhere except under templates/.
rel_name="$(printf '%s' "${rel##*/}" | tr '[:upper:]' '[:lower:]')"
case "$rel_name" in
  *.sql|*.csv|*.tsv|*.parquet|*.xlsx|*.xls)
    case "$(printf '%s' "$rel" | tr '[:upper:]' '[:lower:]')" in
      templates/*) ;;
      reviews/*/source.sql|reviews/*/scope.source.sql|reviews/*/history/*.sql)
        decide deny "$rel is a legacy SQL snapshot path. Store hashes and committed source provenance in the review JSON; use sqlreview.sh materialize for temporary SQL outside the repository." ;;
      *) decide deny "$rel is a SQL or table file. The SQL Review store holds JSON records, hashes and commits only. Keep SQL in the request repository, use sqlreview.sh materialize for temporary SQL outside it, and never store extract output here." ;;
    esac ;;
esac
case "$rel" in
  ledger.json)
    decide deny "Triage ledger entries require validated atomic publication. Use sqlreview.sh ledger set <ticket> <entry.json>; direct Write/Edit of .sqlreview/ledger.json can corrupt other tickets." ;;
  config.json)
    decide ask "Editing .sqlreview/config.json directly bypasses the setup flow. Use /data-request:setup — on an initialised project it shows the per-file delta and applies only what the human confirms." ;;
  reviews/*/review.md|reviews/*/scope.md|reviews/*/lifts.md)
    decide deny "$rel is rendered markdown — never hand-write it. Update reviews/<slug>/$(basename "${rel%.md}").json (whole-file Write, so the guard can validate it) and re-render: S=\${CLAUDE_PLUGIN_ROOT}/skills/setup/scripts; bash \"\$S/sqlreview.sh\" render <slug> $(basename "${rel%.md}")" ;;
  reviews/*/questions.json)
    decide deny "Question stores require identity and closure-history checks. Write questions.draft.json, then run sqlreview.sh publish-questions <slug> <draft>." ;;
  reviews/*/lifts.json)
    decide deny "Lift ledgers require publication checks. Write lifts.draft.json, then run sqlreview.sh publish <slug> lifts <draft> to validate evidence revisions and lifecycle transitions." ;;
  reviews/*/review.json|reviews/*/scope.json)
    ;;  # validated below
  reviews/*/explain.json)
    # The walkthrough state marker is committed, so its analyst identity is checked (#419).
    [ "$tool" = "Write" ] || decide deny "$rel records who ran the walkthrough and is checked as a whole. Write the complete file instead of an Edit fragment."
    [ -n "$checker" ] || decide deny "SQL Review guard cannot find sqlreview.sh, so it cannot check $rel. Reinstall data-request@rdl-agent-extensions before writing it."
    command -v jq >/dev/null 2>&1 || decide deny "$rel is checked with jq, which is not installed. Install jq (>= 1.6) before writing it."
    out="$(field .tool_input.content | jq -r -L "$(dirname "$checker")" 'include "sqlreview-identity"; identity_violations' 2>/dev/null)" ||
      decide deny "$rel is not valid JSON, or the identity check could not read it. Write the complete explain.json as one JSON object."
    [ -z "$out" ] || decide deny "$rel rejected: $(printf '%s' "$out" | tr '\n' ';' | sed 's/;$//'). Record the analyst by GitHub login, else git config user.name; never user.email. If neither is available, ask."
    exit 0 ;;
  releases/*/release.md)
    decide deny "$rel is the rendered release body — never hand-write it. Update releases/<tag>/release.json (whole-file Write) and re-render it with release.sh render: S=\${CLAUDE_PLUGIN_ROOT}/skills/setup/scripts; bash \"\$S/release.sh\" render <record> > <body>" ;;
  releases/*/release.json)
    # The analyst's release record (#407): validated whole, like a review.
    [ "$tool" = "Write" ] || decide deny "$rel is the analyst's release record: it is validated as a whole. Write the complete file instead of an Edit fragment."
    [ -n "$checker" ] || decide deny "SQL Review guard cannot find sqlreview.sh, so it cannot find release.sh next to it. Reinstall data-request@rdl-agent-extensions before writing $rel."
    command -v jq >/dev/null 2>&1 || decide deny "Release records are validated with jq, which is not installed. Install jq (>= 1.6) before writing $rel."
    content="$(field .tool_input.content)"
    out="$(printf '%s' "$content" | bash "$(dirname "$checker")/release.sh" check --stdin 2>&1)" ||
      decide deny "$rel rejected by release.sh check: $(printf '%s' "$out" | tr '\n' ';' | sed 's/;$//'). Put each claim to the analyst via AskUserQuestion and record decided_by and decided_at only from an answered question; keep status draft while any claim is pending or any question is open."
    expected_tag="${rel#releases/}"; expected_tag="${expected_tag%/*}"
    printf '%s' "$content" | jq -e --arg t "$expected_tag" '.tag == $t' >/dev/null ||
      decide deny "The record's tag must match its directory: releases/$expected_tag/."
    exit 0 ;;
  amendments/*.json)
    # The amendment part-state record (#534) holds a release while a part is handed off, so it is
    # validated whole, like the other review documents. The reason names fields and rules only, and
    # never the path: the record name is not checked until release.sh amend-check checks it, with the
    # same rule that the release hold and status use (sr_amend_name_ok).
    [ "$tool" = "Write" ] || decide deny "An amendment part-state record (.sqlreview/amendments/<request>.json) is validated as a whole. Write the complete file instead of an Edit fragment."
    name="${rel#amendments/}"; name="${name%.json}"
    [ -n "$checker" ] || decide deny "SQL Review guard cannot find sqlreview.sh, so it cannot find release.sh next to it. Reinstall data-request@rdl-agent-extensions before writing an amendment record."
    command -v jq >/dev/null 2>&1 || decide deny "Amendment records are validated with jq, which is not installed. Install jq (>= 1.6) before writing an amendment record."
    out="$(field .tool_input.content | bash "$(dirname "$checker")/release.sh" amend-check --stdin --name "$name" 2>/dev/null)" ||
      decide deny "The amendment record (.sqlreview/amendments/<request>.json) was rejected by release.sh amend-check: $(printf '%s' "$out" | tr '\n' ';' | sed 's/;$//'). Write schemaVersion 1, kind amendment (when present) and parts with a unique id P<n> and a status done (with commit), handed off or withdrawn (with reason)."
    exit 0 ;;
  *) exit 0 ;;
esac

if [ "$tool" = "Edit" ]; then
  decide deny "$rel is an authoritative SQL Review document: it is validated as a whole (every assumption and limitation must carry a confirmation record). Write the complete file instead of an Edit fragment."
fi

[ -n "$checker" ] || decide deny "SQL Review guard cannot find sqlreview.sh (looked under \${CLAUDE_PLUGIN_ROOT}/skills/setup/scripts/ and next to this hook). The plugin install is incomplete — reinstall data-request@rdl-agent-extensions before writing $rel."
command -v jq >/dev/null 2>&1 || decide deny "SQL Review documents are validated with jq, which is not installed. Install jq (>= 1.6) before writing $rel."

content="$(field .tool_input.content)"
if printf '%s' "$content" | jq -e '.kind == "review" and any(.limitations[]; has("lift_id"))' >/dev/null 2>&1; then
  decide deny "Review limitations linked to lifts require ledger consistency checks. Write review.draft.json, then run sqlreview.sh publish <slug> review <draft>."
fi
if printf '%s' "$content" | jq -e 'any((.assumptions, .limitations | arrays | .[]); type == "object" and .carried_from_revision != null)' >/dev/null 2>&1; then
  decide deny "Carried confirmations (carried_from_revision) must be proven against the previous revision. Write $(basename "${rel%.json}").draft.json, then run sqlreview.sh publish <slug> $(basename "${rel%.json}") <draft>."
fi
out="$(printf '%s' "$content" | bash "$checker" check --stdin 2>&1)"; rc=$?
if [ "$rc" -eq 0 ]; then
  expected_slug="${rel#reviews/}"; expected_slug="${expected_slug%/*}"
  expected_kind="$(basename "${rel%.json}")"
  printf '%s' "$content" | jq -e --arg s "$expected_slug" --arg k "$expected_kind" '.slug == $s and .kind == $k' >/dev/null || decide deny "Document slug/kind must match its destination."
  exit 0
fi
decide deny "$rel rejected by sqlreview.sh check: $(printf '%s' "$out" | tr '\n' ';' | sed 's/;$//'). Every assumption and limitation must be put to the human via AskUserQuestion and written with status=confirmed, confirmed_by, confirmed_at and confirmed_revision equal to the document revision. Keep unconfirmed candidates in reviews/<slug>/$(basename "${rel%.json}").draft.json instead."
