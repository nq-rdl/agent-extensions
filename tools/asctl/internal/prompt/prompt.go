// Package prompt generates the <available_skills> XML block for agent system prompts.
package prompt

import (
	"bytes"
	"encoding/xml"
	"fmt"
	"strings"

	"github.com/nq-rdl/agent-extensions/tools/asctl/internal/parser"
)

// ToPrompt generates the <available_skills> XML block.
// All text nodes are escaped via encoding/xml so skill metadata containing <, >,
// & or control characters produces well-formed XML.
func ToPrompt(skillDirs []string) (string, error) {
	if len(skillDirs) == 0 {
		return "<available_skills>\n</available_skills>", nil
	}

	lines := []string{"<available_skills>"}

	for _, dir := range skillDirs {
		props, err := parser.ReadProperties(dir)
		if err != nil {
			return "", fmt.Errorf("skill %s: %w", dir, err)
		}

		skillMD := parser.FindSkillMD(dir)

		lines = append(lines,
			"<skill>",
			"<name>",
			escapeXML(props.Name),
			"</name>",
			"<description>",
			escapeXML(props.Description),
			"</description>",
			"<location>",
			escapeXML(skillMD),
			"</location>",
			"</skill>",
		)
	}

	lines = append(lines, "</available_skills>")
	return strings.Join(lines, "\n"), nil
}

func escapeXML(s string) string {
	var buf bytes.Buffer
	if err := xml.EscapeText(&buf, []byte(s)); err != nil {
		// EscapeText only fails on writer errors; bytes.Buffer never errors.
		return s
	}
	return buf.String()
}
