package orchestrate

import (
	"regexp"
	"slices"
	"strconv"
)

// depTriggerRe matches dependency trigger phrases and the #NNN following them.
// It captures the first issue number; additional "and #NNN" are handled by
// extractNumbers on the full phrase.
var depTriggerRe = regexp.MustCompile(`(?i)(?:depends\s+on|after|stacked\s+on|requires)\s+(#\d+(?:\s+and\s+#\d+)*)`)

// excludeRe matches reference-only patterns (closes, fixes, part of).
var excludeRe = regexp.MustCompile(`(?i)(?:part\s+of|clos(?:es?|ed?)|fix(?:es|ed?))\s+#(\d+)`)

// issueNumRe extracts bare #NNN issue numbers from text.
var issueNumRe = regexp.MustCompile(`#(\d+)`)

// ParseDependencies parses a GitHub issue body and extracts issue numbers
// that this issue depends on.
//
// Recognised dependency patterns (case-insensitive):
//
//	"depends on #20", "after #20", "stacked on #20", "requires #20"
//	"after #20 and #21" (multiple deps in one phrase)
//
// Excluded (reference-only, not dependency):
//
//	"part of #12", "closes #12", "fixes #12", "close #12", "fix #12"
func ParseDependencies(body string) []int {
	// Step 1: build exclusion set.
	excludedSet := make(map[int]bool)
	for _, m := range excludeRe.FindAllStringSubmatch(body, -1) {
		if n, err := strconv.Atoi(m[1]); err == nil {
			excludedSet[n] = true
		}
	}

	// Step 2: find all dependency trigger phrases and extract issue numbers from each.
	depsSet := make(map[int]bool)
	for _, phrase := range depTriggerRe.FindAllString(body, -1) {
		for _, m := range issueNumRe.FindAllStringSubmatch(phrase, -1) {
			if n, err := strconv.Atoi(m[1]); err == nil {
				if !excludedSet[n] {
					depsSet[n] = true
				}
			}
		}
	}

	if len(depsSet) == 0 {
		return nil
	}

	deps := make([]int, 0, len(depsSet))
	for n := range depsSet {
		deps = append(deps, n)
	}
	slices.Sort(deps)
	return deps
}
