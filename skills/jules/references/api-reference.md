# Jules API Reference

Complete reference for the Jules REST API used by this skill.

## Base URL

```
https://jules.googleapis.com/v1alpha
```

Override for testing: set `JULES_BASE_URL` environment variable.

## Authentication

All requests require:
```
x-goog-api-key: <JULES_API_KEY>
```

## Endpoints

### Sessions

#### POST /sessions — Create session

Request body:
```json
{
  "prompt": "Fix the login bug in auth/handler.go",
  "sourceContext": {
    "source": "sources/src_abc123",
    "githubRepoContext": {
      "startingBranch": "main"
    }
  }
}
```

*To require plan approval before execution, add `"requirePlanApproval": true`. Omit for fully autonomous sessions (default).*

Response: `Session` object.

#### GET /sessions — List sessions

Response:
```json
{
  "sessions": [...],
  "nextPageToken": "..."
}
```

#### GET /sessions/{id} — Get session

Response: `Session` object.

#### DELETE /sessions/{id} — Delete session

Response: empty body, 200 on success.

#### POST /sessions/{id}:sendMessage — Send message

Request body:
```json
{
  "prompt": "Please focus on the config module only"
}
```

Response: updated `Session` object.

#### POST /sessions/{id}:approvePlan — Approve plan

No request body. Moves session from `AWAITING_PLAN_APPROVAL` → `IN_PROGRESS`.

Response: updated `Session` object.

### Activities

#### GET /sessions/{id}/activities — List activities

Response:
```json
{
  "activities": [...],
  "nextPageToken": "..."
}
```

#### GET /sessions/{id}/activities/{activityId} — Get activity

Response: `Activity` object.

### Sources

#### GET /sources — List sources

Response:
```json
{
  "sources": [...],
  "nextPageToken": "..."
}
```

#### GET /sources/{id} — Get source

Response: `Source` object.

## Data Types

### Session

```json
{
  "name": "sessions/ses_abc123",
  "id": "ses_abc123",
  "prompt": "Fix the login bug",
  "title": "Fix Login Bug",
  "state": "COMPLETED",
  "url": "https://jules.google.com/sessions/ses_abc123",
  "sourceContext": {
    "source": "sources/src_xyz",
    "githubRepoContext": {
      "startingBranch": "main"
    }
  },
  "automationMode": "AUTO_CREATE_PR",
  "outputs": [{"commitSha": "a1b2c3d", "branch": "jules/fix-login-bug", "pullRequestUrl": "https://github.com/owner/repo/pull/42"}],
  "createTime": "2026-03-11T10:00:00Z",
  "updateTime": "2026-03-11T10:05:00Z"
}
```

#### Session states

| State | Description |
|-------|-------------|
| `STATE_UNSPECIFIED` | Default / unset |
| `QUEUED` | Session created, waiting to start |
| `PLANNING` | Jules is analysing the repo and writing a plan |
| `AWAITING_PLAN_APPROVAL` | Plan ready; waiting for human approval |
| `AWAITING_USER_FEEDBACK` | Jules needs additional user input |
| `IN_PROGRESS` | Jules is implementing the changes |
| `PAUSED` | Session suspended temporarily |
| `COMPLETED` | Done; check `outputs` for commit SHAs or PR links |
| `FAILED` | Jules encountered an unrecoverable error |

Terminal states: `COMPLETED`, `FAILED`. No further transitions are possible.

### Activity

```json
{
  "name": "sessions/ses_abc/activities/act_xyz",
  "id": "act_xyz",
  "originator": "JULES",
  "description": "Generated implementation plan",
  "createTime": "2026-03-11T10:02:00Z",
  "artifacts": [],
  "planEvent": {
    "planText": "1. Identify root cause...\n2. Fix handler.go..."
  }
}
```

#### Activity event types (one-of)

| Field | Description |
|-------|-------------|
| `planEvent` | Jules proposed a plan. `planText` contains the plan. |
| `messageEvent` | Conversational message from Jules. |
| `commitEvent` | Jules pushed a commit. Contains `commitSha` and `branch`. |
| `statusEvent` | Session state change. Contains `state` and `message`. |

### Source

```json
{
  "name": "sources/src_abc123",
  "id": "src_abc123",
  "githubRepo": {
    "owner": "my-org",
    "repo": "my-repo",
    "isPrivate": false,
    "defaultBranch": "main",
    "branches": ["main", "develop", "feature/x"]
  }
}
```

## Error Responses

Non-2xx responses return:
```json
{
  "error": {
    "code": 403,
    "status": "PERMISSION_DENIED",
    "message": "API key invalid or not authorised for this resource"
  }
}
```

### Common error codes

| Code | Status | Cause |
|------|--------|-------|
| 400 | `INVALID_ARGUMENT` | Bad request body or missing required field |
| 401 | `UNAUTHENTICATED` | Missing or invalid API key |
| 403 | `PERMISSION_DENIED` | API key not authorised for the resource |
| 404 | `NOT_FOUND` | Session, activity, or source not found |
| 429 | `RESOURCE_EXHAUSTED` | Rate limit exceeded |
| 500 | `INTERNAL` | Jules internal error |

## Rate Limits

Jules is an async service — do not poll more frequently than once every 30 seconds.

## Pagination

List endpoints support `pageToken` query parameter and return `nextPageToken`.
The current CLI implementation does not paginate (returns first page only).
