package main

import (
	"bytes"
	"os"
	"path/filepath"
	"strings"
	"testing"
)

func writeSkill(t *testing.T, root, name, body string) string {
	t.Helper()
	dir := filepath.Join(root, name)
	if err := os.MkdirAll(dir, 0o755); err != nil {
		t.Fatal(err)
	}
	content := "---\nname: " + name + "\ndescription: Test\n---\n" + body
	if err := os.WriteFile(filepath.Join(dir, "SKILL.md"), []byte(content), 0o644); err != nil {
		t.Fatal(err)
	}
	return dir
}

func execute(args ...string) (string, string, error) {
	cmd := newRootCmd()
	var out, stderr bytes.Buffer
	cmd.SetOut(&out)
	cmd.SetErr(&stderr)
	cmd.SetArgs(args)
	cmd.SilenceUsage = true
	cmd.SilenceErrors = true
	err := cmd.Execute()
	return out.String(), stderr.String(), err
}

func TestCommandsEnforceBodyLimit(t *testing.T) {
	for _, lines := range []int{500, 501} {
		root := t.TempDir()
		dir := writeSkill(t, root, "sample", strings.Repeat("x\n", lines))
		for _, args := range [][]string{
			{"validate", dir},
			{"repo-check", "--skills-root", root},
			{"repo-check", "--skills-root", root, "--size-report"},
		} {
			out, stderr, err := execute(args...)
			if lines == 500 && err != nil {
				t.Fatalf("%v rejected 500 lines: %v, %s", args, err, stderr)
			}
			if lines == 501 && (err == nil || !strings.Contains(stderr, "501 lines; repository limit is 500 body lines")) {
				t.Fatalf("%v did not reject 501 lines: %v, %s", args, err, stderr)
			}
			if args[len(args)-1] == "--size-report" && !strings.Contains(out, "Approx tokens") {
				t.Fatalf("missing report for %v: %s", args, out)
			}
		}
	}
}

func TestSizeReportKeepsExistingErrors(t *testing.T) {
	for _, content := range []string{
		"no frontmatter", "---\nname: broken\n", "---\n: invalid: yaml:\n---\n",
		"---\nname: broken\n---\nbody\n",
	} {
		root := t.TempDir()
		dir := writeSkill(t, root, "broken", "")
		if err := os.WriteFile(filepath.Join(dir, "SKILL.md"), []byte(content), 0o644); err != nil {
			t.Fatal(err)
		}
		if err := os.WriteFile(filepath.Join(dir, "unexpected.txt"), nil, 0o644); err != nil {
			t.Fatal(err)
		}
		_, plainErrors, plainErr := execute("repo-check", "--skills-root", root)
		out, reportErrors, reportErr := execute("repo-check", "--skills-root", root, "--size-report")
		if plainErr == nil || reportErr == nil || plainErr.Error() != reportErr.Error() || plainErrors != reportErrors {
			t.Fatalf("report changed validation: %v/%q vs %v/%q", plainErr, plainErrors, reportErr, reportErrors)
		}
		if !strings.Contains(out, "Approx tokens") || !strings.Contains(reportErrors, "unexpected.txt") {
			t.Fatalf("missing report or existing structure error: %q %q", out, reportErrors)
		}
	}
}

func TestSizeReportRespectsSelectedPaths(t *testing.T) {
	root := t.TempDir()
	selected := writeSkill(t, root, "selected", "é界😀\n")
	writeSkill(t, root, "unselected", strings.Repeat("x\n", 501))
	out, stderr, err := execute("repo-check", "--skills-root", root, "--size-report", filepath.Join(selected, "SKILL.md"))
	if err != nil || strings.Contains(out, "unselected") || !strings.Contains(out, "2.50") {
		t.Fatalf("selected report: %v, %q, %q", err, out, stderr)
	}
	out, _, err = execute("repo-check", "--skills-root", root, "--size-report", filepath.Join(t.TempDir(), "README.md"))
	if err != nil || !strings.Contains(out, "No skill directories selected") {
		t.Fatalf("empty selection: %v, %q", err, out)
	}
}
