# Gemini CLI Automation Patterns

Shell-level patterns for automating Gemini CLI in scripts, CI pipelines, and batch workflows. These complement the MCP tools (which handle the common cases) for direct CLI use.

---

## Single One-Shot Call

```bash
gemini -p "Write a haiku about TypeScript" --output-format json | jq -r '.response'
```

## Piping Input

```bash
# File analysis
cat error.log | gemini -p "What's causing these errors? Give me the top 3 causes." \
  --approval-mode yolo --output-format json | jq -r '.response'

# Git diff review
git diff --staged | gemini -p "Write a conventional commit message for these changes." \
  --approval-mode yolo --output-format json | jq -r '.response'

# Command output analysis
kubectl get events --sort-by='.lastTimestamp' | \
  gemini -p "Are there any concerning events?" --approval-mode yolo
```

## Extract Session ID (for multi-turn)

```bash
# Use stream-json to get session ID
OUTPUT=$(gemini -p "Explain transformer attention" \
  --output-format stream-json --approval-mode yolo)

SESSION_ID=$(echo "$OUTPUT" | jq -r 'select(.type == "init") | .sessionId' | head -1)
RESPONSE=$(echo "$OUTPUT" | jq -r 'select(.type == "result") | .response' | head -1)

echo "Session: $SESSION_ID"
echo "Response: $RESPONSE"

# Continue the session
FOLLOW_UP=$(gemini -p "Compare to linear attention" \
  --resume "$SESSION_ID" \
  --output-format stream-json --approval-mode yolo | \
  jq -r 'select(.type == "result") | .response')
```

---

## Bulk File Processing

```bash
#!/usr/bin/env bash
# Process multiple files and collect summaries

for file in *.py; do
  echo "Processing $file..."
  summary=$(cat "$file" | gemini -p "Summarize this Python module in 2 sentences." \
    --approval-mode yolo --output-format json | jq -r '.response')
  echo "## $file" >> summaries.md
  echo "$summary" >> summaries.md
  echo "" >> summaries.md
done
```

## Parallel Batch Processing

```bash
#!/usr/bin/env bash
# Process files in parallel using background processes

process_file() {
  local file=$1
  local result=$(cat "$file" | gemini -p "Extract all TODO comments and their context." \
    --approval-mode yolo --output-format json | jq -r '.response')
  echo "### $file" >> todos.md
  echo "$result" >> todos.md
}

export -f process_file

# Run up to 4 in parallel
find . -name "*.py" | xargs -P 4 -I{} bash -c 'process_file "$@"' _ {}
```

---

## Shell Function Patterns

### Auto-commit message generator

```bash
gcommit() {
  local message=$(git diff --staged | \
    gemini -p "Write a conventional commit message. Return only the commit message, no commentary." \
    --approval-mode yolo --output-format json | jq -r '.response')

  echo "Generated: $message"
  read -p "Use this message? [y/N] " confirm
  if [[ "$confirm" == "y" ]]; then
    git commit -m "$message"
  fi
}
```

### Web search shortcut

```bash
gsearch() {
  gemini -p "Search the web: $*. Return a concise answer with sources." \
    --model flash --approval-mode yolo --output-format json | jq -r '.response'
}

# Usage
gsearch "latest PyTorch 2.5 release notes"
```

### Code review helper

```bash
greview() {
  local target=${1:-HEAD~1}
  git diff "$target" | gemini \
    -p "Review this diff. List: 1) Bugs, 2) Security issues, 3) Improvements. Be concise." \
    --approval-mode yolo --output-format json | jq -r '.response'
}
```

---

## System Context Injection

Use `GEMINI_SYSTEM_MD` to set a system prompt — store prompts in `.gemini/prompts/`:

```bash
# .gemini/prompts/research-assistant.md contains:
#   You are a research assistant focused on machine learning.
#   Always return structured JSON with fields: title, authors, year, summary, url.

GEMINI_SYSTEM_MD=.gemini/prompts/research-assistant.md \
  gemini -p "Find papers on diffusion transformers" \
  --approval-mode yolo --output-format json
```

---

## CI/CD Integration

```yaml
# GitHub Actions: auto-generate PR description
- name: Generate PR description
  run: |
    PR_BODY=$(git diff origin/main...HEAD | \
      gemini -p "Write a GitHub PR description. Include: summary, changes, testing notes." \
      --approval-mode yolo --output-format json | jq -r '.response')
    gh pr edit --body "$PR_BODY"
  env:
    GEMINI_API_KEY: ${{ secrets.GEMINI_API_KEY }}
    GITHUB_TOKEN: ${{ secrets.GITHUB_TOKEN }}
```

---

## Error Handling

```bash
#!/usr/bin/env bash
# Robust headless invocation with exit code handling

run_gemini() {
  local prompt=$1
  local output exit_code

  output=$(gemini -p "$prompt" --output-format json --approval-mode yolo 2>/tmp/gemini-stderr)
  exit_code=$?

  case $exit_code in
    0)
      echo "$output" | jq -r '.response'
      ;;
    1)
      echo "ERROR: API failure" >&2
      cat /tmp/gemini-stderr >&2
      return 1
      ;;
    42)
      echo "ERROR: Invalid input - check your prompt" >&2
      return 1
      ;;
    53)
      echo "ERROR: Turn limit exceeded - break your task into smaller pieces" >&2
      return 1
      ;;
    *)
      echo "ERROR: Unknown exit code $exit_code" >&2
      return 1
      ;;
  esac
}
```
