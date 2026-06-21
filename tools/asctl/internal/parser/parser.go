// Package parser reads and parses SKILL.md frontmatter into structured properties.
package parser

import (
	"fmt"
	"os"
	"path/filepath"
	"strings"

	"github.com/nq-rdl/agent-extensions/tools/asctl/internal/frontmatter"
)

// SkillProperties holds the parsed frontmatter fields from a SKILL.md file.
type SkillProperties struct {
	Name          string            `json:"name"`
	Description   string            `json:"description"`
	License       string            `json:"license,omitempty"`
	Compatibility string            `json:"compatibility,omitempty"`
	AllowedTools  any               `json:"allowed_tools,omitempty"`
	Metadata      map[string]string `json:"metadata,omitempty"`
}

// trimmedString renders a YAML-parsed value as a trimmed string, treating an
// explicit nil (from `name:` or `name: null`) as an empty string rather than
// the literal "<nil>" that fmt.Sprintf would produce.
func trimmedString(v any) string {
	if v == nil {
		return ""
	}
	return strings.TrimSpace(fmt.Sprintf("%v", v))
}

// FindSkillMD returns the path to the SKILL.md file in skillDir.
// Prefers SKILL.md (uppercase), falls back to skill.md. Returns "" if not found.
func FindSkillMD(skillDir string) string {
	for _, name := range []string{"SKILL.md", "skill.md"} {
		p := filepath.Join(skillDir, name)
		if _, err := os.Stat(p); err == nil {
			return p
		}
	}
	return ""
}

// ReadProperties parses the SKILL.md frontmatter and returns skill properties.
// Does not perform full validation — use validator.Validate for that.
func ReadProperties(skillDir string) (*SkillProperties, error) {
	skillMD := FindSkillMD(skillDir)
	if skillMD == "" {
		return nil, fmt.Errorf("SKILL.md not found in %s", skillDir)
	}

	data, err := os.ReadFile(skillMD)
	if err != nil {
		return nil, fmt.Errorf("read %s: %w", skillMD, err)
	}

	meta, _, err := frontmatter.Parse(string(data))
	if err != nil {
		return nil, err
	}

	nameAny, hasName := meta["name"]
	descAny, hasDesc := meta["description"]

	if !hasName {
		return nil, fmt.Errorf("missing required field in frontmatter: name")
	}
	if !hasDesc {
		return nil, fmt.Errorf("missing required field in frontmatter: description")
	}

	name := trimmedString(nameAny)
	desc := trimmedString(descAny)

	if name == "" {
		return nil, fmt.Errorf("field 'name' must be a non-empty string")
	}
	if desc == "" {
		return nil, fmt.Errorf("field 'description' must be a non-empty string")
	}

	props := &SkillProperties{Name: name, Description: desc}

	if lic, ok := meta["license"]; ok {
		props.License = trimmedString(lic)
	}
	if compat, ok := meta["compatibility"]; ok {
		props.Compatibility = trimmedString(compat)
	}
	if tools, ok := meta["allowed-tools"]; ok {
		props.AllowedTools = tools
	}
	if metaMap, ok := meta["metadata"].(map[string]string); ok {
		props.Metadata = metaMap
	}

	return props, nil
}
