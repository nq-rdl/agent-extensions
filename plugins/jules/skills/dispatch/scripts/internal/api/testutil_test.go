package api_test

import (
	"encoding/json"
	"net/http"
	"net/http/httptest"
	"testing"

	"github.com/nq-rdl/agent-skills/skills/jules/scripts/internal/api"
)

// newTestServer creates an httptest.Server that responds with the given status
// code and body. It also records the last request for assertion.
type testServer struct {
	*httptest.Server
	requests []*http.Request
	bodies   [][]byte
}

func newTestServer(t *testing.T, status int, body any) (*testServer, *api.Client) {
	t.Helper()
	ts := &testServer{}

	ts.Server = httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		ts.requests = append(ts.requests, r)
		var b []byte
		dec := json.NewDecoder(r.Body)
		var raw json.RawMessage
		if err := dec.Decode(&raw); err == nil {
			b = raw
		}
		ts.bodies = append(ts.bodies, b)

		w.Header().Set("Content-Type", "application/json")
		w.WriteHeader(status)
		if body != nil {
			_ = json.NewEncoder(w).Encode(body)
		}
	}))

	client := api.NewClientWithBase(t.Context(), ts.URL, "test-api-key")
	t.Cleanup(ts.Server.Close)
	return ts, client
}

// lastRequest returns the most recent request captured by the test server.
func (ts *testServer) lastRequest() *http.Request {
	if len(ts.requests) == 0 {
		return nil
	}
	return ts.requests[len(ts.requests)-1]
}

// lastBody returns the raw JSON body of the most recent request.
func (ts *testServer) lastBody() []byte {
	if len(ts.bodies) == 0 {
		return nil
	}
	return ts.bodies[len(ts.bodies)-1]
}

// errBody returns a GCP-style error response body as a map.
func errBody(code int, status, message string) map[string]any {
	return map[string]any{
		"error": map[string]any{
			"code":    code,
			"status":  status,
			"message": message,
		},
	}
}
