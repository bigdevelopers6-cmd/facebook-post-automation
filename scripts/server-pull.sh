#!/bin/bash
# Safe git pull on EC2 — resets local edits to tracked scripts (avoids "would be overwritten" abort).
set -e
cd "$(dirname "$0")/.."
# shellcheck source=scripts/lib-grep-count.sh
source "$(dirname "$0")/lib-grep-count.sh"

echo "=== Server pull (safe) ==="
echo "Before: $(git rev-parse --short HEAD 2>/dev/null || echo unknown)"

git checkout -- scripts/diagnose-execution.sh scripts/run-now.sh scripts/server-pull.sh scripts/server-deploy.sh scripts/get-execution-error.sh scripts/server-restart.sh scripts/lib-grep-count.sh 2>/dev/null || true
git pull origin main

WF=workflow/facebook-us-news-automation.json
MARKERS=$(grep_count 'function pipelineLog' "$WF")
BUILD=$(grep -o 'workflowBuild[^,}]*' "$WF" | head -1 || echo "")
HAS_V13=$(grep_count 'trace-v13-viral-image' "$WF")
HAS_VIRAL=$(grep_count '"name": "generateViralCopy"' "$WF")
HAS_GATE=$(grep_count '"name": "publishFeedLink"' "$WF")
HAS_PHOTO=$(grep_count '"name": "publishPhotoFacebook"' "$WF")
HAS_ASSERT=$(grep_count '"name": "assertWebhookPost"' "$WF")
CODE_V1=$(grep -A2 '"name": "webhookSetup"' "$WF" | grep -c '"typeVersion": 1' 2>/dev/null || true)
CODE_V1=${CODE_V1:-0}

echo "After:  $(git rev-parse --short HEAD)"
echo "pipelineLog function count (want 0): $MARKERS"
echo "trace-v13 markers (want >=1): $HAS_V13"
echo "generateViralCopy node (want >=1): $HAS_VIRAL"
echo "publishPhotoFacebook node (want >=1): $HAS_PHOTO"
echo "publishFeedLink node (want >=1): $HAS_GATE"
echo "assertWebhookPost node (want >=1): $HAS_ASSERT"
echo "webhookSetup typeVersion 1 (want >=1): $CODE_V1"
echo "meta: $BUILD"

if [ "${HAS_V13:-0}" -lt 1 ]; then
  echo ""
  echo "[!!] ERROR: Workflow on disk is OLD (need trace-v13-viral-image)."
  echo "     Push from PC, then: bash scripts/server-deploy.sh"
  exit 1
fi

if [ "${MARKERS:-0}" -gt 0 ]; then
  echo "[!!] WARN: pipelineLog() wrappers still present — pull latest commit"
fi

echo "[OK] Pull complete — run: bash scripts/server-deploy.sh"
