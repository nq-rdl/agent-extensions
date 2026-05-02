package cli

import (
	"context"
	"flag"
	"fmt"
	"strings"

	"github.com/nq-rdl/agent-skills/skills/jules/scripts/internal/model"
)

func runSource(args []string) int {
	if len(args) == 0 {
		return exitErr("source: action required (list|get|add)")
	}
	switch args[0] {
	case "list":
		return sourceList(args[1:])
	case "get":
		return sourceGet(args[1:])
	case "add":
		return sourceAdd(args[1:])
	default:
		return exitErr("source: unknown action %q", args[0])
	}
}

func sourceList(args []string) int {
	fs := flag.NewFlagSet("jules source list", flag.ContinueOnError)
	var cfg cmdConfig
	cfg.add(fs)
	if err := fs.Parse(args); err != nil {
		return 1
	}

	client, err := cfg.newClient()
	if err != nil {
		return exitErr("%v", err)
	}

	sources, err := client.ListSources(context.Background())
	if err != nil {
		return handleErr(err)
	}

	if cfg.human {
		outputSourceTable(sources)
		return 0
	}
	if err := outputJSON(sources); err != nil {
		return exitErr("%v", err)
	}
	return 0
}

func sourceGet(args []string) int {
	fs := flag.NewFlagSet("jules source get", flag.ContinueOnError)
	var cfg cmdConfig
	cfg.add(fs)
	if err := fs.Parse(args); err != nil {
		return 1
	}
	if fs.NArg() < 1 {
		return exitErr("source get: source ID required")
	}
	id := fs.Arg(0)

	client, err := cfg.newClient()
	if err != nil {
		return exitErr("%v", err)
	}

	source, err := client.GetSource(context.Background(), id)
	if err != nil {
		return handleErr(err)
	}

	if cfg.human {
		outputSourceTable([]model.Source{*source})
		return 0
	}
	if err := outputJSON(source); err != nil {
		return exitErr("%v", err)
	}
	return 0
}

func sourceAdd(args []string) int {
	fs := flag.NewFlagSet("jules source add", flag.ContinueOnError)
	var (
		cfg   cmdConfig
		owner string
		repo  string
	)
	cfg.add(fs)
	fs.StringVar(&owner, "owner", "", "GitHub repository owner")
	fs.StringVar(&repo, "repo", "", "GitHub repository name")
	if err := fs.Parse(args); err != nil {
		return 1
	}

	// Accept owner/repo as positional argument if flags not provided.
	if owner == "" && repo == "" && fs.NArg() >= 1 {
		parts := strings.SplitN(fs.Arg(0), "/", 2)
		if len(parts) == 2 && parts[0] != "" && parts[1] != "" {
			owner, repo = parts[0], parts[1]
		} else {
			return exitErr("source add: expected owner/repo format, got %q", fs.Arg(0))
		}
	}

	if owner == "" || repo == "" {
		return exitErr("source add: owner/repo required (positional arg or --owner + --repo)")
	}

	client, err := cfg.newClient()
	if err != nil {
		return exitErr("%v", err)
	}

	source, err := client.CreateSource(context.Background(), owner, repo)
	if err != nil {
		return handleErr(err)
	}

	if cfg.human {
		fmt.Printf("registered source %s/%s (ID: %s)\n", owner, repo, source.ID)
		outputSourceTable([]model.Source{*source})
		return 0
	}
	if err := outputJSON(source); err != nil {
		return exitErr("%v", err)
	}
	return 0
}
