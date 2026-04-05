// Package cli implements the jules command-line interface.
package cli

import (
	"cmp"
	"errors"
	"flag"
	"fmt"
	"os"

	"github.com/nq-rdl/agent-skills/skills/jules/scripts/internal/api"
	"github.com/nq-rdl/agent-skills/skills/jules/scripts/internal/model"
)

const version = "0.1.2"

// cmdConfig holds global flags shared across all subcommands.
type cmdConfig struct {
	apiKey string
	human  bool
}

func (c *cmdConfig) add(fs *flag.FlagSet) {
	fs.StringVar(&c.apiKey, "api-key", "", "Jules API key (overrides JULES_API_KEY env var)")
	fs.BoolVar(&c.human, "human", false, "Human-readable tabular output instead of JSON")
}

func (c *cmdConfig) newClient() (*api.Client, error) {
	key := cmp.Or(c.apiKey, os.Getenv("JULES_API_KEY"))
	if key == "" {
		return nil, errors.New("Jules API key required: set JULES_API_KEY or use --api-key flag")
	}
	return api.NewClient(key), nil
}

// Run is the main entry point. Returns an OS exit code.
func Run() int {
	if len(os.Args) < 2 {
		printUsage()
		return 1
	}

	switch os.Args[1] {
	case "session":
		return runSession(os.Args[2:])
	case "batch":
		return runBatch(os.Args[2:])
	case "activity":
		return runActivity(os.Args[2:])
	case "source":
		return runSource(os.Args[2:])
	case "orchestrate":
		return runOrchestrate(os.Args[2:])
	case "version", "--version", "-v":
		fmt.Println(version)
		return 0
	case "help", "--help", "-h":
		printUsage()
		return 0
	default:
		fmt.Fprintf(os.Stderr, "jules: unknown command %q\n\n", os.Args[1])
		printUsage()
		return 1
	}
}

func printUsage() {
	fmt.Fprintf(os.Stderr, `jules %s — Jules API client

USAGE
  jules <resource> <action> [flags]

RESOURCES
  session     create | list | get | delete | message | approve | extract | wait | cleanup
  batch       status <ids> [--file manifest.json]
  activity    list | get
  source      list | get | add
  orchestrate parse-issues | build-prompt | split-patch

GLOBAL FLAGS
  --api-key string   Jules API key (overrides JULES_API_KEY)
  --human            Human-readable tabular output (default: JSON)

EXAMPLES
  jules session create --prompt "Fix the login bug"
  jules session list --human
  jules session get <session-id>
  jules session approve <session-id>
  jules session extract <session-id> --output patch.diff
  jules session wait <session-id> --timeout 30m --interval 15s
  jules session cleanup --older-than 7d --archive ~/.jules/archive.jsonl --human
  jules session cleanup --dry-run --state COMPLETED
  jules batch status id1,id2,id3 --human
  jules batch status --file manifest.json
  jules activity list --session <session-id> --human
  jules source list
  jules source add owner/repo
  jules orchestrate parse-issues --repo owner/repo 20 21 22
  jules orchestrate build-prompt --issue 20 --dir /path/to/project
  jules orchestrate split-patch --input combined.diff --work-dir .
`, version)
}

// exitErr prints a usage error to stderr and returns exit code 1.
func exitErr(format string, args ...any) int {
	fmt.Fprintf(os.Stderr, "jules: "+format+"\n", args...)
	return 1
}

// handleErr converts an API or network error into an appropriate exit code.
// *model.APIError → 2, anything else → 3.
func handleErr(err error) int {
	var apiErr *model.APIError
	if errors.As(err, &apiErr) {
		fmt.Fprintf(os.Stderr, "jules: API error: %v\n", apiErr)
		return 2
	}
	fmt.Fprintf(os.Stderr, "jules: error: %v\n", err)
	return 3
}
