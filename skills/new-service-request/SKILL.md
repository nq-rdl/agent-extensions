---
name: new-service-request
license: CC-BY-4.0
description: >-
  Create a new service desk issue from available templates. Use when creating
  GitHub issues for the RDL Service Desk repository with data request, enquiry,
  or ICT request templates.
compatibility: >-
  Requires access to the rdl-service-desk/service-desk GitHub repository.
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
2. the **`gh` CLI**:
   `gh issue create --repo rdl-service-desk/service-desk --template <name> ...`.

First confirm you can reach `rdl-service-desk/service-desk` (see *Compatibility*
above). If you cannot, tell the user what access is missing instead of
guessing.

## Workflow

1. **Ask which template** the request uses — `data-request`, `enquiry`, or
   `ict` (1, 2, or 3).
2. **Ask for the issue number** — the user must supply this; never invent one.
3. **Collect the template's required fields** (see *Template details* below).
4. **Create the issue** in `rdl-service-desk/service-desk` from that template,
   and **assign it to the requesting user**.
5. **Return the new issue's URL** so the user can confirm it.

**Title convention:** match the prefix the service-desk repo already uses for
the chosen template — e.g. an enquiry with issue number `1181` is titled
`THHSRDLENQ-1181`. If you are unsure of the prefix for a template, check an
existing issue of that type in the repo rather than assuming one.

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
