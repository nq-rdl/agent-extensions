# Properties (Frontmatter) Reference

Properties use YAML frontmatter at the start of a note:

```yaml
---
date: 2024-01-15
tags:
  - project
  - important
aliases:
  - My Note
  - Alternative Name
cssclasses:
  - custom-class
status: in-progress
rating: 4.5
completed: false
due: 2024-02-01T14:30:00
---
```

## Property Types

| Type | Example |
|------|---------|
| Text | `status: in-progress` |
| Number | `rating: 4.5` |
| Checkbox | `completed: true` |
| Date | `date: 2024-01-15` |
| Date & Time | `due: 2024-01-15T14:30:00` |
| List | `tags: [one, two]` or YAML list |
| Links | `related: "[[Other Note]]"` |

## Default Properties

- `tags` - Note tags (searchable, shown in graph view)
- `aliases` - Alternative names for the note (used in link suggestions)
- `cssclasses` - CSS classes applied to the note in reading/editing view

All other names (for example `title`, `date`, `status`) are custom properties. A
`title` property does not change the note title, which is the file name. The
singular `tag`, `alias`, and `cssclass` keys were deprecated in 1.4 and are no
longer recognized from 1.9; these three properties must be lists.

## Tags

```markdown
#tag
#nested/tag
#tag-with-dashes
#tag_with_underscores
```

Tags can contain: letters, numbers, underscores `_`, hyphens `-`, forward slashes `/` (for nesting), and common Unicode characters including emoji. No spaces. A tag must contain at least one non-numeric character: `#1984` is invalid, `#y1984` is valid.

In frontmatter:

```yaml
---
tags:
  - tag1
  - nested/tag2
---
```
