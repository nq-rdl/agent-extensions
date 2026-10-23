Library issue evidence block
============================

Use these headings in every newly filed issue. Keep one reusable change per issue;
link related candidates rather than expanding a resolver fix into core redesign.
Do not include patient rows, identifiers or credentials.

Public by default
-----------------

Treat every library issue, comment, title, label and linked example as public, whatever the
repository's current visibility. Do not assume a destination is private because it is a library
issue; visibility can change and an issue is copied, quoted and indexed. An enquiry or approval
number, and a link to a request repository, is request provenance. House convention keeps it
out of public library text, even though it is not patient data.

A public issue describes the reusable need. It never contains:

* an enquiry number, an approval number or any form derived from one (``ENQ…``, a number in
  a file name, a bare number) in a title, body, comment, label, branch name or commit message;
* a link to a request repository, a request-repository file, commit, issue or hand-off comment,
  or to the service desk;
* a request-specific file reference: a request pipeline or SQL path (``sql/v<N>/…``,
  ``…_request.sql``), ``answers.yaml``, ``cohort/request.json``, ``.sqlreview/…`` or ``data/…``;
* a ledger id, a request source revision, a confirmation or the name of the person who
  confirmed it;
* the researcher's study, project or cohort name, or a count small enough to identify a person.

Links to the owning library at a released tag or commit, and to the public ``nq-rdl``
repositories that hold the library and these skills, are fine.

Evidence block
--------------

* **Library baseline** — owning library, and the library release or tag the pipeline pins
  (the ``framework_ref`` or lock version checked). Name the version, not the repository that
  pins it.
* **Need and classification** — required composition and new-capability or
  existing-unit-gap, including output grain. State the classification as the engineer's
  proposal; the confirmed classification lives in the private record.
* **Pinned capability inspected** — unit, module/resolver and test paths in the library at the
  pinned revision; describe the search when no matching unit exists.
* **Shortfall** — observable missing behaviour; distinguish absence from a
  composition error or researcher choice.
* **Delivered workaround** — what is hand-built, in generic terms, and a minimal
  anonymous reproduction (below) in place of the request's file, lines and revision.
* **Canonical SQL / expected contract** — minimal canonical SQL with join, validity,
  cardinality and output expectations, written against synthetic table and column names
  or the library's own. For a
  non-SQL capability include the expected metadata/API contract as well; never
  invent SQL for an introspection feature. Unavailable canonical evidence blocks
  filing until resolved.
* **Proposed fix and tests** — core or source resolver (``resolvers/iemr``,
  ``resolvers/hbcis``), bounded implementation scope, regressions proving
  equivalence with the canonical contract, and exclusions.
* **Rollout** — delivered under the old pin; additive/forward release, no enquiry
  backport. Explicitly recurring extracts may later bump the pin and re-compose.

The anonymous reproduction
--------------------------

Anonymising removes provenance; it must leave an issue someone can act on. Rebuild the
shortfall on synthetic inputs: invented table and column names or the library's own, a few
invented rows, the expected output, and the actual output or the missing behaviour. A reader who
has never seen the request should be able to run it. Do not rename the request's real columns
or codes into a reproduction that still identifies the request, and do not copy its criteria,
code lists or outputs.

Anonymity is not a decision. Rewriting the evidence does not confirm a classification,
settle a research or clinical choice, or turn an engineer's proposal into an agreed
requirement. Do not state an assumption or limitation as confirmed in public text.

Private traceability
--------------------

Keep these in the private request record (the ledger under ``.sqlreview/``, the review and
the engineer's hand-off), never in the public issue:

* the enquiry and approval numbers, the pipeline path and revision, and the ledger id;
* the exact request source revisions and the workaround's file and lines;
* the human confirmations and who gave them;
* the mapping from the private entry to the public work: record the returned issue or
  comment URL on the ledger entry (``filed``) and in the hand-off.

The private side points to the public work; the public side never points back.

Before filing or commenting
---------------------------

1. Write the draft to a local file. Read its title, body, every URL and every file reference
   against **Public by default** above, as a person would read it cold.
2. Remove or generalise each hit. A hit in a quoted snippet, a stack trace, a link
   text or a code comment counts. Do not rely on a match tool to be complete.
3. Show the draft to the human with the confirmation above. Then file it.
4. Search the library's open and closed issues for the reusable need by its wording, not by an
   identifier, before you create anything. After an uncertain response, search the same way
   and compare your own earlier text before retrying, so a retry does not duplicate.
