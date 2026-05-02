package main

import (
	"context"
	"os"

	"charm.land/fang/v2"
)

// version and commit are injected at build time via -ldflags.
var (
	version = "dev"
	commit  = "none"
)

func main() {
	if err := fang.Execute(
		context.Background(),
		newRootCmd(),
		fang.WithVersion(version),
		fang.WithCommit(commit),
	); err != nil {
		os.Exit(1)
	}
}
