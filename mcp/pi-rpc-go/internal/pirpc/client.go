// Package pirpc provides an HTTP client for the pi-rpc ConnectRPC service.
// It calls pirpc.v1.SessionService endpoints using the Connect protocol
// (plain HTTP/JSON POST). Server URL is configured via PI_SERVER_URL
// (default: http://localhost:4097).
package pirpc

import (
	"bytes"
	"encoding/json"
	"fmt"
	"io"
	"net/http"
	"os"
	"strings"
	"time"
)

var (
	baseURL = func() string {
		u := os.Getenv("PI_SERVER_URL")
		if u == "" {
			u = "http://localhost:4097"
		}
		return strings.TrimRight(u, "/") + "/pirpc.v1.SessionService"
	}()

	httpClient = &http.Client{Timeout: 5 * time.Minute}
)

func post(endpoint string, body any) (json.RawMessage, error) {
	payload, err := json.Marshal(body)
	if err != nil {
		return nil, err
	}

	resp, err := httpClient.Post(baseURL+"/"+endpoint, "application/json", bytes.NewReader(payload))
	if err != nil {
		return nil, fmt.Errorf("pi-rpc %s: %w", endpoint, err)
	}
	defer resp.Body.Close()

	raw, _ := io.ReadAll(resp.Body)
	if resp.StatusCode != http.StatusOK {
		return nil, fmt.Errorf("pi-rpc %s failed (%d): %s", endpoint, resp.StatusCode, raw)
	}

	return json.RawMessage(raw), nil
}

func Create(provider, model string, cwd, thinkingLevel string) (json.RawMessage, error) {
	body := map[string]any{"provider": provider, "model": model}
	if cwd != "" {
		body["cwd"] = cwd
	}
	if thinkingLevel != "" {
		body["thinkingLevel"] = thinkingLevel
	}
	return post("Create", body)
}

func Prompt(sessionID, message string) (json.RawMessage, error) {
	return post("Prompt", map[string]string{"sessionId": sessionID, "message": message})
}

func PromptAsync(sessionID, message string) (json.RawMessage, error) {
	return post("PromptAsync", map[string]string{"sessionId": sessionID, "message": message})
}

func GetMessages(sessionID string) (json.RawMessage, error) {
	return post("GetMessages", map[string]string{"sessionId": sessionID})
}

func GetState(sessionID string) (json.RawMessage, error) {
	return post("GetState", map[string]string{"sessionId": sessionID})
}

func Abort(sessionID string) (json.RawMessage, error) {
	return post("Abort", map[string]string{"sessionId": sessionID})
}

func Delete(sessionID string) (json.RawMessage, error) {
	return post("Delete", map[string]string{"sessionId": sessionID})
}

func List() (json.RawMessage, error) {
	return post("List", map[string]any{})
}
