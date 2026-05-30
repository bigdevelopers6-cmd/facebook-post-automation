#!/bin/bash
# Pull latest + import workflow + restart n8n (run on EC2 in ~/awraaq_sgid).
set -e
cd "$(dirname "$0")/.."

bash scripts/server-pull.sh

mkdir -p data/reports
: > data/reports/pipeline.log

echo ""
echo "=== Import workflow ==="
docker cp workflow/facebook-us-news-automation.json facebook-news-n8n:/tmp/workflow.json
docker exec facebook-news-n8n n8n import:workflow --input=/tmp/workflow.json
docker exec facebook-news-n8n n8n publish:workflow --id=facebook-us-news-001
docker restart facebook-news-n8n

echo "Waiting 25s for n8n..."
sleep 25

echo ""
echo "=== Verify workflow in container ==="
docker exec facebook-news-n8n sh -c 'grep -o trace-v6-fix /tmp/workflow.json | head -1' || echo "(import file check failed)"

echo ""
echo "=== Quick env check (keys must be non-empty) ==="
docker exec facebook-news-n8n sh -c 'for v in NEWSAPI_KEY FB_ACCESS_TOKEN ANTHROPIC_API_KEY; do eval "len=\${#$v}"; echo "$v length=$len"; done'

echo "[OK] Deploy done — test: bash scripts/run-now.sh"
