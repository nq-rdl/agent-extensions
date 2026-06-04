package cli

import (
	"context"
	"encoding/json"
	"flag"
	"fmt"
	"os"
	"slices"
	"strconv"
	"strings"
	"time"

	"github.com/nq-rdl/agent-skills/skills/jules/scripts/internal/model"
)

// defaultCleanupStates are the terminal states targeted by cleanup.
var defaultCleanupStates = []string{model.StateCompleted, model.StateFailed}

func sessionCleanup(args []string) int {
	fs := flag.NewFlagSet("jules session cleanup", flag.ContinueOnError)
	var (
		cfg      cmdConfig
		olderStr string
		stateStr string
		archive  string
		dryRun   bool
	)
	cfg.add(fs)
	fs.StringVar(&olderStr, "older-than", "7d", "Delete sessions older than this duration (e.g. 7d, 24h)")
	fs.StringVar(&stateStr, "state", "", "Comma-separated states to target (default: COMPLETED,FAILED)")
	fs.StringVar(&archive, "archive", "", "JSONL file to append session data to before deleting")
	fs.BoolVar(&dryRun, "dry-run", false, "Preview what would be deleted without making changes")

	if err := fs.Parse(args); err != nil {
		return 1
	}

	cutoff, err := parseDuration(olderStr)
	if err != nil {
		return exitErr("session cleanup: bad --older-than: %v", err)
	}

	states := defaultCleanupStates
	if stateStr != "" {
		states = strings.Split(stateStr, ",")
		for i := range states {
			states[i] = strings.TrimSpace(states[i])
		}
	}

	client, err := cfg.newClient()
	if err != nil {
		return exitErr("%v", err)
	}

	ctx := context.Background()
	sessions, err := client.ListSessions(ctx)
	if err != nil {
		return handleErr(err)
	}

	threshold := time.Now().Add(-cutoff)
	candidates := filterSessions(sessions, states, threshold)

	if len(candidates) == 0 {
		if cfg.human {
			fmt.Println("no sessions match cleanup criteria")
		} else {
			_ = outputJSON(map[string]any{"cleaned": 0, "sessions": []string{}})
		}
		return 0
	}

	if dryRun {
		if cfg.human {
			fmt.Printf("dry run: %d session(s) would be cleaned up:\n", len(candidates))
			outputSessionTable(candidates)
		} else {
			ids := make([]string, len(candidates))
			for i, s := range candidates {
				ids[i] = s.ID
			}
			_ = outputJSON(map[string]any{"dry_run": true, "count": len(candidates), "sessions": ids})
		}
		return 0
	}

	// Open archive file if requested (append mode).
	var archiveFile *os.File
	if archive != "" {
		archiveFile, err = os.OpenFile(archive, os.O_APPEND|os.O_CREATE|os.O_WRONLY, 0o644)
		if err != nil {
			return exitErr("open archive file: %v", err)
		}
		defer archiveFile.Close()
	}

	var deleted []string
	var errors []string
	enc := json.NewEncoder(archiveFile) // only used when archiveFile != nil

	for _, s := range candidates {
		// Archive first: write session to JSONL before deleting.
		if archiveFile != nil {
			if err := enc.Encode(s); err != nil {
				errors = append(errors, fmt.Sprintf("%s: archive write failed: %v", s.ID, err))
				continue // skip delete if archive fails
			}
		}

		if err := client.DeleteSession(ctx, s.ID); err != nil {
			errors = append(errors, fmt.Sprintf("%s: delete failed: %v", s.ID, err))
			continue
		}
		deleted = append(deleted, s.ID)
	}

	if cfg.human {
		fmt.Printf("cleaned up %d of %d session(s)\n", len(deleted), len(candidates))
		if archiveFile != nil {
			fmt.Printf("archived to %s\n", archive)
		}
		for _, e := range errors {
			fmt.Fprintf(os.Stderr, "  error: %s\n", e)
		}
	} else {
		_ = outputJSON(map[string]any{
			"cleaned":  len(deleted),
			"deleted":  deleted,
			"errors":   errors,
			"archived": archive,
		})
	}

	if len(errors) > 0 {
		return 2
	}
	return 0
}

// filterSessions returns sessions matching the given states whose createTime
// is before the threshold.
func filterSessions(sessions []model.Session, states []string, threshold time.Time) []model.Session {
	var out []model.Session
	for _, s := range sessions {
		if !slices.Contains(states, s.State) {
			continue
		}
		created, err := time.Parse(time.RFC3339, s.CreateTime)
		if err != nil {
			continue // skip sessions with unparseable timestamps
		}
		if created.Before(threshold) {
			out = append(out, s)
		}
	}
	return out
}

// parseDuration extends time.ParseDuration with support for a "d" (days) suffix.
// Examples: "7d" → 168h, "30d" → 720h, "24h" → 24h, "2h30m" → 2h30m.
func parseDuration(s string) (time.Duration, error) {
	if rest, ok := strings.CutSuffix(s, "d"); ok {
		days, err := strconv.Atoi(rest)
		if err != nil {
			return 0, fmt.Errorf("invalid day count %q", s)
		}
		if days < 0 {
			return 0, fmt.Errorf("duration must be positive: %q", s)
		}
		return time.Duration(days) * 24 * time.Hour, nil
	}
	d, err := time.ParseDuration(s)
	if err != nil {
		return 0, err
	}
	if d < 0 {
		return 0, fmt.Errorf("duration must be positive: %q", s)
	}
	return d, nil
}
