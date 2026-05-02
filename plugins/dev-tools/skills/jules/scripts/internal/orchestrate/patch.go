package orchestrate

import (
	"os"
	"path/filepath"
	"regexp"
	"strings"
)

// diffHeaderRe extracts the b/ path from a "diff --git a/... b/..." header line.
var diffHeaderRe = regexp.MustCompile(`diff --git a/\S+ b/(\S+)`)

// devNullRe detects new-file diffs (--- /dev/null).
var devNullRe = regexp.MustCompile(`(?m)^--- /dev/null`)

// SplitPatch splits a combined unified diff into per-file PatchFile slices.
// Each diff starts with "diff --git a/<path> b/<path>".
// The path is extracted from the "b/<path>" side of the header line.
func SplitPatch(patch string) []PatchFile {
	if patch == "" {
		return nil
	}

	// Normalise: split on "\ndiff --git " as the separator.
	// If the patch starts with "diff --git " (no leading newline), prepend a
	// newline so the split works uniformly.
	if strings.HasPrefix(patch, "diff --git ") {
		patch = "\n" + patch
	}

	const sep = "\ndiff --git "
	parts := strings.Split(patch, sep)
	// parts[0] is the preamble (empty or non-diff content); skip it.

	var files []PatchFile
	for _, part := range parts[1:] {
		chunk := "diff --git " + part
		m := diffHeaderRe.FindStringSubmatch(chunk)
		if m == nil {
			continue
		}
		path := m[1]
		files = append(files, PatchFile{
			Path:      path,
			Diff:      chunk,
			IsNewFile: IsNewFile(chunk),
			IsStub:    false,
		})
	}
	return files
}

// IsNewFile returns true if the diff adds a new file (--- /dev/null header).
func IsNewFile(diff string) bool {
	return devNullRe.MatchString(diff)
}

// IsStub checks whether a patch file represents a stub that already exists
// on disk and is longer than the patch would produce.
func IsStub(pf PatchFile, workDir string) (bool, error) {
	if !pf.IsNewFile {
		return false, nil
	}
	fullPath := filepath.Join(workDir, pf.Path)
	info, err := os.Stat(fullPath)
	if err != nil {
		if os.IsNotExist(err) {
			return false, nil
		}
		return false, err
	}
	return info.Size() > int64(newFileSize(pf.Diff)), nil
}

// newFileSize estimates the byte length of the file a new-file diff would
// create by summing added lines and their trailing newlines.
func newFileSize(diff string) int {
	size := 0
	inHunk := false
	lastLineWasAdd := false

	for _, line := range strings.Split(diff, "\n") {
		switch {
		case strings.HasPrefix(line, "@@"):
			inHunk = true
			lastLineWasAdd = false
		case strings.HasPrefix(line, "diff --git "),
			strings.HasPrefix(line, "index "),
			strings.HasPrefix(line, "new file mode "),
			strings.HasPrefix(line, "--- "),
			strings.HasPrefix(line, "+++ "):
			lastLineWasAdd = false
		case !inHunk:
			lastLineWasAdd = false
		case strings.HasPrefix(line, `\ No newline at end of file`):
			if lastLineWasAdd && size > 0 {
				size--
			}
			lastLineWasAdd = false
		case strings.HasPrefix(line, "+"):
			size += len(line[1:]) + 1
			lastLineWasAdd = true
		default:
			lastLineWasAdd = false
		}
	}

	return size
}
