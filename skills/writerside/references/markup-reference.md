# Writerside Semantic Markup Reference

Complete reference for Writerside's XML semantic markup tags. These tags work in both `.topic` files and embedded within `.md` files.

---

## Topic Root

Every `.topic` file starts with the `<topic>` root element:

```xml
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE topic SYSTEM "https://resources.jetbrains.com/writerside/1.0/xhtml-entities.dtd">
<topic title="Getting Started" id="getting-started" xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance"
       xsi:noNamespaceSchemaLocation="https://resources.jetbrains.com/writerside/1.0/topic.v2.xsd">

    <!-- content here -->

</topic>
```

Markdown files do not need a root element — Writerside wraps them automatically.

---

## Block Elements

### Structure

| Tag | Purpose | Key Attributes |
|-----|---------|---------------|
| `<chapter>` | Hierarchical section (renders as heading + content) | `title`, `id`, `collapsible`, `default-state` |
| `<procedure>` | Ordered step sequence for task instructions | `title`, `id`, `type` (sequence/choices), `collapsible` |
| `<step>` | Individual action within a procedure | — |
| `<p>` | Paragraph | `id` |
| `<title>` | Override element title (for instance filtering) | `instance` |

**Chapter example:**

```xml
<chapter title="Installation" id="installation">
    <p>Follow these steps to install the application.</p>

    <chapter title="Prerequisites" id="prerequisites">
        <p>Ensure you have the following installed:</p>
    </chapter>
</chapter>
```

**Procedure example:**

```xml
<procedure title="Deploy the Service" id="deploy-service">
    <step>
        Clone the repository: <code>git clone https://github.com/org/repo.git</code>
    </step>
    <step>
        Copy the configuration template and update environment variables.
    </step>
    <step>
        Run the deployment command: <code>podman-compose up -d</code>
    </step>
</procedure>
```

### Lists and Definitions

| Tag | Purpose | Key Attributes |
|-----|---------|---------------|
| `<list>` | Bullet or numbered list | `type` (bullet/decimal/alpha-lower/none), `columns`, `sorted` |
| `<li>` | List item | — |
| `<deflist>` | Term-definition pairs | `type` (full/wide/medium/narrow/compact), `collapsible`, `sorted` |
| `<def>` | Single definition entry | `title` |

**Definition list example:**

```xml
<deflist type="medium">
    <def title="Instance">
        A build target that produces one documentation website.
    </def>
    <def title="Topic">
        A single page of documentation, authored as .md or .topic.
    </def>
</deflist>
```

### Code

| Tag | Purpose | Key Attributes |
|-----|---------|---------------|
| `<code-block>` | Formatted code with syntax highlighting | `lang`, `src`, `collapsible`, `prompt`, `noinject` |
| `<compare>` | Side-by-side code comparison | `type` (left-right/top-bottom), `first-title`, `second-title` |

**Code block with language:**

```xml
<code-block lang="python">
def hello():
    return "Hello, Writerside!"
</code-block>
```

**XML/HTML code samples — use CDATA to prevent Writerside from processing tags:**

```xml
<code-block lang="xml">
    <![CDATA[
        <procedure title="Example">
            <step>Do something</step>
        </procedure>
    ]]>
</code-block>
```

**Side-by-side comparison:**

```xml
<compare first-title="Before" second-title="After">
    <code-block lang="java">
        System.out.println("old");
    </code-block>
    <code-block lang="java">
        logger.info("new");
    </code-block>
</compare>
```

### Tabs

| Tag | Purpose | Key Attributes |
|-----|---------|---------------|
| `<tabs>` | Container for tabbed content | — |
| `<tab>` | Individual tab | `title`, `id`, `instance` |

```xml
<tabs>
    <tab id="bash" title="Bash">
        <code-block lang="bash">
            echo "Hello"
        </code-block>
    </tab>
    <tab id="powershell" title="PowerShell">
        <code-block lang="powershell">
            Write-Output "Hello"
        </code-block>
    </tab>
</tabs>
```

### Tables

```xml
<table>
    <tr>
        <td>Header 1</td>
        <td>Header 2</td>
    </tr>
    <tr>
        <td>Data 1</td>
        <td>Data 2</td>
    </tr>
</table>
```

### Admonitions

| Tag | Purpose | Rendering |
|-----|---------|-----------|
| `<tip>` | Helpful suggestion or best practice | Green callout |
| `<note>` | Important information or prerequisites | Blue callout |
| `<warning>` | Critical alert about potential problems | Orange/red callout |
| `<tldr>` | Brief summary (Too Long; Didn't Read) | Highlighted summary block |

```xml
<tldr>
    <p>Quick command: <code>podman-compose up -d</code></p>
    <p>Config location: <path>/etc/app/config.yaml</path></p>
</tldr>

<tip>Use environment variables for configuration that changes between deployments.</tip>

<note>Admin privileges are required for this operation.</note>

<warning>This action cannot be undone. Back up your data first.</warning>
```

### Media

| Tag | Purpose | Key Attributes |
|-----|---------|---------------|
| `<img>` | Image with optional thumbnail | `src`, `alt`, `width`, `height`, `thumbnail`, `border-effect` |
| `<video>` | Video embed | `src`, `width`, `height`, `preview-src` |

```xml
<img src="screenshot.png" alt="Application dashboard" width="600" border-effect="rounded"/>
```

### Reuse and Include

| Tag | Purpose | Key Attributes |
|-----|---------|---------------|
| `<snippet>` | Reusable content block | `id`, `filter` |
| `<include>` | Embed content from another topic | `from`, `element-id`, `use-filter`, `nullable` |

```xml
<!-- Define a reusable snippet in a library topic -->
<snippet id="common-prereqs">
    <list>
        <li>Docker installed (v20+)</li>
        <li>Git configured</li>
    </list>
</snippet>

<!-- Include it in another topic -->
<include from="snippets-lib.topic" element-id="common-prereqs"/>
```

---

## Inline Elements

| Tag | Purpose | Example |
|-----|---------|---------|
| `<code>` | Inline code (functions, commands) | `Use <code>git pull</code> to sync` |
| `<emphasis>` | Italic text for concepts or stress | `<emphasis>Required</emphasis> field` |
| `<control>` | GUI element labels (buttons, menus) | `Click <control>OK</control>` |
| `<path>` | File paths and filenames | `<path>/etc/nginx/nginx.conf</path>` |
| `<ui-path>` | UI navigation with chevron separators | `<ui-path>File \| Settings \| Editor</ui-path>` |
| `<shortcut>` | Keyboard shortcut | `<shortcut key="Ctrl+S"/>` |
| `<a>` | Hyperlink (internal or external) | `<a href="guide.topic">See guide</a>` |
| `<var>` | Variable or placeholder | `<var>PROJECT_NAME</var>` |
| `<format>` | Custom styling (bold, italic, color) | `<format style="bold" color="Red">Alert</format>` |
| `<tooltip>` | Hover popup text | `<tooltip>Additional context</tooltip>` |
| `<icon>` | Icon insertion | `<icon src="check.svg" alt="Done"/>` |
| `<math>` | LaTeX formula | `<math>E=mc^2</math>` |

---

## Conditional Content

Use `<if>` to show content for specific instances or filter conditions:

```xml
<if instance="api-docs">
    <p>This section only appears in the API documentation instance.</p>
</if>

<if instance="!api-docs">
    <p>This appears in all instances except API docs.</p>
</if>
```

Filter by custom conditions:

```xml
<if filter="enterprise">
    <p>Enterprise-only feature.</p>
</if>
```

The `instance` attribute can be applied directly to most elements without wrapping in `<if>`:

```xml
<chapter title="Enterprise Setup" id="enterprise-setup" instance="enterprise">
    <p>Only visible in the enterprise instance.</p>
</chapter>
```

---

## Metadata Elements

| Tag | Purpose |
|-----|---------|
| `<link-summary>` | Custom hover text for internal links to this topic |
| `<card-summary>` | Summary text for section page cards |
| `<web-summary>` | Search engine preview text |
| `<seealso>` | "See Also" reference section at topic bottom |
| `<show-structure>` | Render in-page table of contents |
| `<primary-label>` | Badge/label on topic (references `labels.list`) |

```xml
<link-summary>Learn how to configure authentication for the API.</link-summary>
<card-summary>Step-by-step authentication setup guide.</card-summary>

<seealso>
    <category ref="related">
        <a href="api-reference.topic">API Reference</a>
        <a href="troubleshooting.topic">Troubleshooting</a>
    </category>
</seealso>
```

---

## Section Starting Pages

Landing pages for documentation sections use a card-based layout:

```xml
<section-starting-page>
    <title>Developer Guide</title>
    <description>Everything you need to build with our platform.</description>

    <primary>
        <title>Get started</title>
        <a href="quickstart.topic" summary="5-minute setup guide">Quick Start</a>
        <a href="installation.topic" summary="Detailed installation">Installation</a>
    </primary>

    <misc>
        <cards narrow="true">
            <title>Tools</title>
            <a href="cli.topic">CLI Reference</a>
            <a href="sdk.topic">SDK Guide</a>
        </cards>
    </misc>
</section-starting-page>
```

---

## API Documentation

Writerside can generate API docs from OpenAPI specifications:

```xml
<!-- Full API reference from OpenAPI spec -->
<api-doc openapi-path="openapi.yaml" tag="Users"/>

<!-- Single endpoint -->
<api-endpoint endpoint="/users/{id}" method="GET" openapi-path="openapi.yaml"/>

<!-- Schema definition -->
<api-schema openapi-path="openapi.yaml" name="UserResponse"/>
```

---

## Universal Attributes

Most elements support these attributes:

| Attribute | Purpose |
|-----------|---------|
| `id` | Element identifier for anchoring and cross-references |
| `instance` | Filter to specific instances (comma-separated, negate with `!`) |
| `switcher-key` | Content variant selector |
| `filter` | Custom filter reference |
| `ignore-vars` | Disable variable substitution in this element |
