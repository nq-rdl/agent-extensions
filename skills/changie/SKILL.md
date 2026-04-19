---
name: changie
license: MIT
description: >-
  Changelog entry creation with Changie. Use when writing a changelog entry,
  adding a new change fragment, recording what shipped, or following the Keep a
  Changelog format. Covers non-interactive usage, entry quality rules, issue
  linking, and fragment file naming.
compatibility: >-
  Requires changie CLI
metadata:
  repo: https://github.com/nq-rdl/agent-skills
---

# Changie Skill

Non-interactive changelog entry authoring for agents. Produces human-readable, Keep a Changelog-compliant fragments every time.

---

## Quick Reference

| Kind | SemVer Bump | When to Use |
|------|------------|-------------|
| `Added` | minor | New feature, skill, command, or capability |
| `Changed` | **major** | Existing behaviour modified in a visible way |
| `Deprecated` | minor | Something will be removed in a future version |
| `Removed` | **major** | Feature or capability deleted |
| `Fixed` | patch | Bug, regression, or broken behaviour repaired |
| `Security` | patch | Vulnerability addressed |

---

## The Command

```bash
changie new --interactive=false --kind <Kind> --body "<entry text>"
```

**Dry-run first** (prints the YAML without writing):

```bash
changie new --dry-run --interactive=false --kind Added --body "New `foo` skill for bar"
```

- `--interactive=false` is required — without it changie opens a TUI prompt.
- `--kind` must be one of the six values above, capitalised exactly.
- `--body` is the complete rendered entry. No trailing period.

---

## Writing Rules

Follow all seven rules before running the command.

1. **One entry per logical change.** Two features shipped = two `changie new` calls with two fragments.

2. **20-word limit** (excluding the issue reference). Count words in the body, minus any trailing `(#NNN)`.

3. **Lead with what the user can now do.** Write from a release note perspective, not a commit message perspective.
   - Good: "New `changie` skill teaches agents to write changelog entries in non-interactive mode"
   - Bad: "Added changie skill implementation with SKILL.md and references directory"

4. **Present tense, active voice.** Use "Adds...", "Fixes...", "Removes...", or noun-first "New `foo`...", "Broken `bar`...".

5. **Backtick-delimit code.** Command names, skill names, agent names, file names, flags — wrap in backticks.
   - Good: "New `changie` skill"
   - Bad: "New changie skill"

6. **Em dash for elaboration.** Use ` — ` (space–em-dash–space) to append a "so what" clause.
   - "Fixes crash when `extract` runs on empty PDFs — previously silently produced an empty file"

7. **No trailing period.** Entries are bullet items, not sentences. Changie renders them as `* <body>`.

---

## Issue Linking

Append `(#NNN)` to the body to link a GitHub issue or PR:

```bash
changie new --interactive=false --kind Fixed \
  --body "Fixes crash when `extract` runs on empty PDFs (#42)"
```

- GitHub auto-links bare `#NNN` references in markdown — no full URL needed.
- Find the relevant issue number with `gh issue list` or `gh pr list`.
- Read issue context with `gh issue view NNN` before writing the entry.
- The issue ref does not count toward the 20-word limit.

---

## Good and Bad Examples

| Body | Verdict | Why |
|------|---------|-----|
| `New \`changie\` skill teaches agents to write changelog entries in non-interactive mode` | ✅ Good | Noun-first, backticked name, user benefit clear |
| `New \`copilot-sdk\` skill for building GitHub Copilot extensions in Go — brings the full Copilot SDK API surface into your coding assistant` | ✅ Good | Em-dash elaboration, specific benefit |
| `Fixes crash when \`extract\` runs on empty PDFs — previously silently produced an empty file (#42)` | ✅ Good | Present tense, backtick, em-dash "so what", issue ref |
| `Added changie skill with SKILL.md and references dir` | ❌ Bad | Commit message voice, no backtick, no user benefit |
| `Updated the opencode skill to fix a bug where sessions would not terminate correctly.` | ❌ Bad | Passive voice, trailing period, vague |
| `Fixed bug` | ❌ Bad | No context, not actionable |
| `Fixes crash when \`extract\` runs on empty PDFs — also fixes broken retry logic in \`upload\`` | ❌ Bad | Two logical fixes fused with "also" — Rule #1 violation; split into two `changie new` calls |
| `Fixes crash when \`extract\` runs on empty PDFs` (+ separate) `Fixes broken retry logic in \`upload\`` | ✅ Good | Each fix is its own fragment — two calls, two bullets in the release note |

---

## Trim Example

**Before (64 words — 3× over limit):**

> "tui: guide marker now stays inside the filled region when utilization > guide. At narrow bar widths the fill cell count and marker cell were rounded independently, which could place the │ past the visual fill edge. A new `guidePosition` helper snaps the marker inward so visual ordering matches numeric ordering"

**After (16 words — within limit):**

> "tui: keep guide marker inside the filled region when utilization exceeds the guide on narrow bars"

**What was cut:** root-cause analysis, internal helper name, and implementation mechanics. Those belong in the commit message or PR description, not the changelog. The entry title carries the user-visible outcome.

---

## Fragment File Renaming

After `changie new` creates the fragment, rename it to a human-readable slug:

```bash
# Default name (timestamp-based):
.changes/unreleased/Added-20260319-123456.yaml

# Rename to:
.changes/unreleased/Added-20260319-<slug>.yaml
```

Where `<slug>` is a short kebab-case descriptor (e.g., `changie-skill`, `pdf-empty-fix`).

Changie ignores filenames — it reads the `kind` and `body` fields from YAML. Renaming is for human navigation only.

```bash
# Example rename
mv .changes/unreleased/Added-20260319-*.yaml \
   .changes/unreleased/Added-20260319-changie-skill.yaml
```

---

## Shell Quoting

Bodies containing backticks or apostrophes need careful quoting.

**Backticks in body — use single quotes:**

```bash
changie new --interactive=false --kind Added \
  --body 'New `changie` skill for changelog authoring'
```

**Apostrophes in body — use double quotes:**

```bash
changie new --interactive=false --kind Fixed \
  --body "Fixes parser bug when body contains user's input"
```

**Both — use `$'...'` syntax (bash):**

```bash
changie new --interactive=false --kind Added \
  --body $'New `changie` skill — it\'s the fastest way to ship entries'
```

---

## Release Workflow

**Context only — do not run these commands unless explicitly asked.**

```bash
# Batch unreleased fragments into a versioned release file
changie batch <version>          # e.g., changie batch 0.2.0

# Merge all versioned release files into CHANGELOG.md
changie merge
```

> **WARNING: Do NOT use the `v` prefix with `changie batch`.**
>
> | Command | File created | Result |
> |---------|-------------|--------|
> | `changie batch 0.2.0` | `.changes/0.2.0.md` | ✅ Correct |
> | `changie batch v0.2.0` | `.changes/v0.2.0.md` | ❌ Wrong |
>
> The release workflow strips the `v` from the tag name (`v0.2.0` → `0.2.0`) and looks for
> `.changes/0.2.0.md`. Using the `v` prefix creates the wrong filename, causing the release
> workflow to exit with "file not found" and the GitHub Release to never be created.

These commands are reserved for release managers. Agents must not run them unless the user explicitly requests a release.

---

## Validation Checklist

Run through this before executing `changie new`:

- [ ] Exactly one logical change — if body contains "also", "and also", "additionally", or ", also" stop and split into separate `changie new` calls
- [ ] Kind matches what changed (Added/Changed/Deprecated/Removed/Fixed/Security)
- [ ] Body is ≤ 20 words (excluding issue ref) — count the words; if >20 ask yourself "what can be cut?" and trim before continuing
- [ ] Body uses present tense, active voice
- [ ] Code names are wrapped in backticks
- [ ] Em dash used for elaboration (not comma or semicolon)
- [ ] No trailing period
- [ ] Issue number appended as `(#NNN)` if a relevant issue exists

---

## Reference Files

- [`references/keep-a-changelog.rst`](references/keep-a-changelog.rst) — Keep a Changelog 1.1.0 spec condensed: the six kinds, what not to include, SemVer mapping, and the "Unreleased" concept.
