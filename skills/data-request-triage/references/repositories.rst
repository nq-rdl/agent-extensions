Repository and scaffold state
=============================

Read this when you resolve a request to its child repository, and before you
declare scaffold, scope or branch work missing. Observed on the September 2026
triage of ENQ1187, ENQ1196 and ENQ1213; re-check the organisation's layout
before relying on it.

Enquiry, issue and approval
---------------------------

* Requests are issues in ``rdl-service-desk/service-desk``. The enquiry number
  (``ENQ1196`` or ``THHSRDLENQ-1196``) appears in the title or body. The GitHub
  issue number (``#58``) is unrelated to it. Search titles and bodies, including
  closed issues, for the digits.
* Child repositories are named by approval ID (``THHSAQUIRE-2107``,
  ``SSAQHTS-43408``), not by enquiry number. A link to
  ``rdl-service-desk/THHSRDLENQ-1196`` is stale or invented: report it.
* Take the approval ID from the issue body, comments and amendments. Then
  confirm that the repository exists and that its README, ``.copier-answers.yml``
  or ``answers.yaml`` names the same enquiry. Similar names are not evidence.
* Approval IDs drift in formatting (``THHSAQUIRE2107`` versus
  ``THHSAQUIRE-2107``). Normalise to the hyphenated form for lookup, and keep the
  original spelling in the ledger, the scope and the comment.
* When two approval IDs compete, or a repository names another enquiry, report
  the conflict with both sources and do not choose one.

Scaffold states
---------------

Read ``.copier-answers.yml`` and ``answers.yaml`` on ``main`` and on every open
branch. Three states have been seen:

Legacy shell
   ``_src_path`` points at ``rdl-service-desk/data-science-template``, and the
   ``cohort/``, ``conf/``, ``specs/`` and ``sql/`` directories are absent. The
   current scaffold is unapplied.

Seed-rendered child
   The current template rendered the repository, but ``answers.yaml`` holds empty
   or seed placeholder values. The scaffold is unapplied to this request, even
   though the layout exists.

Current render
   Request answers are filled in. Compare the recorded template commit with the
   template's current release: an older one means the scaffold is outdated, not
   unapplied. Outdated children can lack later fixes, such as a dependency cap
   that the pixi solve needs.

Unapplied and outdated are separate blockers with separate next actions. In both
cases agents never run ``copier update``; report the state and propose the step.

Before you propose a manual port of the current layout, look for an open
bootstrap or scaffold PR. On THHSAQUIRE-2090, PR 2 applied the scaffold while a
later triage PR 6 was cut from the legacy ``main`` and competed with it. Reuse a
sound existing branch, and name the ones to leave alone.

The legacy ``.github/workflows/copier-runner.yml`` workflow triggers on a push to
``main``. Flag it in the triage comment as a merge hazard before anyone merges,
and read what it runs instead of guessing.

Branches, owners and pins
-------------------------

* List open PRs and branches with their last committer and date. A branch with
  no PR (``enq/1196`` was one) can be someone's work in progress. Name its owner
  and ask; never reuse, rebase or delete it unasked.
* Read the child's ``GOVERNANCE.md`` for who reviews and how changes reach
  ``main``.
* Read ``framework_ref`` and the lock file to learn which library revision the
  child uses. A unit in a later release is unavailable to the child until it is
  re-pinned.
* ``query-builder-plugins`` has been consolidated into ``query-builder``. Older
  pins, gap registers and design documents name both, so check where a unit
  lives now before calling it missing.
