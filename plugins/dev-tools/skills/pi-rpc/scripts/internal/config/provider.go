package config

import (
	"encoding/json"
	"log"
	"os"
	"path/filepath"
)

// DetectProvider inspects ~/.pi/agent/auth.json and returns "openai-codex"
// if that key is present, otherwise falls back to "openai".
func DetectProvider() string {
	home, err := os.UserHomeDir()
	if err != nil {
		log.Printf("DetectProvider: cannot determine home directory: %v, defaulting to openai", err)
		return "openai"
	}

	authFile := filepath.Join(home, ".pi", "agent", "auth.json")
	data, err := os.ReadFile(authFile)
	if err != nil {
		// File not found is expected in many environments — no warning needed.
		return "openai"
	}

	var auth map[string]any
	if err := json.Unmarshal(data, &auth); err != nil {
		log.Printf("DetectProvider: cannot parse %s: %v, defaulting to openai", authFile, err)
		return "openai"
	}

	if _, ok := auth["openai-codex"]; ok {
		return "openai-codex"
	}

	return "openai"
}
