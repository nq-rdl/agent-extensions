#!/usr/bin/env bash
# Fetch Red Hat documentation / Customer Portal content by the route that works.
#
#   rh-fetch.sh [-o FILE] [--includes] [--kind KIND] [--rows N] <target>
#
# targets
#   https://docs.redhat.com/<lang>/documentation/<product>/<ver>/html/<book>/<page>[#anchor]
#   https://docs.redhat.com/<lang>/documentation/<product>/<ver>/html-single/<book>/index#anchor
#        → the product's open-source doc repo on GitHub (docs.redhat.com itself returns
#          Akamai 403 to every non-browser client). AsciiDoc source to stdout.
#   https://access.redhat.com/solutions/<id> | /articles/<id> | kcs:<id>
#        → Customer Portal KCS body via the search API (fq=id:), Bearer-authenticated
#          through rh-token.sh. Markdown to stdout. Subscriber-only placeholders = exit 3.
#   search:<terms>           → KCS search (no credential needed for metadata)
#   docs-text:<docs URL>     → EXPERIMENTAL: the KCS index's stored text for a docs.redhat.com
#                              page (Bearer-authenticated). The only route for closed-source
#                              products such as RHEL if the index exposes text to your account.
#
# exit: 0 ok · 1 usage · 2 network/HTTP · 3 not authenticated / not entitled · 4 unresolvable
set -u
here="$(cd "$(dirname "$0")" && pwd)"
# shellcheck source=rh-lib.sh
. "$here/rh-lib.sh"

out=""; includes=0; kind=""; rows="${RH_ROWS:-10}"; target=""
while [ $# -gt 0 ]; do
  case "$1" in
    -o) out="$2"; shift 2 ;;
    --includes) includes=1; shift ;;
    --kind) kind="$2"; shift 2 ;;
    --rows) rows="$2"; shift 2 ;;
    -h|--help) sed -n '2,22p' "$0"; exit 0 ;;
    -*) echo "unknown option: $1" >&2; exit 1 ;;
    *) target="$1"; shift ;;
  esac
done
[ -n "$target" ] || { sed -n '2,22p' "$0" >&2; exit 1; }
command -v jq >/dev/null 2>&1 || { echo "jq is required (brew install jq / dnf install jq / apt install jq)" >&2; exit 1; }
[ "$(rh_fetcher)" != none ] || { echo "neither curl nor wget found — install curl" >&2; exit 1; }

emit() { if [ -n "$out" ]; then cat > "$out"; echo "wrote $out" >&2; else cat; fi; }
urlenc() { jq -rn --arg s "$1" '$s|@uri'; }
tmpf() { local f; f="$(mktemp "${TMPDIR:-/tmp}/rh-fetch.XXXXXX")"; chmod 600 "$f"; printf '%s\n' "$f"; }

# ---------- GitHub source-repo route ----------
tree_paths() { # <repo> <ref> → path list (cached 24h)
  local repo="$1" ref="$2" cache f age
  cache="$(rh_cache_dir)/tree-$(printf '%s' "$repo" | tr '/' '_')-$ref.txt"
  if [ -s "$cache" ]; then
    age=$(( $(date +%s) - $(date -r "$cache" +%s 2>/dev/null || stat -c %Y "$cache" 2>/dev/null || echo 0) ))
    [ "$age" -lt 86400 ] && { cat "$cache"; return 0; }
  fi
  f="$(tmpf)"
  if command -v gh >/dev/null 2>&1 && gh auth status >/dev/null 2>&1; then
    gh api "repos/$repo/git/trees/$ref?recursive=1" --jq '.tree[].path' > "$f" 2>/dev/null
  else
    local code; code="$(rh_http_get "https://api.github.com/repos/$repo/git/trees/$ref?recursive=1" "$f")"
    [ "$code" = "200" ] || { echo "GitHub tree for $repo@$ref: HTTP $code (unauthenticated api.github.com is rate-limited to 60/h — install and log in to gh)" >&2; rm -f "$f"; return 2; }
    jq -r '.tree[].path' "$f" > "$f.paths" && mv "$f.paths" "$f"
  fi
  [ -s "$f" ] || { echo "empty tree for $repo@$ref — does the branch exist?" >&2; rm -f "$f"; return 4; }
  mv "$f" "$cache"; cat "$cache"
}
raw_get() { # <repo> <ref> <path> <outfile>
  local code; code="$(rh_http_get "https://raw.githubusercontent.com/$1/$2/$3" "$4")"
  [ "$code" = "200" ] || { echo "raw fetch $1@$2:$3 → HTTP $code" >&2; return 2; }
}
find_in_tree() { # <treefile> <slug> [prefer-prefix]
  local hits; hits="$(grep -E "(^|/)$2\.adoc\$" "$1" || true)"
  [ -n "$hits" ] || return 1
  if [ -n "${3:-}" ] && printf '%s\n' "$hits" | grep -q "^$3"; then hits="$(printf '%s\n' "$hits" | grep "^$3")"; fi
  printf '%s\n' "$hits" | head -1
}

route_docs() { # <url>
  local url="$1" rest product ver form book page anchor repo ref base tree path modpath f inc rel cand
  anchor="${url#*#}"; [ "$anchor" = "$url" ] && anchor=""
  rest="${url%%#*}"; rest="${rest#https://docs.redhat.com/}"; rest="${rest#*/documentation/}"
  product="${rest%%/*}"; rest="${rest#*/}"
  ver="${rest%%/*}"; rest="${rest#*/}"
  form="${rest%%/*}"; rest="${rest#*/}"
  book="${rest%%/*}"; page="${rest#*/}"; page="${page%%/*}"; page="${page%%\?*}"
  case "$product" in
    red_hat_ansible_automation_platform) repo=ansible/aap-docs; ref="$ver"; base=downstream/modules ;;
    openshift_container_platform)        repo=openshift/openshift-docs; ref="enterprise-$ver"; base="" ;;
    *)
      cat >&2 <<MSG
No known public source repo for product '$product' (docs.redhat.com itself blocks non-browser fetches).
Known: red_hat_ansible_automation_platform → ansible/aap-docs · openshift_container_platform → openshift/openshift-docs
Satellite docs build from theforeman/foreman-documentation (guides/doc-<Title>/, BUILD=satellite) — search it with gh.
RHEL and other closed products: try  rh-fetch.sh 'docs-text:$url'  (needs your offline token) or read the page in a browser.
MSG
      return 4 ;;
  esac
  case "$form" in
    html) slug="$page" ;;
    html-single) [ -n "$anchor" ] || { echo "html-single URLs need a #anchor (or use the multi-page /html/ URL)" >&2; return 4; }; slug="$anchor" ;;
    *) echo "unrecognised docs.redhat.com URL form '$form' — expected /html/<book>/<page> or /html-single/<book>/index#anchor; try docs-text:$url" >&2; return 4 ;;
  esac
  tree="$(tmpf)"; tree_paths "$repo" "$ref" > "$tree" || return $?
  path="$(find_in_tree "$tree" "$slug" "${base%%/*}")" || { echo "no '$slug.adoc' in $repo@$ref — the page slug is not a file name here; try: gh api -X GET search/code -f q='\"[id=\\\"$slug\\\"]\" repo:$repo'" >&2; rm -f "$tree"; return 4; }
  modpath=""
  if [ -n "$anchor" ] && [ "$anchor" != "$slug" ]; then modpath="$(find_in_tree "$tree" "$anchor" "${base%%/*}" || true)"; fi
  f="$(tmpf)"
  {
    echo "// source: https://github.com/$repo/blob/$ref/$path"
    [ -n "$modpath" ] && echo "// anchor '$anchor' → https://github.com/$repo/blob/$ref/$modpath (module printed first)"
    [ -n "$anchor" ] && [ -z "$modpath" ] && echo "// anchor '$anchor' is inside this assembly or one of its includes (use --includes)"
    echo "// docs: $url"; echo "// fetched: $(date -u +%Y-%m-%dT%H:%M:%SZ) by rh-fetch.sh"; echo
    if [ -n "$modpath" ]; then raw_get "$repo" "$ref" "$modpath" "$f" || exit 2; cat "$f"; echo; echo "// ---- containing assembly: $path ----"; fi
    raw_get "$repo" "$ref" "$path" "$f" || exit 2; cat "$f"
    if [ "$includes" = 1 ]; then
      grep -E '^include::[^[]+\[' "$f" | sed 's/^include::\([^[]*\)\[.*/\1/' | while read -r inc; do
        rel="$inc"; cand=""
        for c in "$rel" "$(dirname "$path")/$rel" "${base:+$base/}$rel"; do
          if grep -qxF "$c" "$tree"; then cand="$c"; break; fi
        done
        [ -n "$cand" ] || cand="$(find_in_tree "$tree" "$(basename "$rel" .adoc)" || true)"
        echo; echo "// ---- include: ${cand:-$rel (NOT FOUND in tree)} ----"
        [ -n "$cand" ] && { raw_get "$repo" "$ref" "$cand" "$f.inc" && cat "$f.inc"; }
      done
      rm -f "$f.inc"
    fi
  } | emit
  rm -f "$f" "$tree"
}

# ---------- Customer Portal routes ----------
subscriber_only_fields() { jq -r '[.response.docs[0] | to_entries[] | select(.value == "subscriber_only") | .key] | join(", ")' "$1"; }

route_kcs_id() { # <id>
  local id="$1" cfg f code n so
  cfg="$("$here/rh-token.sh" --curl-config)" || exit $?
  f="$(tmpf)"
  code="$(rh_http_get "$RH_KCS_API?q=*&fq=id:$id&fl=id,documentKind,publishedTitle,view_uri,lastModifiedDate,solution_environment,issue,solution_resolution,solution_rootcause,solution_diagnosticsteps,body,abstract" "$f" "$cfg")"
  [ "$code" = "200" ] || { echo "KCS API: HTTP $code" >&2; rm -f "$f"; exit 2; }
  n="$(jq -r '.response.numFound // 0' "$f")"; [ "$n" -gt 0 ] || { echo "no KCS document with id $id" >&2; rm -f "$f"; exit 4; }
  so="$(subscriber_only_fields "$f")"
  if [ -n "$so" ]; then
    echo "KCS $id returned subscriber_only for: $so. The API answers 200 even when the Bearer token is ignored, so this means your token was not accepted or your account is not entitled. Run: rh-token.sh --check   (then /redhat:setup if it fails)" >&2; rm -f "$f"; exit 3
  fi
  jq -r '
    def s: if type=="array" then join("\n") elif .==null then "" else tostring end;
    .response.docs[0] as $d |
    "# \($d.publishedTitle|s)\n\nSource: \($d.view_uri|s) (KCS \($d.id|s), \($d.documentKind|s), modified \($d.lastModifiedDate|s))\n" +
    ([ ["Environment", ($d.solution_environment|s)], ["Issue", ($d.issue|s)], ["Resolution", ($d.solution_resolution|s)],
       ["Root Cause", ($d.solution_rootcause|s)], ["Diagnostic Steps", ($d.solution_diagnosticsteps|s)], ["Body", ($d.body|s)] ]
      | map(select(.[1] != "")) | map("\n## \(.[0])\n\n\(.[1])\n") | join(""))' "$f" | emit
  rm -f "$f"
}

route_search() { # <terms>
  local f code url; f="$(tmpf)"
  url="$RH_KCS_API?q=$(urlenc "$1")&rows=$rows&fl=id,documentKind,publishedTitle,view_uri"
  [ -n "$kind" ] && url="$url&fq=documentKind:$kind"
  code="$(rh_http_get "$url" "$f")"; [ "$code" = "200" ] || { echo "KCS search: HTTP $code" >&2; rm -f "$f"; exit 2; }
  jq -r '"numFound: \(.response.numFound)", (.response.docs[] | "\(.id)\t\(.documentKind)\t\(.publishedTitle // "-")\t\(.view_uri // "-")")' "$f" | emit
  rm -f "$f"
}

route_docs_text() { # <docs url>
  local url="$1" cfg f code n
  cfg="$("$here/rh-token.sh" --curl-config)" || exit $?
  f="$(tmpf)"
  code="$(rh_http_get "$RH_KCS_API?q=*&fq=id:$(urlenc "\"$url\"")&fl=publishedTitle,view_uri,docs_text_store,large_text_store" "$f" "$cfg")"
  [ "$code" = "200" ] || { echo "KCS API: HTTP $code" >&2; rm -f "$f"; exit 2; }
  n="$(jq -r '.response.numFound // 0' "$f")"; [ "$n" -gt 0 ] || { echo "that URL is not in the KCS Documentation index" >&2; rm -f "$f"; exit 4; }
  if [ "$(jq -r '.response.docs[0] | ((.docs_text_store // "")|tostring|length) + ((.large_text_store // "")|tostring|length)' "$f")" = "0" ]; then
    echo "Documentation text fields came back empty (experimental route — the index may not expose page text to your account). Use the source-repo route or a browser." >&2; rm -f "$f"; exit 3
  fi
  jq -r '.response.docs[0] | "# \(.publishedTitle // "")\n\nSource: \(.view_uri // "")\n\n" + ((.docs_text_store // .large_text_store) | if type=="array" then join("\n") else tostring end)' "$f" | emit
  rm -f "$f"
}

case "$target" in
  search:*)    route_search "${target#search:}" ;;
  kcs:*)       route_kcs_id "${target#kcs:}" ;;
  docs-text:*) route_docs_text "${target#docs-text:}" ;;
  https://docs.redhat.com/*)   route_docs "$target" ;;
  https://access.redhat.com/*)
    id="$(printf '%s' "$target" | sed -n 's#.*/\(solutions\|articles\)/\([0-9]\{1,\}\).*#\2#p')"
    [ -n "$id" ] || { echo "cannot find a solution/article id in $target" >&2; exit 4; }
    route_kcs_id "$id" ;;
  *) echo "unsupported target: $target" >&2; sed -n '2,22p' "$0" >&2; exit 1 ;;
esac
