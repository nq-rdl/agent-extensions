Simplified STE review profile
=============================

Purpose and authority
---------------------

This is the mandatory review profile for documentation produced through
tech-writing:copyedit or the technical writer agent. It is informed by
ASD-STE100 Issue 9 and an independent review of SimpleEnglish at commit
6fa7943df766d73000b6ef8a184b012ac72b136e. It is an authored subset, not a copy
of the standard or its dictionary. Source URLs are in SKILL.md for lychee.

Review the document itself, including file changes when the deliverable is a
file. A statement that checks passed is not review evidence. Check only prose
created or changed for the current task; leave unrelated legacy text alone.

Required checks
---------------

* Classify each passage. Instructions have a 20-word sentence limit;
  descriptions have a 25-word limit and at most six sentences per paragraph.
  Keep one instruction per sentence, except actions that must be simultaneous.
* Put a necessary condition before its action. Preserve the condition’s scope
  and the order of dependent steps. Keep warnings and consequences together.
* Prefer active voice and simple verb forms. Name only actors that the source
  identifies. Do not invent an actor or change timing to simplify a sentence.
* Use complete sentences. Expand contractions and split prose at semicolons.
  Possessive apostrophes are not contractions.
* Keep one name for one concept. Explain unfamiliar domain terms when needed.
  Do not replace distinct technical operations with a single vague synonym.
* Remove empty promotional claims. Keep qualifications, uncertainty, units,
  quantities, negation, and the force of requirements or permissions intact.
* Retain the established project locale and the house recommendation exception.
  Preserve normative must, may, and should. Their presence alone is not a defect.

For this subset’s word count, count a hyphenated term, number with its unit,
inline code span, or quoted literal as one item. Count each list item separately.
Exclude headings, code blocks, URLs, identifiers, file paths, UI labels, and
verbatim output from prose rewrites. Assess table prose cell by cell. This
counting convention is not a substitute for the official standard’s rules.

Completion gate
---------------

The native agent hook reads the current task and deliverable. It returns
``ok: false`` with concrete locations and corrections when findings remain.
It rechecks corrected work; ``stop_hook_active`` is not a waiver. It returns
``ok: true`` only after the applicable checks pass, the task is out of scope,
or the user explicitly stops the work. A real external blocker may end with
an explicit incomplete status, never a fabricated success claim.

The hook is a model review, not a deterministic grammar or dictionary checker.
Claude controls its timeout and repeated-block limit. Disabled hooks, model
errors, or harness limits are not evidence that the document passed review.

Full compliance
---------------

Full ASD-STE100 verification requires the official writing rules and dictionary,
including approved meanings, parts of speech, forms, and permitted technical
terms. A simplified review cannot establish those. Request the official copy
through ASD when needed. Do not derive an authoritative dictionary from memory
or distribute the upstream repository’s word tables as the standard.
