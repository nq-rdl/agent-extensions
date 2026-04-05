# Writerside Linting Strategy

How to handle documentation quality checks and linting for Writerside projects. This addresses the question: **"How do we handle linting?"**

---

## Approach: Writerside Inspections as Primary Linter

Writerside has a **built-in inspection engine** that serves as the primary linting tool. Unlike code linting where you choose an external tool (ESLint, Ruff, etc.), Writerside's inspections are tightly integrated with the markup schema and cannot be fully replicated by external tools.

**Why Writerside inspections are sufficient as the primary linter:**
- They validate against the actual Writerside XML schema (no external tool knows these tags)
- They check cross-topic references, includes, and anchors
- They catch structural issues (empty chapters, orphaned topics, duplicate IDs)
- They run identically in IDE, preview, and Docker builds

---

## Linting Layers

### Layer 1: IDE Inspections (Author Time)

Writerside's IDE plugin provides real-time linting as you type:

| Check | What It Catches |
|-------|----------------|
| Schema validation | Unknown tags, invalid attributes, wrong nesting |
| Reference resolution | Broken links, missing includes, undefined anchors |
| ID uniqueness | Duplicate `id` attributes across topics |
| Image validation | Missing image files, missing `alt` text |
| Variable resolution | Undefined or unused variables |

**How to use:** Open topics in IntelliJ IDEA / Writerside IDE. Problems appear as underlines and in the Problems tool window.

### Layer 2: Build-Time Checks (CI/CD)

The Docker builder runs the same inspections during builds and reports all problems to console output:

```bash
docker run --rm \
  -v .:/opt/sources \
  -e SOURCE_DIR=/opt/sources \
  -e MODULE_INSTANCE=Writerside/hi \
  -e OUTPUT_DIR=/opt/sources/output \
  -e RUNNER=other \
  jetbrains/writerside-builder:2026.02.8644
```

Build errors produce a non-zero exit code — use this as a CI quality gate.

### Layer 3: Optional External Tools

For teams wanting additional coverage beyond Writerside's built-in checks:

| Tool | Purpose | What It Adds |
|------|---------|-------------|
| **xmllint** | XML well-formedness | Catches malformed XML before Writerside processes it |
| **Vale** | Prose style linting | Enforces writing style rules (tone, jargon, passive voice) |
| **markdownlint** | Markdown style | Consistent Markdown formatting in `.md` topic files |
| **linkchecker** | External link validation | Verifies external URLs haven't gone stale |

**When to add external tools:**
- Add **Vale** if your team has a style guide (e.g., Microsoft Style Guide, Google Developer Docs)
- Add **xmllint** if contributors edit `.topic` files outside the Writerside IDE
- Add **linkchecker** if your docs reference many external URLs
- Skip external tools if your team works exclusively in the Writerside IDE

---

## Suppressing Inspections

When Writerside reports false positives or intentional patterns, suppress specific checks in `buildprofiles.xml`:

```xml
<variables>
    <ignore-problems>
        duplicate-id,missing-alt-text
    </ignore-problems>
</variables>
```

**Guidelines for suppression:**
- Only suppress warnings, not errors
- Document why each suppression exists (comment in the XML)
- Review suppressions quarterly — they can mask real issues over time

---

## Recommended Workflow

### For Authors

1. **Write in the Writerside IDE** — inspections run in real-time
2. **Fix all red underlines** before committing (errors)
3. **Review yellow underlines** and fix where appropriate (warnings)
4. **Preview locally** to catch cross-topic issues
5. **Commit** with confidence that the CI build will pass

### For CI/CD

```yaml
# GitHub Actions example
name: Docs Lint
on: [pull_request]

jobs:
  lint-docs:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4

      - name: Build and lint documentation
        run: |
          docker run --rm \
            -v ${{ github.workspace }}:/opt/sources \
            -e SOURCE_DIR=/opt/sources \
            -e MODULE_INSTANCE=Writerside/hi \
            -e OUTPUT_DIR=/opt/sources/output \
            -e RUNNER=github \
            jetbrains/writerside-builder:2026.02.8644

      # Optional: Vale prose linting
      # - name: Prose style check
      #   uses: errata-ai/vale-action@v2
      #   with:
      #     files: Writerside/topics/
```

### For Reviewers

When reviewing Writerside documentation PRs, check:
- [ ] CI build passed (Writerside inspections clean)
- [ ] No suppressed inspections added without justification
- [ ] New topics are included in the documentation tree
- [ ] Procedures use `<procedure>` and `<step>` tags (not plain numbered lists)
- [ ] Code samples use `<code-block>` with correct `lang` attribute
- [ ] XML/HTML examples are wrapped in CDATA sections

---

## Summary

| Question | Answer |
|----------|--------|
| What is the primary linter? | Writerside's built-in inspections |
| Do we need external linting tools? | Not required, but optional for prose style (Vale) or XML validation (xmllint) |
| How do we lint in CI? | Docker build with `jetbrains/writerside-builder` — errors fail the build |
| How do we suppress false positives? | `<ignore-problems>` in `buildprofiles.xml` |
| What about prose quality? | Optional: use Vale with a style guide configuration |
