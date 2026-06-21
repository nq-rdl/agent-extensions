package parser_test

import (
	"os"
	"path/filepath"
	"strings"
	"testing"

	"github.com/nq-rdl/agent-extensions/tools/asctl/internal/parser"
)

func writeSkillMD(t *testing.T, dir, content string) {
	t.Helper()
	if err := os.WriteFile(filepath.Join(dir, "SKILL.md"), []byte(content), 0o644); err != nil {
		t.Fatal(err)
	}
}

func TestReadProperties_valid(t *testing.T) {
	dir := t.TempDir()
	writeSkillMD(t, dir, "---\nname: my-skill\ndescription: A useful skill\nlicense: MIT\n---\n# Body\n")

	props, err := parser.ReadProperties(dir)
	if err != nil {
		t.Fatalf("unexpected error: %v", err)
	}
	if props.Name != "my-skill" {
		t.Errorf("Name = %q, want %q", props.Name, "my-skill")
	}
	if props.Description != "A useful skill" {
		t.Errorf("Description = %q, want %q", props.Description, "A useful skill")
	}
	if props.License != "MIT" {
		t.Errorf("License = %q, want %q", props.License, "MIT")
	}
}

func TestReadProperties_missingFile(t *testing.T) {
	dir := t.TempDir()
	_, err := parser.ReadProperties(dir)
	if err == nil {
		t.Fatal("expected error for missing SKILL.md")
	}
}

func TestReadProperties_missingName(t *testing.T) {
	dir := t.TempDir()
	writeSkillMD(t, dir, "---\ndescription: desc\n---\n")
	_, err := parser.ReadProperties(dir)
	if err == nil {
		t.Fatal("expected error for missing name")
	}
}

func TestReadProperties_explicitNilName(t *testing.T) {
	// `name:` with no value parses as nil. It must fail the non-empty check
	// rather than sneaking through as the literal string "<nil>".
	dir := t.TempDir()
	writeSkillMD(t, dir, "---\nname:\ndescription: desc\n---\n")
	_, err := parser.ReadProperties(dir)
	if err == nil {
		t.Fatal("expected error for null name")
	}
	if !strings.Contains(err.Error(), "non-empty") {
		t.Errorf("error = %q, want non-empty-string error", err.Error())
	}
}

func TestReadProperties_explicitNilDescription(t *testing.T) {
	dir := t.TempDir()
	writeSkillMD(t, dir, "---\nname: x\ndescription: ~\n---\n")
	_, err := parser.ReadProperties(dir)
	if err == nil {
		t.Fatal("expected error for null description")
	}
	if !strings.Contains(err.Error(), "non-empty") {
		t.Errorf("error = %q, want non-empty-string error", err.Error())
	}
}

func TestReadProperties_lowercaseSkillMD(t *testing.T) {
	dir := t.TempDir()
	if err := os.WriteFile(filepath.Join(dir, "skill.md"), []byte("---\nname: x\ndescription: y\n---\n"), 0o644); err != nil {
		t.Fatal(err)
	}
	props, err := parser.ReadProperties(dir)
	if err != nil {
		t.Fatalf("unexpected error with skill.md (lowercase): %v", err)
	}
	if props.Name != "x" {
		t.Errorf("Name = %q, want %q", props.Name, "x")
	}
}

func TestFindSkillMD_prefersUppercase(t *testing.T) {
	dir := t.TempDir()
	upper := filepath.Join(dir, "SKILL.md")
	lower := filepath.Join(dir, "skill.md")
	os.WriteFile(upper, []byte("---\nname: u\ndescription: u\n---\n"), 0o644)
	os.WriteFile(lower, []byte("---\nname: l\ndescription: l\n---\n"), 0o644)

	found := parser.FindSkillMD(dir)
	if found != upper {
		t.Errorf("FindSkillMD returned %q, want SKILL.md path", found)
	}
}
