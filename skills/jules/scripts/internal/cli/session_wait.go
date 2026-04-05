package cli

import (
	"context"
	"flag"
	"fmt"
	"os"
	"slices"
	"time"

	"github.com/nq-rdl/agent-skills/skills/jules/scripts/internal/model"
)

// terminalStates are session states that indicate the session has finished
// (or requires user intervention and will not progress on its own).
var terminalStates = []string{"COMPLETED", "FAILED", "AWAITING_PLAN_APPROVAL"}

func sessionWait(args []string) int {
	fs := flag.NewFlagSet("jules session wait", flag.ContinueOnError)
	var (
		cfg         cmdConfig
		timeoutStr  string
		intervalStr string
		targetState string
	)
	cfg.add(fs)
	fs.StringVar(&timeoutStr, "timeout", "0s", "Max time to wait (e.g. 5m, 1h); 0 = no timeout")
	fs.StringVar(&intervalStr, "interval", "10s", "Poll interval (e.g. 10s, 30s)")
	fs.StringVar(&targetState, "state", "", "Target state to wait for (default: any terminal state)")

	if err := fs.Parse(args); err != nil {
		return 1
	}

	if fs.NArg() < 1 {
		return exitErr("session wait: session ID required")
	}
	id := fs.Arg(0)

	timeout, err := time.ParseDuration(timeoutStr)
	if err != nil {
		return exitErr("session wait: invalid --timeout: %v", err)
	}
	interval, err := time.ParseDuration(intervalStr)
	if err != nil {
		return exitErr("session wait: invalid --interval: %v", err)
	}

	client, err := cfg.newClient()
	if err != nil {
		return exitErr("%v", err)
	}

	ctx := context.Background()
	if timeout > 0 {
		var cancel context.CancelFunc
		ctx, cancel = context.WithTimeout(ctx, timeout)
		defer cancel()
	}

	return pollSession(ctx, client, id, targetState, interval, cfg.human)
}

// sessionGetter is the subset of *api.Client needed by pollSession.
type sessionGetter interface {
	GetSession(ctx context.Context, id string) (*model.Session, error)
}

// pollSession polls until the session reaches the desired state.
// Returns exit code 0 on success, 3 on timeout, or 1/2 on error.
func pollSession(ctx context.Context, client sessionGetter, id, targetState string, interval time.Duration, human bool) int {
	start := time.Now()
	ticker := time.NewTicker(interval)
	defer ticker.Stop()

	for {
		session, err := client.GetSession(ctx, id)
		if err != nil {
			if ctx.Err() != nil {
				fmt.Fprintf(os.Stderr, "jules: session wait: timed out after %s\n", time.Since(start).Truncate(time.Second))
				return 3
			}
			return handleErr(err)
		}

		if isTargetState(session.State, targetState) {
			if human {
				outputSessionTable([]model.Session{*session})
				return 0
			}
			if err := outputJSON(session); err != nil {
				return exitErr("%v", err)
			}
			return 0
		}

		fmt.Fprintf(os.Stderr, "waiting... state=%s (elapsed %s)\n",
			session.State, time.Since(start).Truncate(time.Second))

		select {
		case <-ctx.Done():
			fmt.Fprintf(os.Stderr, "jules: session wait: timed out after %s (last state: %s)\n",
				time.Since(start).Truncate(time.Second), session.State)
			return 3
		case <-ticker.C:
		}
	}
}

// isTargetState returns true if the session state matches the desired condition.
// If targetState is empty, any terminal state matches.
func isTargetState(state, targetState string) bool {
	if targetState != "" {
		return state == targetState
	}
	return slices.Contains(terminalStates, state)
}
