package orchestrate

import (
	"slices"
	"testing"
)

func TestTopoSort(t *testing.T) {
	tests := []struct {
		name        string
		issues      []Issue
		wantOrder   []int
		wantGroups  [][]int
		wantErr     bool
	}{
		{
			name:       "single issue no deps",
			issues:     []Issue{{Number: 5}},
			wantOrder:  []int{5},
			wantGroups: [][]int{{5}},
		},
		{
			name: "linear chain 3 depends on 2 depends on 1",
			issues: []Issue{
				{Number: 3, DependsOn: []int{2}},
				{Number: 2, DependsOn: []int{1}},
				{Number: 1},
			},
			wantOrder:  []int{1, 2, 3},
			wantGroups: [][]int{{1}, {2}, {3}},
		},
		{
			name: "diamond: 3 and 4 depend on 2, 2 depends on 1",
			issues: []Issue{
				{Number: 1},
				{Number: 2, DependsOn: []int{1}},
				{Number: 3, DependsOn: []int{2}},
				{Number: 4, DependsOn: []int{2}},
			},
			wantOrder:  []int{1, 2, 3, 4},
			wantGroups: [][]int{{1}, {2}, {3, 4}},
		},
		{
			name: "independent issues in one group",
			issues: []Issue{
				{Number: 10},
				{Number: 20},
				{Number: 30},
			},
			wantOrder:  []int{10, 20, 30},
			wantGroups: [][]int{{10, 20, 30}},
		},
		{
			name: "external dep treated as satisfied",
			issues: []Issue{
				{Number: 7, DependsOn: []int{999}}, // 999 not in set
			},
			wantOrder:  []int{7},
			wantGroups: [][]int{{7}},
		},
		{
			name: "cycle detection",
			issues: []Issue{
				{Number: 1, DependsOn: []int{2}},
				{Number: 2, DependsOn: []int{1}},
			},
			wantErr: true,
		},
	}

	for _, tc := range tests {
		t.Run(tc.name, func(t *testing.T) {
			order, groups, err := TopoSort(tc.issues)
			if tc.wantErr {
				if err == nil {
					t.Fatalf("TopoSort() expected error, got nil")
				}
				return
			}
			if err != nil {
				t.Fatalf("TopoSort() unexpected error: %v", err)
			}

			if !slices.Equal(order, tc.wantOrder) {
				t.Errorf("order = %v, want %v", order, tc.wantOrder)
			}

			if len(groups) != len(tc.wantGroups) {
				t.Fatalf("groups len = %d, want %d: got %v, want %v",
					len(groups), len(tc.wantGroups), groups, tc.wantGroups)
			}
			for i := range groups {
				if !slices.Equal(groups[i], tc.wantGroups[i]) {
					t.Errorf("groups[%d] = %v, want %v", i, groups[i], tc.wantGroups[i])
				}
			}
		})
	}
}
