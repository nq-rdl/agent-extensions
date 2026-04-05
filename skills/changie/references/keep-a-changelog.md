# Keep a Changelog 1.1.0 — Condensed Reference

Source: [keepachangelog.com](https://keepachangelog.com/en/1.1.0/)

---

## Core Principle

> A changelog is for **humans**, not machines.

It is NOT a git log dump. It answers the question: *"What changed that affects me as a user?"*

---

## The Six Change Types

| Kind | Definition | Maps to SemVer |
|------|------------|----------------|
| **Added** | New features or capabilities | minor |
| **Changed** | Changes to existing behaviour | major |
| **Deprecated** | Features soon to be removed | minor |
| **Removed** | Features removed in this version | major |
| **Fixed** | Bug fixes | patch |
| **Security** | Vulnerabilities addressed | patch |

These map directly to the `kinds` in `.changie.yaml` — use them verbatim.

---

## What NOT to Include

- **Commit message dumps** — "Updated foo.py, changed bar, fixed baz" is not a changelog entry.
- **Invisible refactors** — internal code cleanups with no user-visible effect belong in commit messages, not changelogs.
- **Dependency bumps** — unless the bump brings a behaviour change visible to users.
- **WIP / partial work** — every entry implies the change is complete and available.
- **Duplicate entries** — one logical change = one entry, regardless of how many commits it took.

---

## The "Unreleased" Concept

In this repo, `.changes/unreleased/` holds fragments for changes not yet assigned to a version. These are:
- Created by `changie new` after each meaningful change
- Batched into a release with `changie batch <version>`
- Merged into `CHANGELOG.md` with `changie merge`

Each fragment is a tiny YAML file with `kind`, `body`, and `time` fields. The `body` field becomes the bullet point verbatim, so write it as a finished sentence (without a trailing period).

---

## Kind → SemVer Mapping (auto-bump)

Changie's `auto:` config derives the next version automatically from the highest-impact kind in the unreleased set:

| Highest Kind | Next Version Bump |
|-------------|------------------|
| Changed, Removed | **major** |
| Added, Deprecated | **minor** |
| Fixed, Security | **patch** |

Pick the kind that accurately describes the change — it directly determines the next version number.
