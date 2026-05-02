package orchestrate

import (
	"os"
	"path/filepath"
	"testing"
)

func TestDetectProjectContext_Go(t *testing.T) {
	dir := t.TempDir()
	writeFile(t, filepath.Join(dir, "go.mod"), "module github.com/example/mymod\n\ngo 1.24\n")

	ctx, err := DetectProjectContext(dir)
	if err != nil {
		t.Fatalf("unexpected error: %v", err)
	}

	if ctx.Language != "go" {
		t.Errorf("Language = %q, want %q", ctx.Language, "go")
	}
	if ctx.BuildSystem != "go" {
		t.Errorf("BuildSystem = %q, want %q", ctx.BuildSystem, "go")
	}
	if ctx.VerifyCommand != "go test ./..." {
		t.Errorf("VerifyCommand = %q, want %q", ctx.VerifyCommand, "go test ./...")
	}
	if ctx.ModulePath != "github.com/example/mymod" {
		t.Errorf("ModulePath = %q, want %q", ctx.ModulePath, "github.com/example/mymod")
	}
	if ctx.TestFramework != "go test" {
		t.Errorf("TestFramework = %q, want %q", ctx.TestFramework, "go test")
	}
}

func TestDetectProjectContext_Rust(t *testing.T) {
	dir := t.TempDir()
	writeFile(t, filepath.Join(dir, "Cargo.toml"), "[package]\nname = \"mylib\"\n")

	ctx, err := DetectProjectContext(dir)
	if err != nil {
		t.Fatalf("unexpected error: %v", err)
	}

	if ctx.Language != "rust" {
		t.Errorf("Language = %q, want %q", ctx.Language, "rust")
	}
	if ctx.BuildSystem != "cargo" {
		t.Errorf("BuildSystem = %q, want %q", ctx.BuildSystem, "cargo")
	}
	if ctx.VerifyCommand != "cargo test" {
		t.Errorf("VerifyCommand = %q, want %q", ctx.VerifyCommand, "cargo test")
	}
}

func TestDetectProjectContext_Node(t *testing.T) {
	dir := t.TempDir()
	writeFile(t, filepath.Join(dir, "package.json"), `{"scripts":{"test":"node test.js"},"devDependencies":{}}`)

	ctx, err := DetectProjectContext(dir)
	if err != nil {
		t.Fatalf("unexpected error: %v", err)
	}

	if ctx.Language != "javascript" {
		t.Errorf("Language = %q, want %q", ctx.Language, "javascript")
	}
	if ctx.BuildSystem != "npm" {
		t.Errorf("BuildSystem = %q, want %q", ctx.BuildSystem, "npm")
	}
	if ctx.VerifyCommand != "npm test" {
		t.Errorf("VerifyCommand = %q, want %q", ctx.VerifyCommand, "npm test")
	}
}

func TestDetectProjectContext_NodeJestWithoutTestScript(t *testing.T) {
	dir := t.TempDir()
	writeFile(t, filepath.Join(dir, "package.json"), `{"scripts":{},"devDependencies":{"jest":"^29.0.0"}}`)

	ctx, err := DetectProjectContext(dir)
	if err != nil {
		t.Fatalf("unexpected error: %v", err)
	}

	if ctx.TestFramework != "jest" {
		t.Errorf("TestFramework = %q, want %q", ctx.TestFramework, "jest")
	}
	if ctx.VerifyCommand != "npx jest" {
		t.Errorf("VerifyCommand = %q, want %q", ctx.VerifyCommand, "npx jest")
	}
}

func TestDetectProjectContext_NodeVitestWithoutTestScript(t *testing.T) {
	dir := t.TempDir()
	writeFile(t, filepath.Join(dir, "package.json"), `{"scripts":{},"devDependencies":{"vitest":"^3.0.0"}}`)

	ctx, err := DetectProjectContext(dir)
	if err != nil {
		t.Fatalf("unexpected error: %v", err)
	}

	if ctx.TestFramework != "vitest" {
		t.Errorf("TestFramework = %q, want %q", ctx.TestFramework, "vitest")
	}
	if ctx.VerifyCommand != "npx vitest" {
		t.Errorf("VerifyCommand = %q, want %q", ctx.VerifyCommand, "npx vitest")
	}
}

func TestDetectProjectContext_TypeScript(t *testing.T) {
	dir := t.TempDir()
	writeFile(t, filepath.Join(dir, "package.json"), `{"scripts":{},"devDependencies":{"typescript":"^5.0.0"}}`)
	writeFile(t, filepath.Join(dir, "tsconfig.json"), `{"compilerOptions":{}}`)

	ctx, err := DetectProjectContext(dir)
	if err != nil {
		t.Fatalf("unexpected error: %v", err)
	}

	if ctx.Language != "typescript" {
		t.Errorf("Language = %q, want %q", ctx.Language, "typescript")
	}
}

func TestDetectProjectContext_Python(t *testing.T) {
	dir := t.TempDir()
	writeFile(t, filepath.Join(dir, "pyproject.toml"), "[tool.poetry]\nname = \"myapp\"\n")

	ctx, err := DetectProjectContext(dir)
	if err != nil {
		t.Fatalf("unexpected error: %v", err)
	}

	if ctx.Language != "python" {
		t.Errorf("Language = %q, want %q", ctx.Language, "python")
	}
	if ctx.BuildSystem != "poetry" {
		t.Errorf("BuildSystem = %q, want %q", ctx.BuildSystem, "poetry")
	}
	if ctx.VerifyCommand != "pytest" {
		t.Errorf("VerifyCommand = %q, want %q", ctx.VerifyCommand, "pytest")
	}
	if ctx.TestFramework != "pytest" {
		t.Errorf("TestFramework = %q, want %q", ctx.TestFramework, "pytest")
	}
}

func TestDetectProjectContext_PythonDefaultPip(t *testing.T) {
	dir := t.TempDir()
	writeFile(t, filepath.Join(dir, "pyproject.toml"), "[project]\nname = \"myapp\"\n")

	ctx, err := DetectProjectContext(dir)
	if err != nil {
		t.Fatalf("unexpected error: %v", err)
	}

	if ctx.BuildSystem != "pip" {
		t.Errorf("BuildSystem = %q, want %q", ctx.BuildSystem, "pip")
	}
}

func TestDetectProjectContext_PythonUV(t *testing.T) {
	dir := t.TempDir()
	writeFile(t, filepath.Join(dir, "pyproject.toml"), "[project]\nname = \"myapp\"\n")
	writeFile(t, filepath.Join(dir, "uv.lock"), "# lock\n")

	ctx, err := DetectProjectContext(dir)
	if err != nil {
		t.Fatalf("unexpected error: %v", err)
	}

	if ctx.BuildSystem != "uv" {
		t.Errorf("BuildSystem = %q, want %q", ctx.BuildSystem, "uv")
	}
}

func TestDetectProjectContext_Makefile(t *testing.T) {
	dir := t.TempDir()
	writeFile(t, filepath.Join(dir, "Makefile"), "all:\n\t@echo build\n\ntest:\n\t@go test ./...\n")

	ctx, err := DetectProjectContext(dir)
	if err != nil {
		t.Fatalf("unexpected error: %v", err)
	}

	if ctx.BuildSystem != "make" {
		t.Errorf("BuildSystem = %q, want %q", ctx.BuildSystem, "make")
	}
	if ctx.VerifyCommand != "make test" {
		t.Errorf("VerifyCommand = %q, want %q", ctx.VerifyCommand, "make test")
	}
}

func TestDetectProjectContext_HasClaudeMD(t *testing.T) {
	t.Run("root CLAUDE.md", func(t *testing.T) {
		dir := t.TempDir()
		writeFile(t, filepath.Join(dir, "CLAUDE.md"), "# Project guidelines\n")

		ctx, err := DetectProjectContext(dir)
		if err != nil {
			t.Fatalf("unexpected error: %v", err)
		}
		if !ctx.HasClaudeMD {
			t.Error("HasClaudeMD = false, want true")
		}
	})

	t.Run(".claude/CLAUDE.md", func(t *testing.T) {
		dir := t.TempDir()
		if err := os.MkdirAll(filepath.Join(dir, ".claude"), 0o755); err != nil {
			t.Fatalf("mkdir: %v", err)
		}
		writeFile(t, filepath.Join(dir, ".claude", "CLAUDE.md"), "# Project guidelines\n")

		ctx, err := DetectProjectContext(dir)
		if err != nil {
			t.Fatalf("unexpected error: %v", err)
		}
		if !ctx.HasClaudeMD {
			t.Error("HasClaudeMD = false, want true")
		}
	})
}

func TestDetectProjectContext_Empty(t *testing.T) {
	dir := t.TempDir()

	ctx, err := DetectProjectContext(dir)
	if err != nil {
		t.Fatalf("unexpected error: %v", err)
	}

	if ctx.Language != "" {
		t.Errorf("Language = %q, want empty", ctx.Language)
	}
	if ctx.BuildSystem != "" {
		t.Errorf("BuildSystem = %q, want empty", ctx.BuildSystem)
	}
	if ctx.TestFramework != "" {
		t.Errorf("TestFramework = %q, want empty", ctx.TestFramework)
	}
	if ctx.VerifyCommand != "" {
		t.Errorf("VerifyCommand = %q, want empty", ctx.VerifyCommand)
	}
	if ctx.ModulePath != "" {
		t.Errorf("ModulePath = %q, want empty", ctx.ModulePath)
	}
	if ctx.HasClaudeMD {
		t.Error("HasClaudeMD = true, want false")
	}
}

// writeFile is a test helper that writes content to path, failing the test on error.
func writeFile(t *testing.T, path, content string) {
	t.Helper()
	if err := os.WriteFile(path, []byte(content), 0o644); err != nil {
		t.Fatalf("writeFile %s: %v", path, err)
	}
}
