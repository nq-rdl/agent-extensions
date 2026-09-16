package repocheck_test

import (
	"bytes"
	"os"
	"path/filepath"
	"strings"
	"testing"

	"github.com/nq-rdl/agent-extensions/tools/asctl/internal/repocheck"
)

func TestSizeReportSortsCountsAndMarksUnavailable(t *testing.T) {
	root := t.TempDir()
	alpha := makeSkillDir(t, root, "alpha", "Test")
	beta := makeSkillDir(t, root, "beta", "Test")
	large := makeSkillDir(t, root, "large", "Test")
	broken := makeSkillDir(t, root, "broken", "Test")
	missing := filepath.Join(root, "missing")
	if err := os.Mkdir(missing, 0o755); err != nil {
		t.Fatal(err)
	}
	for dir, body := range map[string]string{alpha: "é界😀\n", beta: "x", large: "\na\n\n"} {
		f, err := os.OpenFile(filepath.Join(dir, "SKILL.md"), os.O_APPEND|os.O_WRONLY, 0o644)
		if err != nil {
			t.Fatal(err)
		}
		if _, err := f.WriteString(body); err != nil {
			f.Close()
			t.Fatal(err)
		}
		if err := f.Close(); err != nil {
			t.Fatal(err)
		}
	}
	if err := os.WriteFile(filepath.Join(broken, "SKILL.md"), []byte("---\n: invalid: yaml:\n---\n"), 0o644); err != nil {
		t.Fatal(err)
	}
	for _, path := range []string{"references/one.rst", "references/nested/two.rst", "references/.hidden.rst", "references/.hidden/three.rst"} {
		full := filepath.Join(alpha, path)
		if err := os.MkdirAll(filepath.Dir(full), 0o755); err != nil {
			t.Fatal(err)
		}
		if err := os.WriteFile(full, nil, 0o644); err != nil {
			t.Fatal(err)
		}
	}
	if err := os.Symlink("one.rst", filepath.Join(alpha, "references/link.rst")); err != nil {
		t.Fatal(err)
	}
	var out bytes.Buffer
	repocheck.WriteSizeReport(&out, []string{missing, broken, beta, alpha, large})
	lines := strings.Split(out.String(), "\n")
	want := [][]string{
		{large, "3", "1.00", "0"},
		{alpha, "1", "2.50", "2"},
		{beta, "1", "0.25", "0"},
		{broken, "n/a", "n/a", "0"},
		{missing, "n/a", "n/a", "0"},
	}
	for i, row := range want {
		if got := strings.Fields(lines[i+2]); strings.Join(got, "|") != strings.Join(row, "|") {
			t.Errorf("row %d = %v, want %v", i, got, row)
		}
	}
	if !strings.Contains(out.String(), "body size unavailable: invalid YAML") || !strings.Contains(out.String(), "not measured model usage") {
		t.Fatalf("missing unavailable/estimate explanations: %s", out.String())
	}
}

func TestReferenceCountFailureIsNotZero(t *testing.T) {
	dir := makeSkillDir(t, t.TempDir(), "sample", "Test")
	if err := os.WriteFile(filepath.Join(dir, "references"), nil, 0o644); err != nil {
		t.Fatal(err)
	}
	var out bytes.Buffer
	repocheck.WriteSizeReport(&out, []string{dir})
	row := strings.Fields(strings.Split(out.String(), "\n")[2])
	if row[len(row)-1] != "n/a" || !strings.Contains(out.String(), "reference count unavailable") {
		t.Fatalf("unavailable reference count reported as zero: %s", out.String())
	}
}
