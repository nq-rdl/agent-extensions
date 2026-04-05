package api_test

import (
	"strings"
	"testing"

	"github.com/nq-rdl/agent-skills/skills/jules/scripts/internal/model"
)

func TestListActivities(t *testing.T) {
	want := model.ListActivitiesResponse{
		Activities: []model.Activity{
			{ID: "act_1", Description: "Analysing repository"},
			{ID: "act_2", Description: "Writing plan"},
		},
	}
	ts, client := newTestServer(t, 200, want)

	got, err := client.ListActivities(t.Context(), "ses_123")
	if err != nil {
		t.Fatalf("unexpected error: %v", err)
	}
	if len(got) != 2 {
		t.Fatalf("len: got %d, want 2", len(got))
	}
	if got[1].ID != "act_2" {
		t.Errorf("activities[1].ID: got %q, want act_2", got[1].ID)
	}

	r := ts.lastRequest()
	if !strings.Contains(r.URL.Path, "ses_123") {
		t.Errorf("path should contain session ID: %s", r.URL.Path)
	}
	if !strings.HasSuffix(r.URL.Path, "/activities") {
		t.Errorf("path should end with /activities: %s", r.URL.Path)
	}
}

func TestGetActivity(t *testing.T) {
	want := model.Activity{
		ID:          "act_xyz",
		Description: "Generated diff",
		PlanEvent:   &model.PlanEvent{PlanText: "1. Fix bug\n2. Add tests"},
	}
	ts, client := newTestServer(t, 200, want)

	got, err := client.GetActivity(t.Context(), "ses_123", "act_xyz")
	if err != nil {
		t.Fatalf("unexpected error: %v", err)
	}
	if got.ID != want.ID {
		t.Errorf("ID: got %q, want %q", got.ID, want.ID)
	}
	if got.PlanEvent == nil {
		t.Fatal("PlanEvent should not be nil")
	}
	if !strings.HasPrefix(got.PlanEvent.PlanText, "1.") {
		t.Errorf("PlanText: got %q", got.PlanEvent.PlanText)
	}

	r := ts.lastRequest()
	if !strings.Contains(r.URL.Path, "act_xyz") {
		t.Errorf("path should contain activity ID: %s", r.URL.Path)
	}
	_ = ts
}
