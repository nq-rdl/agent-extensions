---
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

Creates a new GitHub issue for the RDL Service Desk repository using one of the available templates.

**Repository:** https://github.com/rdl-service-desk/service-desk

## Available Templates

1. **data-request** - Data Request Template
   - Fields: Project title, Approval ID, Workflow Checklist

2. **enquiry** - Enquiry Request Template
   - Fields: Overview, Priority (low/medium/high)

3. **ict** - ICT Request Template
   - Fields: Overview, Priority (low/medium/high)

## Usage

Run `new_service_request` in your terminal and you'll be guided through:
1. Selecting which template to use (1, 2, or 3)
2. Entering the issue number you provide (you must supply this)
3. Filling in the required fields for that template
4. Creating the issue automatically and assigning it to you

Example: You provide issue number `1181`, and it creates `THHSRDLENQ-1181`

## Template Details

### Data Request
- **Project title**: e.g., "Emergency Examination Authority Presentations in the Emergency Department"
- **Approval ID**: e.g., THHSAQUIRE-1234 or SSAQTHS-123456
- **Workflow items**: Mark checklist items as complete (repo bootstrapped, released)

### Enquiry Request
- **Overview**: Brief description (e.g., "Data management review")
- **Priority**: low, medium, or high

### ICT Request
- **Overview**: Brief description (e.g., "New user account setup")
- **Priority**: low, medium, or high
