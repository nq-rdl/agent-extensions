// pi-rpc-mcp is a Model Context Protocol server that wraps the pi.dev RPC service.
// It exposes pi.dev session management as MCP tools over stdio.
// The pi-server must be running (default: http://localhost:4097).
package main

import (
	"context"
	"encoding/json"
	"fmt"
	"os"

	"github.com/mark3labs/mcp-go/mcp"
	"github.com/mark3labs/mcp-go/server"
	"github.com/nq-rdl/agent-extensions/mcp/pi-rpc-go/internal/pirpc"
)

var version = "dev"

func main() {
	s := server.NewMCPServer("pi-rpc", version,
		server.WithToolCapabilities(false),
	)

	registerTools(s)

	// ServeStdio handles SIGTERM/SIGINT internally.
	if err := server.ServeStdio(s); err != nil {
		fmt.Fprintf(os.Stderr, "pi-rpc-mcp: %v\n", err)
		os.Exit(1)
	}
}

func toolResult(raw json.RawMessage, err error) (*mcp.CallToolResult, error) {
	if err != nil {
		return mcp.NewToolResultError(err.Error()), nil
	}

	var pretty []byte
	if pretty, err = json.MarshalIndent(json.RawMessage(raw), "", "  "); err != nil {
		pretty = raw
	}
	return mcp.NewToolResultText(string(pretty)), nil
}

func registerTools(s *server.MCPServer) {
	s.AddTool(mcp.NewTool("pi_create",
		mcp.WithDescription("Create a new pi.dev coding agent session. Spawns a pi --mode rpc subprocess. Returns a session_id for subsequent calls."),
		mcp.WithString("provider",
			mcp.Required(),
			mcp.Description(`AI provider, e.g. "openai-codex" or "anthropic"`),
		),
		mcp.WithString("model",
			mcp.Required(),
			mcp.Description(`Model ID, e.g. "gpt-5.4" or "claude-sonnet-4-20250514"`),
		),
		mcp.WithString("cwd",
			mcp.Description("Working directory for the pi.dev subprocess"),
		),
		mcp.WithString("thinking_level",
			mcp.Description(`Thinking level for reasoning models: "off", "minimal", "low", "medium", "high", "xhigh"`),
		),
	), func(_ context.Context, req mcp.CallToolRequest) (*mcp.CallToolResult, error) {
		args := req.GetArguments()
		provider, _ := args["provider"].(string)
		model, _ := args["model"].(string)
		cwd, _ := args["cwd"].(string)
		thinkingLevel, _ := args["thinking_level"].(string)
		return toolResult(pirpc.Create(provider, model, cwd, thinkingLevel))
	})

	s.AddTool(mcp.NewTool("pi_prompt",
		mcp.WithDescription("Send a prompt to a pi.dev session and wait for completion (synchronous, up to 5 minutes). Returns session state and messages."),
		mcp.WithString("session_id",
			mcp.Required(),
			mcp.Description("Session ID returned by pi_create"),
		),
		mcp.WithString("message",
			mcp.Required(),
			mcp.Description("Prompt to send to the coding agent"),
		),
	), func(_ context.Context, req mcp.CallToolRequest) (*mcp.CallToolResult, error) {
		args := req.GetArguments()
		sid, _ := args["session_id"].(string)
		msg, _ := args["message"].(string)
		return toolResult(pirpc.Prompt(sid, msg))
	})

	s.AddTool(mcp.NewTool("pi_prompt_async",
		mcp.WithDescription("Send a prompt to a pi.dev session without waiting. Returns immediately. Use pi_get_state to monitor progress."),
		mcp.WithString("session_id",
			mcp.Required(),
			mcp.Description("Session ID returned by pi_create"),
		),
		mcp.WithString("message",
			mcp.Required(),
			mcp.Description("Prompt to send to the coding agent"),
		),
	), func(_ context.Context, req mcp.CallToolRequest) (*mcp.CallToolResult, error) {
		args := req.GetArguments()
		sid, _ := args["session_id"].(string)
		msg, _ := args["message"].(string)
		return toolResult(pirpc.PromptAsync(sid, msg))
	})

	s.AddTool(mcp.NewTool("pi_get_messages",
		mcp.WithDescription("Retrieve all conversation messages buffered in a pi.dev session."),
		mcp.WithString("session_id",
			mcp.Required(),
			mcp.Description("Session ID returned by pi_create"),
		),
	), func(_ context.Context, req mcp.CallToolRequest) (*mcp.CallToolResult, error) {
		args := req.GetArguments()
		sid, _ := args["session_id"].(string)
		return toolResult(pirpc.GetMessages(sid))
	})

	s.AddTool(mcp.NewTool("pi_get_state",
		mcp.WithDescription("Get current state of a pi.dev session (IDLE, RUNNING, ERROR, TERMINATED) and metadata."),
		mcp.WithString("session_id",
			mcp.Required(),
			mcp.Description("Session ID returned by pi_create"),
		),
	), func(_ context.Context, req mcp.CallToolRequest) (*mcp.CallToolResult, error) {
		args := req.GetArguments()
		sid, _ := args["session_id"].(string)
		return toolResult(pirpc.GetState(sid))
	})

	s.AddTool(mcp.NewTool("pi_abort",
		mcp.WithDescription("Abort the current operation in a pi.dev session. The session remains open for further prompts."),
		mcp.WithString("session_id",
			mcp.Required(),
			mcp.Description("Session ID returned by pi_create"),
		),
	), func(_ context.Context, req mcp.CallToolRequest) (*mcp.CallToolResult, error) {
		args := req.GetArguments()
		sid, _ := args["session_id"].(string)
		return toolResult(pirpc.Abort(sid))
	})

	s.AddTool(mcp.NewTool("pi_delete",
		mcp.WithDescription("Delete a pi.dev session. Kills the subprocess and frees all resources."),
		mcp.WithString("session_id",
			mcp.Required(),
			mcp.Description("Session ID returned by pi_create"),
		),
	), func(_ context.Context, req mcp.CallToolRequest) (*mcp.CallToolResult, error) {
		args := req.GetArguments()
		sid, _ := args["session_id"].(string)
		return toolResult(pirpc.Delete(sid))
	})

	s.AddTool(mcp.NewTool("pi_list",
		mcp.WithDescription("List all active pi.dev sessions managed by the pi-server. Use as a health check (empty array = server ready)."),
	), func(_ context.Context, _ mcp.CallToolRequest) (*mcp.CallToolResult, error) {
		return toolResult(pirpc.List())
	})
}
