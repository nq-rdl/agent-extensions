package cli

import (
	"encoding/json"
	"fmt"
	"os"
	"text/tabwriter"
	"time"

	"github.com/nq-rdl/agent-skills/skills/jules/scripts/internal/model"
)

func outputJSON(v any) error {
	enc := json.NewEncoder(os.Stdout)
	enc.SetIndent("", "  ")
	return enc.Encode(v)
}

func newTab() *tabwriter.Writer {
	return tabwriter.NewWriter(os.Stdout, 0, 0, 2, ' ', 0)
}

func outputSessionTable(sessions []model.Session) {
	w := newTab()
	fmt.Fprintln(w, "ID\tSTATE\tTITLE\tCREATED")
	for _, s := range sessions {
		fmt.Fprintf(w, "%s\t%s\t%s\t%s\n",
			s.ID, s.State, truncate(s.Title, 40), fmtTime(s.CreateTime))
	}
	w.Flush()
}

func outputActivityTable(activities []model.Activity) {
	w := newTab()
	fmt.Fprintln(w, "ID\tORIGINATOR\tCREATED\tDESCRIPTION")
	for _, a := range activities {
		fmt.Fprintf(w, "%s\t%s\t%s\t%s\n",
			a.ID, a.Originator, fmtTime(a.CreateTime), truncate(a.Description, 60))
	}
	w.Flush()
}

func outputSourceTable(sources []model.Source) {
	w := newTab()
	fmt.Fprintln(w, "ID\tOWNER\tREPO\tDEFAULT BRANCH")
	for _, s := range sources {
		owner, repo, branch := "", "", ""
		if s.GithubRepo != nil {
			owner = s.GithubRepo.Owner
			repo = s.GithubRepo.Repo
			branch = string(s.GithubRepo.DefaultBranch)
		}
		fmt.Fprintf(w, "%s\t%s\t%s\t%s\n", s.ID, owner, repo, branch)
	}
	w.Flush()
}

func truncate(s string, n int) string {
	if len(s) <= n {
		return s
	}
	return s[:n-3] + "..."
}

func fmtTime(t string) string {
	if t == "" {
		return "-"
	}
	p, err := time.Parse(time.RFC3339, t)
	if err != nil {
		return t
	}
	return p.Format("2006-01-02 15:04")
}
