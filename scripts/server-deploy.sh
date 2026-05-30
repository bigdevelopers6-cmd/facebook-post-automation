#!/bin/bash
# Pull latest + import workflow + restart n8n (run on EC2 in ~/awraaq_sgid).
set -e
cd "$(dirname "$0")/.."

bash scripts/server-pull.sh

mkdir -p data/reports
: > data/reports/pipeline.log

if ! docker ps --format '{{.Names}}' | grep -qx 'facebook-news-n8n'; then
  echo ""
  echo "[!!] n8n container not running — starting with compose..."
  bash scripts/server-restart.sh
fi

echo ""
echo "=== Import workflow ==="
docker cp workflow/facebook-us-news-automation.json facebook-news-n8n:/tmp/workflow.json
docker exec facebook-news-n8n n8n import:workflow --input=/tmp/workflow.json
docker restart facebook-news-n8n

echo "Waiting 30s for n8n..."
sleep 30

echo "=== Publish workflow (registers 6:45 AM schedule) ==="
docker exec facebook-news-n8n n8n publish:workflow --id=facebook-us-news-001 2>/dev/null || true
# Legacy n8n: ensure active flag (harmless on n8n 2.x)
docker exec facebook-news-n8n n8n update:workflow --id=facebook-us-news-001 --active=true 2>/dev/null || true

echo ""
echo "=== Verify workflow in container ==="
docker exec facebook-news-n8n sh -c 'grep -o trace-v13-viral-image /tmp/workflow.json | head -1' || echo "(import file check failed)"
docker exec facebook-news-n8n sh -c 'grep -c generateViralCopy /tmp/workflow.json' || true
docker exec facebook-news-n8n sh -c 'grep -c publishPhotoFacebook /tmp/workflow.json' || true

echo ""
echo "=== Quick env check (keys must be non-empty) ==="
docker exec facebook-news-n8n sh -c 'for v in NEWSAPI_KEY FB_ACCESS_TOKEN ANTHROPIC_API_KEY GROQ_API_KEY GEMINI_API_KEY; do eval "len=\${#$v}"; echo "$v length=$len"; done'

echo "[OK] Deploy done — test: bash scripts/run-now.sh"
