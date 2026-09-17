#!/usr/bin/env bash
# Small file-format adapter; stdout is the generated SDD plan, sources stay intact.
set -euo pipefail
if [ "$#" -ne 5 ]; then
  echo 'usage: bridge.sh /absolute/tasks.md /absolute/plan.md /absolute/spec.md /absolute/constitution.md /absolute/approved-analysis.md' >&2
  exit 2
fi
for source in "$@"; do
  case "$source" in /*) ;; *) echo 'source paths must be absolute' >&2; exit 2 ;; esac
  [ -f "$source" ] || { echo "missing source: $source" >&2; exit 2; }
done
# Buffer until parsing succeeds so a failed conversion emits no partial plan.
staging=$(mktemp)
trap 'rm -f "$staging"' EXIT
awk '
function fail(message) { print message > "/dev/stderr"; failed=1; exit 2 }
FILENAME==ARGV[1] {
  sub(/\r$/, "")
  lines[++total]=$0
  fence=$0; sub(/^ ? ? ?/,"",fence)
  if (match(fence, /^(```+|~~~+)/)) {
    delimiter=substr(fence,1,1); width=RLENGTH
    suffix=substr(fence,width+1)
    if (!fenced) { fenced=delimiter; fencewidth=width }
    else if (delimiter==fenced && width>=fencewidth && suffix ~ /^[[:space:]]*$/) fenced=""
    next
  }
  if (fenced) next
  if ($0 ~ /^##+ /) phase=$0
  if ($0 ~ /^- \[[ xX]\] T[0-9]+([[:space:]]|$)/) {
    text=$0; sub(/^- \[[ xX]\] /,"",text)
    sub(/[[:space:]]+$/, "", text)
    id=text; sub(/[[:space:]].*$/, "", id)
    if (seen[id]++) fail("duplicate task ID: " id)
    description=text; sub(/^T[0-9]+[[:space:]]*/, "", description)
    while (sub(/^\[(P|US[0-9]+)\]([[:space:]]+|$)/, "", description)) {}
    if (description !~ /[^[:space:]]/) fail("task has no description: " id)
    start[++count]=total; ids[count]=id; phases[count]=phase
    done[count]=($0 ~ /^- \[[xX]\]/)
    titles[count]=text
  } else if ($0 ~ /^- \[[^]]*\] T/) fail("malformed task: " $0)
  next
}
{
  sub(/\r$/, "")
  for (source=2; source<=5; source++)
    if (FILENAME==ARGV[source]) context[source]=context[source] $0 "\n"
}
END {
  if (failed) exit 2
  if (!count) { print "no spec-kit tasks found" > "/dev/stderr"; exit 2 }
  for (source=2; source<=5; source++)
    if (context[source] !~ /[^[:space:]]/) {
      print "empty source context: " ARGV[source] > "/dev/stderr"; exit 2
    }
  print "# Generated spec-kit SDD plan\n"
  print "## Global Constraints\n"
  print "Source tasks: " ARGV[1] "\nSource plan: " ARGV[2]
  print "Source spec: " ARGV[3] "\nSource constitution: " ARGV[4] "\nSource approved analysis: " ARGV[5] "\n"
  print "Preserve source task IDs and order. Completed tasks are verification-only; do not implement them again."
  print "[P] permits concurrency only after dependencies are satisfied. Story tags do not remove phase dependencies."
  print "Report completion against the original T IDs in tasks.md after tests pass.\n"
  print "Every task worker must read all Global Constraints, including the spec acceptance criteria, constitution and approved analysis below, before implementation and verification.\n"
  # Indent source documents to prevent their headings becoming SDD task boundaries.
  labels[2]="plan"; labels[3]="spec"; labels[4]="constitution"; labels[5]="approved analysis"
  for (source=2; source<=5; source++) {
    print "### Source " labels[source] " (verbatim)\n"
    n=split(context[source],p,"\n"); for (i=1;i<=n;i++) print "    " p[i]
  }
  print "\n### Source task context (verbatim)\n"
  for (i=1;i<=total;i++) print "    " lines[i]
  for (t=1;t<=count;t++) {
    print "\n## Task " t ": " titles[t] "\n"
    print "Source ID: " ids[t] "\nPhase: " phases[t]
    print "Status: " (done[t] ? "complete — verify only" : "pending") "\n"
    print "Use the Global Constraints and source plan above; retain all source acceptance and testing requirements.\n"
    end=(t<count ? start[t+1]-1 : total)
    for (i=start[t];i<=end;i++) print "    " lines[i]
  }
}' "$@" > "$staging"
cat "$staging"
