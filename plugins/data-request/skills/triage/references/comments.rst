Queue and comment formats
=========================

Read this when you write the triage output. In triage-only mode the human posts
everything; in both modes, copyedit human-facing text with
``/tech-writing:copyedit`` before handing it over.

Ordered queue
-------------

Number the queue, one line per request, highest first:

.. code-block:: text

   1. service-desk#49 ENQ1187 (THHSAQUIRE-2090) – Urgent label, 54 calendar days.
      Blocked: scaffold. Next: review PR 2 – owner.

Give the verified priority and its source, the age and how it was counted, the
primary blocker class, and the next action with its owner. List the exclusions
and unresolved inputs after the queue.

Paste-ready comment
-------------------

Write one comment per request in a fenced ``text`` block, so that it pastes
verbatim:

.. code-block:: text

   Triage – ENQ1196 (THHSAQUIRE-2107)

   Status: draft complete; blocked on clarification.
   Repository: rdl-service-desk/THHSAQUIRE-2107 (approval as written: THHSAQUIRE2107).
   Confirmed: population, window and outputs, each with its source.
   Proposed, awaiting confirmation: each assumption with its reason.
   Questions for the requester:
   1. One question per decision.
   Next action: one action – owner.

Keep confirmed requirements and proposed assumptions in separate lines. Include
no patient data, credentials or identifiers beyond the enquiry, approval and
issue references. End the reply by stating that nothing was posted, pushed or
changed.
