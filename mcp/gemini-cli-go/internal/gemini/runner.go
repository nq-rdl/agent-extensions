// Package gemini manages one-shot Gemini CLI subprocess invocations.
// It spawns `gemini --prompt <p> --output-format json` and parses the single
// JSON response: { session_id, response, stats }.
package gemini

import (
	"context"
	"crypto/rand"
	"encoding/hex"
	"encoding/json"
	"errors"
	"fmt"
	"os"
	"os/exec"
	"path/filepath"
	"strings"
	"time"
)

const defaultTimeout = 5 * time.Minute

var modelAliases = map[string]string{
	"fast":    "gemini-3-flash-preview",
	"quality": "gemini-3.1-pro-preview",
}

func resolveModel(m string) string {
	if v, ok := modelAliases[m]; ok {
		return v
	}
	return m
}

func randomHex() string {
	b := make([]byte, 8)
	rand.Read(b) //nolint:errcheck
	return hex.EncodeToString(b)
}

// Options controls a single Gemini CLI invocation.
type Options struct {
	Model         string
	ApprovalMode  string
	Sandbox       bool
	SystemContext string
	CWD           string
	Timeout       time.Duration
	AllowedTools  []string
	SessionID     string // non-empty → --resume
	Stdin         string // non-empty → pipe to stdin
}

// Stats aggregates token usage from the Gemini CLI JSON output.
type Stats struct {
	TotalTokens  *int64                     `json:"total_tokens,omitempty"`
	InputTokens  *int64                     `json:"input_tokens,omitempty"`
	OutputTokens *int64                     `json:"output_tokens,omitempty"`
	Cached       *int64                     `json:"cached,omitempty"`
	DurationMs   *int64                     `json:"duration_ms,omitempty"`
	ToolCalls    *int64                     `json:"tool_calls,omitempty"`
	Models       map[string]json.RawMessage `json:"models,omitempty"`
	Tools        json.RawMessage            `json:"tools,omitempty"`
	Files        json.RawMessage            `json:"files,omitempty"`
}

// Result is returned by Run and Resume.
type Result struct {
	Response  string `json:"response"`
	SessionID string `json:"session_id"`
	Stats     Stats  `json:"stats"`
}

// Run executes a one-shot Gemini prompt and returns the result.
func Run(ctx context.Context, prompt string, opts Options) (*Result, error) {
	return invoke(ctx, prompt, opts)
}

// Resume continues a previous session via --resume <session_id>.
func Resume(ctx context.Context, sessionID, prompt string, opts Options) (*Result, error) {
	opts.SessionID = sessionID
	return invoke(ctx, prompt, opts)
}

func invoke(ctx context.Context, prompt string, opts Options) (*Result, error) {
	binary := os.Getenv("GEMINI_BINARY")
	if binary == "" {
		binary = "gemini"
	}

	defaultModel := os.Getenv("GEMINI_DEFAULT_MODEL")
	if defaultModel == "" {
		defaultModel = "gemini-3-flash-preview"
	}
	model := opts.Model
	if model == "" {
		model = defaultModel
	}

	approvalMode := opts.ApprovalMode
	if approvalMode == "" {
		approvalMode = "yolo"
	}

	timeout := opts.Timeout
	if timeout == 0 {
		timeout = defaultTimeout
	}

	args := []string{
		"--prompt", prompt,
		"--output-format", "json",
		"--model", resolveModel(model),
		"--approval-mode", approvalMode,
	}
	if opts.Sandbox {
		args = append(args, "--sandbox")
	}
	if opts.SessionID != "" {
		args = append(args, "--resume", opts.SessionID)
	}
	if len(opts.AllowedTools) > 0 {
		args = append(args, "--allowed-tools", strings.Join(opts.AllowedTools, ","))
	}

	contextDir, err := prepareSystemContext(opts.SystemContext)
	if err != nil {
		return nil, fmt.Errorf("preparing system context: %w", err)
	}
	if contextDir != "" {
		defer os.RemoveAll(contextDir)
		args = append(args, "--include-directories", contextDir)
	}

	cwd := opts.CWD
	if cwd == "" {
		cwd, _ = os.Getwd()
	}

	ctx, cancel := context.WithTimeout(ctx, timeout)
	defer cancel()

	cmd := exec.CommandContext(ctx, binary, args...)
	cmd.Dir = cwd
	cmd.Env = os.Environ()
	if opts.Stdin != "" {
		cmd.Stdin = strings.NewReader(opts.Stdin)
	}

	stdout, err := cmd.Output()
	if err != nil {
		var exitErr *exec.ExitError
		if errors.As(err, &exitErr) {
			return nil, formatExitError(exitErr)
		}
		if strings.Contains(err.Error(), "executable file not found") ||
			strings.Contains(err.Error(), "no such file") {
			return nil, fmt.Errorf("gemini binary not found; install with: npm install -g @google/gemini-cli or set GEMINI_BINARY")
		}
		return nil, err
	}

	return parseOutput(stdout)
}

func prepareSystemContext(content string) (string, error) {
	if content == "" {
		if envPath := os.Getenv("GEMINI_SYSTEM_MD"); envPath != "" {
			b, err := os.ReadFile(envPath)
			if err != nil {
				return "", nil // best-effort: missing file is not fatal
			}
			content = string(b)
		}
	}
	if content == "" {
		return "", nil
	}

	dir := filepath.Join(os.TempDir(), "gemini-mcp-"+randomHex())
	if err := os.MkdirAll(dir, 0o700); err != nil {
		return "", err
	}
	if err := os.WriteFile(filepath.Join(dir, "GEMINI.md"), []byte(content), 0o600); err != nil {
		os.RemoveAll(dir)
		return "", err
	}
	return dir, nil
}

func parseOutput(stdout []byte) (*Result, error) {
	s := string(stdout)
	idx := strings.Index(s, "{")
	if idx < 0 {
		return nil, fmt.Errorf("gemini CLI returned no JSON output")
	}

	var raw struct {
		Response  string          `json:"response"`
		SessionID string          `json:"session_id"`
		Stats     json.RawMessage `json:"stats"`
	}
	if err := json.Unmarshal([]byte(s[idx:]), &raw); err != nil {
		preview := s
		if len(preview) > 200 {
			preview = preview[:200]
		}
		return nil, fmt.Errorf("failed to parse gemini CLI output: %s", preview)
	}

	return &Result{
		Response:  raw.Response,
		SessionID: raw.SessionID,
		Stats:     normalizeStats(raw.Stats),
	}, nil
}

func normalizeStats(raw json.RawMessage) Stats {
	if len(raw) == 0 {
		return Stats{}
	}

	var m struct {
		TotalTokens  *int64                     `json:"total_tokens"`
		InputTokens  *int64                     `json:"input_tokens"`
		OutputTokens *int64                     `json:"output_tokens"`
		Cached       *int64                     `json:"cached"`
		DurationMs   *int64                     `json:"duration_ms"`
		ToolCalls    *int64                     `json:"tool_calls"`
		Models       map[string]json.RawMessage `json:"models"`
		Tools        json.RawMessage            `json:"tools"`
		Files        json.RawMessage            `json:"files"`
	}
	if err := json.Unmarshal(raw, &m); err != nil {
		return Stats{}
	}

	// Aggregate per-model breakdown when flat summary fields are absent
	if (m.TotalTokens == nil || *m.TotalTokens == 0) && len(m.Models) > 0 {
		var total, input, output, cached, latency int64
		for _, modelRaw := range m.Models {
			var md struct {
				Tokens struct {
					Total      *int64 `json:"total"`
					Input      *int64 `json:"input"`
					Candidates *int64 `json:"candidates"`
					Cached     *int64 `json:"cached"`
				} `json:"tokens"`
				API struct {
					TotalLatencyMs *int64 `json:"totalLatencyMs"`
				} `json:"api"`
			}
			if json.Unmarshal(modelRaw, &md) != nil {
				continue
			}
			if md.Tokens.Total != nil {
				total += *md.Tokens.Total
			}
			if md.Tokens.Input != nil {
				input += *md.Tokens.Input
			}
			if md.Tokens.Candidates != nil {
				output += *md.Tokens.Candidates
			}
			if md.Tokens.Cached != nil {
				cached += *md.Tokens.Cached
			}
			if md.API.TotalLatencyMs != nil {
				latency += *md.API.TotalLatencyMs
			}
		}
		if total > 0 {
			m.TotalTokens = &total
		}
		if input > 0 {
			m.InputTokens = &input
		}
		if output > 0 {
			m.OutputTokens = &output
		}
		if cached > 0 {
			m.Cached = &cached
		}
		if latency > 0 {
			m.DurationMs = &latency
		}
	}

	return Stats{
		TotalTokens:  m.TotalTokens,
		InputTokens:  m.InputTokens,
		OutputTokens: m.OutputTokens,
		Cached:       m.Cached,
		DurationMs:   m.DurationMs,
		ToolCalls:    m.ToolCalls,
		Models:       m.Models,
		Tools:        m.Tools,
		Files:        m.Files,
	}
}

var exitMessages = map[int]string{
	1:  "Gemini CLI returned a general error or API failure",
	42: "Gemini CLI received invalid input (bad prompt or arguments)",
	52: "Gemini CLI configuration error — check $HOME/.gemini/settings.json permissions",
	53: "Gemini CLI turn limit exceeded — break your task into smaller pieces",
}

func formatExitError(e *exec.ExitError) error {
	msg, ok := exitMessages[e.ExitCode()]
	if !ok {
		msg = fmt.Sprintf("Gemini CLI exited with code %d", e.ExitCode())
	}
	if detail := strings.TrimSpace(string(e.Stderr)); detail != "" {
		return fmt.Errorf("%s\nDetails: %s", msg, detail)
	}
	return errors.New(msg)
}

// WriteOutput serialises data as pretty JSON to path, creating parent dirs.
func WriteOutput(path string, data any) (int, error) {
	b, err := json.MarshalIndent(data, "", "  ")
	if err != nil {
		return 0, err
	}
	if err := os.MkdirAll(filepath.Dir(path), 0o755); err != nil {
		return 0, err
	}
	return len(b), os.WriteFile(path, b, 0o644)
}
