---
name: quarto-authoring
license: MIT
description: >-
  Writing and authoring Quarto documents (.qmd), including code cell options,
  figure and table captions, cross-references, callout blocks (notes, warnings,
  tips), citations and bibliography, page layout and columns, Mermaid diagrams,
  YAML metadata configuration, and Quarto extensions. Also covers converting and
  migrating R Markdown (.Rmd), bookdown, blogdown, xaringan, and distill projects
  to Quarto, and creating Quarto websites, books, presentations, and reports.
metadata:
  repo: https://github.com/nq-rdl/agent-skills
---

# Quarto Authoring

> This skill is based on Quarto CLI v1.8.26.

## When to Use What

Task: Write a new Quarto document
Use: Follow "QMD Essentials" below, then see specific reference files

Task: Convert R Markdown to Quarto
Use: [references/conversion-rmarkdown.rst](references/conversion-rmarkdown.rst)

Task: Migrate bookdown project
Use: [references/conversion-bookdown.rst](references/conversion-bookdown.rst)

Task: Migrate xaringan slides
Use: [references/conversion-xaringan.rst](references/conversion-xaringan.rst)

Task: Migrate distill article
Use: [references/conversion-distill.rst](references/conversion-distill.rst)

Task: Migrate blogdown site
Use: [references/conversion-blogdown.rst](references/conversion-blogdown.rst)

Task: Add cross-references
Use: [references/cross-references.rst](references/cross-references.rst)

Task: Configure code cells
Use: [references/code-cells.rst](references/code-cells.rst)

Task: Add figures with captions
Use: [references/figures.rst](references/figures.rst)

Task: Create tables
Use: [references/tables.rst](references/tables.rst)

Task: Add citations and bibliography
Use: [references/citations.rst](references/citations.rst)

Task: Add callout blocks
Use: [references/callouts.rst](references/callouts.rst)

Task: Add diagrams (Mermaid, Graphviz)
Use: [references/diagrams.rst](references/diagrams.rst)

Task: Control page layout
Use: [references/layout.rst](references/layout.rst)

Task: Use shortcodes
Use: [references/shortcodes.rst](references/shortcodes.rst)

Task: Add conditional content
Use: [references/conditional-content.rst](references/conditional-content.rst)

Task: Use divs and spans
Use: [references/divs-and-spans.rst](references/divs-and-spans.rst)

Task: Configure YAML front matter
Use: [references/yaml-front-matter.rst](references/yaml-front-matter.rst)

Task: Find and use extensions
Use: [references/extensions.rst](references/extensions.rst)

Task: Apply markdown linting rules
Use: [references/markdown-linting.rst](references/markdown-linting.rst)

## QMD Essentials

### Basic Document Structure

```markdown
---
title: "Document Title"
author: "Author Name"
date: today
format: html
---

Content goes here.
```

A Quarto document consists of two main parts:

1. **YAML Front Matter**: Metadata and configuration at the top, enclosed by `---`.
2. **Markdown Content**: Main body using standard markdown syntax.

### Divs and Spans

Divs use fenced syntax with three colons:

```markdown
::: {.class-name}
Content inside the div.
:::
```

Spans use bracketed syntax:

```markdown
This is [important text]{.highlight}.
```

Details: [references/divs-and-spans.rst](references/divs-and-spans.rst)

### Code Cell Options Syntax

A code cell starts with triple backticks and a language identifier between curly braces.
Code cells are code blocks that can be executed to produce output.

Quarto uses the language's comment symbol + `|` for cell options. Options use **dashes, not dots** (e.g., `fig-cap` not `fig.cap`).

- R, Python: `#|`
- Mermaid: `%%|`
- Graphviz/DOT: `//|`

````markdown
```{r}
#| label: fig-example
#| echo: false
#| fig-cap: "A scatter plot example."

plot(x, y)
```
````

Common execution options:

| Option    | Description       | Values                    |
| --------- | ----------------- | ------------------------- |
| `eval`    | Evaluate code     | `true`, `false`           |
| `echo`    | Show code         | `true`, `false`, `fenced` |
| `output`  | Include output    | `true`, `false`, `asis`   |
| `warning` | Show warnings     | `true`, `false`           |
| `error`   | Show errors       | `true`, `false`           |
| `include` | Include in output | `true`, `false`           |

Set document-level defaults in YAML front matter:

```yaml
execute:
  echo: false
  warning: false
```

Details: [references/code-cells.rst](references/code-cells.rst)

### Cross-References

Labels must start with a type prefix. Reference with `@`:

- Figure: `fig-` prefix, e.g., `#| label: fig-plot` → `@fig-plot`
- Table: `tbl-` prefix, e.g., `#| label: tbl-data` → `@tbl-data`
- Section: `sec-` prefix, e.g., `{#sec-intro}` → `@sec-intro`
- Equation: `eq-` prefix, e.g., `{#eq-model}` → `@eq-model`

````markdown
```{r}
#| label: fig-plot
#| fig-cap: "A caption for the plot."
plot(1)
```

See @fig-plot for the results.
````

Details: [references/cross-references.rst](references/cross-references.rst)

### Callout Blocks

Five types: `note`, `warning`, `important`, `tip`, `caution`.

```markdown
::: {.callout-note}
This is a note callout.
:::

::: {.callout-warning}

## Custom Title

This is a warning with a custom title.

:::
```

Details: [references/callouts.rst](references/callouts.rst)

### Figures

```markdown
![Caption text](image.png){#fig-name fig-alt="Alt text"}
```

Subfigures:

```markdown
::: {#fig-group layout-ncol=2}
![Sub caption 1](image1.png){#fig-sub1}

![Sub caption 2](image2.png){#fig-sub2}

Main caption for the group.
:::
```

Details: [references/figures.rst](references/figures.rst)

### Tables

```markdown
::: {#tbl-example}

| Column 1 | Column 2 |
| -------- | -------- |
| Data 1   | Data 2   |

Table caption.
:::
```

Details: [references/tables.rst](references/tables.rst)

### Citations

```markdown
According to @smith2020, the results show...
Multiple citations [@smith2020; @jones2021].
```

Configure in YAML:

```yaml
bibliography: references.bib
csl: apa.csl
```

Details: [references/citations.rst](references/citations.rst)

## Common Workflows

### Creating an HTML Document

```yaml
title: "My Report"
author: "Your Name"
date: today
format:
  html:
    toc: true
    code-fold: true
    theme: cosmo
```

### Creating a PDF Document

```yaml
title: "My Report"
format:
  pdf:
    documentclass: article
    papersize: a4
```

### Creating a RevealJS Presentation

```markdown
---
title: "My Presentation"
format: revealjs
---

## First Slide

Content here.

## Second Slide

More content.
```

### Setting Up a Quarto Project

Create `_quarto.yml` in the project root:

```yaml
project:
  type: website

website:
  title: "My Site"
  navbar:
    left:
      - href: index.qmd
        text: Home
      - href: about.qmd
        text: About

format:
  html:
    theme: cosmo
```

## Resources

<!-- lychee-ignore -->
- [Quarto Documentation](https://quarto.org/)
- [Quarto Guide](https://quarto.org/docs/guide/)
<!-- lychee-ignore -->
- [Quarto Extensions](https://quarto.org/docs/extensions/)
- [Community Extensions List](https://m.canouil.dev/quarto-extensions/)
