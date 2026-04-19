package main

import (
	"encoding/json"
	"errors"
	"math"
	"strings"
	"testing"

	"connectrpc.com/connect"
)

func TestStringArg(t *testing.T) {
	tests := []struct {
		name string
		args map[string]any
		key  string
		want string
	}{
		{"missing key", map[string]any{}, "x", ""},
		{"string value", map[string]any{"x": "hello"}, "x", "hello"},
		{"int coerced via fmt", map[string]any{"x": 42}, "x", "42"},
		{"bool coerced via fmt", map[string]any{"x": true}, "x", "true"},
		{"empty string", map[string]any{"x": ""}, "x", ""},
	}
	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			if got := stringArg(tt.args, tt.key); got != tt.want {
				t.Errorf("stringArg(%v, %q) = %q, want %q", tt.args, tt.key, got, tt.want)
			}
		})
	}
}

func TestNumberArg(t *testing.T) {
	tests := []struct {
		name string
		args map[string]any
		want float64
	}{
		{"missing", map[string]any{}, 0},
		{"float64", map[string]any{"n": float64(3.5)}, 3.5},
		{"int (via mcp marshaller)", map[string]any{"n": 42}, 42},
		{"int64", map[string]any{"n": int64(1_000_000)}, 1_000_000},
		{"string is rejected", map[string]any{"n": "42"}, 0},
	}
	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			if got := numberArg(tt.args, "n"); got != tt.want {
				t.Errorf("numberArg = %v, want %v", got, tt.want)
			}
		})
	}
}

func TestSafeInt32(t *testing.T) {
	tests := []struct {
		name string
		in   float64
		want int32
	}{
		{"zero", 0, 0},
		{"small positive", 42, 42},
		{"negative clamped to 0", -100, 0},
		{"NaN clamped to 0", math.NaN(), 0},
		{"overflow clamped to MaxInt32", float64(math.MaxInt32) + 1000, math.MaxInt32},
		{"+Inf clamped to MaxInt32", math.Inf(1), math.MaxInt32},
		{"-Inf clamped to 0", math.Inf(-1), 0},
	}
	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			if got := safeInt32(tt.in); got != tt.want {
				t.Errorf("safeInt32(%v) = %d, want %d", tt.in, got, tt.want)
			}
		})
	}
}

func TestJSONResult(t *testing.T) {
	res, err := jsonResult(map[string]any{"hello": "world", "n": 7})
	if err != nil {
		t.Fatal(err)
	}
	if len(res.Content) == 0 {
		t.Fatal("expected content in result")
	}
}

func TestConnectErrToMCP_sanitizesCodes(t *testing.T) {
	tests := []struct {
		name string
		code connect.Code
		want string
	}{
		{"not found", connect.CodeNotFound, "session not found"},
		{"invalid argument", connect.CodeInvalidArgument, "invalid argument"},
		{"permission denied", connect.CodePermissionDenied, "permission denied"},
		{"unauthenticated", connect.CodeUnauthenticated, "authentication required"},
		{"deadline exceeded", connect.CodeDeadlineExceeded, "deadline exceeded"},
		{"unavailable", connect.CodeUnavailable, "service unavailable"},
		{"internal", connect.CodeInternal, "internal error"},
		{"failed precondition", connect.CodeFailedPrecondition, "failed precondition"},
		{"resource exhausted", connect.CodeResourceExhausted, "resource exhausted"},
	}
	for _, tt := range tests {
		t.Run(tt.name, func(t *testing.T) {
			// Include sensitive-looking detail in the upstream error message
			// that must NOT appear in the sanitised output.
			secret := "SECRET=abc123 /home/alice/.pi/auth.json token=sk-xyz"
			raw := connect.NewError(tt.code, errors.New(secret))
			got := connectErrToMCP(raw)
			if got == nil {
				t.Fatal("expected non-nil error")
			}
			msg := got.Error()
			if !strings.Contains(msg, tt.want) {
				t.Errorf("sanitised message %q missing %q", msg, tt.want)
			}
			for _, leak := range []string{"SECRET", "abc123", "/home/alice", "sk-xyz", "auth.json"} {
				if strings.Contains(msg, leak) {
					t.Errorf("sanitised message leaked sensitive token %q: %q", leak, msg)
				}
			}
		})
	}
}

func TestConnectErrToMCP_nonConnectErrorIsGeneric(t *testing.T) {
	raw := errors.New("internal goroutine panicked: /srv/secret/path")
	got := connectErrToMCP(raw)
	if got == nil {
		t.Fatal("expected non-nil error")
	}
	msg := got.Error()
	if !strings.Contains(msg, "internal error") {
		t.Errorf("expected generic internal error, got %q", msg)
	}
	if strings.Contains(msg, "/srv/secret") || strings.Contains(msg, "panicked") {
		t.Errorf("non-connect error leaked detail: %q", msg)
	}
}

func TestConnectErrToMCP_nilPassesThrough(t *testing.T) {
	if got := connectErrToMCP(nil); got != nil {
		t.Errorf("connectErrToMCP(nil) = %v, want nil", got)
	}
}

func TestSanitizedMessagesAreBounded(t *testing.T) {
	// Every sanitised message must be short, stable, and free of dynamic data
	// so that the LLM host can't be tricked into rendering injected content.
	for code := connect.Code(0); code <= connect.CodeUnauthenticated; code++ {
		msg := sanitizedMessageFor(code)
		if strings.ContainsAny(msg, "\n\r\t") {
			t.Errorf("code %s: message %q contains control characters", code, msg)
		}
		if len(msg) > 64 {
			t.Errorf("code %s: message %q exceeds 64 bytes", code, msg)
		}
		// round-trip through JSON to ensure no escapable chars
		b, err := json.Marshal(msg)
		if err != nil {
			t.Errorf("code %s: cannot marshal %q: %v", code, msg, err)
		}
		if strings.Contains(string(b), `\u`) {
			t.Errorf("code %s: message %q encoded with unicode escape: %s", code, msg, b)
		}
	}
}
