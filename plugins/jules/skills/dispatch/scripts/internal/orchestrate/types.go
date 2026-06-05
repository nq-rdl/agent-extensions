// Package orchestrate implements the Jules orchestrator: issue parsing,
// dependency graph, prompt building, patch splitting, and branch naming.
package orchestrate

// Issue represents a GitHub issue to be dispatched to Jules.
type Issue struct {
	Number    int      `json:"number"`
	Title     string   `json:"title"`
	Body      string   `json:"body"`
	Labels    []string `json:"labels,omitempty"`
	DependsOn []int    `json:"dependsOn,omitempty"`
	Repo      string   `json:"repo,omitempty"`
}

// IssueGraph holds the issues with their computed dependency order.
type IssueGraph struct {
	Issues         []Issue `json:"issues"`
	Order          []int   `json:"order"`
	ParallelGroups [][]int `json:"parallelGroups"`
}

// PatchFile represents one file's diff extracted from a combined patch.
type PatchFile struct {
	Path      string `json:"path"`
	Diff      string `json:"diff"`
	IsNewFile bool   `json:"isNewFile"`
	IsStub    bool   `json:"isStub"`
}
