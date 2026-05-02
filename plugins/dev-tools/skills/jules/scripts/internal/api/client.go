// Package api provides a thin HTTP client for the Jules REST API.
package api

import (
	"bytes"
	"cmp"
	"context"
	"encoding/json"
	"fmt"
	"io"
	"net/http"
	"os"

	"github.com/nq-rdl/agent-skills/skills/jules/scripts/internal/model"
)

const defaultBaseURL = "https://jules.googleapis.com/v1alpha"

// Client is the Jules API client.
type Client struct {
	baseURL    string
	apiKey     string
	httpClient *http.Client
}

// NewClient creates a Client using JULES_BASE_URL env (or the production URL)
// and the given API key.
func NewClient(apiKey string) *Client {
	return &Client{
		baseURL:    cmp.Or(os.Getenv("JULES_BASE_URL"), defaultBaseURL),
		apiKey:     apiKey,
		httpClient: http.DefaultClient,
	}
}

// NewClientWithBase creates a Client with an explicit base URL (used by tests).
func NewClientWithBase(_ context.Context, baseURL, apiKey string) *Client {
	return &Client{
		baseURL:    baseURL,
		apiKey:     apiKey,
		httpClient: http.DefaultClient,
	}
}

// do executes an HTTP request with Jules auth headers.
func (c *Client) do(ctx context.Context, method, path string, body any) (*http.Response, error) {
	var bodyReader io.Reader
	if body != nil {
		b, err := json.Marshal(body)
		if err != nil {
			return nil, fmt.Errorf("marshal request body: %w", err)
		}
		bodyReader = bytes.NewReader(b)
	}

	req, err := http.NewRequestWithContext(ctx, method, c.baseURL+path, bodyReader)
	if err != nil {
		return nil, fmt.Errorf("create request: %w", err)
	}
	req.Header.Set("x-goog-api-key", c.apiKey)
	req.Header.Set("Content-Type", "application/json")
	req.Header.Set("Accept", "application/json")

	resp, err := c.httpClient.Do(req)
	if err != nil {
		return nil, fmt.Errorf("http: %w", err)
	}
	return resp, nil
}

// decode reads the response body and unmarshals it into out.
// Non-2xx responses are returned as *model.APIError.
func (c *Client) decode(resp *http.Response, out any) error {
	defer resp.Body.Close()
	b, err := io.ReadAll(resp.Body)
	if err != nil {
		return fmt.Errorf("read response: %w", err)
	}

	if resp.StatusCode < 200 || resp.StatusCode >= 300 {
		var envelope struct {
			Error model.APIError `json:"error"`
		}
		if json.Unmarshal(b, &envelope) == nil && envelope.Error.Code != 0 {
			return &envelope.Error
		}
		return &model.APIError{Code: resp.StatusCode, Message: string(b)}
	}

	if out == nil || len(b) == 0 {
		return nil
	}
	return json.Unmarshal(b, out)
}

// get performs a GET request and decodes the response into out.
func (c *Client) get(ctx context.Context, path string, out any) error {
	resp, err := c.do(ctx, http.MethodGet, path, nil)
	if err != nil {
		return err
	}
	return c.decode(resp, out)
}

// post performs a POST request with body and decodes the response into out.
func (c *Client) post(ctx context.Context, path string, body, out any) error {
	resp, err := c.do(ctx, http.MethodPost, path, body)
	if err != nil {
		return err
	}
	return c.decode(resp, out)
}

// del performs a DELETE request.
func (c *Client) del(ctx context.Context, path string) error {
	resp, err := c.do(ctx, http.MethodDelete, path, nil)
	if err != nil {
		return err
	}
	return c.decode(resp, nil)
}
