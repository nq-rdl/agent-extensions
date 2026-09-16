---
license: CC-BY-4.0
description: >-
  Report issues with skills to their upstream repository. Use when a skill
  produces errors, unexpected behavior, incorrect output, or fails silently.
  Also trigger when the user says things like "this skill is broken", "file a
  bug for this skill", "report this to the skill author", or when you notice a
  skill behaving incorrectly during normal use. Even if the user doesn't
  explicitly ask, offer to report the issue if you observe a clear skill defect.
metadata:
  repo: https://github.com/nq-rdl/agent-extensions
---

# Report Skill Issue

When a skill fails or behaves unexpectedly, this skill guides you through reporting the issue to the skill's upstream repository — so the author can fix it for everyone.

---

## Workflow

### 1. Identify the Failing Skill

Determine which skill caused the problem. You likely already know this from context (e.g., the skill you just invoked), but if not, ask the user which skill they're referring to.

Locate the skill's `SKILL.md` file. Skills live in a `skills/<name>/` directory structure, so look for:
```
skills/<skill-name>/SKILL.md
```

**If the `SKILL.md` file cannot be located:** Tell the user:
> "I couldn't find a SKILL.md file for the skill '<name>'. It may be installed from a different location or the skill directory may be missing. Do you know where the skill is located, or can you provide the repository URL directly?"

If the user provides a URL, skip to step 3. Otherwise stop and do not proceed.

### 2. Check for a `repo` Field

Read the skill's `SKILL.md` and parse its YAML frontmatter. Look for a `repo` field under `metadata` — this is the URL of the repository where the skill is maintained.

```yaml
---
name: example-skill
description: "..."
metadata:
  repo: https://github.com/org/repo   # ← this is what you need
---
```

**If `repo` is missing or empty:** Tell the user:
> "This skill doesn't have an upstream repository listed in its metadata. I can't file an issue automatically. You could try contacting the skill author directly, or if you know the repo, I can file the issue there."

If the user provides a repo URL, proceed with that.

**If `repo` is present:** Continue to step 3.

### 3. Review and publish the report

Read and follow [references/reporting.rst](references/reporting.rst), the required
shared reporting procedure. It covers duplicate search, diagnosis, draft approval,
publication, and failure handling. Do not skip its review-before-filing step.
