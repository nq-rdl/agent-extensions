package orchestrate

import (
	"strings"
	"testing"
)

func TestSlug(t *testing.T) {
	tests := []struct {
		name  string
		title string
		want  string
	}{
		{
			name:  "simple title",
			title: "Define provider type",
			want:  "define-provider-type",
		},
		{
			name:  "special chars stripped",
			title: "Fix: auth/login (broken!)",
			want:  "fix-auth-login-broken",
		},
		{
			name:  "long title truncated",
			title: "This is a very long title that exceeds fifty characters in total length",
			want:  "this-is-a-very-long-title-that-exceeds-fifty-chara",
		},
		{
			name:  "leading trailing specials",
			title: "  --hello world--  ",
			want:  "hello-world",
		},
		{
			name:  "numbers preserved",
			title: "Issue 42 fix",
			want:  "issue-42-fix",
		},
	}

	for _, tc := range tests {
		t.Run(tc.name, func(t *testing.T) {
			got := Slug(tc.title)
			if len(got) > 50 {
				t.Errorf("Slug(%q) = %q (len %d > 50)", tc.title, got, len(got))
			}
			if strings.HasPrefix(got, "-") || strings.HasSuffix(got, "-") {
				t.Errorf("Slug(%q) = %q has leading/trailing hyphen", tc.title, got)
			}
			if tc.want != "" {
				if got != tc.want {
					t.Errorf("Slug(%q) = %q, want %q", tc.title, got, tc.want)
				}
			}
		})
	}
}

func TestSlugLongTitle(t *testing.T) {
	title := "This is a very long title that exceeds fifty characters in total length"
	got := Slug(title)
	if len(got) > 50 {
		t.Errorf("Slug long title: len %d > 50, got %q", len(got), got)
	}
	if strings.HasSuffix(got, "-") {
		t.Errorf("Slug long title has trailing hyphen: %q", got)
	}
}

func TestBranchName(t *testing.T) {
	tests := []struct {
		name   string
		prefix string
		issue  Issue
		want   string
	}{
		{
			name:   "standard branch",
			prefix: "jules",
			issue:  Issue{Number: 20, Title: "Define provider type"},
			want:   "jules/20-define-provider-type",
		},
		{
			name:   "empty prefix defaults to jules",
			prefix: "",
			issue:  Issue{Number: 5, Title: "Fix login bug"},
			want:   "jules/5-fix-login-bug",
		},
		{
			name:   "custom prefix",
			prefix: "feature",
			issue:  Issue{Number: 99, Title: "Add OAuth support"},
			want:   "feature/99-add-oauth-support",
		},
		{
			name:   "issue number in branch name",
			prefix: "jules",
			issue:  Issue{Number: 42, Title: "Update readme"},
			want:   "jules/42-update-readme",
		},
	}

	for _, tc := range tests {
		t.Run(tc.name, func(t *testing.T) {
			got := BranchName(tc.prefix, tc.issue)
			if got != tc.want {
				t.Errorf("BranchName(%q, %v) = %q, want %q", tc.prefix, tc.issue, got, tc.want)
			}
		})
	}
}
