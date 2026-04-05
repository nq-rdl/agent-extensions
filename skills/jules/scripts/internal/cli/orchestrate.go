package cli

import (
	"encoding/json"
	"flag"
	"fmt"
	"io"
	"os"
	"os/exec"
	"strconv"
	"strings"

	"github.com/nq-rdl/agent-skills/skills/jules/scripts/internal/orchestrate"
)

type ghIssueResponse struct {
	Number int    `json:"number"`
	Title  string `json:"title"`
	Body   string `json:"body"`
	Labels []struct {
		Name string `json:"name"`
	} `json:"labels"`
}

func fetchIssue(n int, repo string) (orchestrate.Issue, error) {
	out, err := exec.Command("gh", "issue", "view", strconv.Itoa(n),
		"--json", "number,title,body,labels",
		"--repo", repo).Output()
	if err != nil {
		return orchestrate.Issue{}, fmt.Errorf("gh issue view %d: %w", n, err)
	}

	var raw ghIssueResponse
	if err := json.Unmarshal(out, &raw); err != nil {
		return orchestrate.Issue{}, fmt.Errorf("parse issue %d response: %w", n, err)
	}

	labels := make([]string, len(raw.Labels))
	for i, l := range raw.Labels {
		labels[i] = l.Name
	}

	return orchestrate.Issue{
		Number:    raw.Number,
		Title:     raw.Title,
		Body:      raw.Body,
		Labels:    labels,
		Repo:      repo,
		DependsOn: orchestrate.ParseDependencies(raw.Body),
	}, nil
}

// runOrchestrate dispatches to orchestrate subcommands.
func runOrchestrate(args []string) int {
	if len(args) == 0 {
		return exitErr("orchestrate: action required (parse-issues|build-prompt|split-patch)")
	}
	switch args[0] {
	case "parse-issues":
		return orchestrateParseIssues(args[1:])
	case "build-prompt":
		return orchestrateBuildPrompt(args[1:])
	case "split-patch":
		return orchestrateSplitPatch(args[1:])
	default:
		return exitErr("orchestrate: unknown action %q", args[0])
	}
}

// orchestrateParseIssues implements: jules orchestrate parse-issues [--repo owner/repo] <issue-numbers...>
func orchestrateParseIssues(args []string) int {
	fs := flag.NewFlagSet("jules orchestrate parse-issues", flag.ContinueOnError)
	var repo string
	fs.StringVar(&repo, "repo", "", "GitHub repository in owner/repo format (auto-detected if omitted)")
	if err := fs.Parse(args); err != nil {
		return 1
	}

	if repo == "" {
		owner, name, err := DetectRepo()
		if err != nil {
			return exitErr("parse-issues: could not detect repo: %v", err)
		}
		repo = owner + "/" + name
	}

	positional := fs.Args()
	if len(positional) == 0 {
		return exitErr("parse-issues: at least one issue number required")
	}

	var issues []orchestrate.Issue
	// TODO: Fetch these in parallel for larger epics; gh calls are currently serial.
	for _, arg := range positional {
		n, err := strconv.Atoi(strings.TrimSpace(arg))
		if err != nil {
			return exitErr("parse-issues: invalid issue number %q: %v", arg, err)
		}

		iss, err := fetchIssue(n, repo)
		if err != nil {
			return exitErr("parse-issues: %v", err)
		}
		issues = append(issues, iss)
	}

	order, groups, err := orchestrate.TopoSort(issues)
	if err != nil {
		return exitErr("parse-issues: %v", err)
	}

	graph := orchestrate.IssueGraph{
		Issues:         issues,
		Order:          order,
		ParallelGroups: groups,
	}

	if err := outputJSON(graph); err != nil {
		return exitErr("%v", err)
	}
	return 0
}

// orchestrateBuildPrompt implements: jules orchestrate build-prompt --issue <N> [--dir .] [--claude-md path]
func orchestrateBuildPrompt(args []string) int {
	fs := flag.NewFlagSet("jules orchestrate build-prompt", flag.ContinueOnError)
	var (
		issueNum int
		dir      string
		claudeMD string
		repo     string
	)
	fs.IntVar(&issueNum, "issue", 0, "Issue number (required)")
	fs.StringVar(&dir, "dir", ".", "Project directory")
	fs.StringVar(&claudeMD, "claude-md", "", "Path to CLAUDE.md file")
	fs.StringVar(&repo, "repo", "", "GitHub repository in owner/repo format (auto-detected if omitted)")
	if err := fs.Parse(args); err != nil {
		return 1
	}

	if issueNum == 0 {
		return exitErr("build-prompt: --issue is required")
	}

	if repo == "" {
		owner, name, err := DetectRepo()
		if err != nil {
			return exitErr("build-prompt: could not detect repo: %v", err)
		}
		repo = owner + "/" + name
	}

	issue, err := fetchIssue(issueNum, repo)
	if err != nil {
		return exitErr("build-prompt: %v", err)
	}

	// Read CLAUDE.md: explicit path, then .claude/CLAUDE.md, then CLAUDE.md.
	var claudeMDContent string
	if claudeMD != "" {
		data, err := os.ReadFile(claudeMD)
		if err != nil {
			return exitErr("build-prompt: read claude-md: %v", err)
		}
		claudeMDContent = string(data)
	} else {
		for _, candidate := range []string{
			dir + "/.claude/CLAUDE.md",
			dir + "/CLAUDE.md",
		} {
			if data, err := os.ReadFile(candidate); err == nil {
				claudeMDContent = string(data)
				break
			}
		}
	}

	projCtx, err := orchestrate.DetectProjectContext(dir)
	if err != nil {
		return exitErr("build-prompt: detect project context: %v", err)
	}

	prompt := orchestrate.BuildPrompt(issue, projCtx, claudeMDContent)
	fmt.Print(prompt)
	return 0
}

// orchestrateSplitPatch implements: jules orchestrate split-patch --input <file> [--work-dir .]
func orchestrateSplitPatch(args []string) int {
	fs := flag.NewFlagSet("jules orchestrate split-patch", flag.ContinueOnError)
	var (
		input   string
		workDir string
	)
	fs.StringVar(&input, "input", "", "Patch file path (use \"-\" for stdin)")
	fs.StringVar(&workDir, "work-dir", ".", "Working directory for stub detection")
	if err := fs.Parse(args); err != nil {
		return 1
	}

	if input == "" {
		return exitErr("split-patch: --input is required")
	}

	var data []byte
	var err error
	if input == "-" {
		data, err = io.ReadAll(os.Stdin)
	} else {
		data, err = os.ReadFile(input)
	}
	if err != nil {
		return exitErr("split-patch: read input: %v", err)
	}

	files := orchestrate.SplitPatch(string(data))
	for i, pf := range files {
		stub, err := orchestrate.IsStub(pf, workDir)
		if err != nil {
			return exitErr("split-patch: check stub %s: %v", pf.Path, err)
		}
		files[i].IsStub = stub
	}

	if err := outputJSON(files); err != nil {
		return exitErr("%v", err)
	}
	return 0
}
