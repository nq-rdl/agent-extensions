# Writerside Topics Reference

Topic files are the fundamental unit of Writerside content. Each topic becomes one page in the published documentation.

---

## File Formats

| Format | Extension | Best For |
|--------|-----------|----------|
| Markdown | `.md` | Small docs, quick content, teams familiar with Markdown |
| Semantic XML | `.topic` | Large projects, extensive reuse, formal documentation |

Projects can mix both formats freely — no migration needed.

**Markdown** uses CommonMark with optional embedded XML tags. Title is defined as the first `#` heading.

**Semantic XML** uses Writerside's structured element schema. Title is declared in the root `<topic>` tag.

---

## Topic IDs

Every topic has an ID derived from its filename (without extension). The ID must be unique within a help module.

- `getting-started.md` → ID: `getting-started`
- `getting-started.topic` → ID declared explicitly: `id="getting-started"`

IDs are used for cross-references, includes, and TOC entries:

```xml
<!-- In tree file -->
<toc-element topic="getting-started.topic"/>

<!-- As a link -->
<a href="getting-started.topic"/>

<!-- For content inclusion -->
<include from="getting-started.topic" element-id="intro"/>
```

---

## XML Topic Structure

```xml
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE topic SYSTEM "https://resources.jetbrains.com/writerside/1.0/xhtml-entities.dtd">
<topic title="Getting Started" id="getting-started"
       xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance"
       xsi:noNamespaceSchemaLocation="https://resources.jetbrains.com/writerside/1.0/topic.v2.xsd">

    <tldr>
        <p>Quick summary of this topic.</p>
    </tldr>

    <chapter title="Overview" id="overview">
        <p>Content here.</p>
    </chapter>

</topic>
```

---

## Metadata Attributes

| Attribute | Location | Purpose |
|-----------|----------|---------|
| `title` | XML root tag or MD `#` heading | Display title and default TOC entry |
| `id` | XML root tag | Unique identifier (XML only, explicit) |
| `toc-title` | `<toc-element>` | Shortened TOC-specific label (overrides title in sidebar) |
| `instance` | `<title instance="...">` | Instance-specific title override |
| `web-file-name` | `<web-file-name>` element | Custom HTML output filename for SEO |

**Custom web filename:**
```xml
<topic title="Setup Guide" id="setup">
    <web-file-name>setup-guide</web-file-name>
    ...
</topic>
```

Default: `Document_everything.topic` → `document-everything.html` (lowercased, special chars replaced with dashes).

---

## When to Use Each Format

Choose **Markdown** when:
- Speed matters more than structure
- Contributors are not comfortable with XML
- The doc set is small or standalone
- Content is not reused across instances

Choose **Semantic XML** when:
- Structure and reuse are priorities
- Content is shared across multiple instances via `<include>`
- The team includes professional technical writers
- You need fine-grained element filtering (`instance`, `filter`)
