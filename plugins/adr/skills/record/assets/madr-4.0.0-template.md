---
status: "{proposed | accepted | rejected | deprecated | superseded by ADR-NNNN}"
date: {YYYY-MM-DD when the decision was last updated}
decision-makers: {names the user gave; omit the line if none}
consulted: {optional; omit if unknown}
informed: {optional; omit if unknown}
---

# {short title naming the solved problem and the chosen solution}

## Context and Problem Statement

{Two to four sentences: the situation, the forces, and the question being decided. Link the issue, PR or spec.}

## Decision Drivers

* {driver 1 — a requirement, constraint or quality goal that separates the options}
* {driver 2}

## Considered Options

* {option 1 — the chosen one need not be first}
* {option 2}

## Decision Outcome

Chosen option: "{option title, verbatim from Considered Options}", because {justification that names at least one driver above}.

### Consequences

* Good, because {positive consequence}
* Bad, because {negative consequence, or "Not recorded — no downside was identified in the discussion"}

### Confirmation

{How compliance is checked: a test, lint rule, review step or metric. Delete this section rather than inventing one.}

## Pros and Cons of the Options

### {option 1}

* Good, because {argument}
* Neutral, because {argument}
* Bad, because {argument}

### {option 2}

* Good, because {argument}
* Bad, because {argument}

## More Information

{Links: related ADRs as relative links (`[ADR-NNNN](NNNN-slug.md)`), "Supersedes `[ADR-NNNN](NNNN-slug.md)`", the PR or merge commit. Reconsider-when triggers. For a retrospective record: "Decided around YYYY-MM; recorded retrospectively on YYYY-MM-DD from <source>."}

<!--
Adapted from MADR 4.0.0 template/adr-template.md
(https://github.com/adr/madr/blob/4.0.0/template/adr-template.md), MIT OR CC0-1.0.
Delete this comment and every unused optional section before writing.
-->
