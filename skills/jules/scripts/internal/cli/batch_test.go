package cli

import (
	"encoding/json"
	"os"
	"path/filepath"
	"testing"
)

func TestCollectSessionIDs_CommaSeparated(t *testing.T) {
	ids, err := collectSessionIDs([]string{"id1,id2,id3"}, "")
	if err != nil {
		t.Fatalf("unexpected error: %v", err)
	}
	want := []string{"id1", "id2", "id3"}
	if len(ids) != len(want) {
		t.Fatalf("len: got %d, want %d", len(ids), len(want))
	}
	for i := range len(want) {
		if ids[i] != want[i] {
			t.Errorf("ids[%d]: got %q, want %q", i, ids[i], want[i])
		}
	}
}

func TestCollectSessionIDs_CommaSeparatedWithSpaces(t *testing.T) {
	ids, err := collectSessionIDs([]string{"id1, id2 , id3"}, "")
	if err != nil {
		t.Fatalf("unexpected error: %v", err)
	}
	want := []string{"id1", "id2", "id3"}
	if len(ids) != len(want) {
		t.Fatalf("len: got %d, want %d", len(ids), len(want))
	}
	for i := range len(want) {
		if ids[i] != want[i] {
			t.Errorf("ids[%d]: got %q, want %q", i, ids[i], want[i])
		}
	}
}

func TestCollectSessionIDs_ManifestFile(t *testing.T) {
	manifest := batchManifest{Sessions: []string{"m1", "m2"}}
	data, err := json.Marshal(manifest)
	if err != nil {
		t.Fatalf("marshal: %v", err)
	}

	path := filepath.Join(t.TempDir(), "manifest.json")
	if err := os.WriteFile(path, data, 0o644); err != nil {
		t.Fatalf("write: %v", err)
	}

	ids, err := collectSessionIDs(nil, path)
	if err != nil {
		t.Fatalf("unexpected error: %v", err)
	}
	if len(ids) != 2 {
		t.Fatalf("len: got %d, want 2", len(ids))
	}
	if ids[0] != "m1" || ids[1] != "m2" {
		t.Errorf("ids: got %v, want [m1 m2]", ids)
	}
}

func TestCollectSessionIDs_Combined(t *testing.T) {
	manifest := batchManifest{Sessions: []string{"m1"}}
	data, err := json.Marshal(manifest)
	if err != nil {
		t.Fatalf("marshal: %v", err)
	}

	path := filepath.Join(t.TempDir(), "manifest.json")
	if err := os.WriteFile(path, data, 0o644); err != nil {
		t.Fatalf("write: %v", err)
	}

	ids, err := collectSessionIDs([]string{"p1,p2"}, path)
	if err != nil {
		t.Fatalf("unexpected error: %v", err)
	}
	want := []string{"p1", "p2", "m1"}
	if len(ids) != len(want) {
		t.Fatalf("len: got %d, want %d", len(ids), len(want))
	}
	for i := range len(want) {
		if ids[i] != want[i] {
			t.Errorf("ids[%d]: got %q, want %q", i, ids[i], want[i])
		}
	}
}

func TestCollectSessionIDs_Empty(t *testing.T) {
	ids, err := collectSessionIDs(nil, "")
	if err != nil {
		t.Fatalf("unexpected error: %v", err)
	}
	if len(ids) != 0 {
		t.Errorf("expected empty slice, got %v", ids)
	}
}

func TestCollectSessionIDs_BadManifest(t *testing.T) {
	path := filepath.Join(t.TempDir(), "bad.json")
	if err := os.WriteFile(path, []byte("not json"), 0o644); err != nil {
		t.Fatalf("write: %v", err)
	}

	_, err := collectSessionIDs(nil, path)
	if err == nil {
		t.Fatal("expected error for bad manifest, got nil")
	}
}

func TestCollectSessionIDs_MissingFile(t *testing.T) {
	_, err := collectSessionIDs(nil, "/nonexistent/manifest.json")
	if err == nil {
		t.Fatal("expected error for missing file, got nil")
	}
}
