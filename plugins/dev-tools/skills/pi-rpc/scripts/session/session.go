package session

import (
	"bufio"
	"context"
	"encoding/json"
	"errors"
	"fmt"
	"io"
	"os/exec"
	"strings"
	"sync"
	"time"

	"github.com/google/uuid"
)

var (
	ErrSessionClosed   = errors.New("session is closed")
	ErrSessionNotFound = errors.New("session not found")
)

// State represents the lifecycle state of a session.
type State int

const (
	StateCreating   State = iota
	StateIdle             // subprocess alive, ready for prompts
	StateRunning          // agent processing a prompt
	StateError            // subprocess or agent error
	StateTerminated       // subprocess killed, resources freed
)

func (s State) String() string {
	switch s {
	case StateCreating:
		return "CREATING"
	case StateIdle:
		return "IDLE"
	case StateRunning:
		return "RUNNING"
	case StateError:
		return "ERROR"
	case StateTerminated:
		return "TERMINATED"
	default:
		return "UNKNOWN"
	}
}

// Event is a parsed JSONL event from the pi.dev subprocess stdout.
type Event struct {
	Type      string          `json:"type"`
	Timestamp time.Time       `json:"-"`
	Raw       json.RawMessage `json:"-"`
}

// DefaultInactivityTimeout is the maximum time a session can stay in
// StateRunning without any events before being marked as errored.
const DefaultInactivityTimeout = 60 * time.Second

// Config holds the parameters for creating a new session.
type Config struct {
	Binary        string // path to pi binary (default: "pi")
	Args          []string
	Provider      string
	Model         string
	Cwd           string
	ThinkingLevel string

	// InactivityTimeout is the maximum time a session can remain in
	// StateRunning with no stdout/stderr activity before being killed.
	// Zero means DefaultInactivityTimeout.
	InactivityTimeout time.Duration
}

// Session wraps a single pi.dev subprocess and its I/O.
type Session struct {
	id        string
	provider  string
	model     string
	cwd       string
	pid       int
	createdAt time.Time

	cmd               *exec.Cmd
	stdin             io.WriteCloser
	stdout            io.ReadCloser
	stderr            io.ReadCloser
	waitDone          chan struct{}
	readers           sync.WaitGroup
	inactivityTimeout time.Duration

	mu           sync.RWMutex
	state        State
	events       []Event
	lastActivity time.Time
	errorMsg     string
	closed       bool
}

// NewSession spawns a subprocess and returns a Session managing it.
func NewSession(ctx context.Context, cfg Config) (*Session, error) {
	binary := cfg.Binary
	if binary == "" {
		binary = "pi"
	}

	cmd := exec.CommandContext(ctx, binary, cfg.Args...)
	if cfg.Cwd != "" {
		cmd.Dir = cfg.Cwd
	}

	stdin, err := cmd.StdinPipe()
	if err != nil {
		return nil, err
	}

	stdout, err := cmd.StdoutPipe()
	if err != nil {
		return nil, err
	}

	stderr, err := cmd.StderrPipe()
	if err != nil {
		return nil, err
	}

	if err := cmd.Start(); err != nil {
		return nil, err
	}

	timeout := cfg.InactivityTimeout
	if timeout == 0 {
		timeout = DefaultInactivityTimeout
	}

	now := time.Now()
	s := &Session{
		id:                uuid.New().String(),
		provider:          cfg.Provider,
		model:             cfg.Model,
		cwd:               cfg.Cwd,
		pid:               cmd.Process.Pid,
		createdAt:         now,
		cmd:               cmd,
		stdin:             stdin,
		stdout:            stdout,
		stderr:            stderr,
		waitDone:          make(chan struct{}),
		inactivityTimeout: timeout,
		state:             StateIdle,
		events:            make([]Event, 0, 64),
		lastActivity:      now,
	}

	s.readers.Add(2)
	go s.readEvents()
	go s.readStderr()
	go s.waitForExit()
	go s.monitorInactivity()

	return s, nil
}

// readEvents reads JSONL from stdout and buffers parsed events.
func (s *Session) readEvents() {
	defer s.readers.Done()

	scanner := bufio.NewScanner(s.stdout)
	// Increase buffer for large tool outputs
	scanner.Buffer(make([]byte, 0, 1024*1024), 10*1024*1024)

	for scanner.Scan() {
		line := scanner.Bytes()
		if len(line) == 0 {
			continue
		}

		var evt Event
		if err := json.Unmarshal(line, &evt); err != nil {
			continue
		}
		evt.Timestamp = time.Now()
		evt.Raw = make(json.RawMessage, len(line))
		copy(evt.Raw, line)

		s.mu.Lock()
		s.events = append(s.events, evt)
		s.lastActivity = evt.Timestamp

		switch evt.Type {
		case "agent_start":
			s.state = StateRunning
		case "agent_end":
			s.state = StateIdle
		}
		s.mu.Unlock()
	}

	if err := scanner.Err(); err != nil {
		s.appendErrorMessage(err.Error())
	}
}

func (s *Session) readStderr() {
	defer s.readers.Done()

	scanner := bufio.NewScanner(s.stderr)
	scanner.Buffer(make([]byte, 0, 64*1024), 1024*1024)

	for scanner.Scan() {
		s.appendErrorMessage(scanner.Text())
	}

	if err := scanner.Err(); err != nil {
		s.appendErrorMessage(err.Error())
	}
}

func (s *Session) waitForExit() {
	err := s.cmd.Wait()
	s.readers.Wait()

	s.mu.Lock()
	defer s.mu.Unlock()
	defer close(s.waitDone)

	if s.closed {
		s.state = StateTerminated
		return
	}

	if err != nil {
		s.state = StateError
		if s.errorMsg == "" {
			s.errorMsg = err.Error()
		}
		return
	}

	s.state = StateTerminated
}

// monitorInactivity periodically checks whether a running session has
// stalled (no stdout/stderr activity for longer than the configured timeout).
// When triggered it sets StateError with a descriptive message and kills
// the subprocess so callers get a clear failure instead of hanging forever.
func (s *Session) monitorInactivity() {
	const checkInterval = 5 * time.Second
	ticker := time.NewTicker(checkInterval)
	defer ticker.Stop()

	for {
		select {
		case <-s.waitDone:
			return
		case <-ticker.C:
			s.mu.RLock()
			state := s.state
			last := s.lastActivity
			closed := s.closed
			s.mu.RUnlock()

			if closed || state == StateTerminated || state == StateError {
				return
			}

			if state == StateRunning && time.Since(last) > s.inactivityTimeout {
				s.mu.Lock()
				if s.state == StateRunning {
					s.state = StateError
					timeoutMsg := fmt.Sprintf(
						"session killed: no activity for %s (provider=%s, model=%s)",
						s.inactivityTimeout, s.provider, s.model,
					)
					if s.errorMsg == "" {
						s.errorMsg = timeoutMsg
					} else {
						s.errorMsg = s.errorMsg + "\n" + timeoutMsg
					}
				}
				s.mu.Unlock()

				// Kill the subprocess to unblock waitForExit.
				if s.cmd.Process != nil {
					_ = s.cmd.Process.Kill()
				}
				return
			}
		}
	}
}

func (s *Session) appendErrorMessage(msg string) {
	msg = strings.TrimSpace(msg)
	if msg == "" {
		return
	}

	s.mu.Lock()
	defer s.mu.Unlock()

	if s.errorMsg == "" {
		s.errorMsg = msg
	} else {
		s.errorMsg += "\n" + msg
	}
	s.lastActivity = time.Now()
}

func (s *Session) ID() string           { return s.id }
func (s *Session) Provider() string     { return s.provider }
func (s *Session) Model() string        { return s.model }
func (s *Session) Cwd() string          { return s.cwd }
func (s *Session) CreatedAt() time.Time { return s.createdAt }

func (s *Session) PID() int {
	if s.cmd != nil && s.cmd.Process != nil {
		return s.cmd.Process.Pid
	}
	return 0
}

func (s *Session) State() State {
	s.mu.RLock()
	defer s.mu.RUnlock()
	return s.state
}

func (s *Session) SetState(st State) {
	s.mu.Lock()
	defer s.mu.Unlock()
	s.state = st
}

func (s *Session) LastActivity() time.Time {
	s.mu.RLock()
	defer s.mu.RUnlock()
	return s.lastActivity
}

func (s *Session) ErrorMessage() string {
	s.mu.RLock()
	defer s.mu.RUnlock()
	return s.errorMsg
}

// Events returns a snapshot of all buffered events.
func (s *Session) Events() []Event {
	s.mu.RLock()
	defer s.mu.RUnlock()
	out := make([]Event, len(s.events))
	copy(out, s.events)
	return out
}

// Send writes a JSONL command to the subprocess stdin.
func (s *Session) Send(data []byte) error {
	select {
	case <-s.waitDone:
		if errorMsg := s.ErrorMessage(); errorMsg != "" {
			return errors.New(errorMsg)
		}
		if s.State() == StateTerminated {
			return ErrSessionClosed
		}
	default:
	}

	s.mu.RLock()
	state := s.state
	closed := s.closed
	errorMsg := s.errorMsg
	s.mu.RUnlock()

	if closed {
		return ErrSessionClosed
	}

	if state == StateError {
		if errorMsg != "" {
			return errors.New(errorMsg)
		}
		return errors.New("session is in error state")
	}

	if state == StateTerminated {
		if errorMsg != "" {
			return fmt.Errorf("session terminated: %s", errorMsg)
		}
		return ErrSessionClosed
	}

	// Append newline if not present
	if len(data) > 0 && data[len(data)-1] != '\n' {
		data = append(data, '\n')
	}
	_, err := s.stdin.Write(data)
	if err != nil {
		if errorMsg := s.ErrorMessage(); errorMsg != "" {
			return fmt.Errorf("%s: %w", errorMsg, err)
		}
	}
	return err
}

// Close terminates the subprocess and marks the session as terminated.
func (s *Session) Close() error {
	s.mu.Lock()
	if s.closed {
		s.mu.Unlock()
		return nil
	}
	s.closed = true
	s.state = StateTerminated
	s.mu.Unlock()

	// Close stdin to signal EOF.
	_ = s.stdin.Close()

	// Kill subprocess.
	if s.cmd.Process != nil {
		_ = s.cmd.Process.Kill()
	}

	<-s.waitDone

	return nil
}
