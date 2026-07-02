# Contract: Skill frontmatter + triggering surface

The `SKILL.md` frontmatter is the skill's public interface — its `description` is the
trigger contract Claude Code matches against. Must satisfy `asctl repo-check`:
`name` required ≤ 64 runes; `description` required ≤ 1024 runes; manifest named exactly
`SKILL.md`; only `SKILL.md` + `lychee.toml` at top level; extras under `assets/`.

## Required frontmatter shape (illustrative)

```yaml
---
name: architecture-decision-records            # 29 runes ≤ 64 OK
license: <SPDX id, e.g. CC-BY-4.0>
description: >-
  Capture architectural decisions in-session as Structured MADR v4 records under
  docs/adr/. Use when the user says "let's record this decision" / "ADR this",
  weighs significant alternatives (framework, library, database, pattern, API,
  auth, infra) and reaches a conclusion, asks "why did we choose X?", or when a
  merged speckit spec should be archived. Auto-detects the moment and OFFERS to
  capture — never writes a file without explicit consent. Maintains the docs/adr
  index with sequential, never-reused numbering.
compatibility: >-
  Targets MADR (adr/madr) spec v4. Documentation-only skill — no CLI or MCP.
metadata:
  repo: https://github.com/nq-rdl/agent-extensions
  spec_url: https://adr.github.io/madr/
---
```

## Contract obligations

- **Triggering (FR-001)**: `description` MUST enumerate both explicit cues and the
  implicit "weighing alternatives" cue, plus the retrieval and archival entry points, so
  the skill fires on all of User Stories 1–3.
- **Version pin (FR-004)**: `compatibility:` MUST name **MADR v4**.
- **Verify-canonical guard (FR-014)**: the body MUST include a one-line
  "verify against the canonical MADR source when being wrong would mislead" pointing at
  `https://adr.github.io/madr/` / `https://github.com/adr/madr`.
- **Non-inferable delta (FR-014)**: body encodes the repo-specific rules — consent gate,
  numbering across `NNNN-*.md` + `adr-NNNN-*.md`, speckit mapping, agent cross-link — not
  a restatement of the public MADR spec.
- **Cross-link (FR-011)**: body references `agents/adr-generator/` for one-shot generation.
- **No `name:` stripping concern**: enters the `planning` bundle as a **flat** member
  (dir name == leaf), so `sync-plugins.sh` copies without rename; grouping guard N/A.
