package cli

import (
	"context"
	"encoding/json"
	"fmt"
	"maps"
	"net/http"
	"net/http/httptest"
	"os"
	"os/exec"
	"path/filepath"
	"runtime"
	"slices"
	"strings"
	"sync"
	"testing"

	"github.com/nq-rdl/agent-skills/skills/jules/scripts/internal/api"
	"github.com/nq-rdl/agent-skills/skills/jules/scripts/internal/model"
	"github.com/nq-rdl/agent-skills/skills/jules/scripts/internal/orchestrate"
)

// brokenEnvironmentPatch is intentionally malformed: the function body is missing
// its closing brace, which causes `go build` to fail with a syntax error.
const brokenEnvironmentPatch = `diff --git a/catalog/environment.go b/catalog/environment.go
new file mode 100644
index 0000000..1111111
--- /dev/null
+++ b/catalog/environment.go
@@ -0,0 +1,5 @@
+package catalog
+
+func BrokenEnvironment() {
+	if true {
+}
`

type fakeIssue struct {
	Number int         `json:"number"`
	Title  string      `json:"title"`
	Body   string      `json:"body"`
	Labels []fakeLabel `json:"labels,omitempty"`
}

type fakeLabel struct {
	Name string `json:"name"`
}

type mockSessionScript struct {
	States  []string
	Outputs json.RawMessage
}

type sessionCreateCall struct {
	Title          string
	StartingBranch string
}

type workflowOptions struct {
	sequential bool
}

type workflowResult struct {
	Issue        orchestrate.Issue
	SessionID    string
	Branch       string
	PRBase       string
	PRURL        string
	Status       string
	SkippedStubs []string
	Err          string
}

type integrationHarness struct {
	t         *testing.T
	repoDir   string
	prLog     string
	client    *api.Client
	jules     *mockJulesServer
	issueRepo string
}

type mockJulesServer struct {
	t           *testing.T
	server      *httptest.Server
	mu          sync.Mutex
	scripts     map[string]mockSessionScript
	sessions    map[string]*mockSessionState
	createCalls []sessionCreateCall
	nextID      int
}

type mockSessionState struct {
	title  string
	script mockSessionScript
	gets   int
}

func TestOrchestratorWorkflowIntegration(t *testing.T) {
	t.Run("happy path", func(t *testing.T) {
		h := newIntegrationHarness(t, defaultIssues(), map[string]mockSessionScript{
			"Define provider catalog": {
				States:  []string{"QUEUED", "COMPLETED"},
				Outputs: patchOutputs(t, fixture(t, "issue-20-provider.patch")),
			},
			"Define package catalog": {
				States:  []string{"QUEUED", "COMPLETED"},
				Outputs: patchOutputs(t, fixture(t, "issue-21-package.patch")),
			},
			"Define environment catalog": {
				States:  []string{"QUEUED", "COMPLETED"},
				Outputs: patchOutputs(t, withoutPaths(fixture(t, "issue-22-environment.patch"), "catalog/provider.go", "catalog/package.go")),
			},
			"Define store catalog": {
				States:  []string{"QUEUED", "COMPLETED"},
				Outputs: patchOutputs(t, withoutPaths(fixture(t, "issue-23-store.patch"), "catalog/provider.go", "catalog/package.go")),
			},
		})

		results, err := h.runWorkflow([]int{20, 21, 22, 23}, workflowOptions{})
		if err != nil {
			t.Fatalf("runWorkflow() unexpected error: %v", err)
		}

		assertStatuses(t, results, map[int]string{
			20: "integrated",
			21: "integrated",
			22: "integrated",
			23: "integrated",
		})
		if got := len(h.jules.createCalls); got != 4 {
			t.Fatalf("session create calls = %d, want 4", got)
		}
		for _, res := range results {
			if len(res.SkippedStubs) != 0 {
				t.Fatalf("issue %d skipped stubs = %v, want none", res.Issue.Number, res.SkippedStubs)
			}
		}
		for i, call := range h.jules.createCalls {
			if call.StartingBranch != "main" {
				t.Errorf("create call %d starting branch = %q, want %q", i+1, call.StartingBranch, "main")
			}
		}

		prs := h.prCreates()
		if got := len(prs); got != 4 {
			t.Fatalf("PRs created = %d, want 4", got)
		}
		wantBases := []string{
			"main",
			results[0].Branch,
			results[1].Branch,
			results[2].Branch,
		}
		for i, pr := range prs {
			if pr.Base != wantBases[i] {
				t.Errorf("PR %d base = %q, want %q", i+1, pr.Base, wantBases[i])
			}
		}
	})

	t.Run("stub conflict", func(t *testing.T) {
		h := newIntegrationHarness(t, defaultIssues(), map[string]mockSessionScript{
			"Define provider catalog": {
				States:  []string{"QUEUED", "COMPLETED"},
				Outputs: patchOutputs(t, fixture(t, "issue-20-provider.patch")),
			},
			"Define package catalog": {
				States:  []string{"QUEUED", "COMPLETED"},
				Outputs: patchOutputs(t, fixture(t, "issue-21-package.patch")),
			},
			"Define environment catalog": {
				States:  []string{"QUEUED", "COMPLETED"},
				Outputs: patchOutputs(t, fixture(t, "issue-22-environment.patch")),
			},
			"Define store catalog": {
				States:  []string{"QUEUED", "COMPLETED"},
				Outputs: patchOutputs(t, fixture(t, "issue-23-store.patch")),
			},
		})

		results, err := h.runWorkflow([]int{20, 21, 22, 23}, workflowOptions{})
		if err != nil {
			t.Fatalf("runWorkflow() unexpected error: %v", err)
		}

		assertStatuses(t, results, map[int]string{
			20: "integrated",
			21: "integrated",
			22: "integrated",
			23: "integrated",
		})
		assertSkippedStubs(t, resultsByIssue(results), 22, []string{"catalog/package.go", "catalog/provider.go"})
		assertSkippedStubs(t, resultsByIssue(results), 23, []string{"catalog/package.go", "catalog/provider.go"})
		if got := len(h.prCreates()); got != 4 {
			t.Fatalf("PRs created = %d, want 4", got)
		}
	})

	t.Run("build failure", func(t *testing.T) {
		h := newIntegrationHarness(t, defaultIssues(), map[string]mockSessionScript{
			"Define provider catalog": {
				States:  []string{"QUEUED", "COMPLETED"},
				Outputs: patchOutputs(t, fixture(t, "issue-20-provider.patch")),
			},
			"Define package catalog": {
				States:  []string{"QUEUED", "COMPLETED"},
				Outputs: patchOutputs(t, fixture(t, "issue-21-package.patch")),
			},
			"Define environment catalog": {
				States:  []string{"QUEUED", "COMPLETED"},
				Outputs: patchOutputs(t, brokenEnvironmentPatch),
			},
			"Define store catalog": {
				States:  []string{"QUEUED", "COMPLETED"},
				Outputs: patchOutputs(t, fixture(t, "issue-23-store.patch")),
			},
		})

		results, err := h.runWorkflow([]int{20, 21, 22, 23}, workflowOptions{})
		if err != nil {
			t.Fatalf("runWorkflow() unexpected error: %v", err)
		}

		assertStatuses(t, results, map[int]string{
			20: "integrated",
			21: "integrated",
			22: "verification_failed",
			23: "blocked",
		})
		if got := len(h.prCreates()); got != 2 {
			t.Fatalf("PRs created = %d, want 2", got)
		}
		if !strings.Contains(resultsByIssue(results)[22].Err, "expected operand") &&
			!strings.Contains(resultsByIssue(results)[22].Err, "syntax error") {
			t.Fatalf("issue 22 error = %q, want compilation failure", resultsByIssue(results)[22].Err)
		}
	})

	t.Run("Jules session failure", func(t *testing.T) {
		h := newIntegrationHarness(t, defaultIssues(), map[string]mockSessionScript{
			"Define provider catalog": {
				States:  []string{"QUEUED", "COMPLETED"},
				Outputs: patchOutputs(t, fixture(t, "issue-20-provider.patch")),
			},
			"Define package catalog": {
				States:  []string{"QUEUED", "COMPLETED"},
				Outputs: patchOutputs(t, fixture(t, "issue-21-package.patch")),
			},
			"Define environment catalog": {
				States: []string{"QUEUED", "FAILED"},
			},
			"Define store catalog": {
				States:  []string{"QUEUED", "COMPLETED"},
				Outputs: patchOutputs(t, fixture(t, "issue-23-store.patch")),
			},
		})

		results, err := h.runWorkflow([]int{20, 21, 22, 23}, workflowOptions{})
		if err != nil {
			t.Fatalf("runWorkflow() unexpected error: %v", err)
		}

		assertStatuses(t, results, map[int]string{
			20: "integrated",
			21: "integrated",
			22: "session_failed",
			23: "blocked",
		})
		if got := len(h.prCreates()); got != 2 {
			t.Fatalf("PRs created = %d, want 2", got)
		}
	})

	t.Run("dispatch_failed", func(t *testing.T) {
		// Issue 22 has no mock script entry, so CreateSession returns HTTP 400.
		h := newIntegrationHarness(t, defaultIssues(), map[string]mockSessionScript{
			"Define provider catalog": {
				States:  []string{"QUEUED", "COMPLETED"},
				Outputs: patchOutputs(t, fixture(t, "issue-20-provider.patch")),
			},
			"Define package catalog": {
				States:  []string{"QUEUED", "COMPLETED"},
				Outputs: patchOutputs(t, fixture(t, "issue-21-package.patch")),
			},
			"Define store catalog": {
				States:  []string{"QUEUED", "COMPLETED"},
				Outputs: patchOutputs(t, fixture(t, "issue-23-store.patch")),
			},
		})

		results, err := h.runWorkflow([]int{20, 21, 22, 23}, workflowOptions{})
		if err != nil {
			t.Fatalf("runWorkflow() unexpected error: %v", err)
		}

		assertStatuses(t, results, map[int]string{
			20: "integrated",
			21: "integrated",
			22: "dispatch_failed",
			23: "blocked",
		})
		if got := len(h.prCreates()); got != 2 {
			t.Fatalf("PRs created = %d, want 2", got)
		}
	})

	t.Run("AWAITING_PLAN_APPROVAL", func(t *testing.T) {
		// Issue 22 session reaches AWAITING_PLAN_APPROVAL, a terminal state that
		// is not COMPLETED, so the harness marks it session_failed.
		h := newIntegrationHarness(t, defaultIssues(), map[string]mockSessionScript{
			"Define provider catalog": {
				States:  []string{"QUEUED", "COMPLETED"},
				Outputs: patchOutputs(t, fixture(t, "issue-20-provider.patch")),
			},
			"Define package catalog": {
				States:  []string{"QUEUED", "COMPLETED"},
				Outputs: patchOutputs(t, fixture(t, "issue-21-package.patch")),
			},
			"Define environment catalog": {
				States: []string{"QUEUED", "AWAITING_PLAN_APPROVAL"},
			},
			"Define store catalog": {
				States:  []string{"QUEUED", "COMPLETED"},
				Outputs: patchOutputs(t, fixture(t, "issue-23-store.patch")),
			},
		})

		results, err := h.runWorkflow([]int{20, 21, 22, 23}, workflowOptions{})
		if err != nil {
			t.Fatalf("runWorkflow() unexpected error: %v", err)
		}

		assertStatuses(t, results, map[int]string{
			20: "integrated",
			21: "integrated",
			22: "session_failed",
			23: "blocked",
		})
		if got := resultsByIssue(results)[22].Err; got != "AWAITING_PLAN_APPROVAL" {
			t.Fatalf("issue 22 Err = %q, want %q", got, "AWAITING_PLAN_APPROVAL")
		}
		if got := len(h.prCreates()); got != 2 {
			t.Fatalf("PRs created = %d, want 2", got)
		}
	})

	t.Run("sequential mode", func(t *testing.T) {
		h := newIntegrationHarness(t, defaultIssues(), map[string]mockSessionScript{
			"Define provider catalog": {
				States:  []string{"QUEUED", "COMPLETED"},
				Outputs: patchOutputs(t, fixture(t, "issue-20-provider.patch")),
			},
			"Define package catalog": {
				States:  []string{"QUEUED", "COMPLETED"},
				Outputs: patchOutputs(t, fixture(t, "issue-21-package.patch")),
			},
			"Define environment catalog": {
				States:  []string{"QUEUED", "COMPLETED"},
				Outputs: patchOutputs(t, withoutPaths(fixture(t, "issue-22-environment.patch"), "catalog/provider.go", "catalog/package.go")),
			},
			"Define store catalog": {
				States:  []string{"QUEUED", "COMPLETED"},
				Outputs: patchOutputs(t, withoutPaths(fixture(t, "issue-23-store.patch"), "catalog/provider.go", "catalog/package.go")),
			},
		})

		results, err := h.runWorkflow([]int{20, 21, 22, 23}, workflowOptions{sequential: true})
		if err != nil {
			t.Fatalf("runWorkflow() unexpected error: %v", err)
		}

		assertStatuses(t, results, map[int]string{
			20: "integrated",
			21: "integrated",
			22: "integrated",
			23: "integrated",
		})
		for _, res := range results {
			if len(res.SkippedStubs) != 0 {
				t.Fatalf("issue %d skipped stubs = %v, want none", res.Issue.Number, res.SkippedStubs)
			}
		}

		wantBranches := []string{
			"main",
			results[0].Branch,
			results[1].Branch,
			results[2].Branch,
		}
		if got := len(h.jules.createCalls); got != len(wantBranches) {
			t.Fatalf("session create calls = %d, want %d", got, len(wantBranches))
		}
		for i, call := range h.jules.createCalls {
			if call.StartingBranch != wantBranches[i] {
				t.Errorf("create call %d starting branch = %q, want %q", i+1, call.StartingBranch, wantBranches[i])
			}
		}
	})

	t.Run("circular dependency", func(t *testing.T) {
		h := newIntegrationHarness(t, map[int]fakeIssue{
			30: {
				Number: 30,
				Title:  "Define alpha catalog",
				Body:   "depends on #31",
			},
			31: {
				Number: 31,
				Title:  "Define beta catalog",
				Body:   "after #30",
			},
		}, nil)

		_, err := h.runWorkflow([]int{30, 31}, workflowOptions{})
		if err == nil {
			t.Fatal("runWorkflow() error = nil, want cycle error")
		}
		if !strings.Contains(err.Error(), "cycle detected") {
			t.Fatalf("runWorkflow() error = %q, want cycle detected", err)
		}
		if got := len(h.jules.createCalls); got != 0 {
			t.Fatalf("session create calls = %d, want 0", got)
		}
	})
}

func newIntegrationHarness(t *testing.T, issues map[int]fakeIssue, scripts map[string]mockSessionScript) *integrationHarness {
	t.Helper()

	repoDir := createTempRepo(t)
	ghDir, prLog := createMockGH(t, issues)
	jules := newMockJulesServer(t, scripts)

	t.Setenv("MOCK_GH_DIR", ghDir)
	t.Setenv("MOCK_GH_EXPECTED_REPO", "example/catalog")
	t.Setenv("PATH", ghDir+string(os.PathListSeparator)+os.Getenv("PATH"))

	return &integrationHarness{
		t:         t,
		repoDir:   repoDir,
		prLog:     prLog,
		client:    api.NewClientWithBase(context.Background(), jules.server.URL, "test-api-key"),
		jules:     jules,
		issueRepo: "example/catalog",
	}
}

func (h *integrationHarness) runWorkflow(issueNumbers []int, opts workflowOptions) ([]workflowResult, error) {
	issues, err := h.fetchIssues(issueNumbers)
	if err != nil {
		return nil, err
	}
	order, _, err := orchestrate.TopoSort(issues)
	if err != nil {
		return nil, err
	}

	ctx, err := orchestrate.DetectProjectContext(h.repoDir)
	if err != nil {
		return nil, fmt.Errorf("DetectProjectContext: %w", err)
	}
	claudeMD, err := os.ReadFile(filepath.Join(h.repoDir, "CLAUDE.md"))
	if err != nil {
		return nil, fmt.Errorf("read CLAUDE.md: %w", err)
	}

	issueByNumber := make(map[int]orchestrate.Issue, len(issues))
	for _, issue := range issues {
		issueByNumber[issue.Number] = issue
	}

	results := make(map[int]*workflowResult, len(issues))
	failed := make(map[int]bool, len(issues))
	currentBranch := "main"

	if opts.sequential {
		for _, n := range order {
			issue := issueByNumber[n]
			res := &workflowResult{Issue: issue}
			results[n] = res
			if hasFailedDependency(issue.DependsOn, failed) {
				res.Status = "blocked"
				res.Err = "dependency failed"
				failed[n] = true
				continue
			}
			if err := h.dispatchAndIntegrate(res, currentBranch, orchestrate.BuildPrompt(issue, ctx, string(claudeMD)), ctx.VerifyCommand); err != nil {
				failed[n] = true
			} else {
				currentBranch = res.Branch
			}
		}
		return orderedResults(order, results), nil
	}

	for _, n := range order {
		issue := issueByNumber[n]
		res := &workflowResult{Issue: issue}
		results[n] = res
		prompt := orchestrate.BuildPrompt(issue, ctx, string(claudeMD))
		session, err := h.client.CreateSession(context.Background(), &model.CreateSessionRequest{
			Prompt: prompt,
			SourceContext: &model.SourceContext{
				Source: "sources/github/example/catalog",
				GithubRepoContext: &model.GithubRepoContext{
					StartingBranch: "main",
				},
			},
		})
		if err != nil {
			res.Status = "dispatch_failed"
			res.Err = err.Error()
			failed[n] = true
			continue
		}
		res.SessionID = session.ID
	}

	for _, n := range order {
		res := results[n]
		if res.Status == "dispatch_failed" {
			continue
		}
		session, err := h.waitForSession(res.SessionID)
		if err != nil {
			res.Status = "session_failed"
			res.Err = err.Error()
			failed[n] = true
			continue
		}
		if session.State != "COMPLETED" {
			res.Status = "session_failed"
			res.Err = session.State
			failed[n] = true
			continue
		}
		if hasFailedDependency(res.Issue.DependsOn, failed) {
			res.Status = "blocked"
			res.Err = "dependency failed"
			failed[n] = true
			continue
		}
		if err := h.integrateIssue(res, session, currentBranch, ctx.VerifyCommand); err != nil {
			failed[n] = true
			continue
		}
		currentBranch = res.Branch
	}

	return orderedResults(order, results), nil
}

func (h *integrationHarness) dispatchAndIntegrate(res *workflowResult, startingBranch, prompt, verifyCommand string) error {
	session, err := h.client.CreateSession(context.Background(), &model.CreateSessionRequest{
		Prompt: prompt,
		SourceContext: &model.SourceContext{
			Source: "sources/github/example/catalog",
			GithubRepoContext: &model.GithubRepoContext{
				StartingBranch: startingBranch,
			},
		},
	})
	if err != nil {
		res.Status = "dispatch_failed"
		res.Err = err.Error()
		return err
	}
	res.SessionID = session.ID

	finalSession, err := h.waitForSession(session.ID)
	if err != nil {
		res.Status = "session_failed"
		res.Err = err.Error()
		return err
	}
	if finalSession.State != "COMPLETED" {
		res.Status = "session_failed"
		res.Err = finalSession.State
		return fmt.Errorf("session %s ended in %s", session.ID, finalSession.State)
	}
	return h.integrateIssue(res, finalSession, startingBranch, verifyCommand)
}

func (h *integrationHarness) integrateIssue(res *workflowResult, session *model.Session, baseBranch, verifyCommand string) error {
	branch := orchestrate.BranchName("jules", res.Issue)
	if _, err := combinedOutput(h.repoDir, "git", "checkout", "-q", "-B", branch, baseBranch); err != nil {
		res.Status = "apply_failed"
		res.Err = err.Error()
		return err
	}

	patch, err := model.ExtractPatch(session.Outputs)
	if err != nil {
		res.Status = "apply_failed"
		res.Err = err.Error()
		_, _ = combinedOutput(h.repoDir, "git", "checkout", "-q", "-f", baseBranch)
		return err
	}

	skipped, err := applyPatch(h.repoDir, patch)
	res.SkippedStubs = skipped
	if err != nil {
		res.Status = "apply_failed"
		res.Err = err.Error()
		_, _ = combinedOutput(h.repoDir, "git", "checkout", "-q", "-f", baseBranch)
		return err
	}

	verifyErr := verifyRepo(h.repoDir, verifyCommand)
	if verifyErr != nil {
		res.Status = "verification_failed"
		res.Err = verifyErr.Error()
		_, _ = combinedOutput(h.repoDir, "git", "checkout", "-q", "-f", baseBranch)
		return verifyErr
	}

	if _, err := combinedOutput(h.repoDir, "git", "add", "-A"); err != nil {
		res.Status = "apply_failed"
		res.Err = err.Error()
		return err
	}
	if _, err := combinedOutput(h.repoDir, "git", "commit", "-q", "-m", fmt.Sprintf("feat(#%d): %s", res.Issue.Number, res.Issue.Title)); err != nil {
		res.Status = "apply_failed"
		res.Err = err.Error()
		return err
	}

	prURL, err := combinedOutput(h.repoDir, "gh", "pr", "create",
		"--base", baseBranch,
		"--head", branch,
		"--title", res.Issue.Title,
		"--body", fmt.Sprintf("Closes #%d", res.Issue.Number))
	if err != nil {
		res.Status = "apply_failed"
		res.Err = err.Error()
		return err
	}

	res.Status = "integrated"
	res.Branch = branch
	res.PRBase = baseBranch
	res.PRURL = strings.TrimSpace(prURL)
	return nil
}

func (h *integrationHarness) fetchIssues(issueNumbers []int) ([]orchestrate.Issue, error) {
	issues := make([]orchestrate.Issue, 0, len(issueNumbers))
	for _, n := range issueNumbers {
		issue, err := fetchIssue(n, h.issueRepo)
		if err != nil {
			return nil, err
		}
		issues = append(issues, issue)
	}
	return issues, nil
}

func (h *integrationHarness) waitForSession(id string) (*model.Session, error) {
	// 8 is a generous ceiling; mock scripts reach a terminal state in ≤2 polls.
	for range 8 {
		session, err := h.client.GetSession(context.Background(), id)
		if err != nil {
			return nil, err
		}
		if isTerminalState(session.State) {
			return session, nil
		}
	}
	return nil, fmt.Errorf("session %s did not reach a terminal state", id)
}

func (h *integrationHarness) prCreates() []prCreate {
	h.t.Helper()

	data, err := os.ReadFile(h.prLog)
	if os.IsNotExist(err) {
		return nil
	}
	if err != nil {
		h.t.Fatalf("read PR log: %v", err)
	}

	var prs []prCreate
	for _, line := range strings.Split(strings.TrimSpace(string(data)), "\n") {
		if strings.TrimSpace(line) == "" {
			continue
		}
		parts := strings.Split(line, "|")
		if len(parts) != 3 {
			h.t.Fatalf("malformed PR log line: %q", line)
		}
		prs = append(prs, prCreate{
			Base: parts[0],
			Head: parts[1],
			URL:  parts[2],
		})
	}
	return prs
}

type prCreate struct {
	Base string
	Head string
	URL  string
}

func newMockJulesServer(t *testing.T, scripts map[string]mockSessionScript) *mockJulesServer {
	t.Helper()

	mock := &mockJulesServer{
		t:        t,
		scripts:  maps.Clone(scripts),
		sessions: make(map[string]*mockSessionState),
		nextID:   1,
	}
	mock.server = httptest.NewServer(http.HandlerFunc(mock.serveHTTP))
	t.Cleanup(mock.server.Close)
	return mock
}

func (m *mockJulesServer) serveHTTP(w http.ResponseWriter, r *http.Request) {
	w.Header().Set("Content-Type", "application/json")

	switch {
	case r.Method == http.MethodPost && r.URL.Path == "/sessions":
		var req model.CreateSessionRequest
		if err := json.NewDecoder(r.Body).Decode(&req); err != nil {
			http.Error(w, err.Error(), http.StatusBadRequest)
			return
		}
		title := promptTitle(req.Prompt)

		m.mu.Lock()
		script, ok := m.scripts[title]
		if !ok {
			m.mu.Unlock()
			http.Error(w, "unknown prompt title", http.StatusBadRequest)
			return
		}
		id := fmt.Sprintf("ses_%02d", m.nextID)
		m.nextID++
		m.sessions[id] = &mockSessionState{title: title, script: script}
		m.createCalls = append(m.createCalls, sessionCreateCall{
			Title:          title,
			StartingBranch: startingBranch(&req),
		})
		initialState := "QUEUED"
		if len(script.States) > 0 {
			initialState = script.States[0]
		}
		m.mu.Unlock()

		_ = json.NewEncoder(w).Encode(model.Session{
			ID:    id,
			Title: title,
			State: initialState,
		})
		return

	case r.Method == http.MethodGet && strings.HasPrefix(r.URL.Path, "/sessions/"):
		id := strings.TrimPrefix(r.URL.Path, "/sessions/")

		m.mu.Lock()
		session, ok := m.sessions[id]
		if !ok {
			m.mu.Unlock()
			http.Error(w, "unknown session", http.StatusNotFound)
			return
		}
		idx := session.gets
		if idx >= len(session.script.States) {
			idx = len(session.script.States) - 1
		}
		state := session.script.States[idx]
		session.gets++
		outputs := json.RawMessage(nil)
		if state == "COMPLETED" {
			outputs = session.script.Outputs
		}
		title := session.title
		m.mu.Unlock()

		_ = json.NewEncoder(w).Encode(model.Session{
			ID:      id,
			Title:   title,
			State:   state,
			Outputs: outputs,
		})
		return
	}

	http.NotFound(w, r)
}

func createTempRepo(t *testing.T) string {
	t.Helper()

	dir := t.TempDir()
	mustWriteFile(t, filepath.Join(dir, "go.mod"), "module example.com/catalog\n\ngo 1.22\n")
	mustWriteFile(t, filepath.Join(dir, "Makefile"), "test:\n\tgo test ./...\n")
	mustWriteFile(t, filepath.Join(dir, "CLAUDE.md"), "# Test repository guidance\n")
	mustWriteFile(t, filepath.Join(dir, "catalog", "doc.go"), "package catalog\n")

	runSuccess(t, dir, "git", "init", "-q")
	runSuccess(t, dir, "git", "checkout", "-q", "-b", "main")
	runSuccess(t, dir, "git", "config", "user.email", "test@example.com")
	runSuccess(t, dir, "git", "config", "user.name", "Test User")
	runSuccess(t, dir, "git", "add", ".")
	runSuccess(t, dir, "git", "commit", "-q", "-m", "base")
	return dir
}

func createMockGH(t *testing.T, issues map[int]fakeIssue) (dir, prLog string) {
	t.Helper()

	dir = t.TempDir()
	issuesDir := filepath.Join(dir, "issues")
	if err := os.MkdirAll(issuesDir, 0o755); err != nil {
		t.Fatalf("mkdir issues dir: %v", err)
	}
	for n, issue := range issues {
		data, err := json.Marshal(issue)
		if err != nil {
			t.Fatalf("marshal issue %d: %v", n, err)
		}
		mustWriteFile(t, filepath.Join(issuesDir, fmt.Sprintf("%d.json", n)), string(data))
	}

	prLog = filepath.Join(dir, "pr-create.log")
	script := `#!/bin/sh
set -eu

if [ "$#" -lt 2 ]; then
  echo "unsupported gh invocation" >&2
  exit 1
fi

cmd="$1"
sub="$2"
shift 2

case "$cmd:$sub" in
  issue:view)
    issue=""
    repo=""
    while [ "$#" -gt 0 ]; do
      case "$1" in
        --repo)
          if [ "$#" -lt 2 ]; then
            echo "--repo requires a value" >&2
            exit 1
          fi
          repo="$2"
          shift 2
          ;;
        --json)
          if [ "$#" -lt 2 ]; then
            echo "--json requires a value" >&2
            exit 1
          fi
          shift 2
          ;;
        -*)
          echo "unknown issue:view flag: $1" >&2
          exit 1
          ;;
        *)
          if [ -n "$issue" ]; then
            echo "unexpected issue:view argument: $1" >&2
            exit 1
          fi
          issue="$1"
          shift 1
          ;;
      esac
    done
    if [ -z "$issue" ]; then
      echo "issue number required" >&2
      exit 1
    fi
    if [ -n "$MOCK_GH_EXPECTED_REPO" ] && [ "$repo" != "$MOCK_GH_EXPECTED_REPO" ]; then
      echo "unexpected --repo: got $repo, want $MOCK_GH_EXPECTED_REPO" >&2
      exit 1
    fi
    cat "$MOCK_GH_DIR/issues/$issue.json"
    ;;
  pr:create)
    base=""
    head=""
    while [ "$#" -gt 0 ]; do
      case "$1" in
        --base)
          if [ "$#" -lt 2 ]; then
            echo "--base requires a value" >&2
            exit 1
          fi
          base="$2"
          shift 2
          ;;
        --head)
          if [ "$#" -lt 2 ]; then
            echo "--head requires a value" >&2
            exit 1
          fi
          head="$2"
          shift 2
          ;;
        # The mock only records base/head; title/body are validated then ignored.
        --title)
          if [ "$#" -lt 2 ]; then
            echo "--title requires a value" >&2
            exit 1
          fi
          shift 2
          ;;
        --body)
          if [ "$#" -lt 2 ]; then
            echo "--body requires a value" >&2
            exit 1
          fi
          shift 2
          ;;
        -*)
          echo "unknown pr:create flag: $1" >&2
          exit 1
          ;;
        *)
          echo "unexpected pr:create argument: $1" >&2
          exit 1
          ;;
      esac
    done
    if [ -z "$base" ]; then
      echo "--base is required" >&2
      exit 1
    fi
    if [ -z "$head" ]; then
      echo "--head is required" >&2
      exit 1
    fi
    url="https://example.test/$head"
    printf '%s|%s|%s\n' "$base" "$head" "$url" >> "$MOCK_GH_DIR/pr-create.log"
    printf '%s\n' "$url"
    ;;
  *)
    echo "unsupported gh invocation" >&2
    exit 1
    ;;
esac
`
	mustWriteFile(t, filepath.Join(dir, "gh"), script)
	if err := os.Chmod(filepath.Join(dir, "gh"), 0o755); err != nil {
		t.Fatalf("chmod gh shim: %v", err)
	}
	return dir, prLog
}

func applyPatch(repoDir, patch string) ([]string, error) {
	var skipped []string
	for _, pf := range orchestrate.SplitPatch(patch) {
		stub, err := orchestrate.IsStub(pf, repoDir)
		if err != nil {
			return skipped, err
		}
		if stub {
			skipped = append(skipped, pf.Path)
			continue
		}

		patchFile, err := os.CreateTemp("", "jules-patch-*.diff")
		if err != nil {
			return skipped, err
		}
		path := patchFile.Name()
		if _, err := patchFile.WriteString(pf.Diff); err != nil {
			_ = patchFile.Close()
			_ = os.Remove(path)
			return skipped, err
		}
		if !strings.HasSuffix(pf.Diff, "\n") {
			if _, err := patchFile.WriteString("\n"); err != nil {
				_ = patchFile.Close()
				_ = os.Remove(path)
				return skipped, err
			}
		}
		if err := patchFile.Close(); err != nil {
			_ = os.Remove(path)
			return skipped, err
		}

		if _, err := combinedOutput(repoDir, "git", "apply", "--check", path); err != nil {
			_ = os.Remove(path)
			return skipped, err
		}
		if _, err := combinedOutput(repoDir, "git", "apply", path); err != nil {
			_ = os.Remove(path)
			return skipped, err
		}
		_ = os.Remove(path)
	}

	slices.Sort(skipped)
	return skipped, nil
}

func verifyRepo(repoDir, command string) error {
	name, args := splitCommand(command)
	_, err := combinedOutput(repoDir, name, args...)
	return err
}

func combinedOutput(dir, name string, args ...string) (string, error) {
	cmd := exec.Command(name, args...)
	cmd.Dir = dir
	out, err := cmd.CombinedOutput()
	if err != nil {
		return string(out), fmt.Errorf("%s %s: %w\n%s", name, strings.Join(args, " "), err, string(out))
	}
	return string(out), nil
}

func runSuccess(t *testing.T, dir, name string, args ...string) {
	t.Helper()
	if _, err := combinedOutput(dir, name, args...); err != nil {
		t.Fatal(err)
	}
}

func fixture(t *testing.T, name string) string {
	t.Helper()
	_, file, _, ok := runtime.Caller(0)
	if !ok {
		t.Fatal("runtime.Caller failed")
	}
	data, err := os.ReadFile(filepath.Join(filepath.Dir(file), "..", "..", "testdata", name))
	if err != nil {
		t.Fatalf("read fixture %s: %v", name, err)
	}
	return string(data)
}

func patchOutputs(t *testing.T, patch string) json.RawMessage {
	t.Helper()
	data, err := json.Marshal([]map[string]any{
		{
			"changeSet": map[string]any{
				"gitPatch": map[string]string{
					"unidiffPatch": patch,
				},
			},
		},
	})
	if err != nil {
		t.Fatalf("marshal outputs: %v", err)
	}
	return data
}

func withoutPaths(patch string, paths ...string) string {
	skip := make(map[string]bool, len(paths))
	for _, path := range paths {
		skip[path] = true
	}

	var b strings.Builder
	for _, pf := range orchestrate.SplitPatch(patch) {
		if skip[pf.Path] {
			continue
		}
		b.WriteString(pf.Diff)
		if !strings.HasSuffix(pf.Diff, "\n") {
			b.WriteString("\n")
		}
	}
	return b.String()
}

func assertStatuses(t *testing.T, results []workflowResult, want map[int]string) {
	t.Helper()
	got := resultsByIssue(results)
	for issue, status := range want {
		if got[issue].Status != status {
			t.Errorf("issue %d status = %q, want %q (err=%q)", issue, got[issue].Status, status, got[issue].Err)
		}
	}
}

func assertSkippedStubs(t *testing.T, got map[int]workflowResult, issue int, want []string) {
	t.Helper()
	if !slices.Equal(got[issue].SkippedStubs, want) {
		t.Fatalf("issue %d skipped stubs = %v, want %v", issue, got[issue].SkippedStubs, want)
	}
}

func resultsByIssue(results []workflowResult) map[int]workflowResult {
	out := make(map[int]workflowResult, len(results))
	for _, res := range results {
		out[res.Issue.Number] = res
	}
	return out
}

func orderedResults(order []int, results map[int]*workflowResult) []workflowResult {
	out := make([]workflowResult, 0, len(order))
	for _, n := range order {
		out = append(out, *results[n])
	}
	return out
}

func splitCommand(command string) (string, []string) {
	fields := strings.Fields(command)
	if len(fields) == 0 {
		return "", nil
	}
	return fields[0], fields[1:]
}

func isTerminalState(state string) bool {
	return state == "COMPLETED" || state == "FAILED" || state == "AWAITING_PLAN_APPROVAL"
}

func promptTitle(prompt string) string {
	firstLine := strings.SplitN(prompt, "\n", 2)[0]
	return strings.TrimPrefix(firstLine, "## Task: ")
}

func startingBranch(req *model.CreateSessionRequest) string {
	if req.SourceContext == nil || req.SourceContext.GithubRepoContext == nil {
		return ""
	}
	return req.SourceContext.GithubRepoContext.StartingBranch
}

func hasFailedDependency(deps []int, failed map[int]bool) bool {
	for _, dep := range deps {
		if failed[dep] {
			return true
		}
	}
	return false
}

func mustWriteFile(t *testing.T, path, content string) {
	t.Helper()
	if err := os.MkdirAll(filepath.Dir(path), 0o755); err != nil {
		t.Fatalf("mkdir %s: %v", path, err)
	}
	if err := os.WriteFile(path, []byte(content), 0o644); err != nil {
		t.Fatalf("write %s: %v", path, err)
	}
}

func defaultIssues() map[int]fakeIssue {
	return map[int]fakeIssue{
		20: {
			Number: 20,
			Title:  "Define provider catalog",
			Body:   "Add provider definitions.",
			Labels: []fakeLabel{{Name: "provider"}},
		},
		21: {
			Number: 21,
			Title:  "Define package catalog",
			Body:   "Add package definitions.",
			Labels: []fakeLabel{{Name: "package"}},
		},
		22: {
			Number: 22,
			Title:  "Define environment catalog",
			Body:   "depends on #20 and #21",
			Labels: []fakeLabel{{Name: "environment"}},
		},
		23: {
			Number: 23,
			Title:  "Define store catalog",
			Body:   "after #22",
			Labels: []fakeLabel{{Name: "store"}},
		},
	}
}
