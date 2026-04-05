# Writerside Diagrams Reference

> **Default: Mermaid.** PlantUML is acceptable when Mermaid lacks the required diagram type.

---

## Mermaid (Default)

Mermaid uses a Markdown-inspired text syntax that renders directly in Writerside topics. No additional server-side setup required.

### Embedding in Topics

**In XML (`.topic`):**
```xml
<code-block lang="mermaid">
    flowchart LR
        A[Start] --> B{Decision}
        B -->|Yes| C[Result A]
        B -->|No| D[Result B]
</code-block>
```

**In Markdown (`.md`):**
````markdown
```mermaid
flowchart LR
    A[Start] --> B{Decision}
    B -->|Yes| C[Result A]
    B -->|No| D[Result B]
```
````

**From external file:**
```xml
<code-block lang="mermaid" src="diagrams/architecture.mermaid"/>
```
Relative paths are supported: `src="../shared/diagrams/flow.mermaid"`

### Supported Diagram Types

| Type | Syntax keyword | Use case |
|------|---------------|----------|
| Flowchart | `flowchart` / `graph` | Process flows, decision trees |
| Sequence | `sequenceDiagram` | Service interactions, API calls |
| State | `stateDiagram-v2` | State machines, lifecycle |
| Git graph | `gitGraph` | Branch strategies |
| Gantt | `gantt` | Project timelines |
| Pie chart | `pie` | Proportional data |
| Class diagram | `classDiagram` | Object structure (limited — see below) |

### Known Limitations

These Mermaid features are **not supported** in Writerside:
- Font Awesome icons
- Theme overrides via `%%{ init: ... }%%` directives
- Namespace groups and cardinality options in class diagrams
- Actor creation/destruction in sequence diagrams

### IDE Support

Install the **Mermaid plugin** (Settings → Plugins → Marketplace → search "Mermaid") for completion, syntax highlighting, and live preview in the editor.

---

## PlantUML (Acceptable Alternative)

Use PlantUML when Mermaid does not support the required diagram type — for example, use case diagrams, detailed UML class diagrams, or mind maps.

### Setup Requirements

PlantUML requires **Graphviz** for node positioning in UML diagrams. Ensure Graphviz is installed on the build system:

```bash
# RHEL/Fedora
dnf install graphviz

# Debian/Ubuntu
apt-get install graphviz
```

### Embedding in Topics

**In XML (`.topic`):**
```xml
<code-block lang="plantuml">
    @startuml
    Bob -> Alice : Hello!
    Alice -> Bob : Hi!
    @enduml
</code-block>
```

**In Markdown (`.md`):**
````markdown
```plantuml
@startuml
Bob -> Alice : Hello!
Alice -> Bob : Hi!
@enduml
```
````

**From external file:**
```xml
<code-block lang="plantuml" src="diagrams/sequence.puml"/>
```

**XML/CDATA note:** In `.topic` files, escape `<` and `>` in PlantUML code as `&lt;` and `&gt;`, or wrap the diagram in a CDATA section:
```xml
<code-block lang="plantuml">
    <![CDATA[
        @startuml
        class Foo {
            +bar() : String
        }
        @enduml
    ]]>
</code-block>
```

### Supported Diagram Types

| Type | When to prefer over Mermaid |
|------|-----------------------------|
| Use case diagrams | Mermaid has no equivalent |
| Detailed class diagrams | When cardinality/namespace groups are needed |
| JSON/YAML visualisation | No Mermaid equivalent |
| Mind maps | No Mermaid equivalent |
| Activity diagrams (complex) | More expressive than Mermaid flowcharts |

### Variable Substitution

By default, Writerside ignores variable substitution inside PlantUML blocks. To enable it:
```xml
<code-block lang="plantuml" ignore-vars="false">
```

---

## Decision Guide

| Situation | Use |
|-----------|-----|
| Flowcharts, sequences, state, git graphs | Mermaid |
| Use case, mind maps, JSON visualisation | PlantUML |
| Complex UML class diagrams with cardinality | PlantUML |
| CI/CD build system without Graphviz | Mermaid |
| Team unfamiliar with PlantUML | Mermaid |
