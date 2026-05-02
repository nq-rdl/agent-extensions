package orchestrate

import (
	"strings"
	"testing"
)

func TestBuildPrompt_TitleAndBody(t *testing.T) {
	issue := Issue{
		Number: 1,
		Title:  "Add logging support",
		Body:   "We need structured logging throughout the service.",
	}
	ctx := &ProjectContext{}

	prompt := BuildPrompt(issue, ctx, "")

	if !strings.Contains(prompt, "## Task: Add logging support") {
		t.Errorf("prompt missing task title; got:\n%s", prompt)
	}
	if !strings.Contains(prompt, "We need structured logging throughout the service.") {
		t.Errorf("prompt missing issue body; got:\n%s", prompt)
	}
}

func TestBuildPrompt_GoContext(t *testing.T) {
	issue := Issue{Number: 2, Title: "Implement feature X", Body: "Details here."}
	ctx := &ProjectContext{
		Language:      "go",
		BuildSystem:   "go",
		TestFramework: "go test",
		ModulePath:    "github.com/example/mymod",
		VerifyCommand: "go test ./...",
	}

	prompt := BuildPrompt(issue, ctx, "")

	if !strings.Contains(prompt, "go test ./...") {
		t.Errorf("prompt missing verify command; got:\n%s", prompt)
	}
	if !strings.Contains(prompt, "github.com/example/mymod") {
		t.Errorf("prompt missing module path; got:\n%s", prompt)
	}
	if !strings.Contains(prompt, "Run `go test ./...` and ensure it passes") {
		t.Errorf("prompt missing verification gate command; got:\n%s", prompt)
	}
}

func TestBuildPrompt_WithClaudeMD(t *testing.T) {
	issue := Issue{Number: 3, Title: "Fix bug", Body: "There is a bug."}
	ctx := &ProjectContext{Language: "go", BuildSystem: "go", VerifyCommand: "go test ./..."}
	claudeMD := "  # My Project\n\nUse tabs for indentation.\n  "

	prompt := BuildPrompt(issue, ctx, claudeMD)

	if !strings.Contains(prompt, "## Project Guidelines (CLAUDE.md)") {
		t.Errorf("prompt missing project guidelines section; got:\n%s", prompt)
	}
	if !strings.Contains(prompt, "Use tabs for indentation.") {
		t.Errorf("prompt missing CLAUDE.md content; got:\n%s", prompt)
	}
	// Content should be trimmed.
	if strings.Contains(prompt, "  # My Project") {
		t.Errorf("prompt CLAUDE.md content was not trimmed; got:\n%s", prompt)
	}
	if !strings.Contains(prompt, "See CLAUDE.md for project-specific guidance") {
		t.Errorf("prompt missing style constraint mention of CLAUDE.md; got:\n%s", prompt)
	}
}

func TestBuildPrompt_WithoutClaudeMD(t *testing.T) {
	issue := Issue{Number: 4, Title: "Refactor module", Body: "Clean up the code."}
	ctx := &ProjectContext{Language: "rust", BuildSystem: "cargo", VerifyCommand: "cargo test"}

	prompt := BuildPrompt(issue, ctx, "")

	if strings.Contains(prompt, "## Project Guidelines (CLAUDE.md)") {
		t.Errorf("prompt should not contain project guidelines section; got:\n%s", prompt)
	}
	if strings.Contains(prompt, "See CLAUDE.md for project-specific guidance") {
		t.Errorf("prompt should not mention CLAUDE.md in style constraints; got:\n%s", prompt)
	}
}

func TestBuildPrompt_EmptyVerifyCommand(t *testing.T) {
	issue := Issue{Number: 5, Title: "Add feature", Body: "Implement it."}
	ctx := &ProjectContext{
		Language:    "python",
		BuildSystem: "pip",
	}

	prompt := BuildPrompt(issue, ctx, "")

	if !strings.Contains(prompt, "Run the project test suite and ensure it passes") {
		t.Errorf("prompt missing generic test suite instruction; got:\n%s", prompt)
	}
	// Should not contain a backtick-wrapped empty command.
	if strings.Contains(prompt, "Run ``") {
		t.Errorf("prompt contains empty backtick command; got:\n%s", prompt)
	}
}
