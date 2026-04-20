package main

import (
	"context"
	"encoding/json"
	"net/http"
	"net/http/httptest"
	"strings"
	"testing"

	"github.com/spf13/cobra"
)

// newTestServer creates an httptest.Server that routes ConnectRPC method paths
// to handler functions that return pre-canned JSON responses.
func newTestServer(t *testing.T, routes map[string]any) *httptest.Server {
	t.Helper()
	mux := http.NewServeMux()
	for path, body := range routes {
		p, b := path, body // capture loop vars
		mux.HandleFunc(p, func(w http.ResponseWriter, r *http.Request) {
			w.Header().Set("Content-Type", "application/json")
			_ = json.NewEncoder(w).Encode(b)
		})
	}
	return httptest.NewServer(mux)
}

// captureOutput runs fn and returns stdout as a string by intercepting writes
// via a strings.Builder passed through the captured output of the command.
// Since pi-cli writes to os.Stdout we test via the run* helpers directly.

func TestServerURLPrecedence(t *testing.T) {
	t.Run("flag overrides env", func(t *testing.T) {
		t.Setenv("PI_SERVER_URL", "http://from-env:9999")
		got := serverURL("http://from-flag:1234")
		if got != "http://from-flag:1234" {
			t.Errorf("serverURL = %q, want flag value", got)
		}
	})

	t.Run("env when no flag", func(t *testing.T) {
		t.Setenv("PI_SERVER_URL", "http://from-env:9999")
		got := serverURL("")
		if got != "http://from-env:9999" {
			t.Errorf("serverURL = %q, want env value", got)
		}
	})

	t.Run("default when nothing set", func(t *testing.T) {
		t.Setenv("PI_SERVER_URL", "")
		got := serverURL("")
		if got != defaultServerURL {
			t.Errorf("serverURL = %q, want default %q", got, defaultServerURL)
		}
	})
}

func TestRunSessionCreate(t *testing.T) {
	srv := newTestServer(t, map[string]any{
		"/pirpc.v1.SessionService/Create": map[string]string{
			"sessionId": "abc-123",
			"state":     "SESSION_STATE_IDLE",
		},
	})
	defer srv.Close()

	// runSessionCreate writes to stdout — we just verify no error is returned
	// and the call succeeds against a real HTTP server.
	if err := runSessionCreate(context.Background(), srv.URL, "anthropic", "claude-opus-4", "/tmp", "", 0); err != nil {
		t.Errorf("runSessionCreate failed: %v", err)
	}
}

func TestRunSessionCreateUnreachableServer(t *testing.T) {
	// Documented behavior: provider/model are optional and fall through to
	// PI_DEFAULT_PROVIDER / PI_DEFAULT_MODEL on the server side. What MUST
	// surface to the CLI user is an RPC error when the server is not reachable.
	err := runSessionCreate(context.Background(),
		"http://127.0.0.1:1", // reserved port; connection must fail fast
		"", "", "/tmp", "", 0)
	if err == nil {
		t.Error("expected error when server is unreachable")
	}
}

func TestRunSessionCreateDefaultsAccepted(t *testing.T) {
	// Issue #70: empty provider/model must be forwarded verbatim so the server
	// can apply PI_DEFAULT_PROVIDER / PI_DEFAULT_MODEL. The CLI must not
	// reject or mutate empty values.
	var receivedProvider, receivedModel string
	done := make(chan struct{})
	srv := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		defer close(done)
		var req map[string]any
		if err := json.NewDecoder(r.Body).Decode(&req); err != nil {
			t.Errorf("decode request body: %v", err)
			return
		}
		receivedProvider, _ = req["provider"].(string)
		receivedModel, _ = req["model"].(string)
		w.Header().Set("Content-Type", "application/json")
		_ = json.NewEncoder(w).Encode(map[string]any{
			"sessionId": "defaults-abc",
			"state":     "SESSION_STATE_IDLE",
		})
	}))
	defer srv.Close()

	if err := runSessionCreate(context.Background(), srv.URL, "", "", t.TempDir(), "", 0); err != nil {
		t.Fatalf("runSessionCreate with empty provider/model failed: %v", err)
	}
	<-done
	if receivedProvider != "" {
		t.Errorf("provider forwarded to server = %q, want empty string", receivedProvider)
	}
	if receivedModel != "" {
		t.Errorf("model forwarded to server = %q, want empty string", receivedModel)
	}
}

func TestRunSessionList(t *testing.T) {
	srv := newTestServer(t, map[string]any{
		"/pirpc.v1.SessionService/List": map[string]any{
			"sessions": []map[string]string{
				{"id": "abc-123", "state": "SESSION_STATE_IDLE", "provider": "anthropic", "model": "claude-opus-4"},
			},
		},
	})
	defer srv.Close()

	if err := runSessionList(context.Background(), srv.URL); err != nil {
		t.Errorf("runSessionList failed: %v", err)
	}
}

func TestRunSessionListEmpty(t *testing.T) {
	srv := newTestServer(t, map[string]any{
		"/pirpc.v1.SessionService/List": map[string]any{
			"sessions": []map[string]string{},
		},
	})
	defer srv.Close()

	if err := runSessionList(context.Background(), srv.URL); err != nil {
		t.Errorf("runSessionList (empty) failed: %v", err)
	}
}

func TestRunSessionDelete(t *testing.T) {
	srv := newTestServer(t, map[string]any{
		"/pirpc.v1.SessionService/Delete": map[string]any{},
	})
	defer srv.Close()

	if err := runSessionDelete(context.Background(), srv.URL, "abc-123"); err != nil {
		t.Errorf("runSessionDelete failed: %v", err)
	}
}

func TestRunSessionDeleteServerError(t *testing.T) {
	srv := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		w.WriteHeader(http.StatusNotFound)
		_ = json.NewEncoder(w).Encode(map[string]string{
			"code":    "not_found",
			"message": "session not found",
		})
	}))
	defer srv.Close()

	err := runSessionDelete(context.Background(), srv.URL, "nonexistent")
	if err == nil {
		t.Error("expected error for server 404 response")
	}
	if !strings.Contains(err.Error(), "session not found") {
		t.Errorf("error message = %q, want 'session not found'", err.Error())
	}
}

func TestRunSessionState(t *testing.T) {
	srv := newTestServer(t, map[string]any{
		"/pirpc.v1.SessionService/GetState": map[string]any{
			"sessionId": "abc-123",
			"state":     "SESSION_STATE_IDLE",
			"provider":  "anthropic",
			"model":     "claude-opus-4",
			"cwd":       "/tmp",
			"pid":       12345,
		},
	})
	defer srv.Close()

	if err := runSessionState(context.Background(), srv.URL, "abc-123"); err != nil {
		t.Errorf("runSessionState failed: %v", err)
	}
}

func TestRunSessionPromptSync(t *testing.T) {
	srv := newTestServer(t, map[string]any{
		"/pirpc.v1.SessionService/Prompt": map[string]any{
			"state":    "SESSION_STATE_IDLE",
			"messages": []map[string]string{{"role": "assistant", "content": "Hello!"}},
		},
	})
	defer srv.Close()

	if err := runSessionPrompt(context.Background(), srv.URL, "abc-123", "hello", false); err != nil {
		t.Errorf("runSessionPrompt (sync) failed: %v", err)
	}
}

func TestRunSessionPromptAsync(t *testing.T) {
	srv := newTestServer(t, map[string]any{
		"/pirpc.v1.SessionService/PromptAsync": map[string]any{},
	})
	defer srv.Close()

	if err := runSessionPrompt(context.Background(), srv.URL, "abc-123", "hello", true); err != nil {
		t.Errorf("runSessionPrompt (async) failed: %v", err)
	}
}

func TestRunSessionAbort(t *testing.T) {
	srv := newTestServer(t, map[string]any{
		"/pirpc.v1.SessionService/Abort": map[string]any{
			"state": "SESSION_STATE_IDLE",
		},
	})
	defer srv.Close()

	if err := runSessionAbort(context.Background(), srv.URL, "abc-123"); err != nil {
		t.Errorf("runSessionAbort failed: %v", err)
	}
}

func TestRpcPostDecodesConnectError(t *testing.T) {
	srv := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		w.WriteHeader(http.StatusBadRequest)
		_ = json.NewEncoder(w).Encode(map[string]string{
			"code":    "invalid_argument",
			"message": "provider is required",
		})
	}))
	defer srv.Close()

	err := rpcPost(context.Background(), srv.URL, "pirpc.v1.SessionService/Create", struct{}{}, nil)
	if err == nil {
		t.Fatal("expected error")
	}
	if !strings.Contains(err.Error(), "provider is required") {
		t.Errorf("error = %q, want message from Connect error body", err.Error())
	}
}

func TestCommandTreeStructure(t *testing.T) {
	root := newRootCmd()

	// Verify top-level subcommands exist
	names := make(map[string]bool)
	for _, c := range root.Commands() {
		names[c.Name()] = true
	}

	for _, want := range []string{"serve", "session"} {
		if !names[want] {
			t.Errorf("root command missing subcommand %q", want)
		}
	}
}

func TestSessionSubcommands(t *testing.T) {
	root := newRootCmd()

	var sessionCmd *cobra.Command
	for _, c := range root.Commands() {
		if c.Name() == "session" {
			sessionCmd = c
			break
		}
	}
	if sessionCmd == nil {
		t.Fatal("session command not found")
	}

	names := make(map[string]bool)
	for _, c := range sessionCmd.Commands() {
		names[c.Name()] = true
	}

	for _, want := range []string{"create", "list", "delete", "prompt", "state", "abort"} {
		if !names[want] {
			t.Errorf("session command missing subcommand %q", want)
		}
	}
}
