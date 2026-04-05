# Writerside Documentation Quality

Reference for Writerside's built-in quality inspections, how to configure them, and how to integrate quality checks into your workflow.

---

## Overview

Writerside provides documentation quality checks at three levels:

1. **IDE editor** — Real-time inspections highlight problems as you type
2. **Local preview** — The Preview tool window lists all problems found in rendered topics
3. **Docker build** — The builder analyzes every topic and reports problems to console output

All three levels run the same inspection engine, so issues caught in the IDE will also be caught during builds.

---

## Inspection Categories

| Category | What It Checks | Examples |
|----------|---------------|----------|
| **Markup validity** | XML/Markdown well-formedness, valid tag usage | Unclosed tags, unknown elements, invalid nesting |
| **References** | Internal links, anchors, includes | Broken `<a href>`, missing `element-id` in `<include>` |
| **IDs** | Uniqueness and validity of element identifiers | Duplicate `id` attributes, invalid ID characters |
| **Images** | Image file references and accessibility | Missing `src` files, missing `alt` text |
| **Structure** | Topic and chapter organization | Empty chapters, orphaned topics not in tree |
| **Variables** | Variable definitions and usage | Undefined variables, unused variable definitions |

---

## Running Quality Checks

### In the IDE

Inspections run automatically in the editor. Problems appear as:
- **Red underlines** — Errors that will break the build
- **Yellow underlines** — Warnings about potential issues
- **Weak warnings** — Style suggestions

Use **Ctrl+Q** (Quick Documentation) on any element to see its valid attributes and usage.

Use **Alt+Insert** to generate valid markup for tables, images, and links.

### In Local Preview

Open the Preview tool window to see a list of all problems found across rendered topics. This catches issues that only appear in the built output (e.g., broken cross-topic links).

### In Docker Builds

The Docker builder reports all problems to console output. In CI/CD pipelines, you can parse this output to fail builds on errors:

```bash
docker run --rm \
  -v .:/opt/sources \
  -e SOURCE_DIR=/opt/sources \
  -e MODULE_INSTANCE=Writerside/hi \
  -e OUTPUT_DIR=/opt/sources/output \
  -e RUNNER=other \
  jetbrains/writerside-builder:2026.02.8644 2>&1 | tee build.log

# Check for errors in build output
if grep -q "ERROR" build.log; then
  echo "Documentation build has errors"
  exit 1
fi
```

---

## Suppressing Inspections

### Per-Build Suppression

In `buildprofiles.xml`, use the `<ignore-problems>` element to suppress specific problem IDs:

```xml
<variables>
    <ignore-problems>
        duplicate-id,missing-alt-text
    </ignore-problems>
</variables>
```

Provide a comma-separated list of problem IDs to suppress.

### When to Suppress

- **Acceptable:** Suppressing warnings for known limitations or intentional patterns
- **Not recommended:** Suppressing errors — these indicate real build problems
- **Review regularly:** Suppressed warnings can mask legitimate issues over time

---

## Quality Workflow

### Recommended Process

1. **Author with IDE inspections active** — Fix errors and warnings as you write
2. **Preview locally** — Check the rendered output and review the problems list
3. **Commit and build** — Docker build catches any remaining issues
4. **CI gate** — Fail the pipeline if the build reports errors

### Pre-Commit Checklist

Before committing documentation changes:

- [ ] No red underlines in the IDE editor
- [ ] Local preview renders correctly
- [ ] All internal links resolve (check Preview problems list)
- [ ] Images referenced in topics exist in the project
- [ ] No duplicate IDs across topics

---

## CI/CD Integration

### GitHub Actions Example

```yaml
name: Docs Quality
on: [pull_request]

jobs:
  build-docs:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4

      - name: Build and check documentation
        run: |
          docker run --rm \
            -v ${{ github.workspace }}:/opt/sources \
            -e SOURCE_DIR=/opt/sources \
            -e MODULE_INSTANCE=Writerside/hi \
            -e OUTPUT_DIR=/opt/sources/output \
            -e RUNNER=github \
            jetbrains/writerside-builder:2026.02.8644

      - name: Upload artifacts
        uses: actions/upload-artifact@v4
        with:
          name: docs
          path: output/
```

Build errors will cause the Docker container to exit with a non-zero code, failing the CI step automatically.

---

## Common Issues and Fixes

| Problem | Cause | Fix |
|---------|-------|-----|
| "Unknown element" | Using a tag not in the Writerside schema | Check [markup-reference.md](markup-reference.md) for valid tags |
| "Duplicate ID" | Two elements share the same `id` value | Rename one of the duplicate IDs |
| "Unresolved reference" | `<a href>` or `<include>` points to missing target | Verify the target topic/element exists |
| "Empty chapter" | `<chapter>` with no content inside | Add content or remove the empty chapter |
| "Missing alt text" | `<img>` without `alt` attribute | Add descriptive `alt` text to all images |
