# The one sanitiser for the text of violations. A violation names the field and the rule, and never a
# value. A string prints as itself only when it has the shape that the caller expects. Anything else
# prints as the fallback, so free text placed in an id or slug field never reaches the output.
# Run with `jq -L <this directory>`; sqlreview-check.jq, sqlreview-identity.jq and release.sh include it.
def safe($re; $fallback): if type == "string" and test($re) then . else $fallback end;
# A review item id (A1, L2, LIFT-3) or a lift id: a short token, never free text.
def id_re: "^[A-Za-z0-9][A-Za-z0-9._-]{0,63}\\z";
def safe_id($re): safe($re; "(invalid id)");
def safe_id: safe_id(id_re);
# A review slug, as sqlreview-slug.jq derives it from a path.
def safe_slug: safe("^[A-Za-z0-9_%.-]+\\z"; "(invalid slug)");
