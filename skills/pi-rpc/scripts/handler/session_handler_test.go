package handler

import (
	"context"
	"net/http"
	"net/http/httptest"
	"path/filepath"
	"runtime"
	"strings"
	"testing"

	"connectrpc.com/connect"
	pirpcv1 "github.com/nq-rdl/agent-skills/skills/pi-rpc/scripts/gen/pirpc/v1"
	"github.com/nq-rdl/agent-skills/skills/pi-rpc/scripts/gen/pirpc/v1/pirpcv1connect"
	"github.com/nq-rdl/agent-skills/skills/pi-rpc/scripts/session"
)

// fakePi returns the path to testdata/fake-pi.sh relative to this test file.
func fakePi(t *testing.T) string {
	t.Helper()
	_, file, _, _ := runtime.Caller(0)
	dir := filepath.Dir(file)
	return filepath.Join(dir, "..", "testdata", "fake-pi.sh")
}

func setupTestServer(t *testing.T) (pirpcv1connect.SessionServiceClient, func()) {
	t.Helper()
	return setupTestServerWithBinary(t, fakePi(t))
}

func setupTestServerWithBinary(t *testing.T, binary string) (pirpcv1connect.SessionServiceClient, func()) {
	t.Helper()

	mgr := session.NewManager(binary)
	h := NewSessionHandler(mgr)

	mux := http.NewServeMux()
	path, handler := pirpcv1connect.NewSessionServiceHandler(h)
	mux.Handle(path, handler)
	server := httptest.NewServer(mux)

	client := pirpcv1connect.NewSessionServiceClient(
		http.DefaultClient,
		server.URL,
	)

	return client, func() {
		mgr.GracefulShutdown()
		server.Close()
	}
}

func TestHandlerCreate(t *testing.T) {
	client, cleanup := setupTestServer(t)
	defer cleanup()

	resp, err := client.Create(context.Background(), connect.NewRequest(&pirpcv1.CreateRequest{
		Provider: "openai-codex",
		Model:    "gpt-5.4",
		Cwd:      t.TempDir(),
	}))
	if err != nil {
		t.Fatalf("Create failed: %v", err)
	}
	if resp.Msg.SessionId == "" {
		t.Error("Create returned empty session ID")
	}
	if resp.Msg.State != pirpcv1.SessionState_SESSION_STATE_IDLE {
		t.Errorf("state = %v, want IDLE", resp.Msg.State)
	}
}

func TestHandlerList(t *testing.T) {
	client, cleanup := setupTestServer(t)
	defer cleanup()

	client.Create(context.Background(), connect.NewRequest(&pirpcv1.CreateRequest{
		Provider: "openai-codex",
		Model:    "gpt-5.4",
		Cwd:      t.TempDir(),
	}))
	client.Create(context.Background(), connect.NewRequest(&pirpcv1.CreateRequest{
		Provider: "anthropic",
		Model:    "claude-sonnet",
		Cwd:      t.TempDir(),
	}))

	resp, err := client.List(context.Background(), connect.NewRequest(&pirpcv1.ListRequest{}))
	if err != nil {
		t.Fatalf("List failed: %v", err)
	}
	if len(resp.Msg.Sessions) != 2 {
		t.Errorf("List returned %d sessions, want 2", len(resp.Msg.Sessions))
	}
}

func TestHandlerDelete(t *testing.T) {
	client, cleanup := setupTestServer(t)
	defer cleanup()

	createResp, _ := client.Create(context.Background(), connect.NewRequest(&pirpcv1.CreateRequest{
		Provider: "openai-codex",
		Model:    "gpt-5.4",
		Cwd:      t.TempDir(),
	}))

	_, err := client.Delete(context.Background(), connect.NewRequest(&pirpcv1.DeleteRequest{
		SessionId: createResp.Msg.SessionId,
	}))
	if err != nil {
		t.Fatalf("Delete failed: %v", err)
	}

	listResp, _ := client.List(context.Background(), connect.NewRequest(&pirpcv1.ListRequest{}))
	if len(listResp.Msg.Sessions) != 0 {
		t.Errorf("List returned %d sessions after delete, want 0", len(listResp.Msg.Sessions))
	}
}

func TestHandlerDeleteNotFound(t *testing.T) {
	client, cleanup := setupTestServer(t)
	defer cleanup()

	_, err := client.Delete(context.Background(), connect.NewRequest(&pirpcv1.DeleteRequest{
		SessionId: "nonexistent-id",
	}))
	if err == nil {
		t.Error("Delete of nonexistent session should fail")
	}
	if connect.CodeOf(err) != connect.CodeNotFound {
		t.Errorf("error code = %v, want NotFound", connect.CodeOf(err))
	}
}

func TestHandlerGetState(t *testing.T) {
	client, cleanup := setupTestServer(t)
	defer cleanup()

	createResp, _ := client.Create(context.Background(), connect.NewRequest(&pirpcv1.CreateRequest{
		Provider: "openai-codex",
		Model:    "gpt-5.4",
		Cwd:      t.TempDir(),
	}))

	stateResp, err := client.GetState(context.Background(), connect.NewRequest(&pirpcv1.GetStateRequest{
		SessionId: createResp.Msg.SessionId,
	}))
	if err != nil {
		t.Fatalf("GetState failed: %v", err)
	}
	if stateResp.Msg.State != pirpcv1.SessionState_SESSION_STATE_IDLE {
		t.Errorf("state = %v, want IDLE", stateResp.Msg.State)
	}
	if stateResp.Msg.Provider != "openai-codex" {
		t.Errorf("provider = %q, want %q", stateResp.Msg.Provider, "openai-codex")
	}
}

func TestHandlerGetStateNotFound(t *testing.T) {
	client, cleanup := setupTestServer(t)
	defer cleanup()

	_, err := client.GetState(context.Background(), connect.NewRequest(&pirpcv1.GetStateRequest{
		SessionId: "nonexistent",
	}))
	if err == nil {
		t.Error("GetState for nonexistent session should fail")
	}
	if connect.CodeOf(err) != connect.CodeNotFound {
		t.Errorf("error code = %v, want NotFound", connect.CodeOf(err))
	}
}

func TestHandlerCreateRejectsFailingSubprocess(t *testing.T) {
	t.Setenv("FAKE_PI_SCENARIO", "fail_start")

	client, cleanup := setupTestServerWithBinary(t, fakePi(t))
	defer cleanup()

	_, err := client.Create(context.Background(), connect.NewRequest(&pirpcv1.CreateRequest{
		Provider: "openai-codex",
		Model:    "gpt-5.4",
		Cwd:      t.TempDir(),
	}))
	if err == nil {
		t.Fatal("Create should fail when subprocess exits immediately with an error")
	}
	if !strings.Contains(err.Error(), "No API key found for openai") {
		t.Fatalf("Create error = %q, want captured stderr", err)
	}
}

func TestHandlerPromptAsyncNotFound(t *testing.T) {
	client, cleanup := setupTestServer(t)
	defer cleanup()

	_, err := client.PromptAsync(context.Background(), connect.NewRequest(&pirpcv1.PromptAsyncRequest{
		SessionId: "nonexistent",
		Message:   "hello",
	}))
	if err == nil {
		t.Error("PromptAsync for nonexistent session should fail")
	}
	if connect.CodeOf(err) != connect.CodeNotFound {
		t.Errorf("error code = %v, want NotFound", connect.CodeOf(err))
	}
}

func TestHandlerPromptAsyncSendsToSession(t *testing.T) {
	client, cleanup := setupTestServer(t)
	defer cleanup()

	createResp, err := client.Create(context.Background(), connect.NewRequest(&pirpcv1.CreateRequest{
		Provider: "openai-codex",
		Model:    "gpt-5.4",
		Cwd:      t.TempDir(),
	}))
	if err != nil {
		t.Fatalf("Create failed: %v", err)
	}

	_, err = client.PromptAsync(context.Background(), connect.NewRequest(&pirpcv1.PromptAsyncRequest{
		SessionId: createResp.Msg.SessionId,
		Message:   "hello",
	}))
	if err != nil {
		t.Fatalf("PromptAsync failed: %v", err)
	}
}

func TestHandlerGetMessagesNotFound(t *testing.T) {
	client, cleanup := setupTestServer(t)
	defer cleanup()

	_, err := client.GetMessages(context.Background(), connect.NewRequest(&pirpcv1.GetMessagesRequest{
		SessionId: "nonexistent",
	}))
	if err == nil {
		t.Error("GetMessages for nonexistent session should fail")
	}
	if connect.CodeOf(err) != connect.CodeNotFound {
		t.Errorf("error code = %v, want NotFound", connect.CodeOf(err))
	}
}

func TestHandlerGetMessagesCollectsEvents(t *testing.T) {
	t.Setenv("FAKE_PI_SCENARIO", "echo")

	client, cleanup := setupTestServerWithBinary(t, fakePi(t))
	defer cleanup()

	createResp, err := client.Create(context.Background(), connect.NewRequest(&pirpcv1.CreateRequest{
		Provider: "openai-codex",
		Model:    "gpt-5.4",
		Cwd:      t.TempDir(),
	}))
	if err != nil {
		t.Fatalf("Create failed: %v", err)
	}

	_, err = client.PromptAsync(context.Background(), connect.NewRequest(&pirpcv1.PromptAsyncRequest{
		SessionId: createResp.Msg.SessionId,
		Message:   "hello",
	}))
	if err != nil {
		t.Fatalf("PromptAsync failed: %v", err)
	}

	// Poll until message_update events are buffered
	var resp *connect.Response[pirpcv1.GetMessagesResponse]
	for i := 0; i < 50; i++ {
		resp, err = client.GetMessages(context.Background(), connect.NewRequest(&pirpcv1.GetMessagesRequest{
			SessionId: createResp.Msg.SessionId,
		}))
		if err == nil && len(resp.Msg.Messages) > 0 {
			break
		}
		// 50ms pause
		func() {
			ctx, cancel := context.WithTimeout(context.Background(), 50*1e6)
			defer cancel()
			<-ctx.Done()
		}()
	}

	if err != nil {
		t.Fatalf("GetMessages failed: %v", err)
	}
	if len(resp.Msg.Messages) == 0 {
		t.Fatal("GetMessages returned no messages, expected at least 1")
	}
	msg := resp.Msg.Messages[0]
	if msg.Role != pirpcv1.MessageRole_MESSAGE_ROLE_ASSISTANT {
		t.Errorf("message role = %v, want ASSISTANT", msg.Role)
	}
	if msg.TimestampMs == 0 {
		t.Error("message timestamp should be non-zero")
	}
}

func TestHandlerGetMessagesEmptyWhenNoMessageEvents(t *testing.T) {
	client, cleanup := setupTestServer(t)
	defer cleanup()

	createResp, err := client.Create(context.Background(), connect.NewRequest(&pirpcv1.CreateRequest{
		Provider: "openai-codex",
		Model:    "gpt-5.4",
		Cwd:      t.TempDir(),
	}))
	if err != nil {
		t.Fatalf("Create failed: %v", err)
	}

	resp, err := client.GetMessages(context.Background(), connect.NewRequest(&pirpcv1.GetMessagesRequest{
		SessionId: createResp.Msg.SessionId,
	}))
	if err != nil {
		t.Fatalf("GetMessages failed: %v", err)
	}
	if len(resp.Msg.Messages) != 0 {
		t.Errorf("GetMessages returned %d messages, want 0", len(resp.Msg.Messages))
	}
}
