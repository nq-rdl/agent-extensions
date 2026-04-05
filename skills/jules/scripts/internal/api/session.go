package api

import (
	"context"
	"fmt"

	"github.com/nq-rdl/agent-skills/skills/jules/scripts/internal/model"
)

// CreateSession creates a new Jules session.
func (c *Client) CreateSession(ctx context.Context, req *model.CreateSessionRequest) (*model.Session, error) {
	var session model.Session
	if err := c.post(ctx, "/sessions", req, &session); err != nil {
		return nil, fmt.Errorf("create session: %w", err)
	}
	return &session, nil
}

// ListSessions returns all sessions visible to the API key.
func (c *Client) ListSessions(ctx context.Context) ([]model.Session, error) {
	var resp model.ListSessionsResponse
	if err := c.get(ctx, "/sessions", &resp); err != nil {
		return nil, fmt.Errorf("list sessions: %w", err)
	}
	return resp.Sessions, nil
}

// GetSession returns a single session by ID.
func (c *Client) GetSession(ctx context.Context, id string) (*model.Session, error) {
	var session model.Session
	if err := c.get(ctx, "/sessions/"+id, &session); err != nil {
		return nil, fmt.Errorf("get session %s: %w", id, err)
	}
	return &session, nil
}

// DeleteSession permanently deletes a session.
func (c *Client) DeleteSession(ctx context.Context, id string) error {
	if err := c.del(ctx, "/sessions/"+id); err != nil {
		return fmt.Errorf("delete session %s: %w", id, err)
	}
	return nil
}

// SendMessage sends a follow-up message to an existing session.
func (c *Client) SendMessage(ctx context.Context, id, message string) (*model.Session, error) {
	req := &model.SendMessageRequest{Message: message}
	var session model.Session
	if err := c.post(ctx, "/sessions/"+id+":sendMessage", req, &session); err != nil {
		return nil, fmt.Errorf("send message to session %s: %w", id, err)
	}
	return &session, nil
}

// ApprovePlan approves the plan for a session in AWAITING_PLAN_APPROVAL state.
func (c *Client) ApprovePlan(ctx context.Context, id string) (*model.Session, error) {
	var session model.Session
	if err := c.post(ctx, "/sessions/"+id+":approvePlan", nil, &session); err != nil {
		return nil, fmt.Errorf("approve plan for session %s: %w", id, err)
	}
	return &session, nil
}
