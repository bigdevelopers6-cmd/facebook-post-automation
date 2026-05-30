#!/bin/bash
# Show live pipeline trace written by workflow Code nodes.
set -e
cd "$(dirname "$0")/.."
LOG="${1:-data/reports/pipeline.log}"
if [ ! -f "$LOG" ]; then
  echo "[!!] No $LOG — run: bash scripts/run-now.sh"
  exit 1
fi
echo "=== $LOG (last 50 lines) ==="
tail -50 "$LOG"
