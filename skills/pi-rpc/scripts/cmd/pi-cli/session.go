package main

import (
	"bytes"
	"context"
	"encoding/json"
	"fmt"
	"io"
	"net/http"
	"os"

	"github.com/spf13/cobra"
)

// serverURL returns the ConnectRPC server base URL, preferring the flag value
// over the PI_SERVER_URL environment variable, with a hardcoded default.
func serverURL(flagVal string) string {
	if flagVal != "" {
		return flagVal
	}
	if env := os.Getenv("PI_SERVER_URL"); env != "" {
		return env
	}
	return defaultServerURL
}

// rpcPost calls a ConnectRPC endpoint and decodes the JSON response.
// It never returns raw upstream error strings to callers — only safe,
// descriptive messages that don't leak internal server details.
func rpcPost(ctx context.Context, base, method string, reqBody, respBody any) error {
	payload, err := json.Marshal(reqBody)
	if err != nil {
		return fmt.Errorf("encode request: %w", err)
	}

	url := base + "/" + method
	req, err := http.NewRequestWithContext(ctx, http.MethodPost, url, bytes.NewReader(payload))
	if err != nil {
		return fmt.Errorf("build request: %w", err)
	}
	req.Header.Set("Content-Type", "application/json")

	resp, err := http.DefaultClient.Do(req)
	if err != nil {
		return fmt.Errorf("call %s: %w", method, err)
	}
	defer resp.Body.Close()

	body, err := io.ReadAll(resp.Body)
	if err != nil {
		return fmt.Errorf("read response: %w", err)
	}

	if resp.StatusCode != http.StatusOK {
		// Extract Connect error message without leaking raw body
		var connectErr struct {
			Message string `json:"message"`
			Code    string `json:"code"`
		}
		if jsonErr := json.Unmarshal(body, &connectErr); jsonErr == nil && connectErr.Message != "" {
			return fmt.Errorf("%s: %s (code: %s)", method, connectErr.Message, connectErr.Code)
		}
		return fmt.Errorf("%s returned status %d", method, resp.StatusCode)
	}

	if respBody != nil {
		if err := json.Unmarshal(body, respBody); err != nil {
			return fmt.Errorf("decode response: %w", err)
		}
	}
	return nil
}

// newSessionCmd builds the `session` parent command with all subcommands.
func newSessionCmd() *cobra.Command {
	var serverFlag string

	cmd := &cobra.Command{
		Use:   "session",
		Short: "Manage pi.dev coding agent sessions",
		Long: `Create, prompt, inspect, and delete pi.dev coding agent sessions.

All subcommands communicate with a running pi-server instance.
Start pi-server with: pi-cli serve

Examples:
  pi-cli session create --provider anthropic --model claude-opus-4 --cwd /my/project
  pi-cli session list
  pi-cli session prompt --id abc-123 "Write a hello world program"
  pi-cli session state --id abc-123
  pi-cli session delete --id abc-123`,
	}

	// --server flag is inherited by all subcommands
	cmd.PersistentFlags().StringVar(&serverFlag, "server", "",
		"pi-server URL (overrides PI_SERVER_URL, default: http://localhost:4097)")

	cmd.AddCommand(
		newSessionCreateCmd(&serverFlag),
		newSessionListCmd(&serverFlag),
		newSessionDeleteCmd(&serverFlag),
		newSessionPromptCmd(&serverFlag),
		newSessionStateCmd(&serverFlag),
		newSessionAbortCmd(&serverFlag),
	)

	return cmd
}

// --- create ---

func newSessionCreateCmd(serverFlag *string) *cobra.Command {
	var (
		provider       string
		model          string
		cwd            string
		thinkingLevel  string
		timeoutSeconds int32
	)

	cmd := &cobra.Command{
		Use:   "create",
		Short: "Spawn a new pi.dev session",
		Long: `Spawn a new pi.dev coding agent session and print the session ID.

If --provider and --model are omitted, defaults (or PI_DEFAULT_PROVIDER/PI_DEFAULT_MODEL) are used.

Tip: validate your provider/model pair before creating sessions:
  pi --provider <PROVIDER> --model <MODEL> --mode json "Reply with OK."`,
		RunE: func(cmd *cobra.Command, args []string) error {
			return runSessionCreate(cmd.Context(), serverURL(*serverFlag), provider, model, cwd, thinkingLevel, timeoutSeconds)
		},
	}

	cmd.Flags().StringVar(&provider, "provider", "", "Provider name, e.g. anthropic, openai-codex")
	cmd.Flags().StringVar(&model, "model", "", "Model ID from pi --list-models")
	cmd.Flags().StringVar(&cwd, "cwd", "", "Working directory for the agent (default: current directory)")
	cmd.Flags().StringVar(&thinkingLevel, "thinking", "", "Thinking level: low, medium, high")
	cmd.Flags().Int32Var(&timeoutSeconds, "timeout", 0, "Inactivity timeout in seconds (0 = server default)")

	return cmd
}

func runSessionCreate(ctx context.Context, base, provider, model, cwd, thinkingLevel string, timeoutSeconds int32) error {
	req := map[string]any{
		"provider":        provider,
		"model":           model,
		"cwd":             cwd,
		"thinking_level":  thinkingLevel,
		"timeout_seconds": timeoutSeconds,
	}

	var resp struct {
		SessionID string `json:"sessionId"`
		State     string `json:"state"`
	}

	if err := rpcPost(ctx, base, "pirpc.v1.SessionService/Create", req, &resp); err != nil {
		return err
	}

	fmt.Printf("session_id: %s\nstate:      %s\n", resp.SessionID, resp.State)
	return nil
}

// --- list ---

func newSessionListCmd(serverFlag *string) *cobra.Command {
	return &cobra.Command{
		Use:   "list",
		Short: "List all active sessions",
		RunE: func(cmd *cobra.Command, args []string) error {
			return runSessionList(cmd.Context(), serverURL(*serverFlag))
		},
	}
}

func runSessionList(ctx context.Context, base string) error {
	var resp struct {
		Sessions []struct {
			ID        string `json:"id"`
			State     string `json:"state"`
			Provider  string `json:"provider"`
			Model     string `json:"model"`
			CreatedAt string `json:"createdAt"`
		} `json:"sessions"`
	}

	if err := rpcPost(ctx, base, "pirpc.v1.SessionService/List", struct{}{}, &resp); err != nil {
		return err
	}

	if len(resp.Sessions) == 0 {
		fmt.Println("no active sessions")
		return nil
	}

	fmt.Printf("%-36s  %-12s  %-20s  %s\n", "ID", "STATE", "PROVIDER", "MODEL")
	for _, s := range resp.Sessions {
		fmt.Printf("%-36s  %-12s  %-20s  %s\n", s.ID, s.State, s.Provider, s.Model)
	}
	return nil
}

// --- delete ---

func newSessionDeleteCmd(serverFlag *string) *cobra.Command {
	var id string

	cmd := &cobra.Command{
		Use:   "delete",
		Short: "Delete a session and free its resources",
		RunE: func(cmd *cobra.Command, args []string) error {
			return runSessionDelete(cmd.Context(), serverURL(*serverFlag), id)
		},
	}

	cmd.Flags().StringVar(&id, "id", "", "Session ID (required)")
	_ = cmd.MarkFlagRequired("id")

	return cmd
}

func runSessionDelete(ctx context.Context, base, id string) error {
	if err := rpcPost(ctx, base, "pirpc.v1.SessionService/Delete", map[string]string{"sessionId": id}, nil); err != nil {
		return err
	}
	fmt.Printf("deleted session %s\n", id)
	return nil
}

// --- prompt ---

func newSessionPromptCmd(serverFlag *string) *cobra.Command {
	var (
		id    string
		async bool
	)

	cmd := &cobra.Command{
		Use:   "prompt",
		Short: "Send a prompt to a session",
		Long: `Send a prompt to a session and wait for the agent to complete (synchronous).

Use --async to return immediately and monitor with: pi-cli session state --id <id>`,
		Args: cobra.ExactArgs(1),
		RunE: func(cmd *cobra.Command, args []string) error {
			return runSessionPrompt(cmd.Context(), serverURL(*serverFlag), id, args[0], async)
		},
	}

	cmd.Flags().StringVar(&id, "id", "", "Session ID (required)")
	cmd.Flags().BoolVar(&async, "async", false, "Return immediately without waiting for completion")
	_ = cmd.MarkFlagRequired("id")

	return cmd
}

func runSessionPrompt(ctx context.Context, base, id, message string, async bool) error {
	req := map[string]string{"sessionId": id, "message": message}

	if async {
		if err := rpcPost(ctx, base, "pirpc.v1.SessionService/PromptAsync", req, nil); err != nil {
			return err
		}
		fmt.Println("prompt dispatched (async) — use `pi-cli session state` to monitor")
		return nil
	}

	var resp struct {
		State    string `json:"state"`
		Messages []struct {
			Role    string `json:"role"`
			Content string `json:"content"`
		} `json:"messages"`
	}

	if err := rpcPost(ctx, base, "pirpc.v1.SessionService/Prompt", req, &resp); err != nil {
		return err
	}

	fmt.Printf("state: %s\n", resp.State)
	for _, m := range resp.Messages {
		fmt.Printf("[%s]: %s\n", m.Role, m.Content)
	}
	return nil
}

// --- state ---

func newSessionStateCmd(serverFlag *string) *cobra.Command {
	var id string

	cmd := &cobra.Command{
		Use:   "state",
		Short: "Get current state of a session",
		RunE: func(cmd *cobra.Command, args []string) error {
			return runSessionState(cmd.Context(), serverURL(*serverFlag), id)
		},
	}

	cmd.Flags().StringVar(&id, "id", "", "Session ID (required)")
	_ = cmd.MarkFlagRequired("id")

	return cmd
}

func runSessionState(ctx context.Context, base, id string) error {
	var resp struct {
		SessionID    string `json:"sessionId"`
		State        string `json:"state"`
		Provider     string `json:"provider"`
		Model        string `json:"model"`
		Cwd          string `json:"cwd"`
		PID          int    `json:"pid"`
		ErrorMessage string `json:"errorMessage"`
	}

	if err := rpcPost(ctx, base, "pirpc.v1.SessionService/GetState", map[string]string{"sessionId": id}, &resp); err != nil {
		return err
	}

	fmt.Printf("session_id: %s\nstate:      %s\nprovider:   %s\nmodel:      %s\ncwd:        %s\npid:        %d\n",
		resp.SessionID, resp.State, resp.Provider, resp.Model, resp.Cwd, resp.PID)

	if resp.ErrorMessage != "" {
		fmt.Printf("error:      %s\n", resp.ErrorMessage)
	}
	return nil
}

// --- abort ---

func newSessionAbortCmd(serverFlag *string) *cobra.Command {
	var id string

	cmd := &cobra.Command{
		Use:   "abort",
		Short: "Abort a running operation in a session",
		RunE: func(cmd *cobra.Command, args []string) error {
			return runSessionAbort(cmd.Context(), serverURL(*serverFlag), id)
		},
	}

	cmd.Flags().StringVar(&id, "id", "", "Session ID (required)")
	_ = cmd.MarkFlagRequired("id")

	return cmd
}

func runSessionAbort(ctx context.Context, base, id string) error {
	var resp struct {
		State string `json:"state"`
	}

	if err := rpcPost(ctx, base, "pirpc.v1.SessionService/Abort", map[string]string{"sessionId": id}, &resp); err != nil {
		return err
	}

	fmt.Printf("aborted session %s — state: %s\n", id, resp.State)
	return nil
}
