package repocheck

import (
	"fmt"
	"io"
	"io/fs"
	"os"
	"path/filepath"
	"sort"
	"strings"
	"text/tabwriter"

	"github.com/nq-rdl/agent-extensions/tools/asctl/internal/frontmatter"
	"github.com/nq-rdl/agent-extensions/tools/asctl/internal/validator"
)

// WriteSizeReport adds advisory metrics without changing validation errors.
// Unreadable/unparseable bodies sort last; failed metrics display n/a instead of
// zero. Reference counts include visible regular files recursively, not symlinks.
func WriteSizeReport(out io.Writer, skillDirs []string) {
	type row struct {
		dir     string
		size    validator.BodySize
		bodyErr error
		refs    int
		refsErr error
	}
	rows := make([]row, 0, len(skillDirs))
	for _, dir := range skillDirs {
		r := row{dir: dir}
		data, err := os.ReadFile(filepath.Join(dir, "SKILL.md"))
		if err == nil {
			var body string
			_, body, err = frontmatter.ParseRaw(string(data))
			if err == nil {
				r.size = validator.MeasureBody(body)
			}
		}
		r.bodyErr = err
		r.refs, r.refsErr = countReferences(filepath.Join(dir, "references"))
		rows = append(rows, r)
	}
	sort.Slice(rows, func(i, j int) bool {
		a, b := rows[i], rows[j]
		if (a.bodyErr == nil) != (b.bodyErr == nil) {
			return a.bodyErr == nil
		}
		if a.size.Lines != b.size.Lines {
			return a.size.Lines > b.size.Lines
		}
		return a.dir < b.dir
	})
	fmt.Fprintln(out, "Skill body size (approximate tokens = raw UTF-8 body bytes / 4; not measured model usage)")
	table := tabwriter.NewWriter(out, 0, 4, 2, ' ', 0)
	fmt.Fprintln(table, "Skill\tBody lines\tApprox tokens\tReference files")
	for _, r := range rows {
		lines, tokens, refs := "n/a", "n/a", "n/a"
		if r.bodyErr == nil {
			lines = fmt.Sprint(r.size.Lines)
			tokens = fmt.Sprintf("%.2f", r.size.ApproxTokens)
		}
		if r.refsErr == nil {
			refs = fmt.Sprint(r.refs)
		}
		fmt.Fprintf(table, "%s\t%s\t%s\t%s\n", r.dir, lines, tokens, refs)
	}
	table.Flush()
	for _, r := range rows {
		if r.bodyErr != nil {
			fmt.Fprintf(out, "%s: body size unavailable: %v\n", r.dir, r.bodyErr)
		}
		if r.refsErr != nil {
			fmt.Fprintf(out, "%s: reference count unavailable: %v\n", r.dir, r.refsErr)
		}
	}
}

func countReferences(root string) (int, error) {
	if _, err := os.Lstat(root); os.IsNotExist(err) {
		return 0, nil
	} else if err != nil {
		return 0, err
	}
	count := 0
	err := filepath.WalkDir(root, func(path string, entry fs.DirEntry, err error) error {
		if err != nil {
			return err
		}
		if path == root && !entry.IsDir() {
			return fmt.Errorf("references/ is not a directory")
		}
		if strings.HasPrefix(entry.Name(), ".") {
			if entry.IsDir() {
				return fs.SkipDir
			}
			return nil
		}
		if entry.Type().IsRegular() {
			count++
		}
		return nil
	})
	return count, err
}
