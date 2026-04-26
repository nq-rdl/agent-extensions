package session

import (
	"context"
	"fmt"
	"sync"
	"time"
)

// SessionSummary is a lightweight view of a session for listing.
type SessionSummary struct {
	ID        string
	State     State
	Provider  string
	Model     string
	CreatedAt time.Time
}

// Manager manages a set of sessions with concurrent-safe access.
type Manager struct {
	mu       sync.RWMutex
	sessions map[string]*Session
	binary   string // path to pi binary
}

// NewManager creates a session manager that spawns subprocesses using the given binary.
func NewManager(binary string) *Manager {
	if binary == "" {
		binary = "pi"
	}
	return &Manager{
		sessions: make(map[string]*Session),
		binary:   binary,
	}
}

// CreateOpts bundles the parameters for Manager.Create.
type CreateOpts struct {
	Provider            string
	Model               string
	Cwd                 string
	ThinkingLevel       string
	TimeoutSeconds      int32
	SystemPrompt        string
	AppendSystemPrompts []string
}

// Create spawns a new session subprocess and adds it to the manager.
func (m *Manager) Create(ctx context.Context, opts CreateOpts) (string, error) {
	sessionCtx := context.Background()
	if ctx != nil {
		sessionCtx = context.WithoutCancel(ctx)
	}

	args := []string{}
	// Only add pi-specific flags when using the real pi binary
	if m.binary == "pi" {
		args = append(args, "--mode", "rpc", "--no-session",
			"--provider", opts.Provider, "--model", opts.Model)
		if opts.ThinkingLevel != "" {
			args = append(args, "--thinking", opts.ThinkingLevel)
		}
	}

	// System-prompt flags are forwarded unconditionally (outside the binary guard)
	// so that fake-pi can capture them in tests via the capture_args scenario.
	if opts.SystemPrompt != "" {
		args = append(args, "--system-prompt", opts.SystemPrompt)
	}
	for _, s := range opts.AppendSystemPrompts {
		args = append(args, "--append-system-prompt", s)
	}

	s, err := NewSession(sessionCtx, Config{
		Binary:            m.binary,
		Args:              args,
		Provider:          opts.Provider,
		Model:             opts.Model,
		Cwd:               opts.Cwd,
		ThinkingLevel:     opts.ThinkingLevel,
		InactivityTimeout: time.Duration(opts.TimeoutSeconds) * time.Second,
	})
	if err != nil {
		return "", err
	}

	// Fast startup check: if the subprocess exits within 200ms (e.g.
	// invalid provider/model, missing API key), return the error
	// immediately instead of handing back a dead session.
	select {
	case <-s.waitDone:
		if msg := s.ErrorMessage(); msg != "" {
			return "", fmt.Errorf("session startup failed: %s", msg)
		}
		return "", fmt.Errorf("session exited immediately (provider=%s, model=%s)", opts.Provider, opts.Model)
	case <-time.After(200 * time.Millisecond):
		// Subprocess still alive — good.
	}

	m.mu.Lock()
	m.sessions[s.ID()] = s
	m.mu.Unlock()

	return s.ID(), nil
}

// Get returns a session by ID.
func (m *Manager) Get(id string) (*Session, bool) {
	m.mu.RLock()
	defer m.mu.RUnlock()
	s, ok := m.sessions[id]
	return s, ok
}

// Delete closes a session and removes it from the manager.
func (m *Manager) Delete(id string) error {
	m.mu.Lock()
	s, ok := m.sessions[id]
	if !ok {
		m.mu.Unlock()
		return ErrSessionNotFound
	}
	delete(m.sessions, id)
	m.mu.Unlock()

	return s.Close()
}

// List returns summaries of all active sessions.
func (m *Manager) List() []SessionSummary {
	m.mu.RLock()
	defer m.mu.RUnlock()

	summaries := make([]SessionSummary, 0, len(m.sessions))
	for _, s := range m.sessions {
		summaries = append(summaries, SessionSummary{
			ID:        s.ID(),
			State:     s.State(),
			Provider:  s.Provider(),
			Model:     s.Model(),
			CreatedAt: s.CreatedAt(),
		})
	}
	return summaries
}

// GracefulShutdown closes all sessions.
func (m *Manager) GracefulShutdown() {
	m.mu.Lock()
	defer m.mu.Unlock()

	for id, s := range m.sessions {
		s.Close()
		delete(m.sessions, id)
	}
}
