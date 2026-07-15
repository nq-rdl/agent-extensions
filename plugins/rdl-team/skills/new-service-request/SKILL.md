---
license: CC-BY-4.0
description: >-
  Create a new service desk issue from available templates. Use when creating
  GitHub issues for the RDL Service Desk repository with data request, enquiry,
  or ICT request templates.
compatibility: >-
  Requires write access to the private rdl-service-desk/service-desk repository,
  via either the GitHub MCP server or an authenticated GitHub CLI (`gh`).
metadata:
  repo: https://github.com/nq-rdl/agent-extensions
---

# New Service Request Skill

Create a new GitHub issue in the RDL Service Desk repository from one of its
issue templates.

**Repository:** `rdl-service-desk/service-desk`
(<https://github.com/rdl-service-desk/service-desk>)

## How to run it

This is an agent skill, not a CLI — there is no `new_service_request` binary.
When it is invoked (e.g. `/rdl-team:new-service-request`), **you** create the
issue using whatever GitHub tooling is available in the session, preferring:

1. the **GitHub MCP server**'s create-issue tool, or
2. the **`gh` CLI** (worked command below).

First confirm you can reach `rdl-service-desk/service-desk` (see *Compatibility*
above). If you cannot, tell the user what access is missing instead of
guessing.

## Available templates

| Template | Label | Source | Fields |
|---|---|---|---|
| data-request | `data-request` | `data_request_template.md` | Project title, Approval ID, Workflow Checklist |
| enquiry | `enquiry` | `enquiry_template.md` | Overview, Priority |
| ict | `ICT` | `ict_request_template.md` | Overview, Priority |

Labels are case-sensitive: `ICT` is uppercase, the other two are not.

## Workflow

1. **Ask which template** the request uses — `data-request`, `enquiry`, or
   `ict` (1, 2, or 3).
2. **Ask for the issue number** — the user must supply this; never invent one.
   It is allocated outside this repository, so it cannot be derived or guessed.
3. **Collect the template's required fields** (see *Template details* below).
4. **Create the issue** in `rdl-service-desk/service-desk`, and **assign it to
   the requesting user**.
5. **Return the new issue's URL** so the user can confirm it.

**Title convention:** the issue number prefixed with `THHSRDLENQ-`, uniform
across all three templates — issue number `1181` becomes the title
`THHSRDLENQ-1181`.

```bash
gh issue create \
  --repo rdl-service-desk/service-desk \
  --title "THHSRDLENQ-1181" \
  --label enquiry \
  --assignee @me \
  --body "$(cat <<'EOF'
## Overview

Data management review

## Priority

medium
EOF
)"
```

The body must use the template's `##` headings verbatim — the repo's
`.github/ISSUE_TEMPLATE/*.md` files are the source of truth, so read the
relevant one first if you need to confirm the current headings.

## Template details

### 1. Data Request (`data-request`)
- **Project title** — e.g. "Emergency Examination Authority Presentations in the Emergency Department"
- **Approval ID** — e.g. `THHSAQUIRE-1234` or `SSAQTHS-123456`
- **Workflow checklist** — mark items complete (e.g. repo bootstrapped, released)

### 2. Enquiry Request (`enquiry`)
- **Overview** — brief description (e.g. "Data management review")
- **Priority** — `low`, `medium`, or `high`

### 3. ICT Request (`ict`)
- **Overview** — brief description (e.g. "New user account setup")
- **Priority** — `low`, `medium`, or `high`
