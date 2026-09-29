# Bases Examples

Complete bases and view snippets to adapt. The rules in SKILL.md still apply:
one key per filter object, `.days` before rounding, guarded optional
properties, and single quotes around formulas that contain double quotes.

Contents:

- [Reading list (cards and table)](#reading-list-cards-and-table)
- [Daily notes index](#daily-notes-index)
- [View snippets](#view-snippets): table, cards, list, map

## Reading list (cards and table)

```yaml
filters:
  or:
    - file.hasTag("book")
    - file.hasTag("article")

formulas:
  reading_time: 'if(pages, (pages * 2).toString() + " min", "")'
  status_icon: 'if(status == "reading", "📖", if(status == "done", "✅", "📚"))'
  year_read: 'if(finished_date, date(finished_date).year, "")'

properties:
  author:
    displayName: Author
  formula.status_icon:
    displayName: ""
  formula.reading_time:
    displayName: "Est. Time"

views:
  - type: cards
    name: "Library"
    order:
      - cover
      - file.name
      - author
      - formula.status_icon
    filters:
      not:
        - 'status == "dropped"'

  - type: table
    name: "Reading List"
    filters:
      and:
        - 'status == "to-read"'
    order:
      - file.name
      - author
      - pages
      - formula.reading_time
```

## Daily notes index

```yaml
filters:
  and:
    - file.inFolder("Daily Notes")
    - '/^\d{4}-\d{2}-\d{2}$/.matches(file.basename)'

formulas:
  word_estimate: '(file.size / 5).round(0)'
  day_of_week: 'date(file.basename).format("dddd")'

properties:
  formula.day_of_week:
    displayName: "Day"
  formula.word_estimate:
    displayName: "~Words"

views:
  - type: table
    name: "Recent Notes"
    limit: 30
    order:
      - file.name
      - formula.day_of_week
      - formula.word_estimate
      - file.mtime
```

## View snippets

### Table

```yaml
views:
  - type: table
    name: "My Table"
    order:
      - file.name
      - status
      - due_date
    summaries:
      price: Sum
      count: Average
```

### Cards

```yaml
views:
  - type: cards
    name: "Gallery"
    order:
      - file.name
      - cover_image
      - description
```

### List (Obsidian 1.10+)

```yaml
views:
  - type: list
    name: "Simple List"
    order:
      - file.name
      - status
```

### Map (Obsidian 1.10+ and the official Maps plugin)

Notes need latitude and longitude properties. Configure which properties hold
the coordinates in the view settings; see
https://help.obsidian.md/bases/views/map for the current options.

```yaml
views:
  - type: map
    name: "Locations"
```
