#!/bin/bash
# Recreate n8n cleanly when "container name already in use" or n8n is down.
set -e
cd "$(dirname "$0")/.."

echo "=== Restart n8n (docker compose) ==="
docker compose down 2>/dev/null || true
docker rm -f facebook-news-n8n 2>/dev/null || true
docker compose up -d

echo "Waiting for n8n health (up to 60s)..."
for i in $(seq 1 30); do
  if curl -sf http://localhost:5678/healthz >/dev/null 2>&1; then
    echo "[OK] n8n is up — http://localhost:5678"
    docker ps --filter name=facebook-news-n8n --format 'table {{.Names}}\t{{.Status}}\t{{.Ports}}'
    exit 0
  fi
  sleep 2
done

echo "[!!] n8n did not become healthy — check: docker compose logs -f --tail=50"
exit 1
