# Shared skill issue-reporting procedure

Follow these steps after identifying the failing skill and its upstream repository.

### 3. Search for Existing Issues

Before creating a new issue, check whether someone has already reported the same problem. Search the repo's open issues for keywords related to the failure.

**Validate the repo URL first:** Strip trailing slashes and `.git` suffixes. Confirm the host is `github.com`. If it is not, tell the user:
> "The `repo` field points to a non-GitHub host (<host>). Automatic issue filing only supports github.com. You will need to file this issue manually at <url>/issues/new."
Then jump to step 5 to prepare the formatted content for manual filing.

**Using an available GitHub integration:** Discover its issue-search capability and use a query containing:
- the skill name
- key error messages or symptoms
- repo: <owner>/<repo>
- is:open

**Fallback — using `gh` CLI:**
```bash
gh issue list --repo <owner>/<repo> --search "<skill-name> <key-symptom>" --state open
```

**If neither MCP nor `gh` CLI is available:** Tell the user:
> "I cannot reach GitHub automatically — the GitHub MCP server is not configured and the `gh` CLI is not installed or not authenticated. Here is the fully-formatted issue you can file manually at https://github.com/<owner>/<repo>/issues/new."
Then jump to step 5, format the issue, present it to the user, and stop (do not proceed to step 6).

**If the search times out or returns an error:** Skip the duplicate check, proceed to step 4, and note in the issue body: "Duplicate search was skipped due to a timeout or API error."

**If a matching issue is found:**
- Tell the user about it (link it)
- Offer to add a comment with their specific details instead of creating a duplicate
- If the user agrees to comment, collect details (step 4), format the complete comment, and follow step 5b with the existing issue URL as the destination. Agreement to add details is not approval of an unseen draft.
- Only after the user approves that complete comment, post it using a structured GitHub tool argument or `gh issue comment <number> --repo <owner>/<repo> --body-file "<approved comment file>"`.
- If the comment call fails, tell the user exactly what failed and present the comment text for manual posting
- Do not proceed to create a new issue if the user chose to comment on an existing one

If no match is found, proceed to step 4.

### 4. Gather Issue Details

Collect the following information. You should already have most of this from the conversation context — fill in what you can and ask the user only for gaps.

| Section | What to Include |
|---------|----------------|
| **What happened** | The error, unexpected behavior, or incorrect output observed. Include exact error messages if available. |
| **Expected behavior** | What the skill should have done instead. |
| **Steps to reproduce** | The prompt or sequence of actions that triggered the problem. Include input files, arguments, and context. |
| **What was tried** | Workarounds or fixes attempted before reporting — e.g., retrying, different inputs, reading skill docs. |
| **Assumptions** | What the reporter assumed about the skill's behavior and where reality diverged. Helps the author understand the user's mental model. |
| **Environment** | Relevant details: AI coding client (Claude Code, etc.), model, OS, tool versions, MCP servers configured. |
| **Additional context** | Logs, screenshots, related issues, or anything else that might help diagnosis. |

### 5. Format the Issue

Use this template for the issue body:

```markdown
## What happened

[Clear description of the failure or unexpected behavior]

## Expected behavior

[What should have happened instead]

## Steps to reproduce

1. [Step-by-step instructions to trigger the issue]
2. [Include the prompt used, input files, etc.]

## What was tried

- [Workaround 1 — result]
- [Workaround 2 — result]

## Assumptions

[What was assumed about the skill's behavior vs. what actually happened]

## Environment

- **Client:** [Claude Code / Gemini CLI / etc.]
- **Model:** [e.g., claude-sonnet-4-20250514]
- **OS:** [e.g., macOS 15.2, Ubuntu 24.04]
- **Skill version:** [commit hash or date if known]

## Additional context

[Logs, screenshots, related issues, or other helpful details]
```

### 5b. Review Before Filing (MANDATORY)

Before publishing either a new issue or a comment on an existing one, present the
complete draft and exact destination to the user. For a comment, show the existing
issue URL and the full comment body; for a new issue, show the repository, title,
and full issue body:

> "Here is the issue I'm about to create on https://github.com/<owner>/<repo>. Please review it for any sensitive information (API keys, internal paths, proprietary data, personal details) before I proceed."
>
> **Title:** [skill:<name>] <summary>
>
> **Body:** <formatted template from step 5>
>
> "Should I file this issue as written, or would you like to redact anything first?"

Do not proceed to step 6 until the user explicitly confirms. For the duplicate-comment
route, do not post the comment until this same completed-draft approval is received.

### 6. File the Issue

Extract `owner/repo` from the `repo` URL:
- Strip trailing slashes and `.git` suffixes (e.g., `https://github.com/org/repo.git` → `org/repo`)
- Use only the path after `github.com/`

**Title format:** `[skill:<skill-name>] <concise summary of the problem>`

**Labels:** Attempt to add `bug` and `skill` labels. If either label does not exist on the repo, do not fail — but tell the user:
> "Note: The label '<label>' does not exist on this repository and was not applied. You may want to add it manually."

**Using an available GitHub integration:** Discover its issue-creation capability and pass owner/repo, the title, and the complete approved body as structured data. Do not assume a particular MCP tool name is installed.

**Fallback — `gh` CLI:** Write the exact approved body to a temporary UTF-8 file, then run:
```bash
gh issue create \
  --repo <owner>/<repo> \
  --title "[skill:<name>] <summary>" \
  --body-file "<path to approved UTF-8 issue body>" \
  --label "bug"
```

**If the MCP call or `gh` command returns an error:**
- Report the error verbatim to the user (e.g., "The API returned 403 Forbidden — this account may not have write access")
- Do NOT tell the user the issue was filed
- Present the fully formatted title and body so the user can file it manually at https://github.com/<owner>/<repo>/issues/new
- Do not proceed to step 7 with a success message

**If neither MCP nor `gh` CLI is available** (discovered here rather than in step 3):
- Tell the user and present the formatted issue for manual filing, as described in step 3

### 7. Confirm to the User

**If a new issue was created successfully:**
- Share the issue URL
- Confirm which labels were applied (or note that none were applied)
- Summarize what was reported in one sentence

**If a comment was added to an existing issue:**
- Share the comment URL and a link to the parent issue
- Tell the user their details were added to an existing report

**If manual filing was required (API failure, missing tools, non-GitHub host):**
- Confirm that the formatted issue content was presented above
- Remind the user to file it at the target URL
- Offer to save the content to a local file (e.g., `/tmp/skill-issue.md`) if that would help

---

## Important Considerations

- **Don't file issues for user errors.** If the skill worked correctly but the user's input was wrong or incomplete, help the user fix their input instead.
- **Don't file issues for clearly documented environment problems.** If the skill's SKILL.md documents a required dependency and the user hasn't installed it, help the user resolve the environment. However, if the skill fails silently when a dependency is missing — without telling the user what is missing or how to fix it — that missing error handling is itself a bug worth reporting.
- **Be specific in reproduction steps.** Vague issues waste the author's time. Include exact prompts, file paths (anonymized if sensitive), and error messages.
- **One issue per problem.** If multiple things are broken, file separate issues rather than a mega-issue.
