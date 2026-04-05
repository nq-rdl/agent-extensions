package orchestrate

import (
	"fmt"
	"slices"
)

// TopoSort performs a topological sort using Kahn's algorithm.
// Returns (order, parallelGroups, err).
//   - order: all issue numbers in topological order (flat)
//   - parallelGroups: issues grouped by BFS level (same group = can run in parallel)
//   - err: non-nil if a cycle is detected
//
// Issues that depend on numbers NOT in the set are treated as having no
// external deps (already satisfied).
// Output is deterministic: within each group, numbers are sorted ascending.
func TopoSort(issues []Issue) (order []int, groups [][]int, err error) {
	// Build a set of all known issue numbers.
	known := make(map[int]bool, len(issues))
	for _, iss := range issues {
		known[iss.Number] = true
	}

	// Build adjacency and in-degree maps.
	// inDegree[n] = number of unresolved dependencies for issue n.
	inDegree := make(map[int]int, len(issues))
	// dependents[n] = list of issue numbers that depend on n.
	dependents := make(map[int][]int, len(issues))

	for _, iss := range issues {
		if _, exists := inDegree[iss.Number]; !exists {
			inDegree[iss.Number] = 0
		}
		for _, dep := range iss.DependsOn {
			if !known[dep] {
				// External dep, already satisfied — skip.
				continue
			}
			inDegree[iss.Number]++
			dependents[dep] = append(dependents[dep], iss.Number)
		}
	}

	// Collect initial frontier: issues with in-degree 0.
	var current []int
	for n, deg := range inDegree {
		if deg == 0 {
			current = append(current, n)
		}
	}
	slices.Sort(current)

	processed := 0
	for len(current) > 0 {
		groups = append(groups, current)
		order = append(order, current...)
		processed += len(current)

		var next []int
		for _, n := range current {
			for _, dep := range dependents[n] {
				inDegree[dep]--
				if inDegree[dep] == 0 {
					next = append(next, dep)
				}
			}
		}
		slices.Sort(next)
		current = next
	}

	if processed != len(issues) {
		// Cycle: find remaining issues.
		var remaining []int
		for n, deg := range inDegree {
			if deg > 0 {
				remaining = append(remaining, n)
			}
		}
		slices.Sort(remaining)
		return nil, nil, fmt.Errorf("cycle detected involving issues: %v", remaining)
	}

	return order, groups, nil
}
