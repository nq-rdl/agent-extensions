// Package frontmatter parses YAML frontmatter from SKILL.md content.
package frontmatter

import (
	"fmt"
	"strings"

	"gopkg.in/yaml.v3"
)

// Parse extracts YAML frontmatter and body from SKILL.md content.
// Returns the metadata map, the markdown body, and any parse error.
//
// Delimiters are recognised only when "---" occupies a whole line, so markdown
// horizontal rules or YAML block scalars containing "---" inside the body do
// not prematurely terminate the frontmatter.
func Parse(content string) (map[string]any, string, error) {
	lines := strings.Split(content, "\n")
	if len(lines) == 0 || strings.TrimRight(lines[0], "\r") != "---" {
		return nil, "", fmt.Errorf("SKILL.md must start with YAML frontmatter (---)")
	}

	closeIdx := -1
	for i := 1; i < len(lines); i++ {
		if strings.TrimRight(lines[i], "\r") == "---" {
			closeIdx = i
			break
		}
	}
	if closeIdx < 0 {
		return nil, "", fmt.Errorf("SKILL.md frontmatter not properly closed with ---")
	}

	yamlPart := strings.Join(lines[1:closeIdx], "\n")
	body := strings.TrimSpace(strings.Join(lines[closeIdx+1:], "\n"))

	var metadata map[string]any
	if err := yaml.Unmarshal([]byte(yamlPart), &metadata); err != nil {
		return nil, "", fmt.Errorf("invalid YAML in frontmatter: %w", err)
	}

	if metadata == nil {
		return nil, "", fmt.Errorf("SKILL.md frontmatter must be a YAML mapping")
	}

	// Normalize metadata sub-map values to string->string, mirroring Python behaviour.
	if meta, ok := metadata["metadata"].(map[string]any); ok {
		normalized := make(map[string]string, len(meta))
		for k, v := range meta {
			normalized[k] = fmt.Sprintf("%v", v)
		}
		metadata["metadata"] = normalized
	}

	return metadata, body, nil
}
