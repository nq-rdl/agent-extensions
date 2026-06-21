package repocheck_test

import (
	"os"
	"path/filepath"
	"testing"

	"github.com/nq-rdl/agent-extensions/tools/asctl/internal/repocheck"
)

func makeSkillDir(t *testing.T, root, name, description string) string {
	t.Helper()
	dir := filepath.Join(root, name)
	if err := os.MkdirAll(dir, 0o755); err != nil {
		t.Fatal(err)
	}
	content := "---\nname: " + name + "\ndescription: " + description + "\n---\n"
	if err := os.WriteFile(filepath.Join(dir, "SKILL.md"), []byte(content), 0o644); err != nil {
		t.Fatal(err)
	}
	return dir
}

func TestIterSkillDirs_sorted(t *testing.T) {
	root := t.TempDir()
	makeSkillDir(t, root, "zebra", "Z")
	makeSkillDir(t, root, "alpha", "A")
	makeSkillDir(t, root, "beta", "B")

	dirs, err := repocheck.IterSkillDirs(root)
	if err != nil {
		t.Fatal(err)
	}
	if len(dirs) != 3 {
		t.Fatalf("expected 3 dirs, got %d", len(dirs))
	}
	want := []string{
		filepath.Join(root, "alpha"),
		filepath.Join(root, "beta"),
		filepath.Join(root, "zebra"),
	}
	for i, d := range dirs {
		if d != want[i] {
			t.Errorf("dirs[%d] = %q, want %q", i, d, want[i])
		}
	}
}

func TestResolveSkillDirs_emptyPathsReturnsAll(t *testing.T) {
	root := t.TempDir()
	makeSkillDir(t, root, "skill-a", "A")
	makeSkillDir(t, root, "skill-b", "B")

	dirs, err := repocheck.ResolveSkillDirs(nil, root)
	if err != nil {
		t.Fatal(err)
	}
	if len(dirs) != 2 {
		t.Errorf("expected 2, got %d: %v", len(dirs), dirs)
	}
}

func TestResolveSkillDirs_pathsOutsideRoot(t *testing.T) {
	root := t.TempDir()
	dirs, err := repocheck.ResolveSkillDirs([]string{"/etc/passwd"}, root)
	if err != nil {
		t.Fatal(err)
	}
	if len(dirs) != 0 {
		t.Errorf("expected 0 dirs for path outside root, got %v", dirs)
	}
}

func TestValidateSkillDirs_allValid(t *testing.T) {
	root := t.TempDir()
	makeSkillDir(t, root, "skill-a", "A useful skill")
	makeSkillDir(t, root, "skill-b", "Another useful skill")

	dirs, _ := repocheck.IterSkillDirs(root)
	errs := repocheck.ValidateSkillDirs(dirs)
	if len(errs) != 0 {
		t.Errorf("expected no errors, got: %v", errs)
	}
}

func TestValidateSkillDirs_invalidSkill(t *testing.T) {
	root := t.TempDir()
	// skill without SKILL.md
	bad := filepath.Join(root, "bad-skill")
	os.Mkdir(bad, 0o755)

	errs := repocheck.ValidateSkillDirs([]string{bad})
	if len(errs) == 0 {
		t.Error("expected errors for invalid skill")
	}
}
