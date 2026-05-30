#!/bin/bash
# Manually trigger a single news post with email notifications
# Usage: ./scripts/run-now.sh

set -e

N8N_URL="http://localhost:5678"
COOKIE_FILE="/tmp/n8n-run-cookies.txt"

echo "=== Facebook News Bot — Manual Trigger ==="
echo ""

# Login
echo "[1/3] Logging in to n8n..."
curl -s -c "$COOKIE_FILE" -X POST "$N8N_URL/rest/login" \
  -H "Content-Type: application/json" \
  -d '{"emailOrLdapLoginId":"bigdevelopers6@gmail.com","password":"Admin@12345"}' > /dev/null

# Trigger manual execution via webhook
echo "[2/3] Triggering test-one (single post)..."
RESPONSE=$(curl -s -b "$COOKIE_FILE" -X POST "$N8N_URL/rest/workflows/facebook-us-news-001/run" \
  -H "Content-Type: application/json" \
  -d '{
    "startNodes": ["manualTrigger"],
    "runData": {
      "manualTrigger": [{
        "json": { "command": "test-one" }
      }]
    }
  }')

EXEC_ID=$(echo "$RESPONSE" | python3 -c "import sys,json; print(json.load(sys.stdin).get('data',{}).get('executionId','unknown'))" 2>/dev/null || echo "unknown")

echo "[3/3] Execution started!"
echo ""
echo "  Execution ID: $EXEC_ID"
echo "  What happens next:"
echo "    1. Production gate checks APIs"
echo "    2. Fetches US politics + celebrity news"
echo "    3. Claude generates caption"
echo "    4. AI compliance review"
echo "    5. Publishes to Facebook"
echo "    6. Emails sent to talhazahoor786@gmail.com"
echo ""
echo "  Check execution status:"
echo "    curl -s -b $COOKIE_FILE $N8N_URL/rest/executions/$EXEC_ID | python3 -m json.tool | grep status"
echo ""

rm -f "$COOKIE_FILE"
echo "Done."
