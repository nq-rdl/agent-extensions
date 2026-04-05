# Writerside Lists Reference

Writerside supports unordered lists, ordered lists, multi-column lists, nested lists, and definition lists. Most list types work in both Markdown and XML modes.

---

## Unordered Lists

**Markdown:**
```markdown
- Item one
- Item two
- Item three
```

**XML:**
```xml
<list>
    <li>Item one</li>
    <li>Item two</li>
    <li>Item three</li>
</list>
```

---

## Ordered Lists

**Markdown:**
```markdown
1. First step
2. Second step
3. Third step
```

**XML** — use `type="decimal"`:
```xml
<list type="decimal">
    <li>First step</li>
    <li>Second step</li>
    <li>Third step</li>
</list>
```

Start at a number other than 1 with `start="2"`:
```xml
<list type="decimal" start="2">
    <li>Second step</li>
    <li>Third step</li>
</list>
```

---

## Nested Lists

Use `type="alpha-lower"` for second-level ordered lists (renders as a, b, c):

**Markdown:**
```markdown
1. First item
   - Sub-item A
   - Sub-item B
2. Second item
```

**XML:**
```xml
<list type="decimal">
    <li>First item
        <list type="alpha-lower">
            <li>Sub-item A</li>
            <li>Sub-item B</li>
        </list>
    </li>
    <li>Second item</li>
</list>
```

---

## Multi-Column Lists

For long lists of short items, render across multiple columns to reduce vertical space:

**Markdown:**
```markdown
- Alpha
- Beta
- Gamma
- Delta
{columns="3"}
```

**XML:**
```xml
<list columns="3">
    <li>Alpha</li>
    <li>Beta</li>
    <li>Gamma</li>
    <li>Delta</li>
</list>
```

---

## Definition Lists

Definition lists pair terms with definitions. Use them for commands, options, parameters, API endpoints, and glossaries.

**Markdown:**
```markdown
Term one
: Definition for term one.

Term two
: Definition for term two. Can span
  multiple lines.
```

**XML:**
```xml
<deflist type="medium">
    <def title="Term one">
        Definition for term one.
    </def>
    <def title="Term two">
        Definition for term two.
    </def>
</deflist>
```

### Definition List Types

| Type | Layout | Best for |
|------|--------|----------|
| `full` (default) | Title on its own line | FAQs, longer definitions |
| `wide` | 1:1 ratio | REST API endpoints |
| `medium` | 1:2 ratio | Methods, functions |
| `narrow` | 2:7 ratio | CLI options, flags |
| `compact` | 1:8 ratio | Abbreviations, short definitions |

**Collapsible definition list** — useful for long reference lists:
```xml
<deflist type="narrow" collapsible="true" default-state="collapsed">
    <def title="--verbose">Enable verbose output.</def>
    <def title="--dry-run">Preview changes without applying them.</def>
</deflist>
```

**Sorted alphabetically:**
```xml
<deflist type="medium" sorted="true">
    ...
</deflist>
```

---

## Best Practices

- Write an introductory sentence before every list — do not start a section with a bare list.
- Aim for 2–8 items per list. Longer lists benefit from definition list or table format.
- Keep list items parallel in structure (all noun phrases, or all imperative sentences).
- Use `<procedure>` and `<step>` instead of an ordered list for task instructions — procedures render with stronger visual separation and are semantically distinct.
- Avoid nesting more than two levels deep.
