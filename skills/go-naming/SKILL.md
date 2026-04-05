---
name: go-naming
license: MIT
description: >-
  Go naming conventions and idiomatic identifier choices. Use when writing new
  Go code, reviewing Go naming decisions, naming packages, types, functions,
  variables, interfaces, constants, or error values — or when the user asks
  about Go naming style, MixedCaps, getter/setter naming, receiver names,
  initialism casing (URL, ID, HTTP), or when they are struggling with what to
  name something in Go. Covers Effective Go, Google Go Style Guide, and
  community conventions.
metadata:
  repo: https://github.com/nq-rdl/agent-skills
---

# Go Naming Conventions

A good name is **consistent** (easy to guess), **short** (easy to type), and
**accurate** (easy to understand). Name length should be proportional to scope
and inversely proportional to usage frequency.

> Sources: [Effective Go](https://go.dev/doc/effective_go),
> [Google Go Style Decisions](https://google.github.io/styleguide/go/decisions.html),
> [What's in a name?](https://go.dev/talks/2014/names.slide),
> [Alex Edwards — Go Naming Conventions](https://www.alexedwards.net/blog/go-naming-conventions)

## Case Convention

Always `MixedCaps` or `mixedCaps` — never `snake_case`. The only exception is
test function names in `*_test.go` files, which may use underscores.

## Packages

- **Lowercase, single-word, no underscores or mixedCaps**: `bytes`, `http`, `bufio`
- **Short and concise** — everyone using it types the name
- **Avoid generic names**: never `util`, `common`, `helpers`, `types`, `misc`
- **Match the last path component**: `encoding/json` → `package json`
- **Don't stutter with exported names**: `bytes.Buffer` not `bytes.ByteBuffer`

```go
// ✓ Good — constructor doesn't repeat the package name
ring.New()       // not ring.NewRing()
bufio.Reader     // not bufio.BufReader

// ✗ Bad — generic, uninformative
package util
package common
package helpers
```

## Variables

Scope determines length — the greater the distance between declaration and use,
the longer the name should be.

| Scope | Style | Example |
|-------|-------|---------|
| 1–7 lines | Short, terse | `i`, `r`, `b`, `ok` |
| 8–15 lines | Moderately descriptive | `count`, `reader` |
| 16–25 lines | Specific | `userCount`, `connPool` |
| 25+ lines | Longer, unambiguous | `requestTimeout`, `primaryDatabase` |

**Don't include the type in the name**:

```go
// ✓ Good
var users int
var name string
var primary *Project

// ✗ Bad
var numUsers int        // "num" is type-like
var nameString string   // type in name
var primaryProject *Project  // type in name
```

**Don't repeat context already visible from the enclosing function or type**:

```go
func (db *DB) UserCount() (int, error) {
    var count int64  // ✓ not "userCount" — context is clear
    // ...
}
```

### Single-Letter Variables

Use only where the full word would be repetitive and the meaning is obvious:

- `r` for `io.Reader` or `*http.Request`
- `w` for `io.Writer` or `http.ResponseWriter`
- `b` for `*bytes.Buffer` or `[]byte`
- `i`, `j`, `k` for loop indices
- `s` for `string` parameters
- `t` for `*testing.T`

## Functions and Methods

### Getters — no `Get` prefix

```go
// ✓ Good
owner := obj.Owner()
obj.SetOwner(user)

// ✗ Bad
owner := obj.GetOwner()
```

Use `Compute`, `Fetch`, or `List` instead of `Get` when the operation is
expensive, involves I/O, or returns a collection.

### Constructors

```go
// Single primary type exported by the package
func New() *Ring              // ring.New()

// Multiple types or disambiguation needed
func NewReader(r io.Reader) *Reader   // bufio.NewReader()
func NewWithName(name string) *Widget // widget.NewWithName()
```

### Don't repeat the package name

```go
// ✓ Good
http.Get()        // not http.HTTPGet()
json.Marshal()    // not json.JSONMarshal()
db.Load()         // not db.LoadFromDatabase()
```

## Interfaces

### Single-method — append `-er`

```go
type Reader interface {
    Read(p []byte) (n int, err error)
}

type Stringer interface {
    String() string
}

type Execer interface {
    Exec(query string, args []Value) (Result, error)
}
```

### Multi-method — describe the capability

```go
type ReadWriter interface { ... }   // composition
type net.Conn                       // connection capability
type http.ResponseWriter            // purpose-driven
```

### Honor canonical signatures

`Read`, `Write`, `Close`, `Flush`, `String` have canonical meanings. Don't use
these names unless your method has the same signature and semantics.

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

## Constants

**MixedCaps, always** — never `ALL_CAPS`:

```go
// ✓ Good
const MaxPacketSize = 512
const defaultTimeout = 30 * time.Second

// ✗ Bad
const MAX_PACKET_SIZE = 512
const kMaxBufferSize = 1024
```

Name constants by their **role**, not their value. If a constant has no role
beyond its value, it shouldn't be a named constant.

## Errors

```go
// Error types: FooError
type ExitError struct { ... }
type PathError struct { ... }

// Sentinel error values: ErrFoo
var ErrNotFound = errors.New("not found")
var ErrFormat   = errors.New("image: unknown format")
```

## Initialisms and Acronyms

Initialisms keep uniform case — all caps when exported, all lower when not:

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

## Named Return Values

Use only for documentation on exported functions, not for saving a `var` line:

```go
// ✓ Good — names document what's returned
func Copy(dst Writer, src Reader) (written int64, err error)
func ScanBytes(data []byte, atEOF bool) (advance int, token []byte, err error)
```

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
