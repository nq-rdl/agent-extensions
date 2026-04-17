---
name: skill-review
license: MIT
description: >-
  Self-improvement loop for Claude Code skills. Spawns a high-effort Sonnet
  subagent to review the current session and produce actionable bugs and
  improvement suggestions for skills. Use at the end of any skill development
  session — after creating, editing, or debugging a skill — to get a second
  opinion and close the feedback loop.
metadata:
  repo: https://github.com/nq-rdl/agent-skills
---

# Skill Review

Spawn a high-effort Sonnet reviewer to audit skills touched in this session.

## Context Loading

The key insight: **you don't need to read a transcript file** — you ARE in the session and already have the full conversation context. Write a structured summary from memory and pass it to the subagent.

## Step 1: Write a Session Context Summary

Before spawning the reviewer, write a structured context block. Include:

- **Touched skills**: which skill directories were created, modified, or discussed (be specific: `skills/charm-tui/`, `skills/pdf/`)
- **Changes made**: new files, edits, key decisions taken
- **Corrections made**: anything the user had to correct — wrong API names, outdated commands, broken patterns. These are the most valuable findings.
- **APIs and patterns used**: specific function names, CLI flags, versions that came up and worked
- **Open questions**: things that seemed off or weren't fully resolved

Be factual and specific — the reviewer has no access to the conversation, only what you write here.

## Step 2: Find the Skills Directory

```bash
# Confirm the skills/ path (should be in current working directory)
ls <cwd>/skills/
```

Also confirm the CLAUDE.md path (usually `<cwd>/CLAUDE.md`).

## Step 3: Spawn the Reviewer

Use the `Agent` tool with `subagent_type: general-purpose` and `model: sonnet` for a high-effort review pass. Pass the context inline in the prompt — do **not** set `run_in_background: true` (the user wants to see the review).

```
subagent_type: general-purpose
model: sonnet

You are reviewing skills touched in a recent Claude Code session. Read each
skill's SKILL.md and any modified files, cross-check against CLAUDE.md
conventions, then return a structured review grouped by severity
(CRITICAL → MODERATE → MINOR).

## Session Context

<your structured summary from Step 1>

## Review Request

Skills directory: <absolute path to skills/>
CLAUDE.md path: <absolute path to CLAUDE.md>

Save the structured review to ~/.claude/skill-reviews/<timestamp>.md and
return the full text.
```

The reviewer will:
1. Read the touched skills
2. Read CLAUDE.md to cross-check conventions
3. Cross-reference against the session context
4. Save a structured review to `~/.claude/skill-reviews/<timestamp>.md`
5. Return the full review text

## Step 4: Present the Findings

After the subagent completes, summarize the key findings for the user. Group by severity (CRITICAL → MODERATE → MINOR) and highlight any corrections from the session that were not yet captured in the skills.

If the review found bugs, offer to fix them immediately.
