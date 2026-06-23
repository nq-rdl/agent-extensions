---
license: CC-BY-4.0
description: >-
  Provides guidance on writing commit messages using the Conventional Commits
  specification. Trigger this skill when writing commit messages, generating
  changelogs, or when the user asks about commit message formatting,
  conventional commits, semantic versioning based on commits, or needs to
  categorize a change (e.g., feat vs fix vs chore).
metadata:
  repo: https://github.com/nq-rdl/agent-extensions
  spec_url: https://www.conventionalcommits.org/en/v1.0.0/
---

# Conventional Commits

The Conventional Commits specification is a lightweight convention on top of commit messages. It provides an easy set of rules for creating an explicit commit history; which makes it easier to write automated tools on top of. This convention dovetails with Semantic Versioning (SemVer), by describing the features, fixes, and breaking changes made in commit messages.

## How commits map to this repo's release flow

Commits here feed **changie** fragments, not the changelog directly. A commit's
type should match the changie `kind` you create with `changie new`:

| Commit type | changie kind | SemVer bump (`.changie.yaml` `auto:`) |
|---|---|---|
| `feat:` | `Added` | minor |
| `fix:` | `Fixed` | patch |
| `feat!:` / `BREAKING CHANGE` (remove/rename a plugin, skill, or public path) | `Removed` or `Changed` | **major** |
| `refactor:`/`perf:`/behavior-preserving `Changed` | `Changed` | major |
| `docs:`/`chore:`/`ci:`/`test:` | usually **no** fragment | — |

Release is tag-driven (`v*` on `main`): the tag triggers `changie batch` + `merge`,
regenerates manifests, and publishes. So the commit type you pick decides the
fragment kind, which decides the next version bump.

### Calls models get wrong
- A user-visible behavior change with no new feature is `fix:` only if it
  corrects a defect; otherwise it's `refactor:`/`feat:`. Don't default to `chore:`.
- Removing or renaming a published plugin/skill is **breaking** (`!` + `Removed`/`Changed` → major), even if "just cleanup."
- A commit that is genuinely two changes → split it; one type per commit.

Spec reference: see `metadata.spec_url` — do not restate it here.
