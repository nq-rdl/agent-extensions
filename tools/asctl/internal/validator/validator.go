// Package validator implements SKILL.md frontmatter validation rules.
package validator

import (
	"fmt"
	"maps"
	"os"
	"path/filepath"
	"slices"
	"strings"
	"unicode"

	"golang.org/x/text/unicode/norm"

	"github.com/nq-rdl/agent-extensions/tools/asctl/internal/frontmatter"
	"github.com/nq-rdl/agent-extensions/tools/asctl/internal/parser"
)

const (
	MaxNameLength          = 64
	MaxDescriptionLength   = 1024
	MaxCompatibilityLength = 500
)

var allowedFields = map[string]bool{
	"name":                     true,
	"description":              true,
	"license":                  true,
	"allowed-tools":            true,
	"argument-hint":            true,
	"compatibility":            true,
	"disable-model-invocation": true,
	"metadata":                 true,
	"user-invocable":           true,
}

// ValidateMetadata validates already-parsed SKILL.md frontmatter.
// skillDir may be empty to skip directory-name matching.
func ValidateMetadata(metadata map[string]any, skillDir string) []string {
	var errors []string

	sortedAllowed := slices.Sorted(maps.Keys(allowedFields))
	for field := range metadata {
		if !allowedFields[field] {
			errors = append(errors, fmt.Sprintf(
				"unexpected field %q in frontmatter; allowed fields: %v", field, sortedAllowed))
		}
	}

	if name, ok := metadata["name"]; !ok {
		errors = append(errors, "missing required field in frontmatter: name")
	} else {
		errors = append(errors, validateName(fmt.Sprintf("%v", name), skillDir)...)
	}

	if desc, ok := metadata["description"]; !ok {
		errors = append(errors, "missing required field in frontmatter: description")
	} else {
		errors = append(errors, validateDescription(fmt.Sprintf("%v", desc))...)
	}

	if compat, ok := metadata["compatibility"]; ok {
		errors = append(errors, validateCompatibility(fmt.Sprintf("%v", compat))...)
	}

	return errors
}

// Validate validates a skill directory's SKILL.md and returns error messages.
// An empty slice means the skill is valid.
func Validate(skillDir string) []string {
	info, err := os.Stat(skillDir)
	if err != nil {
		return []string{fmt.Sprintf("path does not exist: %s", skillDir)}
	}
	if !info.IsDir() {
		return []string{fmt.Sprintf("not a directory: %s", skillDir)}
	}

	skillMD := parser.FindSkillMD(skillDir)
	if skillMD == "" {
		return []string{"missing required file: SKILL.md"}
	}

	data, err := os.ReadFile(skillMD)
	if err != nil {
		return []string{fmt.Sprintf("read %s: %v", skillMD, err)}
	}

	metadata, _, err := frontmatter.Parse(string(data))
	if err != nil {
		return []string{err.Error()}
	}

	return ValidateMetadata(metadata, skillDir)
}

func validateName(name, skillDir string) []string {
	var errors []string

	if strings.TrimSpace(name) == "" {
		return append(errors, "field 'name' must be a non-empty string")
	}

	name = norm.NFKC.String(strings.TrimSpace(name))

	if len([]rune(name)) > MaxNameLength {
		errors = append(errors, fmt.Sprintf(
			"skill name %q exceeds %d character limit (%d chars)",
			name, MaxNameLength, len([]rune(name))))
	}

	if name != strings.ToLower(name) {
		errors = append(errors, fmt.Sprintf("skill name %q must be lowercase", name))
	}

	if strings.HasPrefix(name, "-") || strings.HasSuffix(name, "-") {
		errors = append(errors, "skill name cannot start or end with a hyphen")
	}

	if strings.Contains(name, "--") {
		errors = append(errors, "skill name cannot contain consecutive hyphens")
	}

	for _, r := range name {
		if !unicode.IsLetter(r) && !unicode.IsDigit(r) && r != '-' {
			errors = append(errors, fmt.Sprintf(
				"skill name %q contains invalid characters; only letters, digits, and hyphens are allowed", name))
			break
		}
	}

	if skillDir != "" {
		dirName := norm.NFKC.String(filepath.Base(skillDir))
		if dirName != name {
			errors = append(errors, fmt.Sprintf(
				"directory name %q must match skill name %q", filepath.Base(skillDir), name))
		}
	}

	return errors
}

func validateDescription(desc string) []string {
	if strings.TrimSpace(desc) == "" {
		return []string{"field 'description' must be a non-empty string"}
	}
	if len([]rune(desc)) > MaxDescriptionLength {
		return []string{fmt.Sprintf(
			"description exceeds %d character limit (%d chars)",
			MaxDescriptionLength, len([]rune(desc)))}
	}
	return nil
}

func validateCompatibility(compat string) []string {
	if len([]rune(compat)) > MaxCompatibilityLength {
		return []string{fmt.Sprintf(
			"compatibility exceeds %d character limit (%d chars)",
			MaxCompatibilityLength, len([]rune(compat)))}
	}
	return nil
}
