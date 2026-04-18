// Package acp manages persistent ACP (Agent Communication Protocol) sessions
// with the Gemini CLI. Each named session is a long-lived `gemini --acp`
// subprocess that speaks JSON-RPC 2.0 over stdin/stdout.
//
// Concurrency model
//
//   - sessions registry: guarded by sessionsMu (RWMutex)
//   - per-session mu (Mutex): guards stdin writes and chunks slice
//   - pending map: sync.Map[int64, chan<- message] — reader goroutine delivers
//     responses without holding mu
//   - reader goroutine: context-propagated bufio.Scanner; exits cleanly on
//     process exit or ctx cancellation
//
// The reader goroutine processes messages sequentially (one line at a time)
// so all session/update notifications that precede a session/prompt response
// in the stream are guaranteed to be appended to chunks before the response
// channel fires.
package acp

import (
	"bufio"
	"context"
	"crypto/rand"
	"encoding/hex"
	"encoding/json"
	"fmt"
	"os"
	"os/exec"
	"path/filepath"
	"sync"
	"sync/atomic"
)

// rpcMessage is a union of JSON-RPC response and notification.
type rpcMessage struct {
	JSONRPC string          `json:"jsonrpc"`
	ID      *int64          `json:"id,omitempty"`
	Method  string          `json:"method,omitempty"`
	Params  json.RawMessage `json:"params,omitempty"`
	Result  json.RawMessage `json:"result,omitempty"`
	Error   *rpcError       `json:"error,omitempty"`
}

type rpcError struct {
	Code    int    `json:"code"`
	Message string `json:"message"`
}

type session struct {
	cmd       *exec.Cmd
	stdin     *os.File // unused — we use the pipe below
	stdinPipe interface{ Write([]byte) (int, error) }

	mu        sync.Mutex // guards stdinPipe writes and chunks
	chunks    []string
	nextID    atomic.Int64
	pending   sync.Map // map[int64]chan rpcMessage

	sessionID  string
	turn       int
	model      string
	contextDir string
}

var (
	sessionsMu sync.RWMutex
	sessions   = map[string]*session{}
)

// Options for creating or locating a named ACP session.
type Options struct {
	Model         string
	SystemContext string
	CWD           string
}

// AskResult is returned by Ask.
type AskResult struct {
	Answer    string `json:"answer"`
	SessionID string `json:"session_id"`
	Turn      int    `json:"turn"`
	Usage     any    `json:"usage"`
}

// Ask sends a prompt to a named persistent session, creating it on first call.
func Ask(ctx context.Context, question string, opts Options, sessionName string, extraContext string) (*AskResult, error) {
	s, err := getOrCreate(ctx, sessionName, opts)
	if err != nil {
		return nil, err
	}

	prompt := question
	if extraContext != "" {
		prompt = extraContext + "\n\n" + question
	}

	// Clear chunks for this turn under mu, then write the request
	s.mu.Lock()
	s.chunks = s.chunks[:0]
	s.mu.Unlock()

	resp, err := s.sendRequest(ctx, "session/prompt", map[string]any{
		"sessionId": s.sessionID,
		"prompt":    prompt,
	})
	if err != nil {
		return nil, fmt.Errorf("ACP prompt: %w", err)
	}
	if resp.Error != nil {
		return nil, fmt.Errorf("ACP prompt failed: %s", resp.Error.Message)
	}

	// All session/update notifications before this response have been accumulated
	s.mu.Lock()
	answer := join(s.chunks)
	s.mu.Unlock()

	s.turn++

	var usage any
	if len(resp.Result) > 0 {
		var r struct {
			Usage any `json:"usage"`
		}
		json.Unmarshal(resp.Result, &r) //nolint:errcheck
		usage = r.Usage
	}

	return &AskResult{
		Answer:    answer,
		SessionID: s.sessionID,
		Turn:      s.turn,
		Usage:     usage,
	}, nil
}

// SessionInfo returns lightweight session info for inspection.
func SessionInfo(name string) (sessionID string, turn int, ok bool) {
	sessionsMu.RLock()
	s, exists := sessions[name]
	sessionsMu.RUnlock()
	if !exists {
		return "", 0, false
	}
	return s.sessionID, s.turn, true
}

// ShutdownAll terminates all active ACP sessions.
func ShutdownAll() {
	sessionsMu.Lock()
	all := make([]*session, 0, len(sessions))
	for name, s := range sessions {
		all = append(all, s)
		delete(sessions, name)
	}
	sessionsMu.Unlock()

	for _, s := range all {
		s.cmd.Process.Signal(os.Interrupt) //nolint:errcheck
		if s.contextDir != "" {
			os.RemoveAll(s.contextDir)
		}
	}
}

// getOrCreate returns an existing session or spawns a new one.
func getOrCreate(ctx context.Context, name string, opts Options) (*session, error) {
	sessionsMu.RLock()
	s, ok := sessions[name]
	sessionsMu.RUnlock()
	if ok {
		return s, nil
	}

	s, err := spawn(ctx, name, opts)
	if err != nil {
		return nil, err
	}
	return s, nil
}

func spawn(ctx context.Context, name string, opts Options) (*session, error) {
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
	model = resolveModel(model)

	args := []string{"--acp", "--model", model, "--yolo"}

	var contextDir string
	if opts.SystemContext != "" {
		var err error
		contextDir, err = writeSystemContext(opts.SystemContext)
		if err != nil {
			return nil, fmt.Errorf("writing system context: %w", err)
		}
		args = append(args, "--include-directories", contextDir)
	}

	cwd := opts.CWD
	if cwd == "" {
		cwd, _ = os.Getwd()
	}

	cmd := exec.CommandContext(ctx, binary, args...)
	cmd.Dir = cwd
	cmd.Env = os.Environ()

	stdinPipe, err := cmd.StdinPipe()
	if err != nil {
		return nil, fmt.Errorf("creating stdin pipe: %w", err)
	}
	stdoutPipe, err := cmd.StdoutPipe()
	if err != nil {
		return nil, fmt.Errorf("creating stdout pipe: %w", err)
	}
	// Discard stderr — Gemini CLI writes status/progress there
	cmd.Stderr = nil

	if err := cmd.Start(); err != nil {
		if contextDir != "" {
			os.RemoveAll(contextDir)
		}
		return nil, fmt.Errorf("starting gemini --acp: %w", err)
	}

	s := &session{
		cmd:        cmd,
		stdinPipe:  stdinPipe,
		model:      model,
		contextDir: contextDir,
	}

	// Register before starting reader so cleanup on failure can deregister
	sessionsMu.Lock()
	sessions[name] = s
	sessionsMu.Unlock()

	// Reader goroutine: processes stdout line by line until the process exits
	go func() {
		scanner := bufio.NewScanner(stdoutPipe)
		for scanner.Scan() {
			s.handleLine(scanner.Text())
		}
		// Process exited — reject all pending requests
		s.pending.Range(func(key, val any) bool {
			ch, _ := val.(chan rpcMessage)
			ch <- rpcMessage{Error: &rpcError{Code: -32000, Message: "ACP subprocess exited"}}
			s.pending.Delete(key)
			return true
		})
		// Deregister session
		sessionsMu.Lock()
		if sessions[name] == s {
			delete(sessions, name)
		}
		sessionsMu.Unlock()
		if s.contextDir != "" {
			os.RemoveAll(s.contextDir)
		}
	}()

	// Handshake: initialize
	initResp, err := s.sendRequest(ctx, "initialize", map[string]any{"clientCapabilities": map[string]any{}})
	if err != nil {
		cmd.Process.Kill()
		return nil, fmt.Errorf("ACP initialize: %w", err)
	}
	if initResp.Error != nil {
		cmd.Process.Kill()
		return nil, fmt.Errorf("ACP initialize failed: %s", initResp.Error.Message)
	}

	// Handshake: session/new
	newResp, err := s.sendRequest(ctx, "session/new", map[string]any{"cwd": cwd})
	if err != nil {
		cmd.Process.Kill()
		return nil, fmt.Errorf("ACP session/new: %w", err)
	}
	if newResp.Error != nil {
		cmd.Process.Kill()
		return nil, fmt.Errorf("ACP session/new failed: %s", newResp.Error.Message)
	}

	var newResult struct {
		SessionID string `json:"sessionId"`
	}
	if err := json.Unmarshal(newResp.Result, &newResult); err != nil {
		cmd.Process.Kill()
		return nil, fmt.Errorf("ACP session/new: parsing result: %w", err)
	}
	s.sessionID = newResult.SessionID

	return s, nil
}

// sendRequest sends a JSON-RPC request and waits for the response.
// The per-session mu guards the stdin write; pending uses sync.Map.
func (s *session) sendRequest(ctx context.Context, method string, params any) (rpcMessage, error) {
	id := s.nextID.Add(1)

	req := map[string]any{
		"jsonrpc": "2.0",
		"id":      id,
		"method":  method,
		"params":  params,
	}
	encoded, err := json.Marshal(req)
	if err != nil {
		return rpcMessage{}, err
	}

	ch := make(chan rpcMessage, 1)
	s.pending.Store(id, ch)

	s.mu.Lock()
	_, writeErr := fmt.Fprintf(s.stdinPipe, "%s\n", encoded)
	s.mu.Unlock()

	if writeErr != nil {
		s.pending.Delete(id)
		return rpcMessage{}, fmt.Errorf("writing to ACP stdin: %w", writeErr)
	}

	select {
	case msg := <-ch:
		return msg, nil
	case <-ctx.Done():
		s.pending.Delete(id)
		return rpcMessage{}, ctx.Err()
	}
}

// handleLine processes one stdout line from the ACP subprocess.
func (s *session) handleLine(line string) {
	if line == "" {
		return
	}

	var msg rpcMessage
	if err := json.Unmarshal([]byte(line), &msg); err != nil {
		return // skip non-JSON lines (stderr leaking through, etc.)
	}

	// Notification (no id): accumulate text chunks
	if msg.ID == nil && msg.Method != "" {
		if msg.Method == "session/update" {
			var p struct {
				Update struct {
					Text string `json:"text"`
				} `json:"update"`
			}
			if json.Unmarshal(msg.Params, &p) == nil && p.Update.Text != "" {
				s.mu.Lock()
				s.chunks = append(s.chunks, p.Update.Text)
				s.mu.Unlock()
			}
		}
		return
	}

	// Response (has id): deliver to pending channel
	if msg.ID != nil {
		if val, ok := s.pending.LoadAndDelete(*msg.ID); ok {
			ch, _ := val.(chan rpcMessage)
			ch <- msg
		}
	}
}

func resolveModel(m string) string {
	aliases := map[string]string{
		"fast":    "gemini-3-flash-preview",
		"quality": "gemini-3.1-pro-preview",
	}
	if v, ok := aliases[m]; ok {
		return v
	}
	return m
}

func writeSystemContext(content string) (string, error) {
	b := make([]byte, 8)
	rand.Read(b) //nolint:errcheck
	dir := filepath.Join(os.TempDir(), "gemini-acp-"+hex.EncodeToString(b))
	if err := os.MkdirAll(dir, 0o700); err != nil {
		return "", err
	}
	if err := os.WriteFile(filepath.Join(dir, "GEMINI.md"), []byte(content), 0o600); err != nil {
		os.RemoveAll(dir)
		return "", err
	}
	return dir, nil
}

func join(ss []string) string {
	total := 0
	for _, s := range ss {
		total += len(s)
	}
	b := make([]byte, 0, total)
	for _, s := range ss {
		b = append(b, s...)
	}
	return string(b)
}
