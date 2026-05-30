#!/bin/bash
# Safe git pull on EC2 — resets local edits to tracked scripts (avoids "would be overwritten" abort).
set -e
cd "$(dirname "$0")/.."

echo "=== Server pull (safe) ==="
echo "Before: $(git rev-parse --short HEAD 2>/dev/null || echo unknown)"

git checkout -- scripts/diagnose-execution.sh scripts/run-now.sh scripts/server-pull.sh scripts/server-deploy.sh scripts/get-execution-error.sh 2>/dev/null || true
git pull origin main

MARKERS=$(grep -c 'function pipelineLog' workflow/facebook-us-news-automation.json || echo 0)
BUILD=$(grep -o 'workflowBuild[^,}]*' workflow/facebook-us-news-automation.json | head -1 || echo "")
HAS_V7=$(grep -c 'trace-v7c-webhook-fastpath' workflow/facebook-us-news-automation.json || echo 0)
HAS_ASSERT=$(grep -c '"name": "assertWebhookPost"' workflow/facebook-us-news-automation.json || echo 0)
CODE_V1=$(grep -A2 '"name": "webhookSetup"' workflow/facebook-us-news-automation.json | grep -c '"typeVersion": 1' || echo 0)

echo "After:  $(git rev-parse --short HEAD)"
echo "pipelineLog function count (want 0): $MARKERS"
echo "assertWebhookPost node (want >=1): $HAS_ASSERT"
echo "webhookSetup typeVersion 1 (want >=1): $CODE_V1"
echo "meta: $BUILD"

if [ "${HAS_V7:-0}" -lt 1 ]; then
  echo ""
  echo "[!!] ERROR: Workflow on disk is OLD (need trace-v7c-webhook-fastpath)."
  echo "     Push from PC, then: bash scripts/server-deploy.sh"
  exit 1
fi

if [ "${MARKERS:-0}" -gt 0 ]; then
  echo "[!!] WARN: pipelineLog() wrappers still present — pull latest commit"
fi

echo "[OK] Pull complete — run: bash scripts/server-deploy.sh"
