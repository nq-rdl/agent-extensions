---
name: duckdb-docs
license: CC-BY-4.0
description: Search DuckDB and DuckLake documentation and blog posts with a locally cached full-text index. Use when the user asks how DuckDB works, needs official syntax or behavior details, or wants DuckLake-specific documentation.
---

# DuckDB Docs

Treat the user's request as the documentation query.

Follow these steps in order.

## Step 1 - Check DuckDB Is Installed

```bash
command -v duckdb
```

If not found, open [../install-duckdb/SKILL.md](../install-duckdb/SKILL.md), follow it to install DuckDB, then continue.

## Step 2 - Ensure Required Extensions Are Installed

```bash
duckdb :memory: -c "INSTALL httpfs; INSTALL fts;"
```

If this fails, report the error and stop.

## Step 3 - Choose The Data Source And Extract Search Terms

There are two search indexes available:

| Index | Remote URL | Local cache filename | Versions | Use when |
| --- | --- | --- | --- | --- |
| **DuckDB docs + blog** | `https://duckdb.org/data/docs-search.duckdb` | `duckdb-docs.duckdb` | `lts`, `current`, `blog` | Default for DuckDB questions |
| **DuckLake docs** | `https://ducklake.select/data/docs-search.duckdb` | `ducklake-docs.duckdb` | `stable`, `preview` | Queries that mention DuckLake, catalogs, or DuckLake-specific features |

Both indexes share the same schema:

| Column | Type | Description |
| --- | --- | --- |
| `chunk_id` | `VARCHAR` | For example, `stable/sql/functions/numeric#absx` |
| `page_title` | `VARCHAR` | Page title from front matter |
| `section` | `VARCHAR` | Section heading, or null for page intros |
| `breadcrumb` | `VARCHAR` | For example, `SQL > Functions > Numeric` |
| `url` | `VARCHAR` | URL path with anchor |
| `version` | `VARCHAR` | One of the versions above |
| `text` | `TEXT` | Full markdown of the chunk |

By default, search DuckDB docs and filter to `version = 'lts'`. Use different versions when:

- The user explicitly asks about `current` or nightly features -> `version = 'current'`
- The user asks about a blog post or wants background and motivation -> `version = 'blog'`
- The user asks about DuckLake -> search the DuckLake index with `version = 'stable'`
- When unsure, omit the version filter to search across all versions

If the input is a natural-language question, extract the key technical terms, nouns, function names, and SQL keywords to form a compact BM25 query string. Drop stop words such as "how", "do", "I", and "the".

If the input is already a function name or technical term, for example `arg_max` or `GROUP BY ALL`, use it as-is.

Use the extracted terms as `SEARCH_QUERY` in the next step.

## Step 4 - Ensure The Local Cache Is Fresh

The cache lives at `$HOME/.duckdb/docs/CACHE_FILENAME`, where `CACHE_FILENAME` is `duckdb-docs.duckdb` or `ducklake-docs.duckdb` based on Step 3.

First, ensure the directory exists:

```bash
mkdir -p "$HOME/.duckdb/docs"
```

Then check whether the cache file exists and is fresh, meaning no more than two days old:

```bash
CACHE_FILE="$HOME/.duckdb/docs/CACHE_FILENAME"
if [ -f "$CACHE_FILE" ]; then
    MTIME=$(stat -f %m "$CACHE_FILE" 2>/dev/null || stat -c %Y "$CACHE_FILE")
    CACHE_AGE_DAYS=$(( ( $(date +%s) - MTIME ) / 86400 ))
else
    CACHE_AGE_DAYS=999
fi
echo "Cache age: $CACHE_AGE_DAYS days"
```

If `CACHE_AGE_DAYS <= 2`, skip to Step 5.

Otherwise fetch the index:

```bash
duckdb -c "
LOAD httpfs;
LOAD fts;
ATTACH 'REMOTE_URL' AS remote (READ_ONLY);
ATTACH '$HOME/.duckdb/docs/CACHE_FILENAME.tmp' AS tmp;
COPY FROM DATABASE remote TO tmp;
" && mv "$HOME/.duckdb/docs/CACHE_FILENAME.tmp" "$HOME/.duckdb/docs/CACHE_FILENAME"
```

Replace `REMOTE_URL` and `CACHE_FILENAME` based on Step 3. If the fetch fails, report the error and stop.

## Step 5 - Search The Docs

```bash
duckdb "$HOME/.duckdb/docs/CACHE_FILENAME" -readonly -json -c "
LOAD fts;
SELECT
    chunk_id, page_title, section, breadcrumb, url, version, text,
    fts_main_docs_chunks.match_bm25(chunk_id, 'SEARCH_QUERY') AS score
FROM docs_chunks
WHERE score IS NOT NULL
  AND version = 'VERSION'
ORDER BY score DESC
LIMIT 8;
"
```

Replace `CACHE_FILENAME`, `SEARCH_QUERY`, and `VERSION` based on Step 3. Remove the `AND version = 'VERSION'` line when searching across all versions.

If the user's question could benefit from both DuckDB docs and blog results, run two queries or omit the version filter entirely.

## Step 6 - Handle Errors

- **Extension not installed** (`httpfs` or `fts` not found): run `duckdb :memory: -c "INSTALL httpfs; INSTALL fts;"` and retry.
- **`ATTACH` fails or the network is unreachable**: explain that the docs index is unavailable and suggest checking network access. The DuckDB index is hosted at `https://duckdb.org/data/docs-search.duckdb` and the DuckLake index at `https://ducklake.select/data/docs-search.duckdb`.
- **No results**: broaden the query by dropping the least specific term, or retry with a single-word query. If there are still no results, say so and point the user to `https://duckdb.org/docs` or `https://ducklake.select/docs`.

## Step 7 - Present Results

For each result chunk, ordered by descending score, format as:

```text
### {section} - {page_title}
{url}

{text}

---
```

After presenting the chunks, synthesize a concise answer to the user's original question based on the retrieved documentation. If the chunks directly answer the question, lead with the answer before showing the sources.
