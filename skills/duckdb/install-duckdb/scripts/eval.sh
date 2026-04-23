#!/usr/bin/env bash
# Smoke tests for the install-duckdb workflow.
# Runs representative DuckDB INSTALL statements directly and verifies that the
# listed extensions are loadable afterwards.
#
# Prerequisites: duckdb must be in PATH. Network access is required when the
# requested extension is not already cached locally.
#
# Usage:
#   bash skills/duckdb/install-duckdb/scripts/eval.sh
#   RUN_COMMUNITY_CASES=1 bash skills/duckdb/install-duckdb/scripts/eval.sh
#   RUN_UPDATE_CASES=1 bash skills/duckdb/install-duckdb/scripts/eval.sh

set -u

DUCKDB_BIN="${DUCKDB_BIN:-duckdb}"
PASS=0
FAIL=0
TIMINGS=()

if ! command -v "$DUCKDB_BIN" >/dev/null 2>&1; then
    echo "ERROR: 'duckdb' CLI not found."
    exit 1
fi

eval_case() {
    local desc="$1"; shift
    local sql="$1"; shift
    local exts=("$@")

    printf "  %-56s " "$desc"
    local t0 t1 elapsed result
    t0=$(date +%s)
    result=$("$DUCKDB_BIN" :memory: -c "$sql" 2>&1)
    t1=$(date +%s)
    elapsed=$((t1 - t0))
    TIMINGS+=("$elapsed")

    local ext
    for ext in "${exts[@]}"; do
        if ! "$DUCKDB_BIN" :memory: -c "LOAD ${ext};" >/dev/null 2>&1; then
            echo "FAIL  (${elapsed}s) - LOAD ${ext} failed after install"
            echo "        command output: ${result:0:300}"
            ((FAIL++))
            return
        fi
    done

    echo "PASS  (${elapsed}s)"
    ((PASS++))
}

echo "=== install-duckdb skill eval ==="
echo "DuckDB bin: $DUCKDB_BIN"
echo ""

echo "--- Core extensions ---"
eval_case "Install httpfs"           "INSTALL httpfs;"                    httpfs
eval_case "Install json"             "INSTALL json;"                      json

echo ""
echo "--- Multiple extensions ---"
eval_case "Install spatial + httpfs" "INSTALL spatial; INSTALL httpfs;"   spatial httpfs

if [ "${RUN_COMMUNITY_CASES:-0}" = "1" ]; then
    echo ""
    echo "--- Community extensions ---"
    eval_case "Install magic@community" "INSTALL magic FROM community;" magic
fi

if [ "${RUN_UPDATE_CASES:-0}" = "1" ]; then
    echo ""
    echo "--- Update mode ---"
    eval_case "Update all extensions"      "UPDATE EXTENSIONS;"
    eval_case "Update specific extension"  "UPDATE EXTENSIONS (httpfs);" httpfs
fi

echo ""
total=0
for t in "${TIMINGS[@]}"; do
    total=$((total + t))
done
count=${#TIMINGS[@]}
avg=$(( count > 0 ? total / count : 0 ))

echo "=================================="
echo "Results : $PASS passed, $FAIL failed"
echo "Timing  : total ${total}s, avg ${avg}s per case"
[ "$FAIL" -eq 0 ]
