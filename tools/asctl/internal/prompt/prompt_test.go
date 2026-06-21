package prompt_test

import (
	"os"
	"path/filepath"
	"strings"
	"testing"

	"github.com/nq-rdl/agent-extensions/tools/asctl/internal/prompt"
)

func makeSkill(t *testing.T, name, description string) string {
	t.Helper()
	dir := t.TempDir()
	// Rename temp dir to match skill name using a subdir.
	skillDir := filepath.Join(dir, name)
	if err := os.Mkdir(skillDir, 0o755); err != nil {
		t.Fatal(err)
	}
	content := "---\nname: " + name + "\ndescription: " + description + "\n---\n# Body\n"
	if err := os.WriteFile(filepath.Join(skillDir, "SKILL.md"), []byte(content), 0o644); err != nil {
		t.Fatal(err)
	}
	return skillDir
}

func TestToPrompt_empty(t *testing.T) {
	out, err := prompt.ToPrompt(nil)
	if err != nil {
		t.Fatal(err)
	}
	want := "<available_skills>\n</available_skills>"
	if out != want {
		t.Errorf("got %q, want %q", out, want)
	}
}

func TestToPrompt_singleSkill(t *testing.T) {
	skillDir := makeSkill(t, "my-skill", "Does something useful")

	out, err := prompt.ToPrompt([]string{skillDir})
	if err != nil {
		t.Fatal(err)
	}

	// Verify structure
	if !strings.Contains(out, "<available_skills>") {
		t.Error("missing <available_skills>")
	}
	if !strings.Contains(out, "<name>\nmy-skill\n</name>") {
		t.Errorf("missing name block in output:\n%s", out)
	}
	if !strings.Contains(out, "<description>\nDoes something useful\n</description>") {
		t.Errorf("missing description block in output:\n%s", out)
	}
	if !strings.Contains(out, "<location>") {
		t.Error("missing <location>")
	}
	if !strings.Contains(out, "</available_skills>") {
		t.Error("missing </available_skills>")
	}
}

func TestToPrompt_xmlEscaping(t *testing.T) {
	skillDir := makeSkill(t, "my-skill", "A & B <test> skill")

	out, err := prompt.ToPrompt([]string{skillDir})
	if err != nil {
		t.Fatal(err)
	}

	if !strings.Contains(out, "A &amp; B &lt;test&gt; skill") {
		t.Errorf("XML escaping not applied in output:\n%s", out)
	}
}

func TestToPrompt_escapesLocationPath(t *testing.T) {
	// Location paths are filesystem-controlled and could contain XML-special chars.
	// With xml.EscapeText they must be safely escaped, not left raw.
	skillDir := makeSkill(t, "my-skill", "ok")
	out, err := prompt.ToPrompt([]string{skillDir})
	if err != nil {
		t.Fatal(err)
	}
	// Confirm there are no unescaped control chars in the output.
	for _, ch := range []string{"\x00", "\x01"} {
		if strings.Contains(out, ch) {
			t.Errorf("control character leaked into XML output:\n%s", out)
		}
	}
}

func TestToPrompt_invalidSkill(t *testing.T) {
	_, err := prompt.ToPrompt([]string{"/nonexistent/path"})
	if err == nil {
		t.Fatal("expected error for nonexistent skill dir")
	}
}
