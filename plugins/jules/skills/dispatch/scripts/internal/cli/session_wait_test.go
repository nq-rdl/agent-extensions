package cli

import (
	"context"
	"sync/atomic"
	"testing"
	"time"

	"github.com/nq-rdl/agent-skills/skills/jules/scripts/internal/model"
)

// fakeSessionGetter returns a sequence of sessions, one per call to GetSession.
type fakeSessionGetter struct {
	sessions []model.Session
	calls    atomic.Int32
}

func (f *fakeSessionGetter) GetSession(_ context.Context, id string) (*model.Session, error) {
	idx := int(f.calls.Add(1)) - 1
	if idx >= len(f.sessions) {
		idx = len(f.sessions) - 1
	}
	s := f.sessions[idx]
	s.ID = id
	return &s, nil
}

func TestPollSession_ImmediateTerminal(t *testing.T) {
	fake := &fakeSessionGetter{
		sessions: []model.Session{
			{State: "COMPLETED", Title: "done"},
		},
	}

	code := pollSession(t.Context(), fake, "ses_1", "", 50*time.Millisecond, false)
	if code != 0 {
		t.Errorf("exit code: got %d, want 0", code)
	}
	if got := int(fake.calls.Load()); got != 1 {
		t.Errorf("calls: got %d, want 1", got)
	}
}

func TestPollSession_TransitionsToCompleted(t *testing.T) {
	fake := &fakeSessionGetter{
		sessions: []model.Session{
			{State: "QUEUED"},
			{State: "IN_PROGRESS"},
			{State: "COMPLETED", Title: "finished"},
		},
	}

	code := pollSession(t.Context(), fake, "ses_2", "", 10*time.Millisecond, false)
	if code != 0 {
		t.Errorf("exit code: got %d, want 0", code)
	}
	if got := int(fake.calls.Load()); got != 3 {
		t.Errorf("calls: got %d, want 3", got)
	}
}

func TestPollSession_AwaitingPlanApproval(t *testing.T) {
	fake := &fakeSessionGetter{
		sessions: []model.Session{
			{State: "PLANNING"},
			{State: "AWAITING_PLAN_APPROVAL"},
		},
	}

	code := pollSession(t.Context(), fake, "ses_3", "", 10*time.Millisecond, false)
	if code != 0 {
		t.Errorf("exit code: got %d, want 0", code)
	}
	if got := int(fake.calls.Load()); got != 2 {
		t.Errorf("calls: got %d, want 2", got)
	}
}

func TestPollSession_FailedState(t *testing.T) {
	fake := &fakeSessionGetter{
		sessions: []model.Session{
			{State: "IN_PROGRESS"},
			{State: "FAILED"},
		},
	}

	code := pollSession(t.Context(), fake, "ses_4", "", 10*time.Millisecond, false)
	if code != 0 {
		t.Errorf("exit code: got %d, want 0", code)
	}
}

func TestPollSession_TargetState(t *testing.T) {
	fake := &fakeSessionGetter{
		sessions: []model.Session{
			{State: "QUEUED"},
			{State: "IN_PROGRESS"},
		},
	}

	code := pollSession(t.Context(), fake, "ses_5", "IN_PROGRESS", 10*time.Millisecond, false)
	if code != 0 {
		t.Errorf("exit code: got %d, want 0", code)
	}
	if got := int(fake.calls.Load()); got != 2 {
		t.Errorf("calls: got %d, want 2", got)
	}
}

func TestPollSession_Timeout(t *testing.T) {
	fake := &fakeSessionGetter{
		sessions: []model.Session{
			{State: "IN_PROGRESS"},
		},
	}

	ctx, cancel := context.WithTimeout(t.Context(), 50*time.Millisecond)
	defer cancel()

	code := pollSession(ctx, fake, "ses_6", "", 10*time.Millisecond, false)
	if code != 3 {
		t.Errorf("exit code: got %d, want 3 (timeout)", code)
	}
}

func TestIsTargetState(t *testing.T) {
	tests := []struct {
		state  string
		target string
		want   bool
	}{
		{"COMPLETED", "", true},
		{"FAILED", "", true},
		{"AWAITING_PLAN_APPROVAL", "", true},
		{"IN_PROGRESS", "", false},
		{"QUEUED", "", false},
		{"PLANNING", "", false},
		{"IN_PROGRESS", "IN_PROGRESS", true},
		{"QUEUED", "COMPLETED", false},
		{"COMPLETED", "COMPLETED", true},
	}
	for _, tt := range tests {
		t.Run(tt.state+"_target_"+tt.target, func(t *testing.T) {
			got := isTargetState(tt.state, tt.target)
			if got != tt.want {
				t.Errorf("isTargetState(%q, %q): got %v, want %v", tt.state, tt.target, got, tt.want)
			}
		})
	}
}
