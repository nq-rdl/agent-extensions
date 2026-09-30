// Package localrefs checks that local (non-network) link targets in a skill's
// Markdown and reStructuredText files resolve to files inside the same skill.
//
// It is a deterministic, offline complement to the advisory external HTTP link
// check (lychee). lychee extracts relative Markdown links but treats .rst as
// plain text, so a relative RST target such as `text <missing.rst>`_ is never
// checked there; this package covers both formats with source-relative
// resolution that does not depend on the process working directory.
//
// It is not a full Markdown or RST parser. It recognises the link syntax the
// catalog actually ships (see docs/authoring-skills.md "Local references"):
//
//   - Markdown (.md, and Markdown-flavoured prose in .rst): inline links and
//     images [text](target) / ![alt](target), and reference definitions
//     [label]: target.
//   - RST (.rst): embedded-URI hyperlinks `text <target>`_ and `text <target>`__,
//     hyperlink targets .. _name: target / .. __: target, and the path
//     argument of the image, figure, include and literalinclude directives
//     (including image substitution definitions .. |name| image:: target).
//
// Skipped: fenced code blocks (``` and ~~~ in Markdown; ``` after a blank
// line in RST, where ~~~ is a section adornment), inline code
// spans, HTML comments, YAML frontmatter, RST literal blocks (a paragraph
// ending in "::" and the code, code-block, sourcecode, raw, math and
// parsed-literal directives), RST comments, named/indirect RST references
// (`name`_, `text <name_>`_, .. _name: other_), external targets (any URI
// scheme or //host), fragment-only targets (#anchor) and illustrative
// placeholders (see IsPlaceholder). Fragments and queries are stripped before
// the file-existence check; fragments themselves are not validated.
//
// Targets resolve from the containing file's directory (from the skill root
// for EntrypointOverrides). Root-absolute (/x), home-relative (~/x) and
// skill-escaping (../other-skill/x) targets fail: an installed plugin copies
// only the skill directory. Name matching is exact on every filesystem.
// Not supported: Markdown indented code blocks (use fences), Markdown links
// whose text or destination spans lines, reference-style Markdown usages
// ([text][label]; only the definition is checked), RST anonymous targets in
// the short "__ target" form (use ".. __: target"), non-image substitution
// definitions, and Sphinx roles such as :doc: (none are used in skills/).
package localrefs

import (
	"fmt"
	"io/fs"
	"net/url"
	"os"
	"path/filepath"
	"regexp"
	"sort"
	"strings"
)

// Ref is one local link target found in a source file.
type Ref struct {
	Line   int    // 1-based line number of the target in the source file
	Target string // raw target text as written
}

// EntrypointOverrides lists skill-relative files whose body the Codex packager
// installs as the skill's SKILL.md (registry targets.codex.skillOverrides).
// Their links are therefore resolved relative to the skill root, not to the
// file's own directory. tests/test_localrefs_contract.py keeps the registry in
// step with this list.
var EntrypointOverrides = []string{"references/codex.rst"}

var (
	schemeRe = regexp.MustCompile(`^[A-Za-z][A-Za-z0-9+.-]*:`)

	// Markdown inline link or image: [text](dest "title"). The destination is
	// either <...> or a run without whitespace that may contain one level of
	// balanced parentheses.
	mdInlineRe = regexp.MustCompile(`!?\[(?:[^\[\]\n]|\[[^\[\]\n]*\])*\]\(\s*(<[^<>\n]*>|[^\s()<>]*(?:\([^\s()]*\)[^\s()<>]*)*)(?:\s+(?:"[^"\n]*"|'[^'\n]*'|\([^()\n]*\)))?\s*\)`)
	// Markdown reference definition: [label]: dest (footnotes [^x]: are skipped).
	mdRefDefRe = regexp.MustCompile(`^ {0,3}\[([^\]\n]+)\]:\s*(<[^<>\n]*>|\S+)`)
	fenceRe    = regexp.MustCompile("^\\s*(`{3,}|~{3,})")

	// RST embedded URI: `text <target>`_ or `text <target>`__. The phrase may
	// span lines, so it is matched against a whole paragraph.
	rstEmbeddedRe  = regexp.MustCompile("`[^`]*?<([^<>`]+)>`__?")
	rstDirectiveRe = regexp.MustCompile(`^(\s*)\.\.\s+(?:\|[^|]+\|\s+)?([A-Za-z0-9_-]+(?::[A-Za-z0-9_-]+)?)::(?:\s+(.*))?$`)
	// Hyperlink target: .. _name: target, .. _`name`: target, .. __: target.
	rstTargetRe  = regexp.MustCompile("^(\\s*)\\.\\.\\s+_(?:`[^`]+`|[^:`]*(?:\\\\:[^:`]*)*):(?:\\s+(.*))?$")
	rstCommentRe = regexp.MustCompile(`^(\s*)\.\.(?:\s|$)`)
)

// rstLiteralDirectives have bodies that are not parsed as RST markup.
var rstLiteralDirectives = map[string]bool{
	"code": true, "code-block": true, "sourcecode": true, "raw": true,
	"math": true, "parsed-literal": true, "highlight": true,
}

// rstPathDirectives take a file path as their argument.
var rstPathDirectives = map[string]bool{
	"image": true, "figure": true, "include": true, "literalinclude": true,
}

// IsPlaceholder reports whether target is an illustrative placeholder rather
// than a real path: it contains <, >, {, }, $ (template or variable syntax),
// "..." or "…" (elision), or * (glob).
func IsPlaceholder(target string) bool {
	return strings.ContainsAny(target, "<>{}$*…") || strings.Contains(target, "...")
}

// Check scans every .md and .rst file under skillDir (hidden entries are
// ignored) and returns one message per unresolved local reference, formatted
// as "<file>:<line>: ..." with the file relative to skillDir. Resolution uses
// only skillDir, so results are independent of the working directory.
func Check(skillDir string) []string {
	var errs []string
	var files []string
	walkErr := filepath.WalkDir(skillDir, func(path string, d fs.DirEntry, err error) error {
		if err != nil {
			return err
		}
		if path != skillDir && strings.HasPrefix(d.Name(), ".") {
			if d.IsDir() {
				return fs.SkipDir
			}
			return nil
		}
		if d.IsDir() {
			return nil
		}
		switch strings.ToLower(filepath.Ext(path)) {
		case ".md", ".rst":
			files = append(files, path)
		}
		return nil
	})
	if walkErr != nil {
		return []string{fmt.Sprintf("local references: walk: %v", walkErr)}
	}
	sort.Strings(files)
	for _, f := range files {
		errs = append(errs, checkFile(skillDir, f)...)
	}
	return errs
}

func checkFile(skillDir, path string) []string {
	rel, err := filepath.Rel(skillDir, path)
	if err != nil {
		rel = path
	}
	rel = filepath.ToSlash(rel)
	data, err := os.ReadFile(path)
	if err != nil {
		return []string{fmt.Sprintf("%s: read: %v", rel, err)}
	}
	var refs []Ref
	if strings.EqualFold(filepath.Ext(path), ".rst") {
		refs = ExtractRST(string(data))
	} else {
		refs = ExtractMarkdown(string(data))
	}
	base := filepath.Dir(path)
	for _, e := range EntrypointOverrides {
		if rel == e {
			base = skillDir
		}
	}
	var errs []string
	for _, r := range refs {
		if msg := Resolve(skillDir, base, r.Target); msg != "" {
			errs = append(errs, fmt.Sprintf("%s:%d: local reference %q %s", rel, r.Line, r.Target, msg))
		}
	}
	return errs
}

// Resolve checks one target found in a file whose links resolve against base
// (normally the file's directory). It returns "" when the target is fine or
// out of scope (external, fragment-only, placeholder), else a reason.
func Resolve(skillDir, base, target string) string {
	t := strings.TrimSpace(target)
	if strings.HasPrefix(t, "<") && strings.HasSuffix(t, ">") {
		t = strings.TrimSpace(t[1 : len(t)-1])
	}
	switch {
	case t == "":
		return "is empty"
	case schemeRe.MatchString(t), strings.HasPrefix(t, "//"):
		return "" // external: the advisory lychee check owns it
	case strings.HasPrefix(t, "#"):
		return "" // same-document fragment; anchors are not validated
	case IsPlaceholder(t):
		return ""
	}
	if i := strings.IndexAny(t, "#?"); i >= 0 {
		t = t[:i]
	}
	if u, err := url.PathUnescape(t); err == nil {
		t = u
	}
	switch {
	case strings.HasPrefix(t, "/"):
		return "is root-absolute; installed skills have no site root (use a path relative to this file, or a full URL)"
	case strings.HasPrefix(t, "~"):
		return "is home-relative; link to a file inside the skill, or format the path as inline code"
	}
	absSkill, err := filepath.Abs(skillDir)
	if err != nil {
		return fmt.Sprintf("cannot resolve skill directory: %v", err)
	}
	absBase, err := filepath.Abs(base)
	if err != nil {
		return fmt.Sprintf("cannot resolve base directory: %v", err)
	}
	resolved := filepath.Clean(filepath.Join(absBase, filepath.FromSlash(t)))
	relToSkill, err := filepath.Rel(absSkill, resolved)
	if err != nil || relToSkill == ".." || strings.HasPrefix(relToSkill, ".."+string(filepath.Separator)) {
		return "escapes the skill directory; installed plugins copy only the skill, so the link would dangle"
	}
	if relToSkill == "." {
		return ""
	}
	if missing := missingComponent(absSkill, relToSkill); missing != "" {
		return fmt.Sprintf("does not resolve: %s not found", filepath.ToSlash(missing))
	}
	return ""
}

// missingComponent walks rel below root one component at a time, matching
// names exactly (so results do not depend on filesystem case sensitivity).
// It returns the skill-relative path of the first missing component, or "".
func missingComponent(root, rel string) string {
	cur := root
	parts := strings.Split(rel, string(filepath.Separator))
	for i, p := range parts {
		entries, err := os.ReadDir(cur)
		if err != nil {
			return filepath.Join(parts[:i+1]...)
		}
		found := false
		for _, e := range entries {
			if e.Name() == p {
				found = true
				break
			}
		}
		if !found {
			return filepath.Join(parts[:i+1]...)
		}
		cur = filepath.Join(cur, p)
	}
	return ""
}

// maskInlineCode replaces backtick code spans (matching opening and closing
// runs of equal length) with spaces, preserving offsets and newlines.
func maskInlineCode(s string) string {
	b := []byte(s)
	i := 0
	for i < len(b) {
		if b[i] != '`' {
			i++
			continue
		}
		j := i
		for j < len(b) && b[j] == '`' {
			j++
		}
		n := j - i
		k := j
		closed := -1
		for k < len(b) {
			if b[k] == '\n' && blankLineAfter(b, k) {
				break // code spans do not cross paragraph breaks
			}
			if b[k] != '`' {
				k++
				continue
			}
			m := k
			for m < len(b) && b[m] == '`' {
				m++
			}
			if m-k == n {
				closed = m
				break
			}
			k = m
		}
		if closed < 0 {
			i = j
			continue
		}
		for x := i; x < closed; x++ {
			if b[x] != '\n' {
				b[x] = ' '
			}
		}
		i = closed
	}
	return string(b)
}

// blankLineAfter reports whether the line starting after the newline at
// b[nl] is empty or whitespace-only (a paragraph break).
func blankLineAfter(b []byte, nl int) bool {
	for x := nl + 1; x < len(b); x++ {
		switch b[x] {
		case ' ', '\t', '\r':
			continue
		case '\n':
			return true
		default:
			return false
		}
	}
	return true
}

// maskHTMLComments blanks <!-- ... --> spans, preserving newlines.
func maskHTMLComments(s string) string {
	b := []byte(s)
	for {
		start := strings.Index(string(b), "<!--")
		if start < 0 {
			break
		}
		end := strings.Index(string(b[start+4:]), "-->")
		stop := len(b)
		if end >= 0 {
			stop = start + 4 + end + 3
		}
		for x := start; x < stop; x++ {
			if b[x] != '\n' {
				b[x] = ' '
			}
		}
	}
	return string(b)
}

// fenceTracker recognises ``` / ~~~ fenced blocks line by line.
type fenceTracker struct {
	char byte
	n    int
	rst  bool // RST mode: backtick fences only, and only after a blank line
}

// step reports whether line is part of a fenced block (including its fences).
// In RST mode, prev is the previous line: a run of ~ or ` directly under text
// is a section-title adornment, not a fence.
func (f *fenceTracker) step(line, prev string) bool {
	if f.n > 0 {
		trimmed := strings.TrimSpace(line)
		if len(trimmed) >= f.n && strings.Trim(trimmed, string(f.char)) == "" && trimmed[0] == f.char {
			f.n = 0
		}
		return true
	}
	if m := fenceRe.FindStringSubmatch(line); m != nil {
		if f.rst && (m[1][0] != '`' || !isBlank(prev)) {
			return false
		}
		f.char, f.n = m[1][0], len(m[1])
		return true
	}
	return false
}

func blankLines(lines []string, skip []bool) string {
	out := make([]string, len(lines))
	for i, l := range lines {
		if !skip[i] {
			out[i] = l
		}
	}
	return strings.Join(out, "\n")
}

// lineAt returns the 1-based line number of byte offset off in s.
func lineAt(s string, off int) int {
	return strings.Count(s[:off], "\n") + 1
}

// markdownRefs extracts inline links and reference definitions from text in
// which code has already been masked (line structure preserved).
func markdownRefs(text string) []Ref {
	var refs []Ref
	for _, m := range mdInlineRe.FindAllStringSubmatchIndex(text, -1) {
		if m[0] > 0 && text[m[0]-1] == '\\' {
			continue // \[escaped] is literal text, not a link
		}
		refs = append(refs, Ref{Line: lineAt(text, m[2]), Target: unescapeMarkdown(text[m[2]:m[3]])})
	}
	for i, line := range strings.Split(text, "\n") {
		if m := mdRefDefRe.FindStringSubmatch(line); m != nil && !strings.HasPrefix(m[1], "^") {
			refs = append(refs, Ref{Line: i + 1, Target: unescapeMarkdown(m[2])})
		}
	}
	sort.SliceStable(refs, func(a, b int) bool { return refs[a].Line < refs[b].Line })
	return refs
}

// ExtractMarkdown returns the link targets in a Markdown document, skipping
// frontmatter, fenced code blocks, inline code spans and HTML comments.
func ExtractMarkdown(content string) []Ref {
	lines := strings.Split(content, "\n")
	skip := make([]bool, len(lines))
	start := 0
	if len(lines) > 0 && strings.TrimRight(lines[0], "\r") == "---" {
		for i := 1; i < len(lines); i++ {
			if strings.TrimRight(lines[i], "\r") == "---" {
				for j := 0; j <= i; j++ {
					skip[j] = true
				}
				start = i + 1
				break
			}
		}
	}
	var fence fenceTracker
	for i := start; i < len(lines); i++ {
		if fence.step(lines[i], "") {
			skip[i] = true
		}
	}
	text := maskInlineCode(maskHTMLComments(blankLines(lines, skip)))
	return markdownRefs(text)
}

func indentOf(line string) int {
	n := 0
	for _, c := range line {
		switch c {
		case ' ':
			n++
		case '\t':
			n += 8 - n%8
		default:
			return n
		}
	}
	return n
}

func isBlank(line string) bool { return strings.TrimSpace(line) == "" }

// skipIndentedBody marks the block indented deeper than indent that follows
// line i (blank lines inside it included) and returns the index of the last
// line consumed.
func skipIndentedBody(lines []string, skip []bool, i, indent int) int {
	j := i + 1
	last := i
	for j < len(lines) {
		if isBlank(lines[j]) {
			skip[j] = true
			j++
			continue
		}
		if indentOf(lines[j]) <= indent {
			break
		}
		skip[j] = true
		last = j
		j++
	}
	return last
}

// ExtractRST returns the link targets in a reStructuredText document. It also
// recognises Markdown inline links and reference definitions, because several
// catalog .rst files carry Markdown-flavoured prose that agents read literally.
func ExtractRST(content string) []Ref {
	lines := strings.Split(content, "\n")
	skip := make([]bool, len(lines))
	var refs []Ref
	fence := fenceTracker{rst: true}

	for i := 0; i < len(lines); i++ {
		if skip[i] {
			continue
		}
		line := strings.TrimRight(lines[i], "\r")
		prev := ""
		if i > 0 {
			prev = lines[i-1]
		}
		if fence.step(line, prev) {
			skip[i] = true
			continue
		}
		if m := rstTargetRe.FindStringSubmatch(line); m != nil {
			skip[i] = true
			target := strings.TrimSpace(m[2])
			startLine := i + 1
			// A target URI may continue on following, more-indented lines.
			ind := len(m[1])
			for i+1 < len(lines) && !isBlank(lines[i+1]) && indentOf(lines[i+1]) > ind {
				i++
				skip[i] = true
				target += strings.TrimSpace(lines[i])
			}
			if target != "" && !isIndirectRST(target) {
				refs = append(refs, Ref{Line: startLine, Target: unescapeRST(target)})
			}
			continue
		}
		if m := rstDirectiveRe.FindStringSubmatch(line); m != nil {
			skip[i] = true
			name := strings.ToLower(m[2])
			ind := len(m[1])
			if rstPathDirectives[name] && strings.TrimSpace(m[3]) != "" {
				refs = append(refs, Ref{Line: i + 1, Target: strings.TrimSpace(m[3])})
			}
			if rstLiteralDirectives[name] {
				i = skipIndentedBody(lines, skip, i, ind)
			}
			// Other directive bodies (admonition, container, figure caption,
			// list-table, ...) are ordinary markup and keep being scanned.
			continue
		}
		if m := rstCommentRe.FindStringSubmatch(line); m != nil && !strings.HasPrefix(strings.TrimSpace(line), ".. |") && !strings.HasPrefix(strings.TrimSpace(line), ".. [") {
			// Comment: the line and its indented body are not markup.
			skip[i] = true
			i = skipIndentedBody(lines, skip, i, len(m[1]))
			continue
		}
		if strings.HasSuffix(strings.TrimSpace(line), "::") {
			// Literal block introduced by "::" at the end of a paragraph (or
			// alone). The paragraph line itself is still prose.
			ind := indentOf(line)
			// Measure against the paragraph's first line.
			for k := i - 1; k >= 0 && !isBlank(lines[k]) && !skip[k]; k-- {
				ind = indentOf(lines[k])
			}
			if strings.TrimSpace(line) == "::" {
				skip[i] = true
			}
			i = skipIndentedBody(lines, skip, i, ind)
			continue
		}
	}

	text := blankLines(lines, skip)
	// RST embedded URIs: mask ``literal`` spans first; single-backtick phrases
	// are the link syntax itself.
	rstText := maskDoubleBacktick(text)
	for _, m := range rstEmbeddedRe.FindAllStringSubmatchIndex(rstText, -1) {
		raw := rstText[m[2]:m[3]]
		target := strings.Join(strings.Fields(raw), "")
		if isIndirectRST(target) {
			continue // `text <name_>`_ points at a named target, not a file
		}
		refs = append(refs, Ref{Line: lineAt(rstText, m[2]), Target: unescapeRST(target)})
	}
	// Markdown-flavoured links: mask every backtick span (RST phrases included).
	refs = append(refs, markdownRefs(maskInlineCode(maskHTMLComments(text)))...)
	sort.SliceStable(refs, func(a, b int) bool { return refs[a].Line < refs[b].Line })
	return refs
}

// maskDoubleBacktick blanks “inline literal“ spans only.
func maskDoubleBacktick(s string) string {
	b := []byte(s)
	for i := 0; i+1 < len(b); {
		if b[i] == '`' && b[i+1] == '`' {
			stop := -1
			for k := i + 2; k+1 < len(b); k++ {
				if b[k] == '\n' && blankLineAfter(b, k) {
					break // literals do not cross paragraph breaks
				}
				if b[k] == '`' && b[k+1] == '`' {
					stop = k + 2
					break
				}
			}
			if stop < 0 {
				i += 2
				continue
			}
			for x := i; x < stop; x++ {
				if b[x] != '\n' {
					b[x] = ' '
				}
			}
			i = stop
			continue
		}
		i++
	}
	return string(b)
}

// isIndirectRST reports whether an RST target is a reference to another named
// target (ends in an unescaped "_", no whitespace) rather than a URI.
func isIndirectRST(target string) bool {
	return strings.HasSuffix(target, "_") && !strings.HasSuffix(target, `\_`) && !strings.ContainsAny(target, " \t")
}

// mdEscapeRe matches a CommonMark backslash escape of ASCII punctuation.
var mdEscapeRe = regexp.MustCompile("\\\\([!-/:-@\\[-`{-~])")

func unescapeMarkdown(target string) string {
	return mdEscapeRe.ReplaceAllString(target, "$1")
}

func unescapeRST(target string) string {
	return strings.ReplaceAll(target, `\_`, "_")
}
