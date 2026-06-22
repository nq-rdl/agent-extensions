// Package repocheck orchestrates repository-level skill validation.
package repocheck

import (
	"os"
	"path/filepath"
	"sort"
	"strings"

	"github.com/nq-rdl/agent-extensions/tools/asctl/internal/parser"
	"github.com/nq-rdl/agent-extensions/tools/asctl/internal/prompt"
	"github.com/nq-rdl/agent-extensions/tools/asctl/internal/structure"
	"github.com/nq-rdl/agent-extensions/tools/asctl/internal/validator"
)

// IterSkillDirs returns immediate child directories under skillsRoot, sorted.
func IterSkillDirs(skillsRoot string) ([]string, error) {
	entries, err := os.ReadDir(skillsRoot)
	if err != nil {
		return nil, err
	}
	var dirs []string
	for _, e := range entries {
		if e.IsDir() {
			dirs = append(dirs, filepath.Join(skillsRoot, e.Name()))
		}
	}
	sort.Strings(dirs)
	return dirs, nil
}

// SkillDirFromPath maps any path under skillsRoot to its top-level skill directory.
// Returns the skill dir and true on success; "", false if path is outside skillsRoot.
func SkillDirFromPath(path, skillsRoot string) (string, bool) {
	absPath, err := filepath.Abs(path)
	if err != nil {
		return "", false
	}
	absRoot, err := filepath.Abs(skillsRoot)
	if err != nil {
		return "", false
	}
	rel, err := filepath.Rel(absRoot, absPath)
	if err != nil {
		return "", false
	}
	if rel == ".." || strings.HasPrefix(rel, ".."+string(filepath.Separator)) {
		return "", false
	}
	parts := strings.SplitN(rel, string(filepath.Separator), 2)
	if len(parts) == 0 || parts[0] == "" || parts[0] == "." {
		return "", false
	}
	skillDir := filepath.Join(skillsRoot, parts[0])
	info, err := os.Stat(skillDir)
	if err != nil || !info.IsDir() {
		return "", false
	}
	return skillDir, true
}

// ResolveSkillDirs resolves changed paths to the set of skill dirs to validate.
// If paths is empty, all skill dirs under skillsRoot are returned.
func ResolveSkillDirs(paths []string, skillsRoot string) ([]string, error) {
	if len(paths) == 0 {
		return IterSkillDirs(skillsRoot)
	}
	seen := make(map[string]bool)
	var selected []string
	for _, p := range paths {
		dir, ok := SkillDirFromPath(p, skillsRoot)
		if ok && !seen[dir] {
			seen[dir] = true
			selected = append(selected, dir)
		}
	}
	sort.Strings(selected)
	return selected, nil
}

// ValidateSkillDirs validates skill directories and ensures prompt generation works.
// Returns a list of error messages; an empty slice means all skills are valid.
func ValidateSkillDirs(skillDirs []string) []string {
	var errors []string
	var validDirs []string

	for _, dir := range skillDirs {
		errs := validator.Validate(dir)
		errs = append(errs, structure.ValidateStructure(dir)...)
		if len(errs) > 0 {
			for _, e := range errs {
				errors = append(errors, dir+": "+e)
			}
			continue
		}
		if _, err := parser.ReadProperties(dir); err != nil {
			errors = append(errors, dir+": "+err.Error())
			continue
		}
		validDirs = append(validDirs, dir)
	}

	if len(errors) > 0 {
		return errors
	}

	if _, err := prompt.ToPrompt(validDirs); err != nil {
		errors = append(errors, "prompt generation failed: "+err.Error())
	}

	return errors
}
