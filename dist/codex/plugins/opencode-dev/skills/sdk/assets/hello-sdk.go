// Drive OpenCode from Go via the official SDK.
// Verify the surface in references/go.rst and re-check github.com/anomalyco/opencode-sdk-go
// (module path github.com/sst/opencode-sdk-go; pin and Go version: see SKILL.md provenance).
//
// v0.19.2's default base URL is http://localhost:54321/ (option.WithEnvironmentProduction),
// not the 4096 that `opencode serve` listens on, so set it explicitly (or export
// OPENCODE_BASE_URL). Add auth with option.WithHeader for OPENCODE_SERVER_PASSWORD
// basic auth.
package main

import (
	"context"
	"errors"
	"fmt"
	"time"

	"github.com/sst/opencode-sdk-go"
	"github.com/sst/opencode-sdk-go/option"
)

func main() {
	client := opencode.NewClient(
		option.WithBaseURL("http://127.0.0.1:4096/"),
		option.WithRequestTimeout(30*time.Second), // there is no default timeout
	)

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
