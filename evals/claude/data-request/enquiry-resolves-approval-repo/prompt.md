---
description: An enquiry number resolves to its service-desk issue and approval-ID repository, keeps the original spelling, and takes the amended date window
tags: [triage, resolution]
runs: 3
max_turns: 6
timeout_seconds: 240
allowed_tools: [Read, Glob, Grep, Skill]
---

Triage ENQ1196 only; triage only. A colleague's note just says "look at ticket 1196". I need to know which service-desk issue and which child repository this is, and the date window we should use. This session has no shell or GitHub access; what I gathered is below.

`gh issue list -R rdl-service-desk/service-desk --search 1196 --state all`:

- #58 "THHSRDLENQ-1196 Stroke admissions with pathology" (open, label `priority: Urgent`)

Issue #58 body (opened 2026-07-20):

> Approval: THHSAQUIRE2107
> Date range: 2021-01-01 to 2024-12-31
> Repo: https://github.com/rdl-service-desk/THHSRDLENQ-1196

Issue #58 comments:

- 2026-08-14, requester: "Amendment AMD-2 approved: extend the end date to 31 December 2025. Approval letter attached."
- 2026-08-15, RDL: "Noted."

`gh repo list rdl-service-desk`: service-desk, THHSAQUIRE-2090, THHSAQUIRE-2107, THHSAQUIRE-2120, SSAQHTS-43408

`gh repo view rdl-service-desk/THHSRDLENQ-1196`: `GraphQL: Could not resolve to a Repository with the name 'rdl-service-desk/THHSRDLENQ-1196'.`

`rdl-service-desk/THHSAQUIRE-2107` README: "ENQ1196: stroke admissions linked to pathology (approval THHSAQUIRE-2107)."

End your reply with one fenced `yaml` block with exactly these top-level keys: `enquiry`, `issue`, `approval_as_written`, `repo`, `window_start`, `window_end_exclusive`, `stale_links` (a list).
