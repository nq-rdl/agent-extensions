// gemini-cli-mcp is a Model Context Protocol server that wraps the Gemini CLI.
// It exposes one-shot dispatch, web search, context-piped runs, session resume,
// persistent ACP sessions, and model listing as MCP tools over stdio.
package main

import (
	"context"
	"encoding/json"
	"fmt"
	"os"
	"time"

	"github.com/mark3labs/mcp-go/mcp"
	"github.com/mark3labs/mcp-go/server"
	"github.com/nq-rdl/agent-extensions/mcp/gemini-cli-go/internal/acp"
	"github.com/nq-rdl/agent-extensions/mcp/gemini-cli-go/internal/gemini"
)

var version = "dev"

func main() {
	s := server.NewMCPServer("gemini-cli", version,
		server.WithToolCapabilities(false),
	)

	registerTools(s)

	// ServeStdio handles SIGTERM/SIGINT. Shut down ACP sessions after exit.
	defer acp.ShutdownAll()
	if err := server.ServeStdio(s); err != nil {
		fmt.Fprintf(os.Stderr, "gemini-cli-mcp: %v\n", err)
		os.Exit(1)
	}
}

// geminiResult encodes a gemini.Result as a tool result.
func geminiResult(r *gemini.Result, err error) (*mcp.CallToolResult, error) {
	if err != nil {
		return mcp.NewToolResultError(err.Error()), nil
	}
	b, _ := json.MarshalIndent(r, "", "  ")
	return mcp.NewToolResultText(string(b)), nil
}

// statsOnlyResult writes the full result to outputFile and returns only metadata.
func statsOnlyResult(r *gemini.Result, outputFile string) (*mcp.CallToolResult, error) {
	n, err := gemini.WriteOutput(outputFile, r)
	if err != nil {
		return mcp.NewToolResultError(fmt.Sprintf("writing output file: %v", err)), nil
	}
	meta := map[string]any{
		"session_id":     r.SessionID,
		"stats":          r.Stats,
		"output_file":    outputFile,
		"response_bytes": n,
	}
	b, _ := json.MarshalIndent(meta, "", "  ")
	return mcp.NewToolResultText(string(b)), nil
}

// optStr returns args[key] as a string, or "" if absent.
func optStr(args map[string]any, key string) string {
	v, _ := args[key].(string)
	return v
}

// optBool returns args[key] as bool, or the given default.
func optBool(args map[string]any, key string, def bool) bool {
	if v, ok := args[key]; ok {
		if b, ok := v.(bool); ok {
			return b
		}
	}
	return def
}

// optDuration returns args[key] (float64 ms) as a Duration, or def.
func optDuration(args map[string]any, key string, def time.Duration) time.Duration {
	if v, ok := args[key].(float64); ok && v > 0 {
		return time.Duration(v) * time.Millisecond
	}
	return def
}

// optStrings returns args[key] as []string, or nil.
func optStrings(args map[string]any, key string) []string {
	v, ok := args[key]
	if !ok {
		return nil
	}
	arr, ok := v.([]any)
	if !ok {
		return nil
	}
	out := make([]string, 0, len(arr))
	for _, item := range arr {
		if s, ok := item.(string); ok {
			out = append(out, s)
		}
	}
	return out
}

func registerTools(s *server.MCPServer) {
	// Shared parameter descriptions
	const (
		modelDesc = "Model to use. PREFER 'fast' (→ gemini-3-flash-preview) for most tasks. " +
			"Use 'quality' (→ gemini-3.1-pro-preview) for complex reasoning. " +
			"Avoid 'auto' — routes to cheapest model. " +
			"Default: GEMINI_DEFAULT_MODEL env var or gemini-3-flash-preview."
		approvalDesc   = "yolo=auto-approve all (required for headless); auto_edit=approve edits only; default=blocks in headless. Default: yolo."
		sandboxDesc    = "Sandbox tool execution. Default false — Gemini CLI sandbox sets HOME=/home/node which requires specific system setup."
		sysContextDesc = "System-level instructions injected as GEMINI.md. Sets Gemini's persona/output format."
		timeoutDesc    = "Timeout in milliseconds. Default: 300000 (5 minutes)."
		cwdDesc        = "Working directory for the Gemini subprocess. Defaults to current directory."
		toolsDesc      = "Limit which tools Gemini can use. E.g. [\"web_search\", \"read_file\"]."
		outputFileDesc = "Absolute path to write the full response JSON. When set, only stats + metadata are returned (avoids context window bloat for large outputs)."
	)

	// ── gemini_run ──────────────────────────────────────────────────────────
	s.AddTool(mcp.NewTool("gemini_run",
		mcp.WithDescription(
			"Run a prompt headlessly with Gemini CLI. Returns response, session_id (for follow-up "+
				"with gemini_resume), and token stats. Defaults to yolo for safe headless operation.",
		),
		mcp.WithString("prompt", mcp.Required(), mcp.Description("The prompt or task for Gemini")),
		mcp.WithString("model", mcp.Description(modelDesc)),
		mcp.WithString("approval_mode", mcp.Description(approvalDesc)),
		mcp.WithBoolean("sandbox", mcp.Description(sandboxDesc)),
		mcp.WithString("system_context", mcp.Description(sysContextDesc)),
		mcp.WithNumber("timeout_ms", mcp.Description(timeoutDesc)),
		mcp.WithString("cwd", mcp.Description(cwdDesc)),
		mcp.WithArray("allowed_tools", mcp.Description(toolsDesc)),
		mcp.WithString("output_file", mcp.Description(outputFileDesc)),
	), func(ctx context.Context, req mcp.CallToolRequest) (*mcp.CallToolResult, error) {
		args := req.GetArguments()
		prompt, _ := args["prompt"].(string)

		opts := gemini.Options{
			Model:         optStr(args, "model"),
			ApprovalMode:  optStr(args, "approval_mode"),
			Sandbox:       optBool(args, "sandbox", false),
			SystemContext: optStr(args, "system_context"),
			CWD:           optStr(args, "cwd"),
			Timeout:       optDuration(args, "timeout_ms", 0),
			AllowedTools:  optStrings(args, "allowed_tools"),
		}

		r, err := gemini.Run(ctx, prompt, opts)
		if err != nil {
			return mcp.NewToolResultError(err.Error()), nil
		}
		if of := optStr(args, "output_file"); of != "" {
			return statsOnlyResult(r, of)
		}
		return geminiResult(r, nil)
	})

	// ── gemini_web_search ────────────────────────────────────────────────────
	s.AddTool(mcp.NewTool("gemini_web_search",
		mcp.WithDescription(
			"Search the web using Gemini CLI's built-in search tool. "+
				"Defaults to 'fast' (gemini-3-flash-preview) — retrieval tasks don't need pro quality. "+
				"Use system_context to control output format (e.g. JSON citations).",
		),
		mcp.WithString("query", mcp.Required(), mcp.Description("Natural language search query")),
		mcp.WithString("model", mcp.Description("Model for web search. Default: fast (gemini-3-flash-preview).")),
		mcp.WithString("system_context", mcp.Description(sysContextDesc)),
		mcp.WithNumber("timeout_ms", mcp.Description(timeoutDesc)),
	), func(ctx context.Context, req mcp.CallToolRequest) (*mcp.CallToolResult, error) {
		args := req.GetArguments()
		query, _ := args["query"].(string)
		prompt := "Search the web for: " + query + "\n\nProvide a thorough, accurate answer based on current web results."

		opts := gemini.Options{
			Model:         optStr(args, "model"),
			ApprovalMode:  "yolo",
			Sandbox:       true,
			SystemContext: optStr(args, "system_context"),
			Timeout:       optDuration(args, "timeout_ms", 0),
			AllowedTools:  []string{"web_search"},
		}
		return geminiResult(gemini.Run(ctx, prompt, opts))
	})

	// ── gemini_run_with_context ──────────────────────────────────────────────
	s.AddTool(mcp.NewTool("gemini_run_with_context",
		mcp.WithDescription(
			"Run Gemini with piped context — file contents, git diffs, logs, command output, etc. "+
				"The context is passed via stdin so it doesn't need escaping in the prompt. "+
				"Perfect for code review, log analysis, diff summarization.",
		),
		mcp.WithString("prompt", mcp.Required(), mcp.Description("Instructions for how to process the context")),
		mcp.WithString("context", mcp.Required(), mcp.Description("Content to process (file contents, git diff, logs, etc.)")),
		mcp.WithString("model", mcp.Description(modelDesc)),
		mcp.WithString("approval_mode", mcp.Description(approvalDesc)),
		mcp.WithBoolean("sandbox", mcp.Description(sandboxDesc)),
		mcp.WithString("system_context", mcp.Description(sysContextDesc)),
		mcp.WithNumber("timeout_ms", mcp.Description(timeoutDesc)),
		mcp.WithString("cwd", mcp.Description(cwdDesc)),
		mcp.WithString("output_file", mcp.Description(outputFileDesc)),
	), func(ctx context.Context, req mcp.CallToolRequest) (*mcp.CallToolResult, error) {
		args := req.GetArguments()
		prompt, _ := args["prompt"].(string)
		stdinContext, _ := args["context"].(string)

		opts := gemini.Options{
			Model:         optStr(args, "model"),
			ApprovalMode:  optStr(args, "approval_mode"),
			Sandbox:       optBool(args, "sandbox", false),
			SystemContext: optStr(args, "system_context"),
			CWD:           optStr(args, "cwd"),
			Timeout:       optDuration(args, "timeout_ms", 0),
			Stdin:         stdinContext,
		}

		r, err := gemini.Run(ctx, prompt, opts)
		if err != nil {
			return mcp.NewToolResultError(err.Error()), nil
		}
		if of := optStr(args, "output_file"); of != "" {
			return statsOnlyResult(r, of)
		}
		return geminiResult(r, nil)
	})

	// ── gemini_resume ────────────────────────────────────────────────────────
	s.AddTool(mcp.NewTool("gemini_resume",
		mcp.WithDescription(
			"Continue a previous Gemini session for multi-turn conversations. "+
				"Each gemini_run/gemini_web_search call returns a session_id — use it here to follow up. "+
				"The resumed session has full context of the prior exchange without re-sending it.",
		),
		mcp.WithString("session_id", mcp.Required(), mcp.Description("session_id from a previous gemini_run or gemini_web_search call")),
		mcp.WithString("prompt", mcp.Required(), mcp.Description("Follow-up prompt continuing the previous session")),
		mcp.WithString("model", mcp.Description(modelDesc)),
		mcp.WithString("approval_mode", mcp.Description(approvalDesc)),
		mcp.WithBoolean("sandbox", mcp.Description(sandboxDesc)),
		mcp.WithString("system_context", mcp.Description(sysContextDesc)),
		mcp.WithNumber("timeout_ms", mcp.Description(timeoutDesc)),
	), func(ctx context.Context, req mcp.CallToolRequest) (*mcp.CallToolResult, error) {
		args := req.GetArguments()
		sessionID, _ := args["session_id"].(string)
		prompt, _ := args["prompt"].(string)

		opts := gemini.Options{
			Model:         optStr(args, "model"),
			ApprovalMode:  optStr(args, "approval_mode"),
			Sandbox:       optBool(args, "sandbox", false),
			SystemContext: optStr(args, "system_context"),
			Timeout:       optDuration(args, "timeout_ms", 0),
		}
		return geminiResult(gemini.Resume(ctx, sessionID, prompt, opts))
	})

	// ── gemini_acp_ask ───────────────────────────────────────────────────────
	s.AddTool(mcp.NewTool("gemini_acp_ask",
		mcp.WithDescription(
			"Ask a question to a persistent, stateful Gemini session. Unlike gemini_run (one-shot), "+
				"this maintains full conversation context across calls. Perfect for interactive supervisors, "+
				"iterative reviewers, or any workflow needing back-and-forth collaboration. "+
				"Session created lazily on first call and persists until the MCP server exits. "+
				"Use session_name to run multiple concurrent sessions.",
		),
		mcp.WithString("question", mcp.Required(), mcp.Description("The question or prompt to send to the persistent session")),
		mcp.WithString("context", mcp.Description("Optional extra context prepended to the question")),
		mcp.WithString("session_name", mcp.Description("Named session slot. Each name gets its own persistent subprocess. Default: 'default'")),
		mcp.WithString("model", mcp.Description("Model for this session (set on first call, ignored on subsequent calls to the same session_name)")),
		mcp.WithString("system_context", mcp.Description("Persona/instructions for the session (set on first call via GEMINI.md)")),
	), func(ctx context.Context, req mcp.CallToolRequest) (*mcp.CallToolResult, error) {
		args := req.GetArguments()
		question, _ := args["question"].(string)
		extraContext := optStr(args, "context")
		sessionName := optStr(args, "session_name")
		if sessionName == "" {
			sessionName = "default"
		}

		opts := acp.Options{
			Model:         optStr(args, "model"),
			SystemContext: optStr(args, "system_context"),
		}

		result, err := acp.Ask(ctx, question, opts, sessionName, extraContext)
		if err != nil {
			return mcp.NewToolResultError(err.Error()), nil
		}
		b, _ := json.MarshalIndent(result, "", "  ")
		return mcp.NewToolResultText(string(b)), nil
	})

	// ── gemini_list_models ───────────────────────────────────────────────────
	s.AddTool(mcp.NewTool("gemini_list_models",
		mcp.WithDescription("List available Gemini models with guidance on when to use each."),
	), func(_ context.Context, _ mcp.CallToolRequest) (*mcp.CallToolResult, error) {
		type modelEntry struct {
			ID          string `json:"id"`
			Description string `json:"description"`
		}
		models := []modelEntry{
			{"auto", "Routes to the best model automatically. Use when unsure."},
			{"gemini-3.1-pro-preview", "Gemini 3.1 Pro Preview. Highest quality. Best for: complex reasoning, architecture design, nuanced tasks."},
			{"gemini-3-pro-preview", "Gemini 3 Pro Preview. High quality. Best for: complex tasks requiring strong reasoning."},
			{"gemini-3-flash-preview", "Gemini 3 Flash Preview. Fast and balanced. Best for: web search, code review, most tasks. Recommended default."},
			{"gemini-2.5-pro", "Gemini 2.5 Pro. Stable high quality. Best for: long documents, extended context tasks."},
			{"gemini-2.5-flash", "Gemini 2.5 Flash. Balanced speed/quality. Best for: general tasks."},
			{"gemini-2.5-flash-lite", "Gemini 2.5 Flash-Lite. Fastest, lowest cost. Best for: simple lookups, classification."},
		}
		defaultModel := os.Getenv("GEMINI_DEFAULT_MODEL")
		if defaultModel == "" {
			defaultModel = "auto"
		}
		result := map[string]any{
			"models":        models,
			"default_model": defaultModel,
		}
		b, _ := json.MarshalIndent(result, "", "  ")
		return mcp.NewToolResultText(string(b)), nil
	})
}
