package orchestrate

import (
	"testing"
)

func TestParseDependencies(t *testing.T) {
	tests := []struct {
		name string
		body string
		want []int
	}{
		{
			name: "depends on single",
			body: "depends on #20",
			want: []int{20},
		},
		{
			name: "after multiple",
			body: "After #20 and #21",
			want: []int{20, 21},
		},
		{
			name: "part of excluded",
			body: "Part of #12",
			want: nil,
		},
		{
			name: "depends on with fixes excluded",
			body: "depends on #20, Fixes #21",
			want: []int{20},
		},
		{
			name: "stacked on multiple",
			body: "stacked on #5 and #6",
			want: []int{5, 6},
		},
		{
			name: "requires single",
			body: "requires #30",
			want: []int{30},
		},
		{
			name: "closes excluded depends included",
			body: "closes #10, depends on #11",
			want: []int{11},
		},
		{
			name: "same issue in dependency and close phrase is excluded",
			body: "depends on #20 closes #20",
			want: nil,
		},
		{
			name: "empty body",
			body: "",
			want: nil,
		},
	}

	for _, tc := range tests {
		t.Run(tc.name, func(t *testing.T) {
			got := ParseDependencies(tc.body)
			if len(got) != len(tc.want) {
				t.Fatalf("ParseDependencies(%q) = %v, want %v", tc.body, got, tc.want)
			}
			for i := range got {
				if got[i] != tc.want[i] {
					t.Errorf("ParseDependencies(%q)[%d] = %d, want %d", tc.body, i, got[i], tc.want[i])
				}
			}
		})
	}
}
