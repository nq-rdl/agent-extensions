package cli

import (
	"cmp"
	"context"
	"flag"
	"fmt"
	"os"
	"slices"
	"strings"

	"github.com/nq-rdl/agent-skills/skills/jules/scripts/internal/model"
)

// defaultAutomationMode is AUTO_CREATE_PR so Jules automatically creates a
// branch and pull request when the session completes. This sidesteps the
// AWAITING_PLAN_APPROVAL state-reporting bug (#23) and removes the need for
// manual patch extraction.
const defaultAutomationMode = "AUTO_CREATE_PR"

// resolveAutomationMode returns the effective automation mode: the explicit
// flag value if non-empty, otherwise the default.
func resolveAutomationMode(flagValue string) string {
	return cmp.Or(flagValue, defaultAutomationMode)
}

func runSession(args []string) int {
	if len(args) == 0 {
		fmt.Fprintln(os.Stderr, "jules session: action required (create|list|get|delete|message|approve|extract|wait|cleanup)")
		return 1
	}
	switch args[0] {
	case "create":
		return sessionCreate(args[1:])
	case "list":
		return sessionList(args[1:])
	case "get":
		return sessionGet(args[1:])
	case "delete":
		return sessionDelete(args[1:])
	case "message":
		return sessionMessage(args[1:])
	case "approve":
		return sessionApprove(args[1:])
	case "extract":
		return sessionExtract(args[1:])
	case "wait":
		return sessionWait(args[1:])
	case "cleanup":
		return sessionCleanup(args[1:])
	default:
		return exitErr("session: unknown action %q", args[0])
	}
}

func sessionCreate(args []string) int {
	fs := flag.NewFlagSet("jules session create", flag.ContinueOnError)
	var (
		cfg            cmdConfig
		prompt         string
		source         string
		branch         string
		requireApprove bool
		automationMode string
	)
	cfg.add(fs)
	fs.StringVar(&prompt, "prompt", "", "Coding task description (required)")
	fs.StringVar(&source, "source", "", "Jules source ID (auto-detected from git remote if omitted)")
	fs.StringVar(&branch, "branch", "", "Starting git branch (default: repo default branch)")
	fs.BoolVar(&requireApprove, "require-plan-approval", false, "Pause for plan approval before executing")
	fs.StringVar(&automationMode, "automation-mode", "", "Automation mode (e.g. FULL_AUTO)")

	if err := fs.Parse(args); err != nil {
		return 1
	}
	if prompt == "" {
		return exitErr("session create: --prompt is required")
	}

	client, err := cfg.newClient()
	if err != nil {
		return exitErr("%v", err)
	}

	ctx := context.Background()

	// Auto-detect source from git remote if not given.
	if source == "" {
		source, err = detectSource(ctx, client)
		if err != nil {
			fmt.Fprintf(os.Stderr, "jules: could not auto-detect source: %v\n", err)
			fmt.Fprintln(os.Stderr, "       Use --source to specify a Jules source ID")
			return 1
		}
	}

	// Normalize to full resource name expected by the API.
	source = normalizeSourceName(source)

	req := &model.CreateSessionRequest{
		Prompt:              prompt,
		RequirePlanApproval: requireApprove,
		AutomationMode:      resolveAutomationMode(automationMode),
	}
	if source != "" {
		req.SourceContext = &model.SourceContext{
			Source:            source,
			GithubRepoContext: &model.GithubRepoContext{StartingBranch: branch},
		}
	}

	session, err := client.CreateSession(ctx, req)
	if err != nil {
		return handleErr(err)
	}

	if cfg.human {
		outputSessionTable([]model.Session{*session})
		return 0
	}
	if err := outputJSON(session); err != nil {
		return exitErr("%v", err)
	}
	return 0
}

// sourceDetector is the interface needed by detectSource: list existing sources
// and optionally create a new one when no match is found.
type sourceDetector interface {
	ListSources(context.Context) ([]model.Source, error)
	CreateSource(ctx context.Context, owner, repo string) (*model.Source, error)
}

// detectSource lists Jules sources and finds one matching the current git repo.
// If no existing source matches, it auto-registers the repo and returns the
// newly created source name.
func detectSource(ctx context.Context, client sourceDetector) (string, error) {
	owner, repo, err := DetectRepo()
	if err != nil {
		return "", err
	}

	sources, err := client.ListSources(ctx)
	if err != nil {
		return "", err
	}

	idx := slices.IndexFunc(sources, func(s model.Source) bool {
		return s.GithubRepo != nil &&
			s.GithubRepo.Owner == owner &&
			s.GithubRepo.Repo == repo
	})
	if idx >= 0 {
		return sources[idx].Name, nil
	}

	// No existing source — auto-register this repo.
	fmt.Fprintf(os.Stderr, "jules: auto-registering source %s/%s\n", owner, repo)
	source, err := client.CreateSource(ctx, owner, repo)
	if err != nil {
		return "", fmt.Errorf("auto-register source %s/%s: %w", owner, repo, err)
	}
	return source.Name, nil
}

// normalizeSourceName ensures the source value uses the full resource name
// format ("sources/...") expected by the Jules API. Users may pass the short
// form (e.g. "github/owner/repo") via --source, while auto-detection already
// returns the full name.
func normalizeSourceName(source string) string {
	if _, found := strings.CutPrefix(source, "sources/"); found {
		return source
	}
	return "sources/" + source
}

func sessionList(args []string) int {
	fs := flag.NewFlagSet("jules session list", flag.ContinueOnError)
	var cfg cmdConfig
	cfg.add(fs)
	if err := fs.Parse(args); err != nil {
		return 1
	}

	client, err := cfg.newClient()
	if err != nil {
		return exitErr("%v", err)
	}

	sessions, err := client.ListSessions(context.Background())
	if err != nil {
		return handleErr(err)
	}

	if cfg.human {
		outputSessionTable(sessions)
		return 0
	}
	if err := outputJSON(sessions); err != nil {
		return exitErr("%v", err)
	}
	return 0
}

func sessionGet(args []string) int {
	fs := flag.NewFlagSet("jules session get", flag.ContinueOnError)
	var cfg cmdConfig
	cfg.add(fs)
	if err := fs.Parse(args); err != nil {
		return 1
	}

	if fs.NArg() < 1 {
		return exitErr("session get: session ID required")
	}
	id := fs.Arg(0)

	client, err := cfg.newClient()
	if err != nil {
		return exitErr("%v", err)
	}

	session, err := client.GetSession(context.Background(), id)
	if err != nil {
		return handleErr(err)
	}

	if cfg.human {
		outputSessionTable([]model.Session{*session})
		return 0
	}
	if err := outputJSON(session); err != nil {
		return exitErr("%v", err)
	}
	return 0
}

func sessionDelete(args []string) int {
	fs := flag.NewFlagSet("jules session delete", flag.ContinueOnError)
	var cfg cmdConfig
	cfg.add(fs)
	if err := fs.Parse(args); err != nil {
		return 1
	}

	if fs.NArg() < 1 {
		return exitErr("session delete: session ID required")
	}
	id := fs.Arg(0)

	client, err := cfg.newClient()
	if err != nil {
		return exitErr("%v", err)
	}

	if err := client.DeleteSession(context.Background(), id); err != nil {
		return handleErr(err)
	}

	if cfg.human {
		fmt.Printf("deleted session %s\n", id)
		return 0
	}
	if err := outputJSON(map[string]string{"deleted": id}); err != nil {
		return exitErr("%v", err)
	}
	return 0
}

func sessionMessage(args []string) int {
	fs := flag.NewFlagSet("jules session message", flag.ContinueOnError)
	var (
		cfg     cmdConfig
		message string
	)
	cfg.add(fs)
	fs.StringVar(&message, "message", "", "Message text (or use first positional arg after session ID)")
	if err := fs.Parse(args); err != nil {
		return 1
	}

	if fs.NArg() < 1 {
		return exitErr("session message: session ID required")
	}
	id := fs.Arg(0)

	// Accept message as second positional arg if --message not provided.
	if message == "" && fs.NArg() >= 2 {
		message = fs.Arg(1)
	}
	if message == "" {
		return exitErr("session message: message text required (use --message or pass as argument)")
	}

	client, err := cfg.newClient()
	if err != nil {
		return exitErr("%v", err)
	}

	session, err := client.SendMessage(context.Background(), id, message)
	if err != nil {
		return handleErr(err)
	}

	if cfg.human {
		outputSessionTable([]model.Session{*session})
		return 0
	}
	if err := outputJSON(session); err != nil {
		return exitErr("%v", err)
	}
	return 0
}

func sessionApprove(args []string) int {
	fs := flag.NewFlagSet("jules session approve", flag.ContinueOnError)
	var cfg cmdConfig
	cfg.add(fs)
	if err := fs.Parse(args); err != nil {
		return 1
	}

	if fs.NArg() < 1 {
		return exitErr("session approve: session ID required")
	}
	id := fs.Arg(0)

	client, err := cfg.newClient()
	if err != nil {
		return exitErr("%v", err)
	}

	session, err := client.ApprovePlan(context.Background(), id)
	if err != nil {
		return handleErr(err)
	}

	if cfg.human {
		outputSessionTable([]model.Session{*session})
		return 0
	}
	if err := outputJSON(session); err != nil {
		return exitErr("%v", err)
	}
	return 0
}

func sessionExtract(args []string) int {
	fs := flag.NewFlagSet("jules session extract", flag.ContinueOnError)
	var (
		cfg    cmdConfig
		output string
	)
	cfg.add(fs)
	fs.StringVar(&output, "output", "", "Output file path (default: stdout)")
	if err := fs.Parse(args); err != nil {
		return 1
	}

	if fs.NArg() < 1 {
		return exitErr("session extract: session ID required")
	}
	id := fs.Arg(0)

	client, err := cfg.newClient()
	if err != nil {
		return exitErr("%v", err)
	}

	session, err := client.GetSession(context.Background(), id)
	if err != nil {
		return handleErr(err)
	}

	patch, err := model.ExtractPatch(session.Outputs)
	if err != nil {
		fmt.Fprintf(os.Stderr, "jules: session %s: %v\n", id, err)
		return 2
	}

	if output != "" {
		if err := os.WriteFile(output, []byte(patch), 0o644); err != nil {
			return exitErr("write output file: %v", err)
		}
		fmt.Fprintf(os.Stderr, "jules: wrote patch to %s\n", output)
		return 0
	}

	fmt.Print(patch)
	return 0
}
