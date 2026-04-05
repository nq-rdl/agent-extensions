# Security Audit Checklist for Error Handling

Run through these questions before shipping error handling code.

---

## For Each Error Returned to a Caller

### 1. Is the caller external or untrusted?

- **YES** — Return a generic, static message with a request ID. Never expose the raw error.
- **NO** (internal service you control) — OK to propagate domain errors, but still avoid raw DB/infra errors.

### 2. Does the error message contain sensitive data?

Sensitive data includes: file paths, SQL queries, stack traces, credentials, tokens,
internal hostnames, IP addresses, user PII, or infrastructure topology.

- **YES** — Redact before logging. Never include in client responses.
- **NO** — Safe to include in structured logs.

### 3. Will this error cross a trust boundary?

Trust boundaries include: HTTP response, gRPC response, CLI output, log aggregation
service, error tracking service (Sentry, Datadog), message queue.

- **YES** — Translate to a domain error at the boundary using the DomainError pattern.
- **NO** — Standard error wrapping with `fmt.Errorf("context: %w", err)` is fine.

### 4. Is the system in a corrupted or unknown state?

- **YES** — Fail securely. Return a generic error to the client, log the full details
  with a correlation ID, and consider whether the process should exit (e.g., `log.Fatal`
  for unrecoverable corruption).
- **NO** — Normal error handling applies.

### 5. Do developers need the internal details?

- **YES** — Store them in structured logs with a correlation ID (request_id).
  Never include them in client-facing responses.
- **NO** — A generic domain error is sufficient.

---

## For Each Log Statement Involving Errors

### 1. Are you logging a request or response struct directly?

- **YES** — Stop. Log individual allowlisted fields instead. Structs may gain
  sensitive fields later, and your log statement will silently start leaking them.

### 2. Does any logged value implement `slog.LogValuer`?

- If the type contains sensitive fields and doesn't implement `LogValuer`,
  add a `LogValue()` method that redacts sensitive fields.

### 3. Are you logging HTTP headers?

- Always strip `Authorization`, `Cookie`, `Set-Cookie`, and API key headers
  before logging. Use the `SafeHeaders` helper.

---

## Common Mistakes

| Mistake | Why it's dangerous | Fix |
|---------|-------------------|-----|
| `http.Error(w, err.Error(), 500)` | Sends raw error text to client | Use `writeError` pattern with DomainError |
| `fmt.Fprintf(w, "error: %v", err)` | `%v` calls `Error()` on the raw error | Translate to domain error first |
| `slog.Error("failed", "request", r)` | Logs entire request including auth headers | Log individual safe fields via allowlist |
| `return fmt.Errorf("query %s failed: %w", sql, err)` | Embeds SQL query text in error chain | Use `NewInternal(err)` with safe metadata |
| `log.Printf("auth failed for %s: %v", password, err)` | Logs the password | Log username only, never credentials |
| `json.NewEncoder(w).Encode(err)` | Serializes internal error fields to JSON | Encode a safe response struct instead |
