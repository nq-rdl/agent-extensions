package api_test

import (
	"errors"
	"testing"

	"github.com/nq-rdl/agent-skills/skills/jules/scripts/internal/model"
)

func TestClient_APIError(t *testing.T) {
	ts, client := newTestServer(t, 403, errBody(403, "PERMISSION_DENIED", "API key invalid"))

	_, err := client.GetSession(t.Context(), "ses_123")
	if err == nil {
		t.Fatal("expected error, got nil")
	}

	var apiErr *model.APIError
	if !asAPIError(err, &apiErr) {
		t.Fatalf("expected *model.APIError, got %T: %v", err, err)
	}
	if apiErr.Code != 403 {
		t.Errorf("code: got %d, want 403", apiErr.Code)
	}
	if apiErr.Status != "PERMISSION_DENIED" {
		t.Errorf("status: got %q, want PERMISSION_DENIED", apiErr.Status)
	}

	req := ts.lastRequest()
	if req.Header.Get("x-goog-api-key") != "test-api-key" {
		t.Errorf("auth header: got %q", req.Header.Get("x-goog-api-key"))
	}
}

// asAPIError unwraps err looking for *model.APIError, equivalent to errors.As.
func asAPIError(err error, target **model.APIError) bool {
	return errors.As(err, target)
}
