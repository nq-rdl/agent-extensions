#!/usr/bin/env bash
# tdd-init.sh — Create .tdd/ directory structure and scaffold config.yaml.
# Usage: bash tdd-init.sh
set -euo pipefail

if [ -d .tdd ]; then
  echo ".tdd/ already exists — skipping init"
  exit 0
fi

mkdir -p .tdd

cat > .tdd/.gitignore <<'EOF'
archive/
EOF

if [ ! -f .tdd/config.yaml ]; then
  cat > .tdd/config.yaml <<'EOF'
state_tracking: true
backends:
  red: claude:subagent
  green: claude:subagent
  refactor: claude:subagent
  review: claude:subagent
test_command: auto-detect
max_cycles: 3
EOF
fi

ST_RAW=$(grep '^state_tracking:' .tdd/config.yaml | awk '{print $2}' || true)
if [ "$ST_RAW" = "false" ]; then
  echo "Initialized .tdd/ (state tracking disabled)"
else
  mkdir -p .tdd/{active,archive}
  echo "Initialized .tdd/"
fi
