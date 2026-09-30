Repository and scaffold state
=============================

Read this when you resolve a request to its child repository, and before you
declare scaffold, scope or branch work missing. Observed on September 2026
multi-enquiry triages; the identifiers below are fictional examples. Re-check
the organisation's layout before relying on it.

Read-only access
----------------

Triage reads with ``gh ... view``, ``gh ... list``, ``gh api`` GET requests and
``git`` in a scratch clone. When the ``gh`` CLI is not installed, use the GitHub
MCP read tools for the same queries. Tool names observed in September 2026 (the
host can add a prefix, such as ``mcp__github__``; check its tool list):

* ``get_me`` in place of ``gh auth status``;
* ``search_issues``, ``list_issues`` and ``issue_read`` for requests, comments
  and child issues;
* ``search_repositories`` and ``get_file_contents`` (with ``ref`` set to a
  branch, tag or commit) for repositories and files;
* ``list_branches``, ``list_commits``, ``list_pull_requests`` and
  ``pull_request_read`` for branches, PRs and their checks.

Use only the read tools. The same server also offers write tools (issue and PR
comments, issue and PR edits, project items); these follow the same rules as
``gh`` writes. Report the substitution in the environment probe. The MCP tools
cannot run the pixi solve or local hooks: name those as capabilities the session
lacks.

Enquiry, issue and approval
---------------------------

* Requests are issues in ``rdl-service-desk/service-desk``. The enquiry number
  (``ENQ9003`` or ``THHSRDLENQ-9003``) appears in the title or body. The GitHub
  issue number (``#903``) is unrelated to it. Search titles and bodies, including
  closed issues, for the digits.
* Child repositories are named by approval ID (``THHSAQUIRE-9903``,
  ``SSAQHTS-99001``), not by enquiry number. A link such as
  ``rdl-service-desk/THHSRDLENQ-9003`` can still work: GitHub redirects a renamed
  repository to its new name. Follow the link before you judge it, for example
  ``gh api repos/rdl-service-desk/THHSRDLENQ-9003 --jq .full_name``, and compare
  the resolved ``full_name`` with the approval ID. A match is a rename redirect:
  use the resolved name and report the old link as a redirect. Only a link that
  does not resolve, or resolves to another approval ID, is stale or invented.
  Without ``gh``, ``search_repositories`` does not follow renames: read a file
  through the old owner and name with ``get_file_contents`` (the API follows the
  redirect) and check that it names the approval ID. When you cannot confirm the
  redirect, report the link as unverified, not as a redirect or as stale.
* Take the approval ID from the issue body, comments and amendments. Then
  confirm that the repository exists and that its README, ``.copier-answers.yml``
  or ``answers.yaml`` names the same enquiry. Similar names are not evidence.
* Approval IDs drift in formatting: a missing hyphen (``THHSAQUIRE9903`` versus
  ``THHSAQUIRE-9903``) or trailing punctuation (``THHSAQUIRE-9903-``). Normalise
  to the hyphenated form for lookup, and keep the original spelling in the
  ledger, the scope and the comment.
* A repository can be renamed during the task, for example to drop a trailing
  dash. Re-resolve it through the API before each write, and use the name that
  the API returns.
* When two approval IDs compete, or a repository names another enquiry, report
  the conflict with both sources and do not choose one.

Scaffold states
---------------

Read ``.copier-answers.yml`` and ``answers.yaml`` on ``main`` and on every open
branch. Before you decide a state, parse ``answers.yaml`` with
``yaml.safe_load`` (PyYAML), for example
``git show origin/main:answers.yaml | python3 -c 'import sys, yaml; yaml.safe_load(sys.stdin)'``.
When it does not parse, report the line and column from the error and treat the
answers as unfilled; do not guess values from the broken file. These states have
been seen:

Legacy shell
   ``_src_path`` points at ``rdl-service-desk/data-science-template``, and the
   ``cohort/``, ``conf/``, ``specs/`` and ``sql/`` directories are absent. The
   current scaffold is unapplied.

Legacy-template seed
   ``_src_path`` still points at ``data-science-template`` (a ``v0.1.3`` seed
   render, often with ``seed_mode``), but ``cohort/``, ``conf/``, ``specs/`` and
   ``sql/`` are present, and ``answers.yaml`` is unfilled, partly filled or does
   not parse. The current scaffold is unapplied. ``copier update`` cannot move a
   repository to another template, so the next action is a fresh render (below).

Legacy shell with an outdated bootstrap PR
   ``main`` is a legacy shell or seed with placeholder answers, and an open PR
   carries request-filled answers on an older scaffold. The scaffold is both
   unapplied on ``main`` and outdated on the PR. Name the PR and its owner, and
   propose a fresh render that takes the PR's request answers as input. Do not
   propose merging the PR as it is, and leave it alone until its owner decides.

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

A legacy shell or seed can have no ``pyproject.toml``. The environment probe then
skips the pixi solve and records why; that is not a solve failure.

Fresh render
   The step that moves a legacy-template repository onto the current scaffold.
   Propose it in triage; run it only in co-development, on an agreed branch.
   Render the current scaffold tag from its canonical URL into a scratch
   directory: ``copier copy --vcs-ref <tag> --defaults --trust --data-file
   answers.yaml gh:nq-rdl/data-analysis-scaffold <scratch>`` (copier 9.18.2 in
   September 2026), with an ``answers.yaml`` that parses and uses the scaffold's
   layout. ``--trust`` runs the template's tasks: use it only with the canonical
   ``gh:nq-rdl/data-analysis-scaffold`` at a pinned release tag. Keep the
   request's values byte-identical. Take the template's generic tree onto the
   branch and carry only request-specific files and workflows. Drop only files
   that the template replaces or that the new scaffold's checks reject, and list
   each one in the PR body. One render dropped ``template-sync.yml`` and
   ``scripts/template_sync.py``, ``release.yaml`` and its test,
   ``.seed-manifest.yml``, ``src/service_desk/``, and the ``data/`` README and
   ``DO NOT RELEASE`` files. Re-lock pixi in a separate commit. Record the
   scaffold tag and ``framework_ref`` in the PR body.

Before you propose a manual port of the current layout, look for an open
bootstrap or scaffold PR. In one child, a scaffold PR applied the scaffold while
a later triage PR was cut from the legacy ``main`` and competed with it. Reuse a
sound existing branch, and name the ones to leave alone.

The legacy ``.github/workflows/copier-runner.yml`` workflow triggers on a push to
``main``. Flag it in the triage comment as a merge hazard before anyone merges,
and read what it runs instead of guessing.

Branches, owners and pins
-------------------------

* For a new request branch, use ``enq/<enquiry number>`` with the enquiry's
  digits: ``ENQ9003`` becomes ``enq/9003``, not the service-desk issue number
  ``#903``. For a later version, add a suffix such as ``enq/9003-v2``.
  Reuse a sound existing branch only with its owner's agreement; this naming
  rule is not a reason to replace it. Keep existing ``triage/<n>`` branch names,
  and never rename a branch someone else owns.
* List open PRs and branches with their last committer and date. A branch with
  no PR (such as ``enq/9003``) can be someone's work in progress. Name its owner
  and ask; never reuse, rebase or delete it unasked.
* Read another child's branch without checking it out: ``git show
  <ref>:<path>``, ``git ls-tree -r --name-only <ref> -- <dir>``, or a fetch into
  a scratch clone (``git clone --no-checkout``). Never run ``git checkout``,
  ``git switch`` or ``git worktree add`` in a repository the session did not ask
  to change. Each fires that repository's ``post-checkout`` hook: in one child, a
  DVC hook failed on a missing cache.
* A PR has merged when ``merged_at`` is set, or when its merge commit is an
  ancestor of the base branch (``git merge-base --is-ancestor <sha>
  origin/main``). Do not trust the ``merged`` flag alone: a listing returned
  ``merged: false`` with a ``merged_at`` date for a PR that had merged. A
  ``merge_commit_sha`` alone is not evidence: GitHub also sets it, as a test
  merge, on open PRs and on PRs closed without merging.
* Read the child's ``GOVERNANCE.md`` for who reviews and how changes reach
  ``main``.
* Read ``framework_ref`` and the lock file to learn which library revision the
  child uses. A unit in a later release is unavailable to the child until it is
  re-pinned.
* ``query-builder-plugins`` has been consolidated into ``query-builder``. Older
  pins, gap registers and design documents name both, so check where a unit
  lives now before calling it missing.
