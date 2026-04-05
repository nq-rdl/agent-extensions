package cli

import (
	"testing"
)

func TestNormalizeSourceName(t *testing.T) {
	tests := []struct {
		name   string
		input  string
		want   string
	}{
		{
			name:  "short form gets prefix",
			input: "github/nq-rdl/crabpod",
			want:  "sources/github/nq-rdl/crabpod",
		},
		{
			name:  "full resource name unchanged",
			input: "sources/github/nq-rdl/crabpod",
			want:  "sources/github/nq-rdl/crabpod",
		},
		{
			name:  "different provider short form",
			input: "github/my-org/my-repo",
			want:  "sources/github/my-org/my-repo",
		},
		{
			name:  "bare name gets prefix",
			input: "my-source",
			want:  "sources/my-source",
		},
	}

	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			got := normalizeSourceName(tt.input)
			if got != tt.want {
				t.Errorf("normalizeSourceName(%q) = %q, want %q", tt.input, got, tt.want)
			}
		})
	}
}

func TestDefaultAutomationMode(t *testing.T) {
	if defaultAutomationMode != "AUTO_CREATE_PR" {
		t.Errorf("defaultAutomationMode = %q, want %q", defaultAutomationMode, "AUTO_CREATE_PR")
	}
}

func TestDefaultAutomationMode_AppliedToRequest(t *testing.T) {
	// When no --automation-mode flag is passed, the default should be used.
	// resolveAutomationMode returns the effective mode given a flag value.
	got := resolveAutomationMode("")
	if got != "AUTO_CREATE_PR" {
		t.Errorf("resolveAutomationMode(\"\") = %q, want %q", got, "AUTO_CREATE_PR")
	}
}

func TestResolveAutomationMode_ExplicitOverride(t *testing.T) {
	got := resolveAutomationMode("FULL_AUTO")
	if got != "FULL_AUTO" {
		t.Errorf("resolveAutomationMode(\"FULL_AUTO\") = %q, want %q", got, "FULL_AUTO")
	}
}
