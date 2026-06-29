<!--
Minimal OpenCode Agent Skill skeleton.
Place at one of (folder name MUST equal the `name` below):
  .opencode/skills/<name>/SKILL.md          (project, OpenCode-native)
  ~/.config/opencode/skills/<name>/SKILL.md (global, OpenCode-native)
  .claude/skills/<name>/SKILL.md            (project, Claude Code skills are read VERBATIM)
  ~/.claude/skills/<name>/SKILL.md          (global, Claude Code drop-in)
  .agents/skills/<name>/ or ~/.agents/skills/<name>/
File MUST be named SKILL.md (all caps). Only the five frontmatter fields below
are recognized; any other key (argument-hint, user-invocable, allowed-tools, …)
is silently ignored by OpenCode.
-->
---
name: my-skill                 # 1–64 chars, ^[a-z0-9]+(-[a-z0-9]+)*$, MUST equal the directory name
description: One specific sentence the agent uses to decide when to load this skill. 1–1024 chars; name concrete triggers.
license: MIT                   # optional
compatibility: opencode        # optional
metadata:                      # optional — string→string ONLY (no nesting, no numbers)
  audience: maintainers
---

## What I do

- Step or capability one
- Step or capability two

## When to use me

Describe the trigger conditions. Ask clarifying questions if inputs are ambiguous.

<!-- The agent sees only `name` + `description` until it calls skill({ name: "my-skill" });
     this body loads on demand. Gate access with permission.skill globs in opencode.json:
       { "permission": { "skill": { "*": "allow", "internal-*": "deny" } } }
     Disable the tool entirely for an agent with tools: { skill: false }. -->
