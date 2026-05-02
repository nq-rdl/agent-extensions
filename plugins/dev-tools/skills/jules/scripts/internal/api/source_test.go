package api_test

import (
	"encoding/json"
	"strings"
	"testing"

	"github.com/nq-rdl/agent-skills/skills/jules/scripts/internal/model"
)

func TestListSources(t *testing.T) {
	want := model.ListSourcesResponse{
		Sources: []model.Source{
			{
				ID: "src_1",
				GithubRepo: &model.GithubRepo{
					Owner:         "nq-rdl",
					Repo:          "agent-ops",
					DefaultBranch: "main",
				},
			},
		},
	}
	ts, client := newTestServer(t, 200, want)

	got, err := client.ListSources(t.Context())
	if err != nil {
		t.Fatalf("unexpected error: %v", err)
	}
	if len(got) != 1 {
		t.Fatalf("len: got %d, want 1", len(got))
	}
	if got[0].ID != "src_1" {
		t.Errorf("ID: got %q, want src_1", got[0].ID)
	}
	if got[0].GithubRepo.Owner != "nq-rdl" {
		t.Errorf("Owner: got %q", got[0].GithubRepo.Owner)
	}

	r := ts.lastRequest()
	if r.Method != "GET" {
		t.Errorf("method: got %s, want GET", r.Method)
	}
	if !strings.HasSuffix(r.URL.Path, "/sources") {
		t.Errorf("path: got %s", r.URL.Path)
	}
}

func TestGetSource(t *testing.T) {
	want := model.Source{
		ID: "src_abc",
		GithubRepo: &model.GithubRepo{
			Owner: "nq-rdl",
			Repo:  "jules-test",
		},
	}
	ts, client := newTestServer(t, 200, want)

	got, err := client.GetSource(t.Context(), "src_abc")
	if err != nil {
		t.Fatalf("unexpected error: %v", err)
	}
	if got.ID != "src_abc" {
		t.Errorf("ID: got %q, want src_abc", got.ID)
	}

	r := ts.lastRequest()
	if !strings.HasSuffix(r.URL.Path, "/src_abc") {
		t.Errorf("path: got %s", r.URL.Path)
	}
	_ = ts
}

func TestCreateSource(t *testing.T) {
	want := model.Source{
		ID:   "src_new",
		Name: "sources/github/nq-rdl/new-repo",
		GithubRepo: &model.GithubRepo{
			Owner:         "nq-rdl",
			Repo:          "new-repo",
			DefaultBranch: "main",
		},
	}
	ts, client := newTestServer(t, 200, want)

	got, err := client.CreateSource(t.Context(), "nq-rdl", "new-repo")
	if err != nil {
		t.Fatalf("unexpected error: %v", err)
	}
	if got.ID != "src_new" {
		t.Errorf("ID: got %q, want src_new", got.ID)
	}
	if got.Name != "sources/github/nq-rdl/new-repo" {
		t.Errorf("Name: got %q", got.Name)
	}
	if got.GithubRepo == nil {
		t.Fatal("GithubRepo is nil")
	}
	if got.GithubRepo.Owner != "nq-rdl" {
		t.Errorf("Owner: got %q, want nq-rdl", got.GithubRepo.Owner)
	}
	if got.GithubRepo.Repo != "new-repo" {
		t.Errorf("Repo: got %q, want new-repo", got.GithubRepo.Repo)
	}

	r := ts.lastRequest()
	if r.Method != "POST" {
		t.Errorf("method: got %s, want POST", r.Method)
	}
	if !strings.HasSuffix(r.URL.Path, "/sources") {
		t.Errorf("path: got %s, want .../sources", r.URL.Path)
	}

	var body model.CreateSourceRequest
	if err := json.Unmarshal(ts.lastBody(), &body); err != nil {
		t.Fatalf("unmarshal request body: %v", err)
	}
	if body.GithubRepo == nil {
		t.Fatal("body.GithubRepo is nil")
	}
	if body.GithubRepo.Owner != "nq-rdl" {
		t.Errorf("body.Owner: got %q, want nq-rdl", body.GithubRepo.Owner)
	}
	if body.GithubRepo.Repo != "new-repo" {
		t.Errorf("body.Repo: got %q, want new-repo", body.GithubRepo.Repo)
	}
}
