package orchestrate

import (
	"bufio"
	"encoding/json"
	"os"
	"path/filepath"
	"strings"
)

// ProjectContext captures detected language, build system, test framework,
// verify command, and whether a CLAUDE.md exists.
type ProjectContext struct {
	Language      string `json:"language,omitempty"`
	BuildSystem   string `json:"buildSystem,omitempty"`
	TestFramework string `json:"testFramework,omitempty"`
	ModulePath    string `json:"modulePath,omitempty"`
	VerifyCommand string `json:"verifyCommand,omitempty"`
	HasClaudeMD   bool   `json:"hasClaudeMd,omitempty"`
}

// DetectProjectContext inspects the given directory and returns a ProjectContext.
// Detection precedence: go.mod > Cargo.toml > package.json > pyproject.toml > Makefile.
func DetectProjectContext(dir string) (*ProjectContext, error) {
	ctx := &ProjectContext{}

	// Check for CLAUDE.md in either location.
	ctx.HasClaudeMD = fileExists(filepath.Join(dir, ".claude", "CLAUDE.md")) ||
		fileExists(filepath.Join(dir, "CLAUDE.md"))

	switch {
	case fileExists(filepath.Join(dir, "go.mod")):
		if err := detectGo(ctx, dir); err != nil {
			return nil, err
		}
	case fileExists(filepath.Join(dir, "Cargo.toml")):
		ctx.Language = "rust"
		ctx.BuildSystem = "cargo"
		ctx.TestFramework = "cargo test"
		ctx.VerifyCommand = "cargo test"
	case fileExists(filepath.Join(dir, "package.json")):
		if err := detectNode(ctx, dir); err != nil {
			return nil, err
		}
	case fileExists(filepath.Join(dir, "pyproject.toml")):
		if err := detectPython(ctx, dir); err != nil {
			return nil, err
		}
	case fileExists(filepath.Join(dir, "Makefile")):
		ctx.BuildSystem = "make"
		if makefileHasTestTarget(filepath.Join(dir, "Makefile")) {
			ctx.VerifyCommand = "make test"
		}
	}

	return ctx, nil
}

// detectGo fills ctx for a Go project.
func detectGo(ctx *ProjectContext, dir string) error {
	ctx.Language = "go"
	ctx.BuildSystem = "go"
	ctx.TestFramework = "go test"
	ctx.VerifyCommand = "go test ./..."

	// Parse module path from first line: "module <path>".
	f, err := os.Open(filepath.Join(dir, "go.mod"))
	if err != nil {
		return err
	}
	defer f.Close()

	scanner := bufio.NewScanner(f)
	if scanner.Scan() {
		line := strings.TrimSpace(scanner.Text())
		if rest, ok := strings.CutPrefix(line, "module "); ok {
			ctx.ModulePath = strings.TrimSpace(rest)
		}
	}
	return scanner.Err()
}

// packageJSON is used for partial unmarshalling of package.json.
type packageJSON struct {
	Scripts      map[string]string `json:"scripts"`
	Dependencies map[string]string `json:"dependencies"`
	DevDeps      map[string]string `json:"devDependencies"`
}

// detectNode fills ctx for a Node/TypeScript project.
func detectNode(ctx *ProjectContext, dir string) error {
	data, err := os.ReadFile(filepath.Join(dir, "package.json"))
	if err != nil {
		return err
	}

	var pkg packageJSON
	if err := json.Unmarshal(data, &pkg); err != nil {
		// Treat malformed package.json as empty — still a JS project.
		ctx.Language = "javascript"
		ctx.BuildSystem = "npm"
		return nil
	}

	// Determine language.
	if fileExists(filepath.Join(dir, "tsconfig.json")) {
		ctx.Language = "typescript"
	} else {
		ctx.Language = "javascript"
	}

	ctx.BuildSystem = "npm"

	// Verify command from scripts.
	if _, ok := pkg.Scripts["test"]; ok {
		ctx.VerifyCommand = "npm test"
	}

	// Test framework detection.
	allDeps := make(map[string]string)
	for k, v := range pkg.Dependencies {
		allDeps[k] = v
	}
	for k, v := range pkg.DevDeps {
		allDeps[k] = v
	}

	switch {
	case allDeps["jest"] != "":
		ctx.TestFramework = "jest"
	case allDeps["vitest"] != "":
		ctx.TestFramework = "vitest"
	}
	if ctx.VerifyCommand == "" {
		switch ctx.TestFramework {
		case "jest":
			ctx.VerifyCommand = "npx jest"
		case "vitest":
			ctx.VerifyCommand = "npx vitest"
		}
	}

	return nil
}

// detectPython fills ctx for a Python project.
func detectPython(ctx *ProjectContext, dir string) error {
	ctx.Language = "python"
	ctx.TestFramework = "pytest"
	ctx.VerifyCommand = "pytest"
	ctx.BuildSystem = "pip"

	if fileExists(filepath.Join(dir, "uv.lock")) {
		ctx.BuildSystem = "uv"
		return nil
	}

	data, err := os.ReadFile(filepath.Join(dir, "pyproject.toml"))
	if err != nil {
		return err
	}

	switch {
	case strings.Contains(string(data), "[tool.poetry]"):
		ctx.BuildSystem = "poetry"
	case strings.Contains(string(data), "[tool.uv]"):
		ctx.BuildSystem = "uv"
	}

	return nil
}

// makefileHasTestTarget returns true if the Makefile contains a "test:" target.
func makefileHasTestTarget(path string) bool {
	f, err := os.Open(path)
	if err != nil {
		return false
	}
	defer f.Close()

	scanner := bufio.NewScanner(f)
	for scanner.Scan() {
		line := scanner.Text()
		if strings.HasPrefix(line, "test:") {
			return true
		}
	}
	return false
}

// fileExists reports whether path exists as a regular file.
func fileExists(path string) bool {
	info, err := os.Stat(path)
	return err == nil && !info.IsDir()
}
