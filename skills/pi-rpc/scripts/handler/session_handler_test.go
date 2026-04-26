package handler

import (
	"context"
	"net/http"
	"net/http/httptest"
	"os"
	"path/filepath"
	"runtime"
	"strings"
	"testing"
	"time"

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
	return setupTestServerWithDefaults(t, binary, Defaults{})
}

func setupTestServerWithDefaults(t *testing.T, binary string, defaults Defaults) (pirpcv1connect.SessionServiceClient, func()) {
	t.Helper()

	mgr := session.NewManager(binary)
	h := NewSessionHandler(mgr, defaults)

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

func TestHandlerCreateRejectsNegativeTimeout(t *testing.T) {
	client, cleanup := setupTestServer(t)
	defer cleanup()

	_, err := client.Create(context.Background(), connect.NewRequest(&pirpcv1.CreateRequest{
		Provider:       "openai-codex",
		Model:          "gpt-5.4",
		Cwd:            t.TempDir(),
		TimeoutSeconds: -1,
	}))
	if err == nil {
		t.Fatal("Create with negative timeout should fail")
	}
	if connect.CodeOf(err) != connect.CodeInvalidArgument {
		t.Errorf("error code = %v, want InvalidArgument", connect.CodeOf(err))
	}
}

func TestHandlerCreateAppliesDefaults(t *testing.T) {
	client, cleanup := setupTestServerWithDefaults(t, fakePi(t), Defaults{
		Provider: "default-provider",
		Model:    "default-model",
	})
	defer cleanup()

	// Create with empty provider/model — should apply defaults
	createResp, err := client.Create(context.Background(), connect.NewRequest(&pirpcv1.CreateRequest{
		Cwd: t.TempDir(),
	}))
	if err != nil {
		t.Fatalf("Create with defaults failed: %v", err)
	}

	stateResp, err := client.GetState(context.Background(), connect.NewRequest(&pirpcv1.GetStateRequest{
		SessionId: createResp.Msg.SessionId,
	}))
	if err != nil {
		t.Fatalf("GetState failed: %v", err)
	}
	if stateResp.Msg.Provider != "default-provider" {
		t.Errorf("provider = %q, want %q", stateResp.Msg.Provider, "default-provider")
	}
	if stateResp.Msg.Model != "default-model" {
		t.Errorf("model = %q, want %q", stateResp.Msg.Model, "default-model")
	}
}

func TestHandlerCreateExplicitOverridesDefaults(t *testing.T) {
	client, cleanup := setupTestServerWithDefaults(t, fakePi(t), Defaults{
		Provider: "default-provider",
		Model:    "default-model",
	})
	defer cleanup()

	// Create with explicit values — should override defaults
	createResp, err := client.Create(context.Background(), connect.NewRequest(&pirpcv1.CreateRequest{
		Provider: "explicit-provider",
		Model:    "explicit-model",
		Cwd:      t.TempDir(),
	}))
	if err != nil {
		t.Fatalf("Create with explicit values failed: %v", err)
	}

	stateResp, err := client.GetState(context.Background(), connect.NewRequest(&pirpcv1.GetStateRequest{
		SessionId: createResp.Msg.SessionId,
	}))
	if err != nil {
		t.Fatalf("GetState failed: %v", err)
	}
	if stateResp.Msg.Provider != "explicit-provider" {
		t.Errorf("provider = %q, want %q", stateResp.Msg.Provider, "explicit-provider")
	}
	if stateResp.Msg.Model != "explicit-model" {
		t.Errorf("model = %q, want %q", stateResp.Msg.Model, "explicit-model")
	}
}

// TestHandlerPromptReturnsMessages tests both bugs from issue #80:
//
//  1. Prompt must populate PromptResponse.Messages (bug 1: currently always empty).
//  2. GetMessages must parse the real pi --mode rpc wire format, where the message
//     is nested under a "message" key, not at the top level (bug 2: flat-struct
//     parser silently produces empty fields and the empty-skip drops every message).
//
// The real_shape fake-pi scenario emits event shapes that exactly match the upstream
// AgentEvent union (packages/agent/src/types.ts):
//
//	message_update: {"type":"message_update","message":{...AgentMessage...},"assistantMessageEvent":{...}}
//	message_end:    {"type":"message_end","message":{...AgentMessage...}}
//	agent_end:      {"type":"agent_end","messages":[...AgentMessage...]}
func TestHandlerPromptReturnsMessages(t *testing.T) {
	// Arrange
	t.Setenv("FAKE_PI_SCENARIO", "real_shape")
	client, cleanup := setupTestServerWithBinary(t, fakePi(t))
	defer cleanup()

	createResp, err := client.Create(context.Background(), connect.NewRequest(&pirpcv1.CreateRequest{
		Provider: "anthropic",
		Model:    "claude-sonnet-4-5",
		Cwd:      t.TempDir(),
	}))
	if err != nil {
		t.Fatalf("Create failed: %v", err)
	}
	sid := createResp.Msg.SessionId

	// Act — synchronous Prompt waits for agent_end before returning
	promptResp, err := client.Prompt(context.Background(), connect.NewRequest(&pirpcv1.PromptRequest{
		SessionId: sid,
		Message:   "hello",
	}))
	if err != nil {
		t.Fatalf("Prompt failed: %v", err)
	}

	// Assert bug 1: PromptResponse.Messages must be populated
	if len(promptResp.Msg.Messages) == 0 {
		t.Fatal("bug 1: PromptResponse.Messages is empty; Prompt handler never populates messages")
	}
	gotRole := promptResp.Msg.Messages[0].Role
	if gotRole != pirpcv1.MessageRole_MESSAGE_ROLE_ASSISTANT {
		t.Errorf("bug 1: first message role = %v, want ASSISTANT", gotRole)
	}
	if promptResp.Msg.Messages[0].Content == "" {
		t.Error("bug 1: first message content is empty")
	}

	// Assert bug 2: GetMessages must parse the nested message shape
	msgsResp, err := client.GetMessages(context.Background(), connect.NewRequest(&pirpcv1.GetMessagesRequest{
		SessionId: sid,
	}))
	if err != nil {
		t.Fatalf("GetMessages failed: %v", err)
	}
	if len(msgsResp.Msg.Messages) == 0 {
		t.Fatal("bug 2: GetMessages returned no messages; nested message shape not parsed")
	}
	if msgsResp.Msg.Messages[0].Content == "" {
		t.Error("bug 2: GetMessages first message content is empty; text not extracted from nested content array")
	}
}

func TestHandlerCreateForwardsSystemPrompts(t *testing.T) {
	// Arrange: capture_args scenario writes argv to FAKE_PI_ARGS_FILE
	argsFile := filepath.Join(t.TempDir(), "pi-args.txt")
	t.Setenv("FAKE_PI_ARGS_FILE", argsFile)
	t.Setenv("FAKE_PI_SCENARIO", "capture_args")

	client, cleanup := setupTestServer(t)
	defer cleanup()

	// Act: create a session with system-prompt fields set
	_, err := client.Create(context.Background(), connect.NewRequest(&pirpcv1.CreateRequest{
		Provider:           "anthropic",
		Model:              "claude-sonnet",
		Cwd:                t.TempDir(),
		SystemPrompt:       "You are a SQL reviewer.",
		AppendSystemPrompt: []string{"Use modern SQL.", "Cite sources."},
	}))
	if err != nil {
		t.Fatalf("Create failed: %v", err)
	}

	// Assert: wait up to 2s for the subprocess to write the args file.
	// Generous deadline to avoid CI flakiness under -race / cold caches.
	// Args are null-byte separated so values containing newlines round-trip.
	var argv []string
	deadline := time.Now().Add(2 * time.Second)
	for time.Now().Before(deadline) {
		data, readErr := os.ReadFile(argsFile)
		if readErr == nil && len(data) > 0 {
			for _, arg := range strings.Split(string(data), "\x00") {
				if arg != "" {
					argv = append(argv, arg)
				}
			}
			break
		}
		time.Sleep(20 * time.Millisecond)
	}

	if len(argv) == 0 {
		t.Fatal("args file was not written by fake-pi subprocess; subprocess may not have received the flags")
	}

	// --system-prompt must appear as a consecutive pair
	assertArgPair(t, argv, "--system-prompt", "You are a SQL reviewer.")

	// Each --append-system-prompt entry must appear in order
	assertArgPair(t, argv, "--append-system-prompt", "Use modern SQL.")
	assertArgPair(t, argv, "--append-system-prompt", "Cite sources.")
}

// assertArgPair checks that flag and value appear consecutively in argv.
func assertArgPair(t *testing.T, argv []string, flag, value string) {
	t.Helper()
	for i := 0; i < len(argv)-1; i++ {
		if argv[i] == flag && argv[i+1] == value {
			return
		}
	}
	t.Errorf("argv does not contain consecutive pair %q %q\nfull argv: %v", flag, value, argv)
}
