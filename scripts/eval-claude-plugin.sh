#!/bin/bash
# Run `claude plugin eval` for one Claude plugin without touching a generated tree.
#
# `claude plugin eval` only finds a suite *inside* the plugin root, but
# plugins/<plugin>/ is generated, copied verbatim to users on install, and has a
# Codex twin under dist/codex/plugins/. So suites are authored in
# evals/claude/<plugin>/ and staged next to a throwaway copy of the plugin here;
# the checkout is only read.
#
# By default the working tree is evaluated (uncommitted edits included), which is
# what you want while iterating. Set EVAL_REV=<commit> to stage both the plugin
# and the suite from that revision instead; the pre-push hook does, so it scores
# exactly what is being pushed.
#
# Every run makes real model calls on your claude login. EVAL_MAX_COST_USD caps
# the spend, but runs already in flight finish, so a run can overshoot the cap.
#
# Usage: scripts/eval-claude-plugin.sh <plugin> [claude plugin eval options...]

set -euo pipefail

REPO_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
CLAUDE_BIN="${CLAUDE_BIN:-claude}"

plugin="${1:-}"
[ -n "$plugin" ] || {
  echo "usage: $0 <plugin> [claude plugin eval options...]" >&2
  exit 2
}
shift

command -v "$CLAUDE_BIN" >/dev/null 2>&1 || {
  echo "FATAL: claude CLI not found (set CLAUDE_BIN to override)" >&2
  exit 2
}
"$CLAUDE_BIN" plugin eval --help >/dev/null 2>&1 || {
  echo "FATAL: $("$CLAUDE_BIN" --version 2>/dev/null) has no 'plugin eval' (needs >= 2.1.269)" >&2
  exit 2
}

eval_tmp_root="${XDG_CACHE_HOME:-$HOME/.cache}"
mkdir -p "$eval_tmp_root"
stage="$(mktemp -d "$eval_tmp_root/rdl-claude-eval.XXXXXX")"
trap 'rm -rf "$stage"' EXIT

source_root="$REPO_ROOT"
revision="working-tree"
if [ -n "${EVAL_REV:-}" ]; then
  revision="$(git -C "$REPO_ROOT" rev-parse --verify "$EVAL_REV^{commit}")" || {
    echo "FATAL: EVAL_REV=$EVAL_REV is not a commit" >&2
    exit 2
  }
  source_root="$stage/src"
  mkdir -p "$source_root"
  git -C "$REPO_ROOT" archive "$revision" -- "plugins/$plugin" "evals/claude/$plugin" 2>/dev/null |
    tar -x -C "$source_root" || {
    echo "FATAL: $revision lacks plugins/$plugin or evals/claude/$plugin" >&2
    exit 2
  }
fi

plugin_src="$source_root/plugins/$plugin"
suite_src="$source_root/evals/claude/$plugin"
[ -f "$plugin_src/.claude-plugin/plugin.json" ] || {
  echo "FATAL: no Claude plugin at plugins/$plugin ($revision)" >&2
  exit 2
}
[ -d "$suite_src" ] || {
  echo "FATAL: no eval suite at evals/claude/$plugin ($revision)" >&2
  exit 2
}

output_dir="${EVAL_OUTPUT_DIR:-$REPO_ROOT/.eval-results/$plugin}"
mkdir -p "$output_dir"
echo "$revision" >"$output_dir/revision.txt"
echo "eval-claude-plugin: $plugin @ $revision"

# Keep the directory named after the plugin so skills resolve as <plugin>:<leaf>.
mkdir -p "$stage/run"
cp -R "$plugin_src" "$stage/run/$plugin"
rm -rf "$stage/run/$plugin/evals"
cp -R "$suite_src" "$stage/run/$plugin/evals"

# The staged copy is this checkout's own plugin and suite, hence --trust-plugin.
"$CLAUDE_BIN" plugin eval "$stage/run/$plugin" \
  --trust-plugin \
  --no-publish \
  --max-cost-usd "${EVAL_MAX_COST_USD:-2}" \
  --output-dir "$output_dir" \
  "$@"
