package orchestrate

import (
	"os"
	"path/filepath"
	"testing"
)

const singleFilePatch = `diff --git a/foo/bar.go b/foo/bar.go
index abc..def 100644
--- a/foo/bar.go
+++ b/foo/bar.go
@@ -1,3 +1,4 @@
 package foo
+
+// added line
`

const newFilePatch = `diff --git a/new/file.go b/new/file.go
new file mode 100644
index 000..abc
--- /dev/null
+++ b/new/file.go
@@ -0,0 +1,3 @@
+package new
+
+// new file
`

const multiFilePatch = `diff --git a/alpha.go b/alpha.go
index aaa..bbb 100644
--- a/alpha.go
+++ b/alpha.go
@@ -1 +1,2 @@
 package main
+// alpha
diff --git a/beta.go b/beta.go
index ccc..ddd 100644
--- a/beta.go
+++ b/beta.go
@@ -1 +1,2 @@
 package main
+// beta
`

func TestSplitPatch_empty(t *testing.T) {
	got := SplitPatch("")
	if len(got) != 0 {
		t.Errorf("SplitPatch(\"\") = %v, want empty", got)
	}
}

func TestSplitPatch_singleFile(t *testing.T) {
	got := SplitPatch(singleFilePatch)
	if len(got) != 1 {
		t.Fatalf("SplitPatch single file: got %d files, want 1", len(got))
	}
	if got[0].Path != "foo/bar.go" {
		t.Errorf("path = %q, want %q", got[0].Path, "foo/bar.go")
	}
	if got[0].IsNewFile {
		t.Errorf("IsNewFile should be false for existing file diff")
	}
}

func TestSplitPatch_multiFile(t *testing.T) {
	got := SplitPatch(multiFilePatch)
	if len(got) != 2 {
		t.Fatalf("SplitPatch multi file: got %d files, want 2", len(got))
	}
	if got[0].Path != "alpha.go" {
		t.Errorf("got[0].Path = %q, want %q", got[0].Path, "alpha.go")
	}
	if got[1].Path != "beta.go" {
		t.Errorf("got[1].Path = %q, want %q", got[1].Path, "beta.go")
	}
}

func TestSplitPatch_newFile(t *testing.T) {
	got := SplitPatch(newFilePatch)
	if len(got) != 1 {
		t.Fatalf("SplitPatch new file: got %d files, want 1", len(got))
	}
	if !got[0].IsNewFile {
		t.Errorf("IsNewFile should be true for new file diff")
	}
	if got[0].Path != "new/file.go" {
		t.Errorf("path = %q, want %q", got[0].Path, "new/file.go")
	}
}

func TestIsNewFile(t *testing.T) {
	if !IsNewFile(newFilePatch) {
		t.Errorf("IsNewFile(newFilePatch) = false, want true")
	}
	if IsNewFile(singleFilePatch) {
		t.Errorf("IsNewFile(singleFilePatch) = true, want false")
	}
}

func TestIsStub_newFileLargerOnDisk(t *testing.T) {
	dir := t.TempDir()
	path := filepath.Join(dir, "new/file.go")
	if err := os.MkdirAll(filepath.Dir(path), 0o755); err != nil {
		t.Fatal(err)
	}
	if err := os.WriteFile(path, []byte("package new\n\n// placeholder\n// TODO: implement\n"), 0o644); err != nil {
		t.Fatal(err)
	}

	pf := PatchFile{Path: "new/file.go", Diff: newFilePatch, IsNewFile: true}
	got, err := IsStub(pf, dir)
	if err != nil {
		t.Fatalf("IsStub unexpected error: %v", err)
	}
	if !got {
		t.Errorf("IsStub = false, want true (existing file is larger than patched file)")
	}
}

func TestIsStub_newFileSmallerOnDisk(t *testing.T) {
	dir := t.TempDir()
	path := filepath.Join(dir, "new/file.go")
	if err := os.MkdirAll(filepath.Dir(path), 0o755); err != nil {
		t.Fatal(err)
	}
	if err := os.WriteFile(path, []byte("package new\n"), 0o644); err != nil {
		t.Fatal(err)
	}

	pf := PatchFile{Path: "new/file.go", Diff: newFilePatch, IsNewFile: true}
	got, err := IsStub(pf, dir)
	if err != nil {
		t.Fatalf("IsStub unexpected error: %v", err)
	}
	if got {
		t.Errorf("IsStub = true, want false (existing file is smaller than patched file)")
	}
}

func TestIsStub_newFileNotOnDisk(t *testing.T) {
	dir := t.TempDir()
	pf := PatchFile{Path: "new/file.go", Diff: newFilePatch, IsNewFile: true}
	got, err := IsStub(pf, dir)
	if err != nil {
		t.Fatalf("IsStub unexpected error: %v", err)
	}
	if got {
		t.Errorf("IsStub = true, want false (file not on disk)")
	}
}

func TestIsStub_existingFilePatch(t *testing.T) {
	dir := t.TempDir()
	pf := PatchFile{Path: "foo/bar.go", Diff: singleFilePatch, IsNewFile: false}
	got, err := IsStub(pf, dir)
	if err != nil {
		t.Fatalf("IsStub unexpected error: %v", err)
	}
	if got {
		t.Errorf("IsStub = true, want false (not a new file)")
	}
}
