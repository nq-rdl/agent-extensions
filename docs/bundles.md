---
icon: lucide/package
---

# Bundles

Available skill bundles distributed as Claude Code plugins and a Gemini CLI extension.

## Install

### Claude Code

Skills are distributed as 6 separate plugin bundles. Install the bundles you need:

```bash
# Add the marketplace (once)
/plugin marketplace add nq-rdl/agent-extensions

# Install a bundle
/plugin install <bundle>@rdl
```

### Gemini CLI

All 41 skills are available as a single Gemini CLI extension:

```bash
# From a cloned copy of this repo
gemini extensions link gemini/
```

### pi.dev

All 41 skills are available as a single pi.dev package:

```bash
# From a cloned copy of this repo
pi install ./pidev

# Or via git
pi install git:github.com/nq-rdl/agent-extensions
```

---

## swe

Software engineering — TDD, secure Go, naming, CI/CD, changelogs.

```bash
/plugin install swe@rdl
```

| Skill | Description |
|-------|-------------|
| tdd | Test-driven development concepts, cycle, and anti-patterns |
| tdd-team-workflow | TDD orchestration — red→green→refactor→review cycle with subagents |
| go-secure | Secure Go error handling and information leakage prevention |
| go-naming | Go naming conventions and idiomatic identifier choices |
| go-gh | GitHub Actions CI/CD for Go projects |
| changie | Changelog entry creation with Changie |
| charm-tui | Terminal UIs with the Go Charm ecosystem (Bubbletea, Bubbles, Lip Gloss) |

---

## infra

Infrastructure — Ansible, git hooks, analytical databases.

```bash
/plugin install infra@rdl
```

| Skill | Description |
|-------|-------------|
| ansible | Create, modify, debug, or optimise Ansible playbooks, roles, and inventories |
| husky | Manage Git hooks with husky v9 |
| lefthook | Git hooks management with Lefthook for Go and polyglot projects |
| starrocks | StarRocks analytical data warehouse — SQL, table design, partition and bucket strategies |

---

## dataops

Data operations — CSV, Excel, PDF, Word, design documents.

```bash
/plugin install dataops@rdl
```

| Skill | Description |
|-------|-------------|
| csv | Scan, update, validate, or summarise pipe-delimited CSV extraction sheets |
| xlsx | Read, write, edit, or fix Excel spreadsheet files |
| pdf | Extract text, tables, or data from PDF files, especially academic papers |
| docx | Create, read, edit, or manipulate Word documents (.docx) |
| canvas-design | Create visual art in .png and .pdf documents using design philosophy |

---

## informatics

R ecosystem — package dev, Shiny, Quarto, testing, CRAN.

```bash
/plugin install informatics@rdl
```

| Skill | Description |
|-------|-------------|
| r-expert | R language expert — writing, reviewing, or debugging R code |
| r-lib-cli | R package for CLI styling, semantic messaging, and user communication |
| r-lib-cli-app | Build command-line apps in R using the Rapp package |
| r-lib-cran-extrachecks | Prepare R packages for CRAN submission — ad-hoc requirements not caught by devtools::check() |
| r-lib-lifecycle | R package lifecycle management according to tidyverse principles |
| r-lib-mirai | Async, parallel, and distributed computing in R using mirai |
| r-lib-package-dev | Full R package development lifecycle — creation, structure, devtools, roxygen2 |
| r-lib-testing | R package tests with testthat v3+ — structure, expectations, fixtures, snapshots |
| shiny-bslib | Modern Shiny dashboards and applications using bslib (Bootstrap 5) |
| shiny-bslib-theming | Advanced theming for Shiny apps using bslib and Bootstrap 5 |
| quarto-authoring | Writing and authoring Quarto documents (.qmd) — code cells, cross-references, callouts |
| quarto-alt-text | Generate accessible alt text for data visualizations in Quarto documents |

---

## dev-tools

Developer tools — agent dispatch, multi-agent teams, link checking, docs.

```bash
/plugin install dev-tools@rdl
```

| Skill | Description |
|-------|-------------|
| cc-agent-teams | Claude Code agent teams — coordinate multiple independent sessions in parallel |
| cc-hooks | Create, manage, and debug Claude Code hooks — event-driven scripts |
| dispatch | Route tasks to external coding backends (fan out, offload) |
| document-release | Post-ship documentation update for README, ARCHITECTURE, CHANGELOG, etc. |
| gemini-cli | Gemini CLI headless dispatch — spawn headless Gemini CLI processes |
| jules | Dispatch tasks to Jules AI coding sessions |
| jules-dispatch-creator | Set up and configure Jules GitHub Actions dispatch workflows |
| opencode | Interact with the OpenCode server via its HTTP API |
| pi-rpc | Pi.dev ConnectRPC service — spawn and manage pi.dev coding agent sessions |
| lychee | Fast link checker for documentation, READMEs, and markdown files |
| writerside | JetBrains Writerside documentation topics, markup tags, and projects |

---

## meta

Meta — skill review and issue reporting for skill quality.

```bash
/plugin install meta@rdl
```

| Skill | Description |
|-------|-------------|
| report-skill-issue | Report issues with skills to their upstream repository |
| skill-review | Self-improvement loop — spawns a subagent to review skills and produce actionable feedback |
