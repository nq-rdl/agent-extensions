package validator_test

import (
	"fmt"
	"os"
	"path/filepath"
	"strings"
	"testing"

	"github.com/nq-rdl/agent-extensions/tools/asctl/internal/validator"
)

func TestMeasureBody(t *testing.T) {
	for _, tt := range []struct {
		name   string
		body   string
		lines  int
		tokens float64
	}{
		{"empty", "", 0, 0},
		{"unterminated", "abc", 1, 0.75},
		{"final newline", "abc\n", 1, 1},
		{"blank line", "\n", 1, 0.25},
		{"trailing blank lines", "a\n\n\n", 3, 1},
		{"leading blank line", "\na\n", 2, 0.75},
		{"CRLF", "a\r\n\r\n", 2, 1.25},
		{"multibyte", "é界😀\n", 1, 2.5},
		{"whitespace", " \t", 1, 0.5},
	} {
		t.Run(tt.name, func(t *testing.T) {
			got := validator.MeasureBody(tt.body)
			if got.Lines != tt.lines || got.ApproxTokens != tt.tokens {
				t.Fatalf("MeasureBody = %+v, want %d lines and %.2f estimated tokens", got, tt.lines, tt.tokens)
			}
		})
	}
}

func TestValidateBodyLimit(t *testing.T) {
	for _, newline := range []string{"\n", "\r\n"} {
		for _, final := range []bool{false, true} {
			for _, lines := range []int{500, 501} {
				t.Run(fmt.Sprintf("newline=%q/final=%t/lines=%d", newline, final, lines), func(t *testing.T) {
					dir := filepath.Join(t.TempDir(), "sample")
					if err := os.Mkdir(dir, 0o755); err != nil {
						t.Fatal(err)
					}
					body := strings.Repeat("x"+newline, lines)
					if !final {
						body = strings.TrimSuffix(body, newline)
					}
					content := strings.Join([]string{"---", "name: sample", "description: Test", "---", ""}, newline) + body
					if err := os.WriteFile(filepath.Join(dir, "SKILL.md"), []byte(content), 0o644); err != nil {
						t.Fatal(err)
					}
					errs := validator.Validate(dir)
					if lines == 500 && len(errs) != 0 {
						t.Fatalf("500 lines should pass: %v", errs)
					}
					if lines == 501 && (len(errs) != 1 || !strings.Contains(errs[0], "501 lines; repository limit is 500 body lines")) {
						t.Fatalf("expected actionable body limit error, got %v", errs)
					}
				})
			}
		}
	}
}

func TestValidateCountsBlankLinesAndPreservesMetadataErrors(t *testing.T) {
	dir := filepath.Join(t.TempDir(), "sample")
	if err := os.Mkdir(dir, 0o755); err != nil {
		t.Fatal(err)
	}
	// A leading and a trailing blank line bring the body from 499 to 501.
	content := "---\nname: sample\n---\n\n" + strings.Repeat("x\n", 499) + "\n"
	if err := os.WriteFile(filepath.Join(dir, "SKILL.md"), []byte(content), 0o644); err != nil {
		t.Fatal(err)
	}
	errs := validator.Validate(dir)
	if !containsSubstr(errs, "501 lines") || !containsSubstr(errs, "missing required field in frontmatter: description") {
		t.Fatalf("expected size and metadata errors, got %v", errs)
	}
}
