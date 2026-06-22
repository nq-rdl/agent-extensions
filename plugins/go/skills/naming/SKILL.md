---
license: CC-BY-4.0
description: >-
  Go naming conventions and idiomatic identifier choices. Use when writing new
  Go code, reviewing Go naming decisions, naming packages, types, functions,
  variables, interfaces, constants, or error values — or when the user asks
  about Go naming style, MixedCaps, getter/setter naming, receiver names,
  initialism casing (URL, ID, HTTP), or when they are struggling with what to
  name something in Go. Covers Effective Go, Google Go Style Guide, and
  community conventions.
metadata:
  repo: https://github.com/nq-rdl/agent-extensions
---

# Go Naming Conventions

> Full rationale: [Effective Go](https://go.dev/doc/effective_go) and the
> [Google Go Style Guide](https://google.github.io/styleguide/go/decisions.html).
> This skill keeps only the items models actually slip on plus a checklist — it
> does not restate the guides.

## Initialisms and Acronyms

Initialisms keep uniform case — all caps when exported, all lower when not.
Never title-case them (`Url`, `Id`, `Http`).

| Term | Exported | Unexported | Wrong |
|------|----------|------------|-------|
| URL | `URL` | `url` | `Url` |
| ID | `ID` | `id` | `Id` |
| HTTP | `HTTP` | `http` | `Http` |
| XML API | `XMLAPI` | `xmlAPI` | `XmlApi` |
| gRPC | `GRPC` | `gRPC` | `Grpc` |
| DDoS | `DDoS` | `ddos` | `DDOS` |
| DB | `DB` | `db` | `Db` |

```go
// ✓ Good
func ServeHTTP(w http.ResponseWriter, r *http.Request)
type URLValidator struct{}
var userID string

// ✗ Bad
func ServeHttp(...)
type UrlValidator struct{}
var odpsId string
```

## Getters — no `Get` prefix

```go
// ✓ Good
owner := obj.Owner()
obj.SetOwner(user)

// ✗ Bad
owner := obj.GetOwner()
```

Use `Compute`, `Fetch`, or `List` instead of `Get` when the operation is
expensive, involves I/O, or returns a collection.

## Don't stutter

Drop the package name from exported identifiers — the caller already qualifies
with it.

```go
// ✓ Good
ring.New()        // not ring.NewRing()
bytes.Buffer      // not bytes.ByteBuffer
http.Get()        // not http.HTTPGet()
json.Marshal()    // not json.JSONMarshal()

// ✗ Bad
ring.NewRing()
bufio.BufReader
```

## Receivers

- **One or two characters** reflecting the type name
- **Consistent** across all methods of the type
- **Never** use `this` or `self`

```go
func (b *Buffer) Read(p []byte) (n int, err error)
func (r Rectangle) Size() Point
func (sh serverHandler) ServeHTTP(w ResponseWriter, req *Request)
```

| Avoid | Use |
|-------|-----|
| `func (this *ReportWriter)` | `func (w *ReportWriter)` |
| `func (self *Scanner)` | `func (s *Scanner)` |
| `func (tray Tray)` | `func (t Tray)` |
| `func (info *ResearchInfo)` | `func (ri *ResearchInfo)` |

## Summary Checklist

1. Use `MixedCaps` — never underscores (except test names)
2. Short names for small scopes, long names for large scopes
3. Don't stutter — `pkg.New()` not `pkg.NewPkg()`
4. Don't embed the type — `users` not `userSlice`
5. Don't embed context — `count` not `userCount` inside `UserCount()`
6. Getters have no `Get` prefix — `Owner()` not `GetOwner()`
7. Interfaces: `-er` suffix for single-method, descriptive for multi-method
8. Receivers: 1–2 chars, consistent, never `this`/`self`
9. Constants: `MixedCaps` not `ALL_CAPS`
10. Errors: `ErrFoo` for values, `FooError` for types
11. Initialisms: `URL`/`url`, `ID`/`id` — never `Url`/`Id`
