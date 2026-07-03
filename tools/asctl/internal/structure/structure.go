// Package structure implements the skill directory-structure standard (v1):
// which subdirectories and top-level files a skill may contain, and what may
// live under references/. It complements validator, which checks SKILL.md
// frontmatter.
package structure

import (
	"fmt"
	"io/fs"
	"os"
	"path/filepath"
	"slices"
	"strings"
)

// allowedSubdirs are the only non-hidden subdirectories a skill may contain.
var allowedSubdirs = []string{"assets", "references", "scripts"}

// allowedTopLevelFiles lists the non-hidden files permitted at the skill root:
// SKILL.md (the manifest — required, exact uppercase) and the optional
// lychee.toml link-check config. Kept small and explicit (see CONTRIBUTING.md
// "Skill directory structure" rule 6).
var allowedTopLevelFiles = []string{"SKILL.md", "lychee.toml"}

// isHidden reports whether a directory entry name is dot-prefixed. Hidden
// entries (e.g. .evals, .git) are ignored entirely by the structure lint.
func isHidden(name string) bool {
	return strings.HasPrefix(name, ".")
}

// ValidateStructure enforces the v1 skill-structure standard for skillDir and
// returns error messages with no directory prefix (repocheck adds it). An empty
// slice means the structure is valid.
func ValidateStructure(skillDir string) []string {
	entries, err := os.ReadDir(skillDir)
	if err != nil {
		return []string{fmt.Sprintf("read directory: %v", err)}
	}

	var errors []string
	for _, e := range entries {
		name := e.Name()
		if isHidden(name) {
			continue
		}
		if e.IsDir() {
			errors = append(errors, checkSubdir(skillDir, name)...)
			continue
		}
		if name == "skill.md" {
			errors = append(errors,
				"skill manifest must be named exactly SKILL.md (uppercase); rename skill.md to SKILL.md")
			continue
		}
		if !slices.Contains(allowedTopLevelFiles, name) {
			errors = append(errors, fmt.Sprintf(
				"disallowed top-level file %q; allowed top-level files: %s (put other files under assets/, scripts/, or references/)",
				name, strings.Join(allowedTopLevelFiles, ", ")))
		}
	}
	return errors
}

// checkSubdir validates a single non-hidden subdirectory: that it is in the
// allowlist (with a dedicated message for the agents/ anti-pattern), and that
// references/ holds only .rst files.
func checkSubdir(skillDir, name string) []string {
	if name == "agents" {
		return []string{
			"agents/ is not allowed inside a skill; agents live in the top-level agents/<name>/agent.md and are bundled into the plugin via the registry (registry/bundles/<bundle>.yaml)",
		}
	}
	if !slices.Contains(allowedSubdirs, name) {
		return []string{fmt.Sprintf(
			"disallowed subdirectory %q; allowed subdirectories: assets, references, scripts", name)}
	}
	if name == "references" {
		return checkReferences(filepath.Join(skillDir, name))
	}
	return nil
}

// checkReferences walks references/ (to any depth) and flags every non-.rst
// file. Directories and hidden entries are not flagged.
func checkReferences(refsDir string) []string {
	var errors []string
	walkErr := filepath.WalkDir(refsDir, func(path string, d fs.DirEntry, err error) error {
		if err != nil {
			return err
		}
		if isHidden(d.Name()) {
			if d.IsDir() && path != refsDir {
				return fs.SkipDir
			}
			return nil
		}
		if d.IsDir() {
			return nil
		}
		if strings.ToLower(filepath.Ext(d.Name())) != ".rst" {
			rel, relErr := filepath.Rel(refsDir, path)
			if relErr != nil {
				rel = path
			}
			errors = append(errors, fmt.Sprintf(
				"non-.rst file under references/: %s (references/ holds prose docs as .rst only; put other files under assets/)",
				filepath.ToSlash(filepath.Join("references", rel))))
		}
		return nil
	})
	if walkErr != nil {
		errors = append(errors, fmt.Sprintf("walk references/: %v", walkErr))
	}
	return errors
}
