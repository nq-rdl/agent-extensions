---
name: changie
license: CC-BY-4.0
description: >-
  Changelog entry creation with Changie. Use when writing a changelog entry,
  adding a new change fragment, recording what shipped, or following the Keep a
  Changelog format. Covers non-interactive usage, entry quality rules, and
  issue linking.
compatibility: >-
  Requires changie CLI
metadata:
  repo: https://github.com/nq-rdl/agent-extensions
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

2. **Keep it short.** If the project's `.changie.yaml` sets `body.maxLength`, that is the hard cap — changie rejects a longer `--body`; a hand-edited fragment bypasses that check, so stay under it anyway. Without a cap, aim for one line. Cut root cause, internal helper names, and implementation mechanics — they belong in the commit message or PR description.

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
- The issue ref counts toward any `body.maxLength` cap — it is part of the body.

---

## Good and Bad Examples

| Body | Verdict | Why |
|------|---------|-----|
| `New \`changie\` skill teaches agents to write changelog entries in non-interactive mode` | ✅ Good | Noun-first, backticked name, user benefit clear |
| `New \`copilot-sdk\` skill for building GitHub Copilot extensions in Go — brings the full Copilot SDK API surface into your coding assistant` | ✅ Good | Em-dash elaboration, specific benefit |
| `Fixes crash when \`extract\` runs on empty PDFs — previously silently produced an empty file (#42)` | ✅ Good | Present tense, backtick, em-dash "so what", issue ref |
| `Added changie skill with SKILL.md and references dir` | ❌ Bad | Commit message voice, no backtick, no user benefit |
| `Updated the worker to fix a bug where jobs would not finish correctly.` | ❌ Bad | Passive voice, trailing period, vague |
| `Fixed bug` | ❌ Bad | No context, not actionable |
| `Fixes crash when \`extract\` runs on empty PDFs — also fixes broken retry logic in \`upload\`` | ❌ Bad | Two logical fixes fused with "also" — Rule #1 violation; split into two `changie new` calls |
| `Fixes crash when \`extract\` runs on empty PDFs` (+ separate) `Fixes broken retry logic in \`upload\`` | ✅ Good | Each fix is its own fragment — two calls, two bullets in the release note |

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
> Changie keeps the prefix in the filename, so release tooling that looks up
> `.changes/0.2.0.md` will not find it. Match the naming of the project's existing
> `.changes/<version>.md` files, and follow the project's own release process (which may
> batch in CI from an explicit version input) rather than batching by hand.

These commands are reserved for release managers. Agents must not run them unless the user explicitly requests a release.

---

## Validation Checklist

Run through this before executing `changie new`:

- [ ] Exactly one logical change — if body contains "also", "and also", "additionally", or ", also" stop and split into separate `changie new` calls
- [ ] Kind matches what changed (Added/Changed/Deprecated/Removed/Fixed/Security)
- [ ] Body fits the project's `body.maxLength` in `.changie.yaml` (if set) — if it is long, ask "what can be cut?" and trim, or split into more fragments
- [ ] Body uses present tense, active voice
- [ ] Code names are wrapped in backticks
- [ ] Em dash used for elaboration (not comma or semicolon)
- [ ] No trailing period
- [ ] Issue number appended as `(#NNN)` if a relevant issue exists

---

## Reference Files

- [`references/keep-a-changelog.rst`](references/keep-a-changelog.rst) — Keep a Changelog 1.1.0 spec condensed: the six kinds, what not to include, SemVer mapping, and the "Unreleased" concept.
