#!/bin/bash
# Synchronize release versions across published manifests.
#
# Usage:
#   scripts/bump-release-version.sh v0.2.0
#   scripts/bump-release-version.sh 0.2.0

set -euo pipefail

REPO_ROOT="$(cd "$(dirname "$0")/.." && pwd)"

usage() {
  echo "Usage: $(basename "$0") <version>" >&2
  echo "Accepts versions like 0.2.0 or tags like v0.2.0." >&2
}

if [ $# -ne 1 ]; then
  usage
  exit 1
fi

raw_version="$1"
version="${raw_version#v}"

if [[ ! "$version" =~ ^[0-9]+\.[0-9]+\.[0-9]+([.-][0-9A-Za-z.-]+)?$ ]]; then
  echo "Invalid version: $raw_version" >&2
  usage
  exit 1
fi

update_file_versions() {
  local file="$1"

  RELEASE_VERSION="$version" perl -0pi -e 's/("version"\s*:\s*")[^"]+(")/$1$ENV{RELEASE_VERSION}$2/g' "$file"
  echo "Updated $file"
}

shopt -s nullglob

update_file_versions "$REPO_ROOT/.claude-plugin/marketplace.json"

for file in \
  "$REPO_ROOT"/plugins/*/.claude-plugin/plugin.json \
  "$REPO_ROOT"/gemini-extension.json \
  "$REPO_ROOT"/pidev/package.json \
  "$REPO_ROOT"/mcp/*/package.json; do
  update_file_versions "$file"
done

echo "Synchronized release manifests to $version"
