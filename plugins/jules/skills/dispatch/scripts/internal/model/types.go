// Package model defines the data types for the Jules REST API.
package model

import (
	"encoding/json"
	"errors"
)

// FlexibleString unmarshals either a plain JSON string ("main") or an object
// with a name field ({"name": "main"}), to handle API response format changes.
type FlexibleString string

func (f *FlexibleString) UnmarshalJSON(data []byte) error {
	var s string
	if err := json.Unmarshal(data, &s); err == nil {
		*f = FlexibleString(s)
		return nil
	}
	var obj struct {
		Name string `json:"name"`
	}
	if err := json.Unmarshal(data, &obj); err != nil {
		return err
	}
	*f = FlexibleString(obj.Name)
	return nil
}

// FlexibleStringList unmarshals either a plain JSON string array (["main"]) or
// an object array ([{"name": "main"}]), to handle API response format changes.
type FlexibleStringList []string

func (f *FlexibleStringList) UnmarshalJSON(data []byte) error {
	var ss []string
	if err := json.Unmarshal(data, &ss); err == nil {
		*f = FlexibleStringList(ss)
		return nil
	}
	var objs []struct {
		Name string `json:"name"`
	}
	if err := json.Unmarshal(data, &objs); err != nil {
		return err
	}
	result := make(FlexibleStringList, len(objs))
	for i, o := range objs {
		result[i] = o.Name
	}
	*f = result
	return nil
}

// Session states as reported by the Jules API.
const (
	StateUnspecified          = "STATE_UNSPECIFIED"
	StateQueued               = "QUEUED"
	StatePlanning             = "PLANNING"
	StateAwaitingPlanApproval = "AWAITING_PLAN_APPROVAL"
	StateAwaitingUserFeedback = "AWAITING_USER_FEEDBACK"
	StateInProgress           = "IN_PROGRESS"
	StatePaused               = "PAUSED"
	StateCompleted            = "COMPLETED"
	StateFailed               = "FAILED"
)

// IsTerminal reports whether the session state is a terminal state
// (no further transitions possible).
func IsTerminal(state string) bool {
	return state == StateCompleted || state == StateFailed
}

// Session represents a Jules coding session.
// States: QUEUED → PLANNING → AWAITING_PLAN_APPROVAL → IN_PROGRESS → COMPLETED | FAILED
type Session struct {
	Name                string          `json:"name,omitempty"`
	ID                  string          `json:"id,omitempty"`
	Prompt              string          `json:"prompt,omitempty"`
	Title               string          `json:"title,omitempty"`
	State               string          `json:"state,omitempty"`
	URL                 string          `json:"url,omitempty"`
	SourceContext       *SourceContext  `json:"sourceContext,omitempty"`
	RequirePlanApproval bool            `json:"requirePlanApproval,omitempty"`
	AutomationMode      string          `json:"automationMode,omitempty"`
	Outputs             json.RawMessage `json:"outputs,omitempty"`
	CreateTime          string          `json:"createTime,omitempty"`
	UpdateTime          string          `json:"updateTime,omitempty"`
}

// SourceContext holds the repository context for a session.
type SourceContext struct {
	Source            string             `json:"source,omitempty"`
	GithubRepoContext *GithubRepoContext `json:"githubRepoContext,omitempty"`
}

// GithubRepoContext specifies which branch to start from.
type GithubRepoContext struct {
	StartingBranch string `json:"startingBranch,omitempty"`
}

// ExtractPatch parses the session Outputs (json.RawMessage) and returns the
// unidiff patch string. The expected structure is:
//
//	[{"changeSet": {"gitPatch": {"unidiffPatch": "..."}}}]
//
// Returns an error if outputs is empty/null or does not contain a patch.
func ExtractPatch(outputs json.RawMessage) (string, error) {
	if len(outputs) == 0 {
		return "", errors.New("no outputs available")
	}

	var elements []json.RawMessage
	if err := json.Unmarshal(outputs, &elements); err != nil {
		return "", errors.New("outputs is not a JSON array")
	}
	if len(elements) == 0 {
		return "", errors.New("outputs array is empty")
	}

	// Walk each output element looking for a changeSet with a gitPatch.
	for _, elem := range elements {
		var output struct {
			ChangeSet *struct {
				GitPatch *struct {
					UnidiffPatch string `json:"unidiffPatch"`
				} `json:"gitPatch"`
			} `json:"changeSet"`
		}
		if err := json.Unmarshal(elem, &output); err != nil {
			continue
		}
		if output.ChangeSet != nil && output.ChangeSet.GitPatch != nil && output.ChangeSet.GitPatch.UnidiffPatch != "" {
			return output.ChangeSet.GitPatch.UnidiffPatch, nil
		}
	}

	return "", errors.New("no patch found in session outputs")
}

// Activity represents an action taken by Jules within a session.
type Activity struct {
	Name        string     `json:"name,omitempty"`
	ID          string     `json:"id,omitempty"`
	Originator  string     `json:"originator,omitempty"`
	Description string     `json:"description,omitempty"`
	CreateTime  string     `json:"createTime,omitempty"`
	Artifacts   []Artifact `json:"artifacts,omitempty"`

	// Event fields (one-of semantics — only one will be non-nil).
	PlanEvent    *PlanEvent    `json:"planEvent,omitempty"`
	MessageEvent *MessageEvent `json:"messageEvent,omitempty"`
	CommitEvent  *CommitEvent  `json:"commitEvent,omitempty"`
	StatusEvent  *StatusEvent  `json:"statusEvent,omitempty"`
}

// Artifact is a file or diff produced by an activity.
type Artifact struct {
	Name    string `json:"name,omitempty"`
	Content string `json:"content,omitempty"`
	Type    string `json:"type,omitempty"`
}

// PlanEvent carries Jules's proposed plan.
type PlanEvent struct {
	PlanText string `json:"planText,omitempty"`
}

// MessageEvent carries a conversational message.
type MessageEvent struct {
	Text string `json:"text,omitempty"`
}

// CommitEvent carries a git commit reference.
type CommitEvent struct {
	CommitSHA string `json:"commitSha,omitempty"`
	Branch    string `json:"branch,omitempty"`
}

// StatusEvent carries a session state transition.
type StatusEvent struct {
	State   string `json:"state,omitempty"`
	Message string `json:"message,omitempty"`
}

// Source represents a GitHub repository registered with Jules.
type Source struct {
	Name       string      `json:"name,omitempty"`
	ID         string      `json:"id,omitempty"`
	GithubRepo *GithubRepo `json:"githubRepo,omitempty"`
}

// GithubRepo holds the GitHub repository details for a source.
type GithubRepo struct {
	Owner         string             `json:"owner,omitempty"`
	Repo          string             `json:"repo,omitempty"`
	IsPrivate     bool               `json:"isPrivate,omitempty"`
	DefaultBranch FlexibleString     `json:"defaultBranch,omitempty"`
	Branches      FlexibleStringList `json:"branches,omitempty"`
}

// ─── Request bodies ───────────────────────────────────────────────────────────

// CreateSourceRequest is the body for POST /sources.
type CreateSourceRequest struct {
	GithubRepo *GithubRepo `json:"githubRepo,omitempty"`
}

// CreateSessionRequest is the body for POST /sessions.
type CreateSessionRequest struct {
	Prompt              string         `json:"prompt"`
	SourceContext       *SourceContext `json:"sourceContext,omitempty"`
	RequirePlanApproval bool           `json:"requirePlanApproval,omitempty"`
	AutomationMode      string         `json:"automationMode,omitempty"`
}

// SendMessageRequest is the body for POST /sessions/{id}:sendMessage.
type SendMessageRequest struct {
	Message string `json:"prompt"`
}

// ─── Response wrappers ────────────────────────────────────────────────────────

// ListSessionsResponse is the response for GET /sessions.
type ListSessionsResponse struct {
	Sessions      []Session `json:"sessions"`
	NextPageToken string    `json:"nextPageToken,omitempty"`
}

// ListActivitiesResponse is the response for GET /sessions/{id}/activities.
type ListActivitiesResponse struct {
	Activities    []Activity `json:"activities"`
	NextPageToken string     `json:"nextPageToken,omitempty"`
}

// ListSourcesResponse is the response for GET /sources.
type ListSourcesResponse struct {
	Sources       []Source `json:"sources"`
	NextPageToken string   `json:"nextPageToken,omitempty"`
}

// ─── Error types ──────────────────────────────────────────────────────────────

// APIError represents a non-2xx response from the Jules API.
type APIError struct {
	Code    int    `json:"code"`
	Message string `json:"message"`
	Status  string `json:"status"`
}

func (e *APIError) Error() string {
	if e.Status != "" {
		return "jules API " + e.Status + ": " + e.Message
	}
	return "jules API error: " + e.Message
}
