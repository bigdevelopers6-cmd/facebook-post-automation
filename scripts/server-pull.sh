#!/bin/bash
# Safe git pull on EC2 — resets local edits to tracked scripts (avoids "would be overwritten" abort).
set -e
cd "$(dirname "$0")/.."

echo "=== Server pull (safe) ==="
echo "Before: $(git rev-parse --short HEAD 2>/dev/null || echo unknown)"

git checkout -- scripts/diagnose-execution.sh scripts/run-now.sh scripts/server-pull.sh scripts/server-deploy.sh 2>/dev/null || true
git pull origin main

MARKERS=$(grep -c 'function pipelineLog' workflow/facebook-us-news-automation.json || echo 0)
BUILD=$(grep -o 'workflowBuild[^,}]*' workflow/facebook-us-news-automation.json | head -1 || echo "")
HAS_V5=$(grep -c 'trace-v5' workflow/facebook-us-news-automation.json || echo 0)
echo "After:  $(git rev-parse --short HEAD)"
echo "pipelineLog markers in workflow: $MARKERS"
echo "meta: $BUILD"

if [ "${MARKERS:-0}" -lt 3 ] || [ "${HAS_V5:-0}" -lt 1 ]; then
  echo ""
  echo "[!!] ERROR: Workflow on disk is OLD (missing pipeline tracing)."
  echo "     On your PC run: git push origin main"
  echo "     Then run this script again."
  exit 1
fi

echo "[OK] Pull complete — run: bash scripts/server-deploy.sh"
