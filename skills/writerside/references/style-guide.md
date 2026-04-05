# Writerside Style Guide Configuration

Writerside's built-in style guide system uses a subset of the Vale syntax. It enforces prose rules at the project level and integrates with the IDE editor for real-time feedback.

---

## Setup

Right-click the project name in the Writerside tool window and select **New | Writerside Style Guide File**. This creates `.wrs-style-guide.yaml` at the project root.

Add `.wrs-style-guide.yaml` files in subdirectories to override parent rules for specific sections.

---

## Rule Types

### existence — Flag unwanted tokens

Flag words or phrases that should be avoided:

```yaml
extends: existence
message: "Avoid '%s' — use simpler language."
level: warning
tokens:
  - utilize
  - leverage
  - in order to
```

### substitution — Recommend replacements

```yaml
extends: substitution
message: "Use '%s' instead of '%s'."
level: warning
swap:
  utilize: use
  leverage: use
  commence: start
  terminate: end|stop
```

Pipes separate multiple alternatives: `end|stop` means either is acceptable.

### occurrence — Limit frequency

```yaml
extends: occurrence
message: "Sentence exceeds %s words."
level: suggestion
max: 30
token: '\b\w+\b'
scope: sentence
```

### conditional — Require co-occurrence

```yaml
extends: conditional
message: "Acronym '%s' must be expanded on first use."
level: warning
first: '\b[A-Z]{3,}\b'
second: '\b[A-Z]{3,}\s*\('
```

---

## Scopes

Apply rules to specific content sections:

| Scope | Matches |
|-------|---------|
| `sentence` | Full sentences |
| `paragraph` | Full paragraphs |
| `heading` | All headings |
| `heading.h1` | H1 headings only |
| `strong` | Bold text |
| `emphasis` | Italic text |
| `link` | Link text |
| `raw` | Code blocks (skip prose rules here) |

---

## Severity Levels

| Level | IDE Rendering | Build Behaviour |
|-------|--------------|-----------------|
| `suggestion` | Grey underline | Build passes |
| `warning` | Yellow underline | Build passes |
| `error` | Red underline | Build fails |

---

## Spell Checker: Australian English (en-AU)

Writerside uses the IDE's built-in spell checker. To configure it for **Australian English**:

1. Open **Settings → Editor → Natural Languages**
2. Set the **Project language** to `English (Australian)` (`en-AU`)
3. Commit `.idea/dictionaries/` and `.idea/encodings.xml` to share spell checker settings with the team

**Project-level dictionary** — add custom terms (product names, acronyms, domain vocabulary) so they are not flagged:

1. Right-click any flagged word in the editor → **Save to project-level dictionary**
2. The dictionary file is stored at `.idea/dictionaries/<username>.xml` — commit it

**Typical RDL dictionary entries:** field names, dataset identifiers, tool names, statistical terminology.

**Note:** The `.wrs-style-guide.yaml` system governs prose rule enforcement. Spell checking is a separate IDE feature configured in Settings, not in the YAML file.

---

## Recommended Starter Rules

```yaml
# .wrs-style-guide.yaml
---
- extends: substitution
  message: "Use '%s' instead of '%s'."
  level: warning
  swap:
    utilize: use
    leverage: use
    in order to: to
    is able to: can
    due to the fact that: because

- extends: existence
  message: "Avoid passive voice marker '%s'."
  level: suggestion
  tokens:
    - was \w+ed by
    - were \w+ed by
    - is \w+ed by

- extends: occurrence
  message: "Heading exceeds %s words — consider shortening."
  level: suggestion
  max: 8
  token: '\b\w+\b'
  scope: heading
```
