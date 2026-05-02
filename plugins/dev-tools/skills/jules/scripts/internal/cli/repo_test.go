package cli

import (
	"testing"
)

func TestParseGitURL(t *testing.T) {
	tests := []struct {
		name    string
		url     string
		owner   string
		repo    string
		wantErr bool
	}{
		{
			name:  "ssh format",
			url:   "git@github.com:nq-rdl/agent-ops.git",
			owner: "nq-rdl",
			repo:  "agent-ops",
		},
		{
			name:  "https with .git suffix",
			url:   "https://github.com/nq-rdl/agent-ops.git",
			owner: "nq-rdl",
			repo:  "agent-ops",
		},
		{
			name:  "https without .git suffix",
			url:   "https://github.com/nq-rdl/agent-ops",
			owner: "nq-rdl",
			repo:  "agent-ops",
		},
		{
			name:  "ssh org with dashes",
			url:   "git@github.com:my-org/my-repo.git",
			owner: "my-org",
			repo:  "my-repo",
		},
		{
			name:    "ssh no colon",
			url:     "git@github.com",
			wantErr: true,
		},
		{
			name:    "only owner, no repo",
			url:     "https://github.com/nq-rdl",
			wantErr: true,
		},
	}

	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			owner, repo, err := parseGitURL(tt.url)
			if (err != nil) != tt.wantErr {
				t.Fatalf("error: got %v, wantErr %v", err, tt.wantErr)
			}
			if err != nil {
				return
			}
			if owner != tt.owner {
				t.Errorf("owner: got %q, want %q", owner, tt.owner)
			}
			if repo != tt.repo {
				t.Errorf("repo: got %q, want %q", repo, tt.repo)
			}
		})
	}
}
