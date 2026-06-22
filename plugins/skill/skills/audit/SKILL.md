---
license: CC-BY-4.0
description: >-
  Audit a skill for non-inferable value. Use when creating, compressing, or
  reviewing a SKILL.md to check it encodes a gap the fresh model cannot see
  rather than restating public specs. Applies the Biggs "could a fresh model
  write this verbatim?" test and the SkillsBench conciseness rubric, checks
  version pins and the verify-canonical guard, and flags reference-card skills.
metadata:
  repo: https://github.com/nq-rdl/agent-extensions
---

# Skill Audit

Run the non-inferable-value rubric over a target `SKILL.md` (or the session's
skill diff). See CONTRIBUTING.md → "Skill content conventions" for the authoring
rules this enforces.

## Rubric
1. **Non-inferable value (Biggs):** could a fresh model write this verbatim? If yes → cut.
2. **Conciseness (SkillsBench):** verifier-facing, non-inferable detail over comprehensive prose.
3. **Version pins:** any encoded library/tool API surface is pinned in `compatibility:`.
4. **Verify-canonical guard:** fast-moving/high-stakes subjects point to canonical docs.
5. **Frontmatter/discovery:** `name` matches dir; `description` triggers well; structure-standard clean.
6. **Complexity contract:** the skill earns its context cost.

## How to run
Use the `Agent` tool with `subagent_type: skill-auditor` (high effort). Pass the
target path(s) and the rubric above inline; the subagent reads the SKILL.md,
scores each rubric item, and returns severity-rated findings (CRITICAL / MODERATE / MINOR)
with file:line anchors and a keep/cut/pin recommendation. Do not set
`run_in_background: true` — the user wants to see the findings.
