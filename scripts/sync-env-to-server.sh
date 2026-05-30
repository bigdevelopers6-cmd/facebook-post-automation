#!/bin/bash
# From your PC (with .env in project root): copies .env to EC2 and restarts n8n.
# Usage: ./scripts/sync-env-to-server.sh ubuntu@3.23.247.238
set -e
HOST="${1:?Usage: $0 ubuntu@YOUR_EC2_IP}"
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
if [ ! -f "$ROOT/.env" ]; then
  echo "Missing $ROOT/.env"
  exit 1
fi
scp "$ROOT/.env" "$HOST:~/awraaq_sgid/.env"
ssh "$HOST" 'cd ~/awraaq_sgid && docker compose down && docker compose up -d && sleep 12 && docker restart facebook-news-n8n && sleep 10 && echo "Env loaded. Keys in container:" && docker exec facebook-news-n8n sh -c "echo GROQ=\${GROQ_API_KEY:0:8}... GEMINI=\${GEMINI_API_KEY:0:8}... NEWS=\${NEWSAPI_KEY:0:8}..."'
echo "Done. Run on server: ./scripts/run-now.sh"
