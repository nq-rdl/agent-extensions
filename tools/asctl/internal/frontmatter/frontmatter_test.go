package frontmatter_test

import (
	"strings"
	"testing"

	"github.com/nq-rdl/agent-extensions/tools/asctl/internal/frontmatter"
)

func TestParse_valid(t *testing.T) {
	content := `---
name: my-skill
description: Does something useful
license: MIT
---
# My Skill
`
	meta, body, err := frontmatter.Parse(content)
	if err != nil {
		t.Fatalf("unexpected error: %v", err)
	}
	if meta["name"] != "my-skill" {
		t.Errorf("name = %q, want %q", meta["name"], "my-skill")
	}
	if meta["description"] != "Does something useful" {
		t.Errorf("description = %q, want %q", meta["description"], "Does something useful")
	}
	if body != "# My Skill" {
		t.Errorf("body = %q, want %q", body, "# My Skill")
	}
}

func TestParse_missingOpenDelimiter(t *testing.T) {
	_, _, err := frontmatter.Parse("name: foo\n---\nbody")
	if err == nil {
		t.Fatal("expected error for missing opening ---")
	}
}

func TestParse_unclosedDelimiter(t *testing.T) {
	_, _, err := frontmatter.Parse("---\nname: foo\n")
	if err == nil {
		t.Fatal("expected error for unclosed frontmatter")
	}
}

func TestParse_invalidYAML(t *testing.T) {
	_, _, err := frontmatter.Parse("---\n: invalid: yaml:\n---\n")
	if err == nil {
		t.Fatal("expected error for invalid YAML")
	}
}

func TestParse_horizontalRuleInBody(t *testing.T) {
	// A markdown horizontal rule "---" in the body must not be mistaken for
	// the closing frontmatter delimiter.
	content := "---\nname: x\ndescription: y\n---\n# Heading\n\nIntro.\n\n---\n\nMore body.\n"
	meta, body, err := frontmatter.Parse(content)
	if err != nil {
		t.Fatalf("unexpected error: %v", err)
	}
	if meta["name"] != "x" {
		t.Errorf("name = %q, want %q", meta["name"], "x")
	}
	if !strings.Contains(body, "---") {
		t.Errorf("body lost its horizontal rule: %q", body)
	}
	if !strings.Contains(body, "More body.") {
		t.Errorf("body truncated before horizontal rule: %q", body)
	}
}

func TestParse_tripleDashInYAMLValue(t *testing.T) {
	// A literal-block scalar that contains "---" inside it (not at line start)
	// must not be treated as a delimiter.
	content := "---\nname: x\ndescription: \"note with --- inside\"\n---\nbody\n"
	meta, body, err := frontmatter.Parse(content)
	if err != nil {
		t.Fatalf("unexpected error: %v", err)
	}
	if meta["description"] != "note with --- inside" {
		t.Errorf("description = %q, want %q", meta["description"], "note with --- inside")
	}
	if body != "body" {
		t.Errorf("body = %q, want %q", body, "body")
	}
}

func TestParse_metadataSubmap(t *testing.T) {
	content := "---\nname: x\ndescription: y\nmetadata:\n  repo: https://example.com\n  version: \"1\"\n---\n"
	meta, _, err := frontmatter.Parse(content)
	if err != nil {
		t.Fatalf("unexpected error: %v", err)
	}
	m, ok := meta["metadata"].(map[string]string)
	if !ok {
		t.Fatalf("metadata not normalized to map[string]string, got %T", meta["metadata"])
	}
	if m["repo"] != "https://example.com" {
		t.Errorf("repo = %q, want %q", m["repo"], "https://example.com")
	}
}

func TestParseRawPreservesBody(t *testing.T) {
	for _, body := range []string{"", "\n", "\n# Body\n\n", "\r\n# Body\r\n\r\n", "é界😀", " \t"} {
		t.Run(body, func(t *testing.T) {
			for _, newline := range []string{"\n", "\r\n"} {
				content := strings.Join([]string{"---", "name: sample", "description: Test", "---", ""}, newline) + body
				_, got, err := frontmatter.ParseRaw(content)
				if err != nil || got != body {
					t.Fatalf("raw body = %q, err = %v; want %q", got, err, body)
				}
				_, trimmed, err := frontmatter.Parse(content)
				if err != nil || trimmed != strings.TrimSpace(body) {
					t.Fatalf("trimmed Parse contract changed: %q, %v", trimmed, err)
				}
			}
		})
	}
	_, body, err := frontmatter.ParseRaw("---\nname: sample\n---")
	if err != nil || body != "" {
		t.Fatalf("closing fence at EOF: body = %q, err = %v", body, err)
	}
}

func TestParseRawPreservesParseFailures(t *testing.T) {
	for _, content := range []string{
		"no frontmatter\n", "---\nname: sample\n", "---\n: invalid: yaml:\n---\n",
		"---\n---\n", "---\n- sequence\n---\n",
	} {
		_, _, original := frontmatter.Parse(content)
		_, _, raw := frontmatter.ParseRaw(content)
		if original == nil || raw == nil || original.Error() != raw.Error() {
			t.Fatalf("parse errors for %q: Parse=%v, ParseRaw=%v", content, original, raw)
		}
	}
}
