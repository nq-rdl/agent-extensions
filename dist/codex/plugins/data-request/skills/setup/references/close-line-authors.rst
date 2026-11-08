Who may close a handed-off amendment part
=========================================

.. contents::
   :local:

A handed-off part of an amendment stays open until a later comment on the deliverable PR closes it.
Two strict one-line forms close a part: ``done:`` and ``withdrawn:``. The amend and release skills
apply the same check to the writer of that line. Read this rule before you act on either form.

Read the writers
----------------

Read the comment authors from the deliverable PR. Use this command:

``gh pr view PR --json author,assignees,reviewRequests,comments``

Replace ``PR`` with the PR number or URL. Read the PR only. Post nothing.

Who counts
----------

* The ``done:`` line counts only from the engineer named in the hand-off comment. If the comment
  names none, the line counts only from the PR author or an assignee.
* The ``withdrawn:`` line counts only from the analyst named on the PR, as assignee or requested
  reviewer.
* The analyst cannot close a part with ``done:``. The engineer cannot close a part with
  ``withdrawn:``.

When the writer does not count
------------------------------

A line from anyone else leaves the part open. So does a PR that names no one for that role. Say
who wrote the line and which role the rule expected. The human can then name the person.

Do the writer check before any other check on the line. Check the commit of a ``done:`` line only
after the writer counts.
