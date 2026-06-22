package structure_test

import (
	"os"
	"path/filepath"
	"strings"
	"testing"

	"github.com/nq-rdl/agent-extensions/tools/asctl/internal/structure"
)

// file describes a single file to create relative to the skill root, with
// parent directories created as needed.
type file struct {
	path    string // slash-separated, relative to the skill dir
	content string
}

// buildSkill materializes a skill directory from a list of relative file paths.
// A SKILL.md is always written so fixtures resemble real skills.
func buildSkill(t *testing.T, files []file) string {
	t.Helper()
	dir := t.TempDir()
	all := append([]file{{path: "SKILL.md", content: "---\nname: x\ndescription: y\n---\n"}}, files...)
	for _, f := range all {
		full := filepath.Join(dir, filepath.FromSlash(f.path))
		if err := os.MkdirAll(filepath.Dir(full), 0o755); err != nil {
			t.Fatal(err)
		}
		if err := os.WriteFile(full, []byte(f.content), 0o644); err != nil {
			t.Fatal(err)
		}
	}
	return dir
}

func TestValidateStructure(t *testing.T) {
	tests := []struct {
		name    string
		files   []file
		dirs    []string // empty dirs to create (in addition to file parents)
		wantOK  bool     // expect zero errors
		wantSub string   // substring expected in an error (when !wantOK)
	}{
		{
			name: "clean skill passes",
			files: []file{
				{path: "scripts/run.sh", content: "#!/bin/sh\n"},
				{path: "references/guide.rst", content: "Guide\n"},
				{path: "assets/config.json", content: "{}\n"},
			},
			wantOK: true,
		},
		{
			name:   "bare skill with only SKILL.md passes",
			files:  nil,
			wantOK: true,
		},
		{
			name:    "disallowed subdir fails",
			dirs:    []string{"examples"},
			wantOK:  false,
			wantSub: `disallowed subdirectory "examples"`,
		},
		{
			name: "non-.rst under references fails",
			files: []file{
				{path: "references/notes.md", content: "# notes\n"},
			},
			wantOK:  false,
			wantSub: "references/notes.md",
		},
		{
			name: "nested non-.rst under references fails",
			files: []file{
				{path: "references/deep/nested/data.json", content: "{}\n"},
			},
			wantOK:  false,
			wantSub: "references/deep/nested/data.json",
		},
		{
			name: "rst files under references pass (incl. nested)",
			files: []file{
				{path: "references/top.rst", content: "x\n"},
				{path: "references/sub/inner.rst", content: "y\n"},
			},
			wantOK: true,
		},
		{
			name:    "agents subdir inside skill fails",
			dirs:    []string{"agents"},
			wantOK:  false,
			wantSub: "agents/ is not allowed inside a skill",
		},
		{
			name: "hidden dir is ignored",
			files: []file{
				{path: ".evals/harness.py", content: "print()\n"},
				{path: ".evals/cases/case1.txt", content: "x\n"},
			},
			wantOK: true,
		},
		{
			name: "hidden top-level file is ignored",
			files: []file{
				{path: ".gitignore", content: "*.tmp\n"},
			},
			wantOK: true,
		},
		{
			name: "disallowed top-level file fails",
			files: []file{
				{path: "notes.txt", content: "hi\n"},
			},
			wantOK:  false,
			wantSub: `disallowed top-level file "notes.txt"`,
		},
		{
			name: "allowed lychee.toml passes",
			files: []file{
				{path: "lychee.toml", content: "[]\n"},
			},
			wantOK: true,
		},
		{
			name: "hidden file inside references is ignored",
			files: []file{
				{path: "references/guide.rst", content: "x\n"},
				{path: "references/.DS_Store", content: "junk\n"},
			},
			wantOK: true,
		},
	}

	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			dir := buildSkill(t, tt.files)
			for _, d := range tt.dirs {
				if err := os.MkdirAll(filepath.Join(dir, filepath.FromSlash(d)), 0o755); err != nil {
					t.Fatal(err)
				}
			}

			errs := structure.ValidateStructure(dir)

			if tt.wantOK {
				if len(errs) != 0 {
					t.Fatalf("expected no errors, got: %v", errs)
				}
				return
			}
			if len(errs) == 0 {
				t.Fatalf("expected an error containing %q, got none", tt.wantSub)
			}
			if !containsSubstr(errs, tt.wantSub) {
				t.Fatalf("expected an error containing %q, got: %v", tt.wantSub, errs)
			}
		})
	}
}

// TestValidateStructure_lowercaseManifestRejected guards the rule that the
// manifest filename must be exactly SKILL.md (uppercase): a lowercase-only
// skill.md must be rejected so such a skill fails repo-check rather than
// slipping through. Uses a manual fixture (not buildSkill, which always injects
// an uppercase SKILL.md) and is portable to case-insensitive filesystems
// because ValidateStructure reads the real on-disk entry name via os.ReadDir.
func TestValidateStructure_lowercaseManifestRejected(t *testing.T) {
	dir := t.TempDir()
	if err := os.WriteFile(filepath.Join(dir, "skill.md"), []byte("---\nname: x\ndescription: y\n---\n"), 0o644); err != nil {
		t.Fatal(err)
	}
	errs := structure.ValidateStructure(dir)
	if !containsSubstr(errs, "SKILL.md") {
		t.Fatalf("expected a SKILL.md-naming error for lowercase-only skill.md, got: %v", errs)
	}
}

func TestValidateStructure_missingDir(t *testing.T) {
	errs := structure.ValidateStructure(filepath.Join(t.TempDir(), "does-not-exist"))
	if !containsSubstr(errs, "read directory") {
		t.Fatalf("expected read-directory error, got: %v", errs)
	}
}

func containsSubstr(errs []string, substr string) bool {
	for _, e := range errs {
		if strings.Contains(e, substr) {
			return true
		}
	}
	return false
}
