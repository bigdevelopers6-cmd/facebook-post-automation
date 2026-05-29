#!/usr/bin/env bash
# Stop n8n to avoid API charges when production cost guard halts the workflow.
set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
cd "$PROJECT_DIR"
echo "Stopping Facebook US News Automation (n8n)..."
docker compose down
echo "Done. Server stopped. Fix API keys, then: cd ~/awraaq_sgid && docker compose up -d"
