---
name: read-memories
license: CC-BY-4.0
description: Search prior agent session logs stored as JSONL to recover decisions, patterns, or unresolved work. Use when the user references past conversations, asks what was done before, or wants context recovered from local transcript files.
---

# Read Memories

Search past session logs silently. Do not narrate the lookup process; absorb the results and continue with enriched context.

Treat the first argument as the keyword or phrase to search. Treat `--here` as a request to scope the search to the current project when the log layout supports project-specific directories.

## Step 1 - Resolve The Search Path

First resolve a compatible log root:

- If the user supplied a path to transcript files, use it.
- Otherwise, if `$HOME/.claude/projects` exists, use the Claude Code JSONL layout from the upstream DuckDB skill.
- Otherwise, ask the user for the transcript directory or report that no compatible local session log store was found.

Once you have a log root, query it with DuckDB:

Before constructing the SQL, escape any single quotes in the search term by doubling them:

```bash
KEYWORD="<KEYWORD>"
SQL_KEYWORD=${KEYWORD//\'/\'\'}
```

```bash
duckdb :memory: -c "
SELECT
  regexp_extract(filename, 'projects/([^/]+)/', 1) AS project,
  strftime(timestamp::TIMESTAMPTZ, '%Y-%m-%d %H:%M') AS ts,
  message.role AS role,
  left(message.content::VARCHAR, 500) AS content
FROM read_ndjson('<SEARCH_PATH>', auto_detect=true, ignore_errors=true, filename=true)
WHERE message::VARCHAR ILIKE '%<SQL_KEYWORD>%'
  AND message.role IS NOT NULL
ORDER BY timestamp
LIMIT 40;
"
```

Common search paths:

- All Claude Code projects: `$HOME/.claude/projects/*/*.jsonl`
- Current Claude Code project with `--here`: `$HOME/.claude/projects/$(echo "$PWD" | sed 's|[/_]|-|g')/*.jsonl`

Replace `<SEARCH_PATH>` and `<SQL_KEYWORD>` before running. Use the escaped `SQL_KEYWORD`, not the raw keyword, anywhere the term is interpolated into SQL.

## Step 2 - Internalize

From the results, extract decisions, patterns, unresolved TODOs, and user corrections. Use this to inform the current response. Do not repeat raw transcript lines unless the user explicitly asks for them.
