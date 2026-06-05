package cli

import (
	"context"
	"flag"

	"github.com/nq-rdl/agent-skills/skills/jules/scripts/internal/model"
)

func runActivity(args []string) int {
	if len(args) == 0 {
		return exitErr("activity: action required (list|get)")
	}
	switch args[0] {
	case "list":
		return activityList(args[1:])
	case "get":
		return activityGet(args[1:])
	default:
		return exitErr("activity: unknown action %q", args[0])
	}
}

func activityList(args []string) int {
	fs := flag.NewFlagSet("jules activity list", flag.ContinueOnError)
	var (
		cfg       cmdConfig
		sessionID string
	)
	cfg.add(fs)
	fs.StringVar(&sessionID, "session", "", "Session ID (required)")
	if err := fs.Parse(args); err != nil {
		return 1
	}
	if sessionID == "" {
		return exitErr("activity list: --session is required")
	}

	client, err := cfg.newClient()
	if err != nil {
		return exitErr("%v", err)
	}

	activities, err := client.ListActivities(context.Background(), sessionID)
	if err != nil {
		return handleErr(err)
	}

	if cfg.human {
		outputActivityTable(activities)
		return 0
	}
	if err := outputJSON(activities); err != nil {
		return exitErr("%v", err)
	}
	return 0
}

func activityGet(args []string) int {
	fs := flag.NewFlagSet("jules activity get", flag.ContinueOnError)
	var (
		cfg       cmdConfig
		sessionID string
	)
	cfg.add(fs)
	fs.StringVar(&sessionID, "session", "", "Session ID (required)")
	if err := fs.Parse(args); err != nil {
		return 1
	}
	if sessionID == "" {
		return exitErr("activity get: --session is required")
	}
	if fs.NArg() < 1 {
		return exitErr("activity get: activity ID required")
	}
	activityID := fs.Arg(0)

	client, err := cfg.newClient()
	if err != nil {
		return exitErr("%v", err)
	}

	activity, err := client.GetActivity(context.Background(), sessionID, activityID)
	if err != nil {
		return handleErr(err)
	}

	if cfg.human {
		outputActivityTable([]model.Activity{*activity})
		return 0
	}
	if err := outputJSON(activity); err != nil {
		return exitErr("%v", err)
	}
	return 0
}
