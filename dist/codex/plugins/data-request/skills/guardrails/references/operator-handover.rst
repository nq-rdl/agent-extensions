Operator hand-over
==================

Read this before you ask the authorised operator to run anything: a delivery run,
a probe, a helper that the agent cannot run, or a file that the agent cannot write.
The operator works from the hand-over text alone. A step that is missing from the
text costs one operator round trip. Every hand-over names the nine items below, in order.

The hand-over template
----------------------

1. **Branch.** Name the branch to check out. Never leave it implied, because the
   default branch can hold only the seed of the repository. Name the pull request
   that carries the branch.
2. **Sync to the head.** Tell the operator to fetch and then fast-forward the
   branch to the pull request head. A stale clone is the most common cause of a wrong run.
3. **Head check.** Name the commit that the operator must see. Ask the operator to
   confirm that ``HEAD`` equals it before any other step. Stop if it differs.
4. **Local configuration.** If the operator keeps an untracked or modified local
   server file, name it and give the exact command to set it aside and restore it.
   Do not write "stash" alone. Say which file, which command and when to restore it.
5. **Files the agent cannot write.** Give the full content of each file, with its
   exact path. Do not describe a file in words. Keep values out of the content.
6. **One task.** Name the single ``pixi`` task or command to run, with its exact
   arguments. Do not offer a choice between tasks.
7. **Commit, then push.** Tell the operator to add the exact files by path, commit,
   and only then push. Name each file. Never write ``git add -A``, ``git add .`` or
   ``git commit -a``, because they stage unrelated and untracked files.
8. **Verdict block.** Ask the operator to paste back one value-free block. It holds
   a pass or fail verdict for each named check and the commit that was run. It holds no counts
   unless a recorded count exception covers that probe, no patient values and no paths that name a request.
9. **Hold line.** State that the agent pushes nothing while the operator run is open.
   An agent push moves the remote and breaks the operator push. Write the hold in the
   hand-over and lift it only when the operator reports back.

Check the scaffold version first
--------------------------------

Before you describe what the runner prints, writes or accepts, read the scaffold
version that the child pins. Do not rely on a version that you read earlier in the
session, because the pin can move. Describe only the output that the pinned version
produces. If the pinned version lacks a feature that you want to name, say so and give
the route that the pinned version supports.

Probes never run through the extract runner
-------------------------------------------

The extract runner writes and tracks the delivery workbook. A probe that runs through
it overwrites the workbook and adds probe output to tracked data.

* Never ask the operator to run a probe with the extract runner or its task.
* Use the scaffold probe route if the pinned scaffold has one. Otherwise save the
  probe SQL at a path that you name, outside every delivery path, and ask the
  operator to run that file with their own client.
* Make the probe a verdict probe where a verdict is enough. See "Verdict probes"
  in ``performance.rst``.
* The operator pastes back the verdict block from item 8. The agent asks for that
  block only. If other output arrives, follow "Default and count exception" in
  ``release.rst`` and repeat none of it.
* One other paste-back is allowed: a lookup discovery grid, only when a verdict cannot
  answer the lookup question. It holds codes, labels and matched-term provenance only.
  It holds no count, row total, frequency, rank by frequency or other column that comes
  from the population. The lookup skill's disclosure controls apply. A grid with a count
  needs a recorded ``count_exception``. Without one, stop and hand off.
  Plausibility checks stay verdict-only.

A probe proposal is not run authority. Disclosure rules for what may come back are in
``release.rst``, "Probe disclosure control". This page changes none of them.
