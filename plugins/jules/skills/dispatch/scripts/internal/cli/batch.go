package cli

import (
	"context"
	"encoding/json"
	"flag"
	"fmt"
	"maps"
	"os"
	"slices"
	"strings"

	"github.com/nq-rdl/agent-skills/skills/jules/scripts/internal/model"
)

func runBatch(args []string) int {
	if len(args) == 0 {
		return exitErr("batch: action required (status)")
	}
	switch args[0] {
	case "status":
		return batchStatus(args[1:])
	default:
		return exitErr("batch: unknown action %q", args[0])
	}
}

// batchManifest is the JSON structure for a manifest file.
type batchManifest struct {
	Sessions []string `json:"sessions"`
}

// batchResult pairs a fetched session with any per-session error.
type batchResult struct {
	session model.Session
	err     error
}

func batchStatus(args []string) int {
	fs := flag.NewFlagSet("jules batch status", flag.ContinueOnError)
	var (
		cfg  cmdConfig
		file string
	)
	cfg.add(fs)
	fs.StringVar(&file, "file", "", "Path to JSON manifest file containing session IDs")
	if err := fs.Parse(args); err != nil {
		return 1
	}

	ids, err := collectSessionIDs(fs.Args(), file)
	if err != nil {
		return exitErr("batch status: %v", err)
	}
	if len(ids) == 0 {
		return exitErr("batch status: no session IDs provided (use positional arg or --file)")
	}

	client, err := cfg.newClient()
	if err != nil {
		return exitErr("%v", err)
	}

	ctx := context.Background()

	results := make([]batchResult, len(ids))
	for i, id := range ids {
		s, err := client.GetSession(ctx, id)
		if err != nil {
			results[i] = batchResult{session: model.Session{ID: id}, err: err}
		} else {
			results[i] = batchResult{session: *s}
		}
	}

	if cfg.human {
		outputBatchStatusTable(results)
		return 0
	}

	// JSON output: array of sessions (errors get state "ERROR").
	sessions := make([]model.Session, len(results))
	for i, r := range results {
		if r.err != nil {
			sessions[i] = model.Session{ID: r.session.ID, State: "ERROR"}
		} else {
			sessions[i] = r.session
		}
	}
	if err := outputJSON(sessions); err != nil {
		return exitErr("%v", err)
	}
	return 0
}

// collectSessionIDs gathers session IDs from positional args (comma-separated)
// and/or a manifest file.
func collectSessionIDs(positional []string, file string) ([]string, error) {
	var ids []string

	// Collect from positional args (comma-separated).
	for _, arg := range positional {
		for id := range strings.SplitSeq(arg, ",") {
			id = strings.TrimSpace(id)
			if id != "" {
				ids = append(ids, id)
			}
		}
	}

	// Collect from manifest file.
	if file != "" {
		data, err := os.ReadFile(file)
		if err != nil {
			return nil, fmt.Errorf("read manifest: %w", err)
		}
		var manifest batchManifest
		if err := json.Unmarshal(data, &manifest); err != nil {
			return nil, fmt.Errorf("parse manifest: %w", err)
		}
		ids = append(ids, manifest.Sessions...)
	}

	return ids, nil
}

// outputBatchStatusTable prints a human-readable table with a summary line.
func outputBatchStatusTable(results []batchResult) {
	w := newTab()
	fmt.Fprintln(w, "ID\tSTATE\tTITLE\tCREATED\tUPDATED")
	counts := make(map[string]int)
	for _, r := range results {
		state := r.session.State
		if r.err != nil {
			state = "ERROR"
		}
		counts[state]++
		fmt.Fprintf(w, "%s\t%s\t%s\t%s\t%s\n",
			r.session.ID, state,
			truncate(r.session.Title, 40),
			fmtTime(r.session.CreateTime),
			fmtTime(r.session.UpdateTime))
	}
	w.Flush()

	// Summary line.
	keys := slices.Sorted(maps.Keys(counts))
	parts := make([]string, 0, len(keys))
	for _, k := range keys {
		parts = append(parts, fmt.Sprintf("%d %s", counts[k], k))
	}
	fmt.Printf("\nSummary: %s\n", strings.Join(parts, ", "))
}
