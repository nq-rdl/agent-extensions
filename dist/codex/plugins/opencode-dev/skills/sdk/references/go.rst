<!-- Source: https://github.com/sst/opencode-sdk-go (README, main) — fetched 2026-06-29. Canonical truth; verify here (and re-check the live page for drift) before authoring OpenCode sdk code. -->

> TRAP: `https://opencode.ai/docs/go/` is NOT the Go SDK — it documents the "OpenCode Zen Go" subscription (curated coding models, billing). The Go *SDK* truth is this repo: `github.com/sst/opencode-sdk-go`. Full API in its `api.md`.

# Opencode Go API Library

The Opencode Go library provides convenient access to the [Opencode REST API](https://opencode.ai/docs) from applications written in Go. Generated with Stainless.

## Installation

```go
import (
	"github.com/sst/opencode-sdk-go" // imported as opencode
)
```

Pin the version:

```sh
go get -u 'github.com/sst/opencode-sdk-go@v0.19.2'
```

## Requirements

This library requires Go 1.22+.

## Usage

The full API of this library can be found in `api.md`.

```go
package main

import (
	"context"
	"fmt"

	"github.com/sst/opencode-sdk-go"
)

func main() {
	client := opencode.NewClient()
	sessions, err := client.Session.List(context.TODO(), opencode.SessionListParams{})
	if err != nil {
		panic(err.Error())
	}
	fmt.Printf("%+v\n", sessions)
}
```

### Request fields

All request parameters are wrapped in a generic `Field` type, used to distinguish zero values from null or omitted fields. Construct fields with `String()`, `Int()`, `Float()`, or the generic `F[T]()`. To send a null, use `Null[T]()`; to send a nonconforming value, use `Raw[T](any)`. Any field not specified is not sent.

```go
params := FooParams{
	Name: opencode.F("hello"),

	// Explicitly send `"description": null`
	Description: opencode.Null[string](),

	Point: opencode.F(opencode.Point{
		X: opencode.Int(0),
		Y: opencode.Int(1),

		// In cases where the API specifies a given type,
		// but you want to send something else, use `Raw`:
		Z: opencode.Raw[int64](0.01), // sends a float
	}),
}
```

### Response objects

All fields in response structs are value types (not pointers or wrappers). If a field is `null`, not present, or invalid, it is its zero value. Each response struct includes a special `JSON` field:

```go
if res.Name == "" {
	res.JSON.Name.IsNull()    // true if `"name"` is not present or explicitly null
	res.JSON.Name.IsMissing() // true if the `"name"` key was not present at all
	if res.JSON.Name.IsInvalid() {
		raw := res.JSON.Name.Raw()
		// ...
	}
}
```

`.JSON` structs include an `Extras`/`ExtraFields` map for properties not in the struct:

```go
body := res.JSON.ExtraFields["my_unexpected_field"].Raw()
```

### RequestOptions (functional options pattern)

Functions in the `option` package return a `RequestOption`. Supply to client or per-request:

```go
client := opencode.NewClient(
	option.WithHeader("X-Some-Header", "custom_header_info"),
)

client.Session.List(context.TODO(), ...,
	option.WithHeader("X-Some-Header", "some_other_custom_header_info"),
	option.WithJSONSet("some.json.path", map[string]string{"my": "object"}),
)
```

### Pagination

`.ListAutoPaging()` iterates items across all pages; `.List()` fetches a single page with helpers like `.GetNextPage()`.

### Errors

Non-success status codes return `*opencode.Error` (with `StatusCode`, `*http.Request`, `*http.Response`). Use `errors.As`:

```go
_, err := client.Session.List(context.TODO(), opencode.SessionListParams{})
if err != nil {
	var apierr *opencode.Error
	if errors.As(err, &apierr) {
		println(string(apierr.DumpRequest(true)))  // serialized HTTP request
		println(string(apierr.DumpResponse(true))) // serialized HTTP response
	}
	panic(err.Error()) // GET "/session": 400 Bad Request { ... }
}
```

### Timeouts

Requests do not time out by default; use context. Per-retry timeout via `option.WithRequestTimeout()`:

```go
ctx, cancel := context.WithTimeout(context.Background(), 5*time.Minute)
defer cancel()
client.Session.List(ctx, opencode.SessionListParams{},
	option.WithRequestTimeout(20*time.Second),
)
```

### File uploads

Parameters for file uploads are typed `param.Field[io.Reader]`. Default multipart file name `anonymous_file`, content-type `application/octet-stream`. Helper: `opencode.FileParam(reader io.Reader, filename string, contentType string)`.

### Retries

Retries 2 times by default (connection errors, 408, 409, 429, >=500). Configure with `option.WithMaxRetries()`:

```go
client := opencode.NewClient(option.WithMaxRetries(0)) // default is 2
client.Session.List(context.TODO(), opencode.SessionListParams{}, option.WithMaxRetries(5))
```

### Accessing raw response data

```go
var response *http.Response
sessions, err := client.Session.List(context.TODO(), opencode.SessionListParams{},
	option.WithResponseInto(&response))
fmt.Printf("Status Code: %d\n", response.StatusCode)
```

### Custom/undocumented requests

Use `client.Get`, `client.Post`, etc. for undocumented endpoints; `option.WithQuerySet()` / `option.WithJSONSet()` for undocumented params; `result.JSON.RawJSON()` / `result.JSON.Foo.Raw()` for undocumented response properties.

### Middleware

```go
func Logger(req *http.Request, next option.MiddlewareNext) (res *http.Response, err error) {
	res, err = next(req)
	return res, err
}
client := opencode.NewClient(option.WithMiddleware(Logger))
```

Replace the default `http.Client` with `option.WithHTTPClient(client)`.
