#!/bin/bash
# Install the local native Codex marketplace in an isolated CODEX_HOME and
# verify every phase-one plugin and its directory-derived skill names.

set -euo pipefail

REPO_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
CODEX_BIN="${CODEX_BIN:-codex}"
MARKETPLACE_NAME="rdl-agent-extensions"
MARKETPLACE_MANIFEST="$REPO_ROOT/.agents/plugins/marketplace.json"

command -v "$CODEX_BIN" >/dev/null 2>&1 || {
  echo "FATAL: codex CLI not found (set CODEX_BIN to override)" >&2
  exit 2
}
command -v jq >/dev/null 2>&1 || {
  echo "FATAL: jq not found" >&2
  exit 2
}

smoke_tmp_root="${XDG_CACHE_HOME:-$HOME/.cache}"
mkdir -p "$smoke_tmp_root"
CODEX_HOME="$(mktemp -d "$smoke_tmp_root/rdl-codex-smoke.XXXXXX")"
export CODEX_HOME
trap 'rm -rf "$CODEX_HOME"' EXIT

"$CODEX_BIN" plugin marketplace add "$REPO_ROOT" --json >/dev/null

expected_plugins=()
while IFS= read -r plugin; do
  expected_plugins+=("$plugin")
done < <(jq -r '.plugins[].name' "$MARKETPLACE_MANIFEST")
if [ "${#expected_plugins[@]}" -eq 0 ]; then
  echo "FATAL: generated Codex marketplace contains no plugins" >&2
  exit 1
fi

available="$($CODEX_BIN plugin list --marketplace "$MARKETPLACE_NAME" --available --json)"
available_count="$(jq --arg marketplace "$MARKETPLACE_NAME" \
  '[.available[] | select(.marketplaceName == $marketplace)] | length' <<<"$available")"
if [ "$available_count" -ne "${#expected_plugins[@]}" ]; then
  echo "FATAL: Codex listed $available_count plugins; expected ${#expected_plugins[@]}" >&2
  exit 1
fi

expected_skills=()
shopt -s nullglob
for plugin in "${expected_plugins[@]}"; do
  jq -e --arg plugin "$plugin" --arg marketplace "$MARKETPLACE_NAME" \
    '.available[] | select(.name == $plugin and .marketplaceName == $marketplace)' \
    <<<"$available" >/dev/null || {
    echo "FATAL: $plugin is not listed in the generated Codex marketplace" >&2
    exit 1
  }
  "$CODEX_BIN" plugin add "$plugin@$MARKETPLACE_NAME" --json >/dev/null

  skill_dirs=("$REPO_ROOT/plugins/$plugin/skills"/*)
  if [ "${#skill_dirs[@]}" -eq 0 ]; then
    echo "FATAL: $plugin contains no skills to verify" >&2
    exit 1
  fi
  for skill_dir in "${skill_dirs[@]}"; do
    [ -d "$skill_dir" ] || continue
    expected_skills+=("$plugin:$(basename "$skill_dir")")
  done
done

smoke_workspace="$CODEX_HOME/workspace"
mkdir -p "$smoke_workspace"
cd "$smoke_workspace"
prompt_input="$($CODEX_BIN debug prompt-input "Use the installed plugin skills.")"
for qualified in "${expected_skills[@]}"; do
  leaf="${qualified#*:}"
  if ! jq -e --arg prefix "- $qualified:" --arg suffix "/$leaf/SKILL.md)" \
    '.. | strings | split("\n")[] | select(startswith($prefix) and endswith($suffix))' \
    <<<"$prompt_input" >/dev/null; then
    echo "FATAL: installed plugin skill $qualified was not discovered" >&2
    exit 1
  fi
done

sample_skill="${expected_skills[0]}"
sample_plugin="${sample_skill%%:*}"
sample_leaf="${sample_skill#*:}"
sample_source="$REPO_ROOT/plugins/$sample_plugin/skills/$sample_leaf/SKILL.md"
sample_paths=(
  "$CODEX_HOME/plugins/cache/$MARKETPLACE_NAME/$sample_plugin"/*/skills/"$sample_leaf"/SKILL.md
)
if [ "${#sample_paths[@]}" -ne 1 ]; then
  echo "FATAL: discovered plugin skill $sample_skill has no unique cached copy" >&2
  exit 1
fi
if ! cmp -s "$sample_source" "${sample_paths[0]}"; then
  echo "FATAL: discovered plugin skill $sample_skill does not match its packaged body" >&2
  exit 1
fi

echo "Codex marketplace smoke test passed: ${#expected_plugins[@]} plugins installed; ${#expected_skills[@]} skills available."
