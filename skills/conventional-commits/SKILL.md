---
name: conventional-commits
license: CC-BY-4.0
description: >-
  Provides guidance on writing commit messages using the Conventional Commits
  specification. Trigger this skill when writing commit messages, generating
  changelogs, or when the user asks about commit message formatting,
  conventional commits, semantic versioning based on commits, or needs to
  categorize a change (e.g., feat vs fix vs chore).
metadata:
  repo: https://github.com/nq-rdl/agent-skills
  spec_url: https://www.conventionalcommits.org/en/v1.0.0/
---

# Conventional Commits

The Conventional Commits specification is a lightweight convention on top of commit messages. It provides an easy set of rules for creating an explicit commit history; which makes it easier to write automated tools on top of. This convention dovetails with Semantic Versioning (SemVer), by describing the features, fixes, and breaking changes made in commit messages.

## Message Structure

A commit message should be structured as follows:

```
<type>[optional scope]: <description>

[optional body]

[optional footer(s)]
```

## Common Types

- **`feat`**: Introduces a new feature to the codebase (correlates with MINOR in SemVer).
- **`fix`**: Patches a bug in your codebase (correlates with PATCH in SemVer).
- **`chore`**: Maintenance tasks, dependency updates, or internal changes that don't affect production code.
- **`docs`**: Documentation only changes.
- **`style`**: Changes that do not affect the meaning of the code (white-space, formatting, missing semi-colons, etc).
- **`refactor`**: A code change that neither fixes a bug nor adds a feature.
- **`perf`**: A code change that improves performance.
- **`test`**: Adding missing tests or correcting existing tests.
- **`build`**: Changes that affect the build system or external dependencies (example scopes: gulp, broccoli, npm).
- **`ci`**: Changes to our CI configuration files and scripts (example scopes: Travis, Circle, BrowserStack, SauceLabs).
- **`revert`**: Reverts a previous commit.

## Breaking Changes

A commit that has a footer `BREAKING CHANGE:`, or appends a `!` after the type/scope, introduces a breaking API change (correlating with MAJOR in Semantic Versioning). A BREAKING CHANGE can be part of commits of any type.

## Examples

### With Scope
```
feat(parser): add ability to parse arrays
```

### Breaking Change
```
feat!: send an email to the customer when a product is shipped
```
or
```
feat: allow provided config object to extend other configs

BREAKING CHANGE: `extends` key in config file is now used for extending other config files
```

### Multi-paragraph Body and Footers
```
fix: prevent racing of requests

Introduce a request id and a reference to latest request. Dismiss
incoming responses other than from latest request.

Remove timeouts which were used to mitigate the racing issue but are
obsolete now.

Reviewed-by: Z
Refs: #123
```

## Further Guidance

For comprehensive details on the specification, including rules, FAQs, and edge cases, see the [Conventional Commits Guidance](references/guidance.rst).
