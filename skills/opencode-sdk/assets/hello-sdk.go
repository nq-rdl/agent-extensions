// Drive OpenCode from Go via the official SDK.
// Verify the surface in references/go.md and re-check github.com/sst/opencode-sdk-go for drift.
//
// Official module (NOT the anomalyco/manno23 forks):
//   go get -u 'github.com/sst/opencode-sdk-go@v0.19.2'   // requires Go 1.22+
//
// NewClient() targets a running `opencode serve` (default http://127.0.0.1:4096).
// Point it elsewhere or add auth with option.With* (e.g. option.WithBaseURL,
// option.WithHeader for OPENCODE_SERVER_PASSWORD basic auth).
package main

import (
	"context"
	"errors"
	"fmt"

	"github.com/sst/opencode-sdk-go"
)

func main() {
	client := opencode.NewClient()

	sessions, err := client.Session.List(context.TODO(), opencode.SessionListParams{})
	if err != nil {
		// All request params are wrapped in opencode.F(...) / Null[T]() / Raw[T]().
		var apiErr *opencode.Error
		if errors.As(err, &apiErr) {
			fmt.Println(string(apiErr.DumpRequest(true)))
		}
		panic(err.Error())
	}

	fmt.Printf("%+v\n", sessions)
}
