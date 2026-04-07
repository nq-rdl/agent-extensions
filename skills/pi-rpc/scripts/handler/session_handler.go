package handler

import (
	"context"
	"encoding/json"
	"errors"
	"fmt"
	"time"

	"connectrpc.com/connect"
	pirpcv1 "github.com/nq-rdl/agent-skills/skills/pi-rpc/scripts/gen/pirpc/v1"
	"github.com/nq-rdl/agent-skills/skills/pi-rpc/scripts/gen/pirpc/v1/pirpcv1connect"
	"github.com/nq-rdl/agent-skills/skills/pi-rpc/scripts/session"
	"google.golang.org/protobuf/types/known/timestamppb"
)

// Defaults holds fallback provider/model values applied when a CreateRequest
// omits them. Set via PI_DEFAULT_PROVIDER / PI_DEFAULT_MODEL env vars.
type Defaults struct {
	Provider string
	Model    string
}

// SessionHandler implements the ConnectRPC SessionServiceHandler interface.
type SessionHandler struct {
	mgr      *session.Manager
	defaults Defaults
}

var _ pirpcv1connect.SessionServiceHandler = (*SessionHandler)(nil)

// NewSessionHandler creates a handler backed by the given session manager.
// An optional Defaults value configures fallback provider/model.
func NewSessionHandler(mgr *session.Manager, defaults ...Defaults) *SessionHandler {
	var d Defaults
	if len(defaults) > 0 {
		d = defaults[0]
	}
	return &SessionHandler{mgr: mgr, defaults: d}
}

func (h *SessionHandler) Create(ctx context.Context, req *connect.Request[pirpcv1.CreateRequest]) (*connect.Response[pirpcv1.CreateResponse], error) {
	provider := req.Msg.Provider
	if provider == "" {
		provider = h.defaults.Provider
	}
	model := req.Msg.Model
	if model == "" {
		model = h.defaults.Model
	}
	if req.Msg.TimeoutSeconds < 0 {
		return nil, connect.NewError(connect.CodeInvalidArgument, fmt.Errorf("timeout_seconds must be non-negative, got %d", req.Msg.TimeoutSeconds))
	}
	id, err := h.mgr.Create(ctx, provider, model, req.Msg.Cwd, req.Msg.ThinkingLevel, req.Msg.TimeoutSeconds)
	if err != nil {
		return nil, connect.NewError(connect.CodeInternal, fmt.Errorf("create session: %w", err))
	}

	return connect.NewResponse(&pirpcv1.CreateResponse{
		SessionId: id,
		State:     pirpcv1.SessionState_SESSION_STATE_IDLE,
	}), nil
}

func (h *SessionHandler) Prompt(ctx context.Context, req *connect.Request[pirpcv1.PromptRequest]) (*connect.Response[pirpcv1.PromptResponse], error) {
	s, ok := h.mgr.Get(req.Msg.SessionId)
	if !ok {
		return nil, connect.NewError(connect.CodeNotFound, fmt.Errorf("session %q not found", req.Msg.SessionId))
	}

	cmd := map[string]string{"type": "prompt", "message": req.Msg.Message}
	data, _ := json.Marshal(cmd)
	if err := s.Send(data); err != nil {
		return nil, connect.NewError(connect.CodeInternal, fmt.Errorf("send prompt: %w", describeSendError(s, err)))
	}

	s.SetState(session.StateRunning)

	// Wait for agent_end or timeout
	timeout := time.After(5 * time.Minute)
	ticker := time.NewTicker(100 * time.Millisecond)
	defer ticker.Stop()

	for {
		select {
		case <-ctx.Done():
			return nil, connect.NewError(connect.CodeCanceled, ctx.Err())
		case <-timeout:
			return nil, connect.NewError(connect.CodeDeadlineExceeded, fmt.Errorf("prompt timed out after 5 minutes"))
		case <-ticker.C:
			state := s.State()
			if state == session.StateIdle || state == session.StateError || state == session.StateTerminated {
				return connect.NewResponse(&pirpcv1.PromptResponse{
					State: stateToProto(state),
				}), nil
			}
		}
	}
}

func (h *SessionHandler) PromptAsync(ctx context.Context, req *connect.Request[pirpcv1.PromptAsyncRequest]) (*connect.Response[pirpcv1.PromptAsyncResponse], error) {
	s, ok := h.mgr.Get(req.Msg.SessionId)
	if !ok {
		return nil, connect.NewError(connect.CodeNotFound, fmt.Errorf("session %q not found", req.Msg.SessionId))
	}

	cmd := map[string]string{"type": "prompt", "message": req.Msg.Message}
	data, err := json.Marshal(cmd)
	if err != nil {
		return nil, connect.NewError(connect.CodeInternal, fmt.Errorf("marshal prompt: %w", err))
	}
	if err := s.Send(data); err != nil {
		return nil, connect.NewError(connect.CodeInternal, fmt.Errorf("send prompt: %w", describeSendError(s, err)))
	}

	s.SetState(session.StateRunning)

	return connect.NewResponse(&pirpcv1.PromptAsyncResponse{}), nil
}

func (h *SessionHandler) StreamEvents(ctx context.Context, req *connect.Request[pirpcv1.StreamEventsRequest], stream *connect.ServerStream[pirpcv1.SessionEvent]) error {
	s, ok := h.mgr.Get(req.Msg.SessionId)
	if !ok {
		return connect.NewError(connect.CodeNotFound, fmt.Errorf("session %q not found", req.Msg.SessionId))
	}

	seen := 0
	ticker := time.NewTicker(200 * time.Millisecond)
	defer ticker.Stop()

	for {
		select {
		case <-ctx.Done():
			return nil
		case <-ticker.C:
			events := s.Events()
			for i := seen; i < len(events); i++ {
				evt := events[i]
				protoEvt := &pirpcv1.SessionEvent{
					SessionId: s.ID(),
					Type:      eventTypeToProto(evt.Type),
					Timestamp: timestamppb.New(evt.Timestamp),
					Data:      evt.Raw,
				}
				if err := stream.Send(protoEvt); err != nil {
					return err
				}
			}
			seen = len(events)

			// Stop streaming when session is terminal
			state := s.State()
			if state == session.StateTerminated || state == session.StateError {
				return nil
			}
		}
	}
}

func (h *SessionHandler) GetMessages(ctx context.Context, req *connect.Request[pirpcv1.GetMessagesRequest]) (*connect.Response[pirpcv1.GetMessagesResponse], error) {
	s, ok := h.mgr.Get(req.Msg.SessionId)
	if !ok {
		return nil, connect.NewError(connect.CodeNotFound, fmt.Errorf("session %q not found", req.Msg.SessionId))
	}

	// Collect messages from buffered session events.
	events := s.Events()
	var msgs []*pirpcv1.Message
	for _, evt := range events {
		if evt.Type != "message_update" {
			continue
		}
		var parsed struct {
			Role       string `json:"role"`
			Content    string `json:"content"`
			IsError    bool   `json:"is_error"`
			ToolCallID string `json:"tool_call_id"`
		}
		if err := json.Unmarshal(evt.Raw, &parsed); err != nil {
			continue
		}
		msgs = append(msgs, &pirpcv1.Message{
			Role:        messageRoleToProto(parsed.Role),
			Content:     parsed.Content,
			IsError:     parsed.IsError,
			ToolCallId:  parsed.ToolCallID,
			TimestampMs: evt.Timestamp.UnixMilli(),
		})
	}

	return connect.NewResponse(&pirpcv1.GetMessagesResponse{
		Messages: msgs,
	}), nil
}

func (h *SessionHandler) GetState(ctx context.Context, req *connect.Request[pirpcv1.GetStateRequest]) (*connect.Response[pirpcv1.GetStateResponse], error) {
	s, ok := h.mgr.Get(req.Msg.SessionId)
	if !ok {
		return nil, connect.NewError(connect.CodeNotFound, fmt.Errorf("session %q not found", req.Msg.SessionId))
	}

	return connect.NewResponse(&pirpcv1.GetStateResponse{
		SessionId:    s.ID(),
		State:        stateToProto(s.State()),
		Provider:     s.Provider(),
		Model:        s.Model(),
		Cwd:          s.Cwd(),
		Pid:          int32(s.PID()),
		CreatedAt:    timestamppb.New(s.CreatedAt()),
		LastActivity: timestamppb.New(s.LastActivity()),
		ErrorMessage: s.ErrorMessage(),
	}), nil
}

func (h *SessionHandler) Abort(ctx context.Context, req *connect.Request[pirpcv1.AbortRequest]) (*connect.Response[pirpcv1.AbortResponse], error) {
	s, ok := h.mgr.Get(req.Msg.SessionId)
	if !ok {
		return nil, connect.NewError(connect.CodeNotFound, fmt.Errorf("session %q not found", req.Msg.SessionId))
	}

	cmd := map[string]string{"type": "abort"}
	data, _ := json.Marshal(cmd)
	if err := s.Send(data); err != nil {
		if errors.Is(err, session.ErrSessionClosed) {
			return connect.NewResponse(&pirpcv1.AbortResponse{
				State: pirpcv1.SessionState_SESSION_STATE_TERMINATED,
			}), nil
		}
		return nil, connect.NewError(connect.CodeInternal, fmt.Errorf("send abort: %w", describeSendError(s, err)))
	}

	return connect.NewResponse(&pirpcv1.AbortResponse{
		State: stateToProto(s.State()),
	}), nil
}

func (h *SessionHandler) Delete(ctx context.Context, req *connect.Request[pirpcv1.DeleteRequest]) (*connect.Response[pirpcv1.DeleteResponse], error) {
	err := h.mgr.Delete(req.Msg.SessionId)
	if err != nil {
		if errors.Is(err, session.ErrSessionNotFound) {
			return nil, connect.NewError(connect.CodeNotFound, fmt.Errorf("session %q not found", req.Msg.SessionId))
		}
		return nil, connect.NewError(connect.CodeInternal, fmt.Errorf("delete session: %w", err))
	}

	return connect.NewResponse(&pirpcv1.DeleteResponse{}), nil
}

func (h *SessionHandler) List(ctx context.Context, req *connect.Request[pirpcv1.ListRequest]) (*connect.Response[pirpcv1.ListResponse], error) {
	summaries := h.mgr.List()

	protoSummaries := make([]*pirpcv1.SessionSummary, len(summaries))
	for i, s := range summaries {
		protoSummaries[i] = &pirpcv1.SessionSummary{
			Id:        s.ID,
			State:     stateToProto(s.State),
			Provider:  s.Provider,
			Model:     s.Model,
			CreatedAt: timestamppb.New(s.CreatedAt),
		}
	}

	return connect.NewResponse(&pirpcv1.ListResponse{
		Sessions: protoSummaries,
	}), nil
}

func describeSendError(s *session.Session, err error) error {
	if errors.Is(err, session.ErrSessionClosed) {
		return err
	}

	deadline := time.Now().Add(250 * time.Millisecond)
	for time.Now().Before(deadline) {
		if msg := s.ErrorMessage(); msg != "" {
			return errors.New(msg)
		}
		if state := s.State(); state == session.StateError || state == session.StateTerminated {
			break
		}
		time.Sleep(10 * time.Millisecond)
	}

	if msg := s.ErrorMessage(); msg != "" {
		return errors.New(msg)
	}

	return err
}

func stateToProto(s session.State) pirpcv1.SessionState {
	switch s {
	case session.StateCreating:
		return pirpcv1.SessionState_SESSION_STATE_CREATING
	case session.StateIdle:
		return pirpcv1.SessionState_SESSION_STATE_IDLE
	case session.StateRunning:
		return pirpcv1.SessionState_SESSION_STATE_RUNNING
	case session.StateError:
		return pirpcv1.SessionState_SESSION_STATE_ERROR
	case session.StateTerminated:
		return pirpcv1.SessionState_SESSION_STATE_TERMINATED
	default:
		return pirpcv1.SessionState_SESSION_STATE_UNSPECIFIED
	}
}

func messageRoleToProto(role string) pirpcv1.MessageRole {
	switch role {
	case "user":
		return pirpcv1.MessageRole_MESSAGE_ROLE_USER
	case "assistant":
		return pirpcv1.MessageRole_MESSAGE_ROLE_ASSISTANT
	case "tool_result":
		return pirpcv1.MessageRole_MESSAGE_ROLE_TOOL_RESULT
	default:
		return pirpcv1.MessageRole_MESSAGE_ROLE_UNSPECIFIED
	}
}

func eventTypeToProto(t string) pirpcv1.EventType {
	switch t {
	case "agent_start":
		return pirpcv1.EventType_EVENT_TYPE_AGENT_START
	case "agent_end":
		return pirpcv1.EventType_EVENT_TYPE_AGENT_END
	case "turn_start":
		return pirpcv1.EventType_EVENT_TYPE_TURN_START
	case "turn_end":
		return pirpcv1.EventType_EVENT_TYPE_TURN_END
	case "message_update":
		return pirpcv1.EventType_EVENT_TYPE_MESSAGE_UPDATE
	case "tool_execution_start":
		return pirpcv1.EventType_EVENT_TYPE_TOOL_START
	case "tool_execution_end":
		return pirpcv1.EventType_EVENT_TYPE_TOOL_END
	default:
		return pirpcv1.EventType_EVENT_TYPE_UNSPECIFIED
	}
}
