---
name: send-pr
license: CC-BY-4.0
description: >-
  Commits, pushes and raises a PR. Use this skill when the user asks to "ship", "commit, push and raise PR", or similar commands.
disable-model-invocation: true
metadata:
  repo: https://github.com/nq-rdl/agent-skills
---

# Commit, Push and Raise PR

This skill handles the complete workflow of committing staged/unstaged changes, pushing to the remote, and raising a Pull Request.

## Workflow

1. **Analyse Changes** - Review all pending changes (staged and unstaged) to understand the scope and nature of the work
2. **Commit** - Create a well-formed conventional commit
3. **Push** - Push the current feature branch to origin
4. **Raise PR** - Create a Pull Request
5. **Request Review** - Prompt the user for reviewer logins and assign them to the PR

## Commit Message Format

Use Conventional Commits format:
```
<type>: <description>

[optional body with more detail]
```

### Types
- `feat` - new functionality
- `fix` - bug fixes
- `refactor` - code restructuring without behaviour change
- `docs` - documentation only
- `test` - adding or updating tests
- `chore` - maintenance tasks, dependency updates

### Rules
- First line should be **50 characters or fewer** for `git log --oneline` readability (GitHub itself truncates display at ~72; treat 72 as a hard ceiling)
- Description should be lowercase, imperative mood ("add feature" not "added feature")
- Body (if needed) should be wrapped at 72 characters

## Pull Request Format

The PR title should match the first line of the commit message (including the conventional commit prefix).

Use this template for the PR body:
```markdown
## Summary
[2-3 sentences describing what this PR accomplishes and why]

## Changes
[Bullet points of the key modifications, grouped logically]

## Test Plan
- [ ] [Specific scenario to verify]
- [ ] [Another test case]
- [ ] [Edge case to check]

## Notes for Reviewers
[Any context that will help reviewers: areas of uncertainty, alternative approaches considered, architectures and patterns worthy of note, or specific files to scrutinise]
```

## Execution Steps

1. Run `git status`, `git diff`, and `git diff --staged` to understand all pending changes
2. Analyse the changes to determine the appropriate commit type and craft a meaningful message
3. Stage files by name (e.g. `git add path/to/file ...`). Avoid `git add -A`/`git add .` unless step 1's review confirms there are no `.env`, credentials, or large binaries that would be swept in
4. Commit with the crafted message
5. Push the branch with `git push -u origin HEAD`
6. Determine the target (base) branch:
   - Try `gh repo view --json defaultBranchRef -q .defaultBranchRef.name` first
   - If that fails, run `git symbolic-ref refs/remotes/origin/HEAD | sed 's|^refs/remotes/origin/||'` to derive the plain branch name (the raw `git symbolic-ref` output is `refs/remotes/origin/<branch>` and cannot be passed directly to `gh pr create --base`)
   - Only if both fail, fall back to scanning remote branches: `git branch -r | sed 's|^[[:space:]]*origin/||' | grep -E '^(develop|main|master)$' | head -1`
7. Write the PR body to a temporary file, then create the PR with `gh pr create --base <target branch> --title "<commit first line>" --body-file <path to PR body file>`. Clean up the temp file once the PR is created
8. Ask the user which GitHub login(s) to request a review from, then run `gh pr edit --add-reviewer <login>[,<login>...]` (no PR identifier needed — `gh pr edit` resolves it from the current branch; skip if the user declines)

## Important Notes

- Derive the commit message and PR content entirely from analysing the actual changes - do not ask the user to describe them
- The test plan should contain **specific, actionable** test cases derived from the changes, not generic placeholders
- If changes span multiple concerns and would benefit from separate commits, note this to the user but proceed with a single commit unless instructed otherwise
