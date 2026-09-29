#!/usr/bin/env bash
# check-alt.sh — check alt text in rendered Quarto HTML.
#
# usage: check-alt.sh FILE.html [FILE.html ...]
#
# Render first (quarto render doc.qmd --to html), then pass the HTML files.
# Checks the markup Quarto actually emits, not the .qmd source:
#   - every <img> with class figure-img (code-cell plots, Markdown figures,
#     subfigures, labelled or not) has a non-empty alt attribute. Quarto omits
#     alt when fig-alt is missing; it does not fall back to the caption.
#   - no raw "{#fig-... fig-alt=" text reached the page. This is what a
#     multi-line "#| fig-alt: |" block produces under the Jupyter engine
#     (checked with Quarto 1.9.38 and 1.10.18): the caption lands in alt, the
#     attribute text in the page, and the figure loses its id.
#   - no unresolved cross-reference ("?@fig-...") is left in the page.
# Images outside figures (logos, inline icons) are not checked.
#
# Exit status: 0 all good, 1 problems found, 2 usage or unreadable file.
# Bash 3.2 compatible; needs grep, sed, tr.

if [ "$#" -eq 0 ]; then
  echo "usage: check-alt.sh FILE.html [FILE.html ...]" >&2
  exit 2
fi

status=0
for f in "$@"; do
  if [ ! -r "$f" ]; then
    echo "check-alt: cannot read $f" >&2
    status=2
    continue
  fi
  html="$(tr '\r\n' '  ' < "$f")"
  count=0
  problems=0
  tags="$(printf '%s' "$html" | grep -o '<img[^>]*>' | grep 'figure-img')"
  while IFS= read -r tag; do
    [ -n "$tag" ] || continue
    count=$((count + 1))
    if ! printf '%s' "$tag" | grep -q '[[:space:]]alt="[^"]*[^"[:space:]][^"]*"'; then
      src="$(printf '%s' "$tag" | sed -n 's/.*[[:space:]]src="\([^"]*\)".*/\1/p')"
      echo "$f: missing or empty alt: ${src:-<img without src>}"
      problems=$((problems + 1))
    fi
  done <<EOF
$tags
EOF
  leak="$(printf '%s' "$html" | grep -o '{#fig-[^}]*fig-alt=' | head -n 1)"
  if [ -n "$leak" ]; then
    echo "$f: raw attribute text in the page: $leak (multi-line fig-alt under the Jupyter engine? use a one-line quoted string)"
    problems=$((problems + 1))
  fi
  unresolved="$(printf '%s' "$html" | grep -o '?@fig-[A-Za-z0-9_-]*' | sort -u | tr '\n' ' ')"
  if [ -n "$unresolved" ]; then
    echo "$f: unresolved cross-references: $unresolved"
    problems=$((problems + 1))
  fi
  echo "$f: $count figure images checked, $problems problem(s)"
  if [ "$problems" -gt 0 ] && [ "$status" -eq 0 ]; then
    status=1
  fi
done
exit "$status"
