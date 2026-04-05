#!/usr/bin/env bash
# tdd-clean.sh — Remove .tdd/ directory or just the archive.
# Usage: bash tdd-clean.sh [--archive-only]
# Compatible with reworked TDDCycle schema (2026-03-22)
set -euo pipefail

if [ "${1:-}" = "--archive-only" ]; then
  if [ -d .tdd/archive ]; then
    rm -rf .tdd/archive/*
    echo "Cleaned .tdd/archive/"
  else
    echo "No .tdd/archive/ directory found"
  fi
else
  if [ -d .tdd ]; then
    rm -rf .tdd
    echo "Removed .tdd/"
  else
    echo "No .tdd/ directory found"
  fi
fi
