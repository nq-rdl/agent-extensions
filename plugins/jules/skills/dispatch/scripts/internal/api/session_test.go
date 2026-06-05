package api_test

import (
	"encoding/json"
	"strings"
	"testing"

	"github.com/nq-rdl/agent-skills/skills/jules/scripts/internal/model"
)

func TestCreateSession(t *testing.T) {
	want := model.Session{
		ID:    "ses_abc",
		State: "QUEUED",
		Title: "Fix login bug",
	}
	ts, client := newTestServer(t, 200, want)

	req := &model.CreateSessionRequest{
		Prompt: "Fix the login bug",
		SourceContext: &model.SourceContext{
			Source: "sources/src_123",
			GithubRepoContext: &model.GithubRepoContext{
				StartingBranch: "main",
			},
		},
	}

	got, err := client.CreateSession(t.Context(), req)
	if err != nil {
		t.Fatalf("unexpected error: %v", err)
	}
	if got.ID != want.ID {
		t.Errorf("ID: got %q, want %q", got.ID, want.ID)
	}
	if got.State != want.State {
		t.Errorf("State: got %q, want %q", got.State, want.State)
	}

	r := ts.lastRequest()
	if r.Method != "POST" {
		t.Errorf("method: got %s, want POST", r.Method)
	}
	if !strings.HasSuffix(r.URL.Path, "/sessions") {
		t.Errorf("path: got %s, want .../sessions", r.URL.Path)
	}

	var body model.CreateSessionRequest
	if err := json.Unmarshal(ts.lastBody(), &body); err != nil {
		t.Fatalf("unmarshal request body: %v", err)
	}
	if body.Prompt != req.Prompt {
		t.Errorf("body.Prompt: got %q, want %q", body.Prompt, req.Prompt)
	}
}

func TestListSessions(t *testing.T) {
	want := model.ListSessionsResponse{
		Sessions: []model.Session{
			{ID: "ses_1", State: "COMPLETED"},
			{ID: "ses_2", State: "QUEUED"},
		},
	}
	ts, client := newTestServer(t, 200, want)

	got, err := client.ListSessions(t.Context())
	if err != nil {
		t.Fatalf("unexpected error: %v", err)
	}
	if len(got) != 2 {
		t.Fatalf("len: got %d, want 2", len(got))
	}
	if got[0].ID != "ses_1" {
		t.Errorf("sessions[0].ID: got %q, want ses_1", got[0].ID)
	}

	r := ts.lastRequest()
	if r.Method != "GET" {
		t.Errorf("method: got %s, want GET", r.Method)
	}
	_ = ts // avoid unused warning
}

func TestGetSession(t *testing.T) {
	want := model.Session{ID: "ses_xyz", State: "IN_PROGRESS"}
	_, client := newTestServer(t, 200, want)

	got, err := client.GetSession(t.Context(), "ses_xyz")
	if err != nil {
		t.Fatalf("unexpected error: %v", err)
	}
	if got.ID != want.ID {
		t.Errorf("ID: got %q, want %q", got.ID, want.ID)
	}
}

func TestDeleteSession(t *testing.T) {
	ts, client := newTestServer(t, 200, nil)

	if err := client.DeleteSession(t.Context(), "ses_del"); err != nil {
		t.Fatalf("unexpected error: %v", err)
	}
	r := ts.lastRequest()
	if r.Method != "DELETE" {
		t.Errorf("method: got %s, want DELETE", r.Method)
	}
	if !strings.HasSuffix(r.URL.Path, "/ses_del") {
		t.Errorf("path: got %s", r.URL.Path)
	}
}

func TestSendMessage(t *testing.T) {
	want := model.Session{ID: "ses_msg", State: "PLANNING"}
	ts, client := newTestServer(t, 200, want)

	got, err := client.SendMessage(t.Context(), "ses_msg", "please focus on the auth module")
	if err != nil {
		t.Fatalf("unexpected error: %v", err)
	}
	if got.ID != want.ID {
		t.Errorf("ID: got %q, want %q", got.ID, want.ID)
	}

	r := ts.lastRequest()
	if !strings.HasSuffix(r.URL.Path, ":sendMessage") {
		t.Errorf("path: got %s, want .../sendMessage", r.URL.Path)
	}

	var body model.SendMessageRequest
	if err := json.Unmarshal(ts.lastBody(), &body); err != nil {
		t.Fatalf("unmarshal: %v", err)
	}
	if body.Message != "please focus on the auth module" {
		t.Errorf("message: got %q", body.Message)
	}
}

func TestApprovePlan(t *testing.T) {
	want := model.Session{ID: "ses_plan", State: "IN_PROGRESS"}
	ts, client := newTestServer(t, 200, want)

	got, err := client.ApprovePlan(t.Context(), "ses_plan")
	if err != nil {
		t.Fatalf("unexpected error: %v", err)
	}
	if got.State != "IN_PROGRESS" {
		t.Errorf("State: got %q", got.State)
	}

	r := ts.lastRequest()
	if !strings.HasSuffix(r.URL.Path, ":approvePlan") {
		t.Errorf("path: got %s, want .../approvePlan", r.URL.Path)
	}
	_ = ts
}
