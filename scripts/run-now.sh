#!/bin/bash
# Trigger one test post and show live pipeline progress in the console.
set -e
cd "$(dirname "$0")/.."

N8N_EMAIL="${N8N_EMAIL:-bigdevelopers6@gmail.com}"
N8N_PASSWORD="${N8N_PASSWORD:-Admin@12345}"
WF_ID="${WF_ID:-facebook-us-news-001}"
FB_PAGE="${FB_PAGE_ID:-1191676374021102}"
POLL_SECS="${POLL_SECS:-120}"
POLL_INTERVAL="${POLL_INTERVAL:-3}"

n8n_login() {
  curl -s -c /tmp/n8n-cookies.txt -X POST http://localhost:5678/rest/login \
    -H "Content-Type: application/json" \
    -d "{\"emailOrLdapLoginId\":\"$N8N_EMAIL\",\"password\":\"$N8N_PASSWORD\"}" > /dev/null
}

fetch_latest_execution_id() {
  curl -s -b /tmp/n8n-cookies.txt \
    "http://localhost:5678/rest/executions?limit=1&workflowId=$WF_ID" | \
    python3 -c "import sys,json; print(json.load(sys.stdin)['data']['results'][0]['id'])"
}

fetch_execution_json() {
  local id="$1"
  curl -s -b /tmp/n8n-cookies.txt \
    "http://localhost:5678/rest/executions/${id}?includeData=true" -o /tmp/exec.json
}

show_progress() {
  local elapsed="$1"
  if [ -f scripts/pipeline-progress.py ]; then
    python3 scripts/pipeline-progress.py /tmp/exec.json "$elapsed"
  else
    python3 << PY
import json
with open("/tmp/exec.json") as f: root=json.load(f)
data=root.get("data",{}); inner=data.get("data")
if isinstance(inner,str): inner=json.loads(inner)
rd=(inner.get("resultData") if isinstance(inner,dict) else None) or {}
run=rd.get("runData",{}) if isinstance(rd,dict) else {}
print("Last node:", rd.get("lastNodeExecuted"), "| nodes:", len(run), "| status:", data.get("status"))
PY
  fi
}

echo "=============================================="
echo " Facebook US News Bot — Manual test post"
echo "=============================================="
echo ""

n8n_login

echo "[>>] IN PROGRESS  Trigger webhook..."
RESPONSE=$(curl -s -w "\nHTTP_CODE:%{http_code}" http://localhost:5678/webhook/trigger-post)
HTTP_CODE=$(echo "$RESPONSE" | grep HTTP_CODE | cut -d: -f2)
BODY=$(echo "$RESPONSE" | grep -v HTTP_CODE)

if [ "$HTTP_CODE" != "200" ] && [ "$HTTP_CODE" != "201" ]; then
  echo "[!!] FAILED       Webhook HTTP $HTTP_CODE: $BODY"
  exit 1
fi
echo "[OK]  DONE         Webhook accepted: $BODY"
echo ""
echo "Polling execution every ${POLL_INTERVAL}s (max ${POLL_SECS}s)..."
echo ""

sleep 2
EXEC_ID=""
START=$(date +%s)

while true; do
  NOW=$(date +%s)
  ELAPSED=$((NOW - START))

  if [ -z "$EXEC_ID" ]; then
    EXEC_ID=$(fetch_latest_execution_id 2>/dev/null || true)
  fi

  if [ -n "$EXEC_ID" ]; then
    fetch_execution_json "$EXEC_ID"
    clear 2>/dev/null || true
    echo "Execution ID: $EXEC_ID"
    show_progress "$ELAPSED"
    echo ""
    echo "Facebook page: https://www.facebook.com/$FB_PAGE"
    echo "(Ctrl+C to stop watching — workflow may still run in n8n)"
  else
    echo "[..] PENDING      Waiting for execution to appear... (${ELAPSED}s)"
  fi

  STATUS=$(python3 -c "
import json
try:
  d=json.load(open('/tmp/exec.json'))
  print(d.get('data',{}).get('status',''))
except Exception:
  print('')
" 2>/dev/null || echo "")

  if [ "$STATUS" = "success" ] || [ "$STATUS" = "error" ] || [ "$STATUS" = "crashed" ]; then
    echo ""
    if [ "$STATUS" = "success" ]; then
      echo "[OK]  DONE         Workflow finished (success)."
    else
      echo "[!!] FAILED       Workflow finished with status: $STATUS"
      echo "Run: ./scripts/diagnose-execution.sh $EXEC_ID"
    fi
    break
  fi

  if [ "$ELAPSED" -ge "$POLL_SECS" ]; then
    echo ""
    echo "[..] TIMEOUT      Still running after ${POLL_SECS}s — check n8n UI Executions."
    break
  fi

  sleep "$POLL_INTERVAL"
done

echo ""
echo "Full node list:"
chmod +x scripts/diagnose-execution.sh 2>/dev/null || true
if [ -x scripts/diagnose-execution.sh ] && [ -n "$EXEC_ID" ]; then
  ./scripts/diagnose-execution.sh "$EXEC_ID" 2>/dev/null | tail -n +3 || true
fi
