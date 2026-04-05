package api

import (
	"context"
	"fmt"

	"github.com/nq-rdl/agent-skills/skills/jules/scripts/internal/model"
)

// ListSources returns all GitHub sources registered with Jules.
func (c *Client) ListSources(ctx context.Context) ([]model.Source, error) {
	var resp model.ListSourcesResponse
	if err := c.get(ctx, "/sources", &resp); err != nil {
		return nil, fmt.Errorf("list sources: %w", err)
	}
	return resp.Sources, nil
}

// GetSource returns a single source by ID.
func (c *Client) GetSource(ctx context.Context, id string) (*model.Source, error) {
	var source model.Source
	if err := c.get(ctx, "/sources/"+id, &source); err != nil {
		return nil, fmt.Errorf("get source %s: %w", id, err)
	}
	return &source, nil
}

// CreateSource registers a new GitHub repository as a Jules source.
func (c *Client) CreateSource(ctx context.Context, owner, repo string) (*model.Source, error) {
	req := &model.CreateSourceRequest{
		GithubRepo: &model.GithubRepo{Owner: owner, Repo: repo},
	}
	var source model.Source
	if err := c.post(ctx, "/sources", req, &source); err != nil {
		return nil, fmt.Errorf("create source %s/%s: %w", owner, repo, err)
	}
	return &source, nil
}
