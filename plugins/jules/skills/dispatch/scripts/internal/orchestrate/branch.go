package orchestrate

import (
	"cmp"
	"fmt"
	"regexp"
	"strings"
)

// nonAlphanumRe matches one or more non-alphanumeric characters.
var nonAlphanumRe = regexp.MustCompile(`[^a-z0-9]+`)

// Slug converts a title to kebab-case, max 50 chars, alphanumeric + hyphens only.
// Non-ASCII characters are treated as separators, which matches the mostly-ASCII
// issue titles this helper is expected to receive from GitHub.
func Slug(title string) string {
	s := strings.ToLower(title)
	s = nonAlphanumRe.ReplaceAllString(s, "-")
	s = strings.Trim(s, "-")
	if len(s) <= 50 {
		return s
	}
	s = s[:50]
	// Strip trailing hyphen after truncation.
	s = strings.TrimRight(s, "-")
	return s
}

// BranchName returns a git branch name like "jules/20-define-provider-type".
// prefix defaults to "jules" if empty.
func BranchName(prefix string, issue Issue) string {
	prefix = cmp.Or(prefix, "jules")
	return fmt.Sprintf("%s/%d-%s", prefix, issue.Number, Slug(issue.Title))
}
