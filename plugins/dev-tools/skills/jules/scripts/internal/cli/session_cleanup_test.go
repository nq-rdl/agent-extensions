package cli

import (
	"testing"
	"time"

	"github.com/nq-rdl/agent-skills/skills/jules/scripts/internal/model"
)

func TestParseDuration(t *testing.T) {
	tests := []struct {
		input   string
		want    time.Duration
		wantErr bool
	}{
		{"7d", 7 * 24 * time.Hour, false},
		{"1d", 24 * time.Hour, false},
		{"30d", 30 * 24 * time.Hour, false},
		{"0d", 0, false},
		{"24h", 24 * time.Hour, false},
		{"2h30m", 2*time.Hour + 30*time.Minute, false},
		{"-1d", 0, true},
		{"-24h", 0, true},
		{"abc", 0, true},
		{"d", 0, true}, // no number before 'd'
	}

	for _, tt := range tests {
		t.Run(tt.input, func(t *testing.T) {
			got, err := parseDuration(tt.input)
			if tt.wantErr {
				if err == nil {
					t.Errorf("parseDuration(%q) = %v, want error", tt.input, got)
				}
				return
			}
			if err != nil {
				t.Errorf("parseDuration(%q) returned error: %v", tt.input, err)
				return
			}
			if got != tt.want {
				t.Errorf("parseDuration(%q) = %v, want %v", tt.input, got, tt.want)
			}
		})
	}
}

func TestFilterSessions(t *testing.T) {
	now := time.Now()
	old := now.Add(-10 * 24 * time.Hour).Format(time.RFC3339)    // 10 days ago
	recent := now.Add(-2 * 24 * time.Hour).Format(time.RFC3339)  // 2 days ago
	future := now.Add(24 * time.Hour).Format(time.RFC3339)        // tomorrow

	sessions := []model.Session{
		{ID: "old-completed", State: model.StateCompleted, CreateTime: old},
		{ID: "old-failed", State: model.StateFailed, CreateTime: old},
		{ID: "old-running", State: model.StateInProgress, CreateTime: old},
		{ID: "recent-completed", State: model.StateCompleted, CreateTime: recent},
		{ID: "future-completed", State: model.StateCompleted, CreateTime: future},
		{ID: "bad-time", State: model.StateCompleted, CreateTime: "not-a-time"},
	}

	threshold := now.Add(-7 * 24 * time.Hour) // 7 days ago
	states := []string{model.StateCompleted, model.StateFailed}

	got := filterSessions(sessions, states, threshold)

	if len(got) != 2 {
		t.Fatalf("filterSessions returned %d sessions, want 2", len(got))
	}

	wantIDs := map[string]bool{"old-completed": true, "old-failed": true}
	for _, s := range got {
		if !wantIDs[s.ID] {
			t.Errorf("unexpected session %q in results", s.ID)
		}
	}
}

func TestFilterSessions_CustomStates(t *testing.T) {
	old := time.Now().Add(-10 * 24 * time.Hour).Format(time.RFC3339)

	sessions := []model.Session{
		{ID: "completed", State: model.StateCompleted, CreateTime: old},
		{ID: "failed", State: model.StateFailed, CreateTime: old},
		{ID: "paused", State: model.StatePaused, CreateTime: old},
	}

	threshold := time.Now().Add(-7 * 24 * time.Hour)

	// Only target FAILED state.
	got := filterSessions(sessions, []string{model.StateFailed}, threshold)
	if len(got) != 1 || got[0].ID != "failed" {
		t.Errorf("expected only 'failed' session, got %v", got)
	}
}

func TestFilterSessions_Empty(t *testing.T) {
	got := filterSessions(nil, defaultCleanupStates, time.Now())
	if len(got) != 0 {
		t.Errorf("expected 0 sessions from nil input, got %d", len(got))
	}
}
