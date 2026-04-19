// Command pi-mcp exposes the pi-rpc session service as an MCP server over stdio.
// It embeds the session manager directly — no running pi-server required.
package main

import (
	"cmp"
	"context"
	"encoding/json"
	"errors"
	"fmt"
	"log/slog"
	"math"
	"os"

	"connectrpc.com/connect"
	"github.com/mark3labs/mcp-go/mcp"
	"github.com/mark3labs/mcp-go/server"

	pirpcv1 "github.com/nq-rdl/agent-skills/skills/pi-rpc/scripts/gen/pirpc/v1"
	"github.com/nq-rdl/agent-skills/skills/pi-rpc/scripts/handler"
	"github.com/nq-rdl/agent-skills/skills/pi-rpc/scripts/session"
)

var version = "dev"

func main() {
	if err := run(); err != nil {
		slog.Error("pi-mcp exited with error", "err", err)
		os.Exit(1)
	}
}

func run() error {
	binary := cmp.Or(os.Getenv("PI_BINARY"), "pi")
	defaults := handler.Defaults{
		Provider: cmp.Or(os.Getenv("PI_DEFAULT_PROVIDER"), "openai"),
		Model:    cmp.Or(os.Getenv("PI_DEFAULT_MODEL"), "gpt-4.1"),
	}

	mgr := session.NewManager(binary)
	defer mgr.GracefulShutdown()

	h := handler.NewSessionHandler(mgr, defaults)

	s := server.NewMCPServer("pi-mcp", version, server.WithToolCapabilities(true))

	s.AddTool(
		mcp.NewTool("session_create",
			mcp.WithDescription("Spawn a pi.dev coding agent session. Returns session_id for subsequent calls."),
			mcp.WithString("cwd", mcp.Required(), mcp.Description("Working directory for the session")),
			mcp.WithString("provider", mcp.Description("AI provider (e.g. anthropic, openai). Uses PI_DEFAULT_PROVIDER if omitted.")),
			mcp.WithString("model", mcp.Description("Model name. Uses PI_DEFAULT_MODEL if omitted.")),
			mcp.WithString("thinking_level", mcp.Description("Thinking level (auto, low, medium, high)")),
			mcp.WithNumber("timeout_seconds", mcp.Description("Inactivity timeout in seconds (0 = default)")),
		),
		func(ctx context.Context, req mcp.CallToolRequest) (*mcp.CallToolResult, error) {
			args := req.GetArguments()
			createReq := &pirpcv1.CreateRequest{
				Cwd:            stringArg(args, "cwd"),
				Provider:       stringArg(args, "provider"),
				Model:          stringArg(args, "model"),
				ThinkingLevel:  stringArg(args, "thinking_level"),
				TimeoutSeconds: safeInt32(numberArg(args, "timeout_seconds")),
			}
			resp, err := h.Create(ctx, connect.NewRequest(createReq))
			if err != nil {
				return nil, connectErrToMCP(err)
			}
			return jsonResult(map[string]any{
				"session_id": resp.Msg.SessionId,
				"state":      resp.Msg.State.String(),
			})
		},
	)

	s.AddTool(
		mcp.NewTool("session_list",
			mcp.WithDescription("List all active pi.dev sessions."),
		),
		func(ctx context.Context, req mcp.CallToolRequest) (*mcp.CallToolResult, error) {
			resp, err := h.List(ctx, connect.NewRequest(&pirpcv1.ListRequest{}))
			if err != nil {
				return nil, connectErrToMCP(err)
			}
			sessions := make([]map[string]any, len(resp.Msg.Sessions))
			for i, s := range resp.Msg.Sessions {
				sessions[i] = map[string]any{
					"id":         s.Id,
					"state":      s.State.String(),
					"provider":   s.Provider,
					"model":      s.Model,
					"created_at": s.CreatedAt.AsTime().Format("2006-01-02T15:04:05Z"),
				}
			}
			return jsonResult(map[string]any{"sessions": sessions})
		},
	)

	s.AddTool(
		mcp.NewTool("session_get_state",
			mcp.WithDescription("Get the current state and metadata of a session."),
			mcp.WithString("session_id", mcp.Required(), mcp.Description("Session ID returned by session_create")),
		),
		func(ctx context.Context, req mcp.CallToolRequest) (*mcp.CallToolResult, error) {
			resp, err := h.GetState(ctx, connect.NewRequest(&pirpcv1.GetStateRequest{
				SessionId: stringArg(req.GetArguments(), "session_id"),
			}))
			if err != nil {
				return nil, connectErrToMCP(err)
			}
			m := resp.Msg
			return jsonResult(map[string]any{
				"session_id":    m.SessionId,
				"state":         m.State.String(),
				"provider":      m.Provider,
				"model":         m.Model,
				"cwd":           m.Cwd,
				"pid":           m.Pid,
				"error_message": m.ErrorMessage,
			})
		},
	)

	s.AddTool(
		mcp.NewTool("session_prompt",
			mcp.WithDescription("Send a prompt to a session and wait for the agent to finish (up to 5 minutes)."),
			mcp.WithString("session_id", mcp.Required(), mcp.Description("Session ID")),
			mcp.WithString("message", mcp.Required(), mcp.Description("Prompt message to send")),
		),
		func(ctx context.Context, req mcp.CallToolRequest) (*mcp.CallToolResult, error) {
			resp, err := h.Prompt(ctx, connect.NewRequest(&pirpcv1.PromptRequest{
				SessionId: stringArg(req.GetArguments(), "session_id"),
				Message:   stringArg(req.GetArguments(), "message"),
			}))
			if err != nil {
				return nil, connectErrToMCP(err)
			}
			return jsonResult(map[string]any{"state": resp.Msg.State.String()})
		},
	)

	s.AddTool(
		mcp.NewTool("session_prompt_async",
			mcp.WithDescription("Send a prompt to a session and return immediately without waiting."),
			mcp.WithString("session_id", mcp.Required(), mcp.Description("Session ID")),
			mcp.WithString("message", mcp.Required(), mcp.Description("Prompt message to send")),
		),
		func(ctx context.Context, req mcp.CallToolRequest) (*mcp.CallToolResult, error) {
			_, err := h.PromptAsync(ctx, connect.NewRequest(&pirpcv1.PromptAsyncRequest{
				SessionId: stringArg(req.GetArguments(), "session_id"),
				Message:   stringArg(req.GetArguments(), "message"),
			}))
			if err != nil {
				return nil, connectErrToMCP(err)
			}
			return jsonResult(map[string]any{"status": "sent"})
		},
	)

	s.AddTool(
		mcp.NewTool("session_get_messages",
			mcp.WithDescription("Retrieve the conversation messages from a session."),
			mcp.WithString("session_id", mcp.Required(), mcp.Description("Session ID")),
		),
		func(ctx context.Context, req mcp.CallToolRequest) (*mcp.CallToolResult, error) {
			resp, err := h.GetMessages(ctx, connect.NewRequest(&pirpcv1.GetMessagesRequest{
				SessionId: stringArg(req.GetArguments(), "session_id"),
			}))
			if err != nil {
				return nil, connectErrToMCP(err)
			}
			msgs := make([]map[string]any, len(resp.Msg.Messages))
			for i, m := range resp.Msg.Messages {
				msgs[i] = map[string]any{
					"role":         m.Role.String(),
					"content":      m.Content,
					"is_error":     m.IsError,
					"tool_call_id": m.ToolCallId,
					"timestamp_ms": m.TimestampMs,
				}
			}
			return jsonResult(map[string]any{"messages": msgs})
		},
	)

	s.AddTool(
		mcp.NewTool("session_abort",
			mcp.WithDescription("Cancel a running operation in a session."),
			mcp.WithString("session_id", mcp.Required(), mcp.Description("Session ID")),
		),
		func(ctx context.Context, req mcp.CallToolRequest) (*mcp.CallToolResult, error) {
			resp, err := h.Abort(ctx, connect.NewRequest(&pirpcv1.AbortRequest{
				SessionId: stringArg(req.GetArguments(), "session_id"),
			}))
			if err != nil {
				return nil, connectErrToMCP(err)
			}
			return jsonResult(map[string]any{"state": resp.Msg.State.String()})
		},
	)

	s.AddTool(
		mcp.NewTool("session_delete",
			mcp.WithDescription("Kill a session subprocess and free its resources."),
			mcp.WithString("session_id", mcp.Required(), mcp.Description("Session ID")),
		),
		func(ctx context.Context, req mcp.CallToolRequest) (*mcp.CallToolResult, error) {
			_, err := h.Delete(ctx, connect.NewRequest(&pirpcv1.DeleteRequest{
				SessionId: stringArg(req.GetArguments(), "session_id"),
			}))
			if err != nil {
				return nil, connectErrToMCP(err)
			}
			return jsonResult(map[string]any{"status": "deleted"})
		},
	)

	if err := server.ServeStdio(s); err != nil {
		return fmt.Errorf("serve stdio: %w", err)
	}
	return nil
}

func stringArg(args map[string]any, key string) string {
	if v, ok := args[key]; ok {
		if s, ok := v.(string); ok {
			return s
		}
		return fmt.Sprintf("%v", v)
	}
	return ""
}

// numberArg accepts JSON numbers (float64) and integer-typed values that some
// MCP clients emit. Non-numeric or missing keys return 0.
func numberArg(args map[string]any, key string) float64 {
	v, ok := args[key]
	if !ok {
		return 0
	}
	switch n := v.(type) {
	case float64:
		return n
	case float32:
		return float64(n)
	case int:
		return float64(n)
	case int32:
		return float64(n)
	case int64:
		return float64(n)
	}
	return 0
}

// safeInt32 clamps a float64 into the int32 range, rejecting NaN.
// Untrusted MCP client input must never overflow the protobuf int32 field.
func safeInt32(n float64) int32 {
	if math.IsNaN(n) || n < 0 {
		return 0
	}
	if n > math.MaxInt32 {
		return math.MaxInt32
	}
	return int32(n)
}

func jsonResult(v any) (*mcp.CallToolResult, error) {
	data, err := json.Marshal(v)
	if err != nil {
		return nil, fmt.Errorf("marshal tool result: %w", err)
	}
	return mcp.NewToolResultText(string(data)), nil
}

// connectErrToMCP sanitises a ConnectRPC error before it crosses the MCP
// stdio boundary to the host agent. The host may relay errors into LLM prompts,
// so raw upstream error text (which can contain paths, model IDs, credentials,
// or internal state) never escapes. The full error is logged to stderr for
// local operators via slog.
func connectErrToMCP(err error) error {
	if err == nil {
		return nil
	}
	slog.Error("pi-rpc call failed", "err", err)

	var cerr *connect.Error
	if errors.As(err, &cerr) {
		return fmt.Errorf("pi-rpc: %s", sanitizedMessageFor(cerr.Code()))
	}
	return errors.New("pi-rpc: internal error")
}

func sanitizedMessageFor(code connect.Code) string {
	switch code {
	case connect.CodeNotFound:
		return "session not found"
	case connect.CodeInvalidArgument:
		return "invalid argument"
	case connect.CodePermissionDenied:
		return "permission denied"
	case connect.CodeUnauthenticated:
		return "authentication required"
	case connect.CodeDeadlineExceeded:
		return "deadline exceeded"
	case connect.CodeCanceled:
		return "canceled"
	case connect.CodeUnavailable:
		return "service unavailable"
	case connect.CodeFailedPrecondition:
		return "failed precondition"
	case connect.CodeAlreadyExists:
		return "already exists"
	case connect.CodeResourceExhausted:
		return "resource exhausted"
	case connect.CodeInternal:
		return "internal error"
	default:
		return "request failed"
	}
}
