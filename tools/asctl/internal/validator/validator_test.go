package validator_test

import (
	"os"
	"path/filepath"
	"strings"
	"testing"

	"github.com/nq-rdl/agent-extensions/tools/asctl/internal/validator"
)

func TestValidateMetadata_valid(t *testing.T) {
	meta := map[string]any{
		"name":        "my-skill",
		"description": "Does something useful",
		"license":     "MIT",
	}
	errs := validator.ValidateMetadata(meta, "")
	if len(errs) != 0 {
		t.Errorf("expected no errors, got: %v", errs)
	}
}

func TestValidateMetadata_missingName(t *testing.T) {
	meta := map[string]any{"description": "desc"}
	errs := validator.ValidateMetadata(meta, "")
	if !containsSubstr(errs, "name") {
		t.Errorf("expected name error, got: %v", errs)
	}
}

func TestValidateMetadata_missingDescription(t *testing.T) {
	meta := map[string]any{"name": "my-skill"}
	errs := validator.ValidateMetadata(meta, "")
	if !containsSubstr(errs, "description") {
		t.Errorf("expected description error, got: %v", errs)
	}
}

func TestValidateMetadata_unknownField(t *testing.T) {
	meta := map[string]any{
		"name":        "my-skill",
		"description": "desc",
		"bogus-field": "value",
	}
	errs := validator.ValidateMetadata(meta, "")
	if !containsSubstr(errs, "bogus-field") {
		t.Errorf("expected unknown field error, got: %v", errs)
	}
}

func TestValidateName_uppercase(t *testing.T) {
	meta := map[string]any{"name": "MySkill", "description": "desc"}
	errs := validator.ValidateMetadata(meta, "")
	if !containsSubstr(errs, "lowercase") {
		t.Errorf("expected lowercase error, got: %v", errs)
	}
}

func TestValidateName_leadingHyphen(t *testing.T) {
	meta := map[string]any{"name": "-skill", "description": "desc"}
	errs := validator.ValidateMetadata(meta, "")
	if !containsSubstr(errs, "hyphen") {
		t.Errorf("expected hyphen error, got: %v", errs)
	}
}

func TestValidateName_consecutiveHyphens(t *testing.T) {
	meta := map[string]any{"name": "my--skill", "description": "desc"}
	errs := validator.ValidateMetadata(meta, "")
	if !containsSubstr(errs, "consecutive") {
		t.Errorf("expected consecutive hyphens error, got: %v", errs)
	}
}

func TestValidateName_tooLong(t *testing.T) {
	meta := map[string]any{
		"name":        "a" + string(make([]byte, validator.MaxNameLength)),
		"description": "desc",
	}
	errs := validator.ValidateMetadata(meta, "")
	if !containsSubstr(errs, "character limit") {
		t.Errorf("expected length error, got: %v", errs)
	}
}

func TestValidateName_dirMismatch(t *testing.T) {
	meta := map[string]any{"name": "other-name", "description": "desc"}
	errs := validator.ValidateMetadata(meta, "/skills/my-skill")
	if !containsSubstr(errs, "match") {
		t.Errorf("expected dir mismatch error, got: %v", errs)
	}
}

func TestValidate_missingSkillMD(t *testing.T) {
	dir := t.TempDir()
	errs := validator.Validate(dir)
	if !containsSubstr(errs, "SKILL.md") {
		t.Errorf("expected SKILL.md error, got: %v", errs)
	}
}

func TestValidate_validSkillMD(t *testing.T) {
	// Use a named subdir so filepath.Base(dir) matches the skill name in SKILL.md.
	root := t.TempDir()
	dir := filepath.Join(root, "my-skill")
	if err := os.Mkdir(dir, 0o755); err != nil {
		t.Fatal(err)
	}
	content := "---\nname: my-skill\ndescription: A test skill\nlicense: MIT\n---\n# Body\n"
	if err := os.WriteFile(filepath.Join(dir, "SKILL.md"), []byte(content), 0o644); err != nil {
		t.Fatal(err)
	}
	errs := validator.Validate(dir)
	if len(errs) != 0 {
		t.Errorf("expected no errors, got: %v", errs)
	}
}

func containsSubstr(errs []string, substr string) bool {
	for _, e := range errs {
		if strings.Contains(e, substr) {
			return true
		}
	}
	return false
}
