package config

import (
	"os"
	"path/filepath"
	"testing"
)

func TestDetectProvider(t *testing.T) {
	tests := []struct {
		name     string
		content  string // empty means no file
		want     string
	}{
		{
			name: "no auth file",
			want: "openai",
		},
		{
			name:    "openai-codex key present",
			content: `{"openai-codex": {"token": "abc"}}`,
			want:    "openai-codex",
		},
		{
			name:    "only openai key",
			content: `{"openai": {"token": "xyz"}}`,
			want:    "openai",
		},
		{
			name:    "both keys present prefers openai-codex",
			content: `{"openai": {"token": "xyz"}, "openai-codex": {"token": "abc"}}`,
			want:    "openai-codex",
		},
		{
			name:    "malformed json",
			content: `{bad json`,
			want:    "openai",
		},
	}

	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			// Create a temp home directory
			tmpHome := t.TempDir()
			t.Setenv("HOME", tmpHome)

			if tt.content != "" {
				authDir := filepath.Join(tmpHome, ".pi", "agent")
				if err := os.MkdirAll(authDir, 0o755); err != nil {
					t.Fatal(err)
				}
				if err := os.WriteFile(filepath.Join(authDir, "auth.json"), []byte(tt.content), 0o644); err != nil {
					t.Fatal(err)
				}
			}

			got := DetectProvider()
			if got != tt.want {
				t.Errorf("DetectProvider() = %q, want %q", got, tt.want)
			}
		})
	}
}
