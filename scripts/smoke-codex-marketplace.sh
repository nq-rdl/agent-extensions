#!/bin/bash
# Install the local native Codex marketplace in an isolated CODEX_HOME and
# verify every published plugin and its directory-derived skill names.

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

marketplace_source="${CODEX_MARKETPLACE_SOURCE:-$REPO_ROOT}"
marketplace_args=()
[ -n "${CODEX_MARKETPLACE_REF:-}" ] && marketplace_args+=(--ref "$CODEX_MARKETPLACE_REF")
"$CODEX_BIN" plugin marketplace add "$marketplace_source" "${marketplace_args[@]}" --json >/dev/null

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

  source_path="$(jq -r --arg p "$plugin" '.plugins[] | select(.name==$p) | .source.path' "$MARKETPLACE_MANIFEST")"
  package_root="$REPO_ROOT/${source_path#./}"
  skill_dirs=("$package_root/skills"/*)
  for skill_dir in "${skill_dirs[@]}"; do
    [ -d "$skill_dir" ] || continue
    # Explicit-only skills remain installed, but are omitted from automatic prompt input.
    if ! grep -Eq '^disable-model-invocation: true$' "$skill_dir/SKILL.md"; then
      expected_skills+=("$plugin:$(basename "$skill_dir")")
    fi
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

# Compare whole installed skill trees, including references, scripts, and assets.
# Discovery alone would miss a package whose SKILL.md survives but helpers do not.
for plugin in "${expected_plugins[@]}"; do
  cached_skills=("$CODEX_HOME/plugins/cache/$MARKETPLACE_NAME/$plugin"/*)
  if [ "${#cached_skills[@]}" -ne 1 ]; then
    echo "FATAL: $plugin has no unique cached skills directory" >&2
    exit 1
  fi
  source_path="$(jq -r --arg p "$plugin" '.plugins[] | select(.name==$p) | .source.path' "$MARKETPLACE_MANIFEST")"
  diff -r "$REPO_ROOT/${source_path#./}" "${cached_skills[0]}"
done

for plugin in "${expected_plugins[@]}"; do
  "$CODEX_BIN" plugin remove "$plugin@$MARKETPLACE_NAME" --json >/dev/null
  cached_skills=("$CODEX_HOME/plugins/cache/$MARKETPLACE_NAME/$plugin"/*)
  if [ "${#cached_skills[@]}" -ne 0 ]; then
    echo "FATAL: removed plugin $plugin still has cached skills" >&2
    exit 1
  fi
done
removed_input="$($CODEX_BIN debug prompt-input "List available skills.")"
for qualified in "${expected_skills[@]}"; do
  if jq -e --arg prefix "- $qualified:" \
    '.. | strings | split("\n")[] | select(startswith($prefix))' \
    <<<"$removed_input" >/dev/null; then
    echo "FATAL: removed skill $qualified is still discovered" >&2
    exit 1
  fi
done

# Reinstall from the still-registered marketplace to catch stale removal state.
for plugin in "${expected_plugins[@]}"; do
  "$CODEX_BIN" plugin add "$plugin@$MARKETPLACE_NAME" --json >/dev/null
done
reinstalled_input="$($CODEX_BIN debug prompt-input "List available skills.")"
for qualified in "${expected_skills[@]}"; do
  jq -e --arg prefix "- $qualified:" \
    '.. | strings | split("\n")[] | select(startswith($prefix))' \
    <<<"$reinstalled_input" >/dev/null || {
    echo "FATAL: reinstalled skill $qualified was not discovered" >&2
    exit 1
  }
done

echo "Codex marketplace smoke test passed: ${#expected_plugins[@]} plugins; ${#expected_skills[@]} skills; full package cache, removal, and reinstallation verified."
