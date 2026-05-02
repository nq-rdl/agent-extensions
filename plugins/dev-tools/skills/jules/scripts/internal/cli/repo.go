package cli

import (
	"fmt"
	"net/url"
	"os/exec"
	"strings"
)

// DetectRepo runs git remote get-url origin and returns the GitHub owner and
// repository name parsed from the URL.
func DetectRepo() (owner, repo string, err error) {
	out, err := exec.Command("git", "remote", "get-url", "origin").Output()
	if err != nil {
		return "", "", fmt.Errorf("git remote get-url origin: %w", err)
	}
	return parseGitURL(strings.TrimSpace(string(out)))
}

// parseGitURL handles SSH (git@github.com:owner/repo.git) and HTTPS formats.
func parseGitURL(rawURL string) (owner, repo string, err error) {
	if strings.HasPrefix(rawURL, "git@") {
		// git@github.com:owner/repo.git
		parts := strings.SplitN(rawURL, ":", 2)
		if len(parts) != 2 {
			return "", "", fmt.Errorf("unrecognised SSH git URL: %q", rawURL)
		}
		return splitOwnerRepo(parts[1])
	}

	u, err := url.Parse(rawURL)
	if err != nil {
		return "", "", fmt.Errorf("parse git URL %q: %w", rawURL, err)
	}
	return splitOwnerRepo(u.Path)
}

func splitOwnerRepo(path string) (owner, repo string, err error) {
	path = strings.TrimPrefix(path, "/")
	path = strings.TrimSuffix(path, ".git")
	parts := strings.SplitN(path, "/", 2)
	if len(parts) != 2 || parts[0] == "" || parts[1] == "" {
		return "", "", fmt.Errorf("expected owner/repo in %q", path)
	}
	return parts[0], parts[1], nil
}
