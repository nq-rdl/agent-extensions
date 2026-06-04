package api

import (
	"context"
	"fmt"

	"github.com/nq-rdl/agent-skills/skills/jules/scripts/internal/model"
)

// ListActivities returns all activities for a session.
func (c *Client) ListActivities(ctx context.Context, sessionID string) ([]model.Activity, error) {
	var resp model.ListActivitiesResponse
	path := "/sessions/" + sessionID + "/activities"
	if err := c.get(ctx, path, &resp); err != nil {
		return nil, fmt.Errorf("list activities for session %s: %w", sessionID, err)
	}
	return resp.Activities, nil
}

// GetActivity returns a single activity within a session.
func (c *Client) GetActivity(ctx context.Context, sessionID, activityID string) (*model.Activity, error) {
	var activity model.Activity
	path := "/sessions/" + sessionID + "/activities/" + activityID
	if err := c.get(ctx, path, &activity); err != nil {
		return nil, fmt.Errorf("get activity %s in session %s: %w", activityID, sessionID, err)
	}
	return &activity, nil
}
