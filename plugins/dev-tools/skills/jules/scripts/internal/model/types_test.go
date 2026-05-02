package model

import (
	"encoding/json"
	"testing"
)

func TestExtractPatch(t *testing.T) {
	tests := []struct {
		name    string
		outputs json.RawMessage
		want    string
		wantErr string
	}{
		{
			name:    "nil outputs",
			outputs: nil,
			wantErr: "no outputs available",
		},
		{
			name:    "empty outputs",
			outputs: json.RawMessage{},
			wantErr: "no outputs available",
		},
		{
			name:    "not an array",
			outputs: json.RawMessage(`{"changeSet": {}}`),
			wantErr: "outputs is not a JSON array",
		},
		{
			name:    "empty array",
			outputs: json.RawMessage(`[]`),
			wantErr: "outputs array is empty",
		},
		{
			name:    "no changeSet in element",
			outputs: json.RawMessage(`[{"status": "done"}]`),
			wantErr: "no patch found in session outputs",
		},
		{
			name:    "changeSet without gitPatch",
			outputs: json.RawMessage(`[{"changeSet": {"description": "changes"}}]`),
			wantErr: "no patch found in session outputs",
		},
		{
			name:    "gitPatch with empty unidiffPatch",
			outputs: json.RawMessage(`[{"changeSet": {"gitPatch": {"unidiffPatch": ""}}}]`),
			wantErr: "no patch found in session outputs",
		},
		{
			name:    "valid patch",
			outputs: json.RawMessage(`[{"changeSet": {"gitPatch": {"unidiffPatch": "diff --git a/file.go b/file.go\n--- a/file.go\n+++ b/file.go\n@@ -1 +1 @@\n-old\n+new\n"}}}]`),
			want:    "diff --git a/file.go b/file.go\n--- a/file.go\n+++ b/file.go\n@@ -1 +1 @@\n-old\n+new\n",
		},
		{
			name:    "patch in second element",
			outputs: json.RawMessage(`[{"status": "done"}, {"changeSet": {"gitPatch": {"unidiffPatch": "diff --git a/x b/x\n"}}}]`),
			want:    "diff --git a/x b/x\n",
		},
		{
			name:    "first valid patch wins",
			outputs: json.RawMessage(`[{"changeSet": {"gitPatch": {"unidiffPatch": "first"}}}, {"changeSet": {"gitPatch": {"unidiffPatch": "second"}}}]`),
			want:    "first",
		},
		{
			name:    "malformed element skipped",
			outputs: json.RawMessage(`["not-an-object", {"changeSet": {"gitPatch": {"unidiffPatch": "patch-data"}}}]`),
			want:    "patch-data",
		},
	}

	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			got, err := ExtractPatch(tt.outputs)
			if tt.wantErr != "" {
				if err == nil {
					t.Fatalf("expected error containing %q, got nil", tt.wantErr)
				}
				if err.Error() != tt.wantErr {
					t.Errorf("error: got %q, want %q", err.Error(), tt.wantErr)
				}
				return
			}
			if err != nil {
				t.Fatalf("unexpected error: %v", err)
			}
			if got != tt.want {
				t.Errorf("patch: got %q, want %q", got, tt.want)
			}
		})
	}
}

func TestIsTerminal(t *testing.T) {
	terminal := []string{StateCompleted, StateFailed}
	for _, s := range terminal {
		if !IsTerminal(s) {
			t.Errorf("IsTerminal(%q) = false, want true", s)
		}
	}

	nonTerminal := []string{StateQueued, StatePlanning, StateAwaitingPlanApproval, StateInProgress, StatePaused, StateAwaitingUserFeedback, StateUnspecified}
	for _, s := range nonTerminal {
		if IsTerminal(s) {
			t.Errorf("IsTerminal(%q) = true, want false", s)
		}
	}
}

func TestCreateSessionRequestJSONOmitsZeroValues(t *testing.T) {
	data, err := json.Marshal(CreateSessionRequest{Prompt: "hello"})
	if err != nil {
		t.Fatalf("Marshal(CreateSessionRequest): %v", err)
	}

	got := string(data)
	if got != `{"prompt":"hello"}` {
		t.Fatalf("CreateSessionRequest JSON = %s, want %s", got, `{"prompt":"hello"}`)
	}
}
