package localrefs_test

import (
	"os"
	"path/filepath"
	"reflect"
	"strings"
	"testing"

	"github.com/nq-rdl/agent-extensions/tools/asctl/internal/localrefs"
)

// writeSkill creates a skill directory from a map of skill-relative paths to
// contents and returns its path.
func writeSkill(t *testing.T, files map[string]string) string {
	t.Helper()
	dir := filepath.Join(t.TempDir(), "demo-skill")
	for rel, content := range files {
		p := filepath.Join(dir, filepath.FromSlash(rel))
		if err := os.MkdirAll(filepath.Dir(p), 0o755); err != nil {
			t.Fatal(err)
		}
		if err := os.WriteFile(p, []byte(content), 0o644); err != nil {
			t.Fatal(err)
		}
	}
	return dir
}

const skillMD = "---\nname: demo-skill\ndescription: Demo\n---\n\n"

func targets(refs []localrefs.Ref) []string {
	out := []string{}
	for _, r := range refs {
		out = append(out, r.Target)
	}
	return out
}

func assertErrors(t *testing.T, got []string, wantSubstrings ...string) {
	t.Helper()
	if len(got) != len(wantSubstrings) {
		t.Fatalf("got %d error(s), want %d:\n%s", len(got), len(wantSubstrings), strings.Join(got, "\n"))
	}
	for i, want := range wantSubstrings {
		if !strings.Contains(got[i], want) {
			t.Errorf("error[%d] = %q, want substring %q", i, got[i], want)
		}
	}
}

func TestMarkdownMissingTargetFailsExistingPasses(t *testing.T) {
	dir := writeSkill(t, map[string]string{
		"SKILL.md": skillMD +
			"See [layout](references/layout.rst) and ![logo](assets/logo.png).\n" +
			"Also [gone](references/missing.rst).\n",
		"references/layout.rst": "Layout\n",
		"assets/logo.png":       "png",
	})
	assertErrors(t, localrefs.Check(dir),
		`SKILL.md:7: local reference "references/missing.rst" does not resolve: references/missing.rst not found`)
}

func TestRSTMissingTargetFailsExistingPasses(t *testing.T) {
	// The fixture from issue #300: lychee treats .rst as plain text and never
	// checks this relative target.
	dir := writeSkill(t, map[string]string{
		"SKILL.md": skillMD,
		"references/guide.rst": "See `missing reference <definitely-missing.rst>`_.\n\n" +
			"See `the sibling <sibling.rst>`__ and `wrapped\nlink text <sibling.rst#part>`_.\n",
		"references/sibling.rst": "Sibling\n",
	})
	assertErrors(t, localrefs.Check(dir),
		`references/guide.rst:1: local reference "definitely-missing.rst" does not resolve`)
}

func TestNamedRSTTargets(t *testing.T) {
	dir := writeSkill(t, map[string]string{
		"SKILL.md": skillMD,
		"references/guide.rst": ".. _intro:\n\nIntro\n=====\n\n" +
			"See intro_ and `intro`_ and `text <intro_>`_.\n\n" +
			".. _manual: manual.rst\n" +
			".. _alias: intro_\n" +
			".. _`quoted name`: gone.rst\n" +
			".. __: anon.rst\n\n" +
			"Read manual_ and `quoted name`_ and `anon`__.\n",
		"references/manual.rst": "Manual\n",
		"references/anon.rst":   "Anon\n",
	})
	assertErrors(t, localrefs.Check(dir),
		`references/guide.rst:10: local reference "gone.rst" does not resolve`)
}

func TestFragmentsAndQueriesAreStripped(t *testing.T) {
	dir := writeSkill(t, map[string]string{
		"SKILL.md": skillMD +
			"[a](#same-page) [b](references/x.rst#section) [c](references/x.rst?raw=1)\n" +
			"[d](references/missing.rst#section)\n",
		"references/x.rst": "`e <#local>`__ `f <x.rst#sec>`_ `g <nope.rst#sec>`_\n",
	})
	assertErrors(t, localrefs.Check(dir),
		`SKILL.md:7: local reference "references/missing.rst#section" does not resolve`,
		`references/x.rst:1: local reference "nope.rst#sec" does not resolve`)
}

func TestCodeExamplesAreIgnored(t *testing.T) {
	md := skillMD + "Inline `[x](a.md)` and ``[y](b.md)``.\n\n" +
		"```markdown\n[fenced](c.md)\n```\n\n" +
		"~~~~\n[tilde](d.md)\n~~~~\n\n" +
		"<!-- [commented](e.md) -->\n\n" +
		"  ```\n  [indented fence](f.md)\n  ```\n"
	rst := "Example::\n\n   `lit <g.rst>`_\n   [lit](h.md)\n\nBack to prose.\n\n" +
		".. code:: markdown\n\n   [code](i.md)\n\n   `code <j.rst>`_\n\n" +
		".. code-block:: rst\n   :caption: x\n\n   `k <k.rst>`_\n\n" +
		".. this is a comment `l <l.rst>`_\n   continued [m](m.md)\n\n" +
		"Use ``literal `n <n.rst>`_`` text.\n\n" +
		"```md\n[o](o.md)\n```\n\n" +
		"Section\n~~~~~~~\n\nAfter a ~~~ adornment `p <p.rst>`_ is prose.\n"
	dir := writeSkill(t, map[string]string{
		"SKILL.md":             md,
		"references/guide.rst": rst,
	})
	assertErrors(t, localrefs.Check(dir),
		`references/guide.rst:31: local reference "p.rst" does not resolve`)
}

func TestFrontmatterIsIgnored(t *testing.T) {
	refs := localrefs.ExtractMarkdown("---\nname: x\ndescription: see [a](b.md)\n---\n[c](d.md)\n")
	if got := targets(refs); !reflect.DeepEqual(got, []string{"d.md"}) {
		t.Fatalf("targets = %v", got)
	}
	if refs[0].Line != 5 {
		t.Fatalf("line = %d, want 5", refs[0].Line)
	}
}

func TestPlaceholdersAndExternalTargetsAreSkipped(t *testing.T) {
	dir := writeSkill(t, map[string]string{
		"SKILL.md": skillMD +
			"[a](<name>.md) [b]({slug}.rst) [c]($DIR/file.md) [d](${ROOT}/x) " +
			"[e](path/.../x.md) [f](docs/*.md) [g](…/x.md)\n" +
			"[h](https://example.com/x.md) [i](mailto:user@example.com) [j](//cdn.example.com/x.js) " +
			"[k](data:text/plain,hi) [l](ftp://example.com/x)\n",
		"references/r.rst": "`a <{name}.rst>`_ `b <https://example.org/x.rst>`_ `c <$X.rst>`__\n",
	})
	assertErrors(t, localrefs.Check(dir))
	for _, p := range []string{"<name>.md", "{slug}.rst", "$VAR", "a/.../b", "*.md", "…"} {
		if !localrefs.IsPlaceholder(p) {
			t.Errorf("IsPlaceholder(%q) = false", p)
		}
	}
	for _, p := range []string{"references/x.rst", "a%20b.md", "name_(1).md"} {
		if localrefs.IsPlaceholder(p) {
			t.Errorf("IsPlaceholder(%q) = true", p)
		}
	}
}

func TestNonFileTargetsFail(t *testing.T) {
	dir := writeSkill(t, map[string]string{
		"SKILL.md": skillMD +
			"[a](/docs/config) [b](~/notes.md) [c](../other-skill/SKILL.md) [d]()\n",
	})
	assertErrors(t, localrefs.Check(dir),
		`"/docs/config" is root-absolute`,
		`"~/notes.md" is home-relative`,
		`"../other-skill/SKILL.md" escapes the skill directory`,
		`"" is empty`)
}

func TestEscapingViaReferencesFailsEvenIfFileExists(t *testing.T) {
	root := t.TempDir()
	dir := filepath.Join(root, "demo")
	if err := os.MkdirAll(filepath.Join(dir, "references"), 0o755); err != nil {
		t.Fatal(err)
	}
	if err := os.MkdirAll(filepath.Join(root, "assets"), 0o755); err != nil {
		t.Fatal(err)
	}
	if err := os.WriteFile(filepath.Join(root, "assets", "shot.png"), nil, 0o644); err != nil {
		t.Fatal(err)
	}
	if err := os.WriteFile(filepath.Join(dir, "references", "p.rst"),
		[]byte(".. image:: ../../assets/shot.png\n   :alt: shot\n"), 0o644); err != nil {
		t.Fatal(err)
	}
	assertErrors(t, localrefs.Check(dir), `escapes the skill directory`)
}

func TestExactCaseMatching(t *testing.T) {
	dir := writeSkill(t, map[string]string{
		"SKILL.md":              skillMD + "[a](references/Layout.rst) [b](References/layout.rst)\n",
		"references/layout.rst": "x\n",
	})
	assertErrors(t, localrefs.Check(dir),
		`does not resolve: references/Layout.rst not found`,
		`does not resolve: References not found`)
}

func TestDirectivesAndSubstitutionImages(t *testing.T) {
	dir := writeSkill(t, map[string]string{
		"SKILL.md": skillMD,
		"references/d.rst": ".. image:: ../assets/ok.png\n   :alt: ok\n\n" +
			".. figure:: ../assets/missing.png\n\n   Caption with `link <gone.rst>`_.\n\n" +
			".. include:: part.rst\n\n" +
			".. |icon| image:: data:image/svg+xml;base64,AAAA\n" +
			".. |shot| image:: ../assets/nope.png\n",
		"references/part.rst": "part\n",
		"assets/ok.png":       "png",
	})
	assertErrors(t, localrefs.Check(dir),
		`references/d.rst:4: local reference "../assets/missing.png" does not resolve`,
		`references/d.rst:6: local reference "gone.rst" does not resolve`,
		`references/d.rst:11: local reference "../assets/nope.png" does not resolve`)
}

func TestAdmonitionAndContainerBodiesAreProse(t *testing.T) {
	refs := localrefs.ExtractRST(".. note::\n\n   Read `the wrapped\n   manual <manual.rst>`_.\n\n" +
		".. container:: language-toml highlight\n\n   ::\n\n      `fake <fake.rst>`_\n\n" +
		".. admonition:: More\n\n   Read `details <details.rst>`__.\n")
	if got := targets(refs); !reflect.DeepEqual(got, []string{"manual.rst", "details.rst"}) {
		t.Fatalf("targets = %v", got)
	}
	if refs[0].Line != 4 {
		t.Errorf("wrapped link line = %d, want 4 (the line holding the target)", refs[0].Line)
	}
}

func TestMarkdownFlavouredLinksInRST(t *testing.T) {
	refs := localrefs.ExtractRST("Read [guide](guide.rst) and `code [x](y.md)`.\n\n[def]: def.rst\n")
	if got := targets(refs); !reflect.DeepEqual(got, []string{"guide.rst", "def.rst"}) {
		t.Fatalf("targets = %v", got)
	}
}

func TestMarkdownDestinationSyntax(t *testing.T) {
	refs := localrefs.ExtractMarkdown("[a](<with spaces.md> \"T\") [b](name(1).md) [c](name\\(2\\).md)\n" +
		"\\[not](a-link.md) [d](enc%20oded.md 'T')\n[ref]: ref.md\n[^1]: footnote [e](e.md)\n")
	want := []string{"<with spaces.md>", "name(1).md", "name(2).md", "enc%20oded.md", "ref.md", "e.md"}
	if got := targets(refs); !reflect.DeepEqual(got, want) {
		t.Fatalf("targets = %v, want %v", got, want)
	}
	dir := writeSkill(t, map[string]string{
		"SKILL.md":       skillMD + "[a](<with spaces.md>) [b](enc%20oded.md)\n",
		"with spaces.md": "x",
		"enc oded.md":    "x",
	})
	assertErrors(t, localrefs.Check(dir))
}

func TestEntrypointOverrideResolvesFromSkillRoot(t *testing.T) {
	dir := writeSkill(t, map[string]string{
		"SKILL.md": skillMD + "See [codex](references/codex.rst).\n",
		"references/codex.rst": "Read [references/subagent.rst](references/subagent.rst) and\n" +
			"[missing](references/missing.rst).\n",
		"references/subagent.rst": "x\n",
		"references/other.rst":    "Read [x](references/subagent.rst).\n",
	})
	assertErrors(t, localrefs.Check(dir),
		`references/codex.rst:2: local reference "references/missing.rst" does not resolve`,
		`references/other.rst:1: local reference "references/subagent.rst" does not resolve: references/references not found`)
}

func TestIndependentOfWorkingDirectory(t *testing.T) {
	dir := writeSkill(t, map[string]string{
		"SKILL.md":              skillMD + "[ok](references/a.rst) [bad](references/b.rst)\n",
		"references/a.rst":      "`up <../SKILL.md>`_\n",
		"elsewhere/decoy/b.rst": "decoy",
	})
	want := localrefs.Check(dir)
	assertErrors(t, want, `"references/b.rst" does not resolve`)

	// A decoy references/b.rst in the working directory must not satisfy the
	// link, and a relative skill path must give identical results.
	unrelated := t.TempDir()
	if err := os.MkdirAll(filepath.Join(unrelated, "references"), 0o755); err != nil {
		t.Fatal(err)
	}
	if err := os.WriteFile(filepath.Join(unrelated, "references", "b.rst"), nil, 0o644); err != nil {
		t.Fatal(err)
	}
	t.Chdir(unrelated)
	if got := localrefs.Check(dir); !reflect.DeepEqual(got, want) {
		t.Fatalf("from unrelated cwd:\n got %v\nwant %v", got, want)
	}
	t.Chdir(filepath.Dir(dir))
	if got := localrefs.Check(filepath.Base(dir)); !reflect.DeepEqual(got, want) {
		t.Fatalf("with relative skill path:\n got %v\nwant %v", got, want)
	}
}

func TestHiddenEntriesAndOtherExtensionsIgnored(t *testing.T) {
	dir := writeSkill(t, map[string]string{
		"SKILL.md":           skillMD,
		".evals/notes.md":    "[x](missing.md)\n",
		"scripts/readme.txt": "[x](missing.md)\n",
		"assets/tpl.MD":      "[x](missing.md)\n",
	})
	assertErrors(t, localrefs.Check(dir), `assets/tpl.MD:1: local reference "missing.md"`)
}

func TestDirectoryTargetsResolve(t *testing.T) {
	dir := writeSkill(t, map[string]string{
		"SKILL.md":         skillMD + "[refs](references/) [self](.) [scripts](./scripts)\n",
		"references/a.rst": "x\n",
		"scripts/run.sh":   "#!/bin/sh\n",
	})
	assertErrors(t, localrefs.Check(dir))
}
