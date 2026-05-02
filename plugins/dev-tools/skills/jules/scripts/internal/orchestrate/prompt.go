package orchestrate

import (
	"cmp"
	"strings"
)

// BuildPrompt constructs a Jules session prompt from the issue, project context,
// and optional CLAUDE.md contents.
func BuildPrompt(issue Issue, ctx *ProjectContext, claudeMD string) string {
	var b strings.Builder

	// Title and body.
	b.WriteString("## Task: ")
	b.WriteString(issue.Title)
	b.WriteString("\n\n")
	b.WriteString(issue.Body)
	b.WriteString("\n\n")

	// Project context section.
	b.WriteString("## Project Context\n\n")
	b.WriteString("- Language: ")
	b.WriteString(cmp.Or(ctx.Language, "unknown"))
	b.WriteString("\n")
	b.WriteString("- Build system: ")
	b.WriteString(cmp.Or(ctx.BuildSystem, "unknown"))
	b.WriteString("\n")
	b.WriteString("- Test framework: ")
	b.WriteString(cmp.Or(ctx.TestFramework, "unknown"))
	b.WriteString("\n")

	if ctx.ModulePath != "" {
		b.WriteString("- Module: ")
		b.WriteString(ctx.ModulePath)
		b.WriteString("\n")
	}
	if ctx.VerifyCommand != "" {
		b.WriteString("- Verify command: `")
		b.WriteString(ctx.VerifyCommand)
		b.WriteString("`\n")
	}

	b.WriteString("\n")

	// Style constraints section.
	b.WriteString("## Style Constraints\n\n")
	b.WriteString("- Follow existing code conventions in the repository\n")
	b.WriteString("- Keep changes minimal and focused on the task\n")
	b.WriteString("- Add tests for any new behaviour\n")
	if claudeMD != "" {
		b.WriteString("- See CLAUDE.md for project-specific guidance\n")
	}

	b.WriteString("\n")

	// Verification gate section.
	b.WriteString("## Verification Gate\n\n")
	b.WriteString("Before considering the task complete:\n")
	if ctx.VerifyCommand != "" {
		b.WriteString("1. Run `")
		b.WriteString(ctx.VerifyCommand)
		b.WriteString("` and ensure it passes\n")
	} else {
		b.WriteString("1. Run the project test suite and ensure it passes\n")
	}
	b.WriteString("2. Ensure no regressions in existing tests\n")
	b.WriteString("3. Review your changes for correctness and completeness\n")

	// Optional CLAUDE.md section.
	if claudeMD != "" {
		b.WriteString("\n## Project Guidelines (CLAUDE.md)\n\n")
		b.WriteString(strings.TrimSpace(claudeMD))
		b.WriteString("\n")
	}

	return b.String()
}
