#!/bin/bash
# Trigger one test post and show live pipeline progress + file trace.
set -e
cd "$(dirname "$0")/.."

N8N_EMAIL="${N8N_EMAIL:-bigdevelopers6@gmail.com}"
N8N_PASSWORD="${N8N_PASSWORD:-Admin@12345}"
WF_ID="${WF_ID:-facebook-us-news-001}"
FB_PAGE="${FB_PAGE_ID:-1191676374021102}"
POLL_SECS="${POLL_SECS:-120}"
POLL_INTERVAL="${POLL_INTERVAL:-3}"
WORKFLOW_BUILD_EXPECT="${WORKFLOW_BUILD_EXPECT:-2026-05-30-trace-v8-webhook-direct}"

n8n_login() {
  curl -s -c /tmp/n8n-cookies.txt -X POST http://localhost:5678/rest/login \
    -H "Content-Type: application/json" \
    -d "{\"emailOrLdapLoginId\":\"$N8N_EMAIL\",\"password\":\"$N8N_PASSWORD\"}" > /dev/null
}

fetch_latest_execution_id() {
  local since_epoch="${1:-0}"
  curl -s -b /tmp/n8n-cookies.txt \
    "http://localhost:5678/rest/executions?limit=8&workflowId=$WF_ID" | \
    python3 -c "
import sys, json
from datetime import datetime
since = int(sys.argv[1]) if len(sys.argv) > 1 else 0
data = json.load(sys.stdin).get('data', {}).get('results', [])
picked = None
for e in data:
    if e.get('mode') not in ('webhook', 'manual', 'trigger'):
        continue
    started = e.get('startedAt') or ''
    try:
        ts = datetime.fromisoformat(started.replace('Z', '+00:00')).timestamp()
    except Exception:
        ts = 0
    if since and ts < since - 10:
        continue
    picked = e['id']
    break
if picked is None and data:
    picked = data[0]['id']
if picked:
    print(picked)
" "$since_epoch"
}

fetch_execution_json() {
  local id="$1"
  curl -s -b /tmp/n8n-cookies.txt \
    "http://localhost:5678/rest/executions/${id}?includeData=true" -o /tmp/exec.json
}

preflight() {
  local markers
  markers=$(grep -c 'function pipelineLog' workflow/facebook-us-news-automation.json 2>/dev/null || echo 0)
  v8=$(grep -c 'trace-v8-webhook-direct' workflow/facebook-us-news-automation.json 2>/dev/null || echo 0)
  echo "Workflow: trace-v8=$v8 pipelineLog-fn=$markers (want v8>=1, fn=0)"
  if [ "${v8:-0}" -lt 1 ]; then
    echo "[!!] FAILED  OLD workflow JSON on server."
    echo "        Run: bash scripts/server-pull.sh && bash scripts/server-deploy.sh"
    exit 1
  fi
  echo "[OK]  Trace will be in execution JSON (staticData.pipelineLog)"
}

echo "=============================================="
echo " Facebook US News Bot — Manual test post"
echo " Build expect: $WORKFLOW_BUILD_EXPECT"
echo "=============================================="
echo ""

preflight
n8n_login

TRIGGER_EPOCH=$(date +%s)
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
    EXEC_ID=$(fetch_latest_execution_id "$TRIGGER_EPOCH" 2>/dev/null || true)
  fi

  if [ -n "$EXEC_ID" ]; then
    fetch_execution_json "$EXEC_ID"
    clear 2>/dev/null || true
    echo "Execution ID: $EXEC_ID"
    if [ -f scripts/pipeline-progress.py ]; then
      python3 scripts/pipeline-progress.py /tmp/exec.json "$ELAPSED" 2>/dev/null || true
    fi
    echo ""
    echo "Facebook page: https://www.facebook.com/$FB_PAGE"
  else
    echo "[..] PENDING      Waiting for execution... (${ELAPSED}s)"
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
    if [ "$STATUS" = "success" ] && [ "$ELAPSED" -lt 8 ]; then
      echo "[!!] WARNING      Finished in ${ELAPSED}s — usually means NO POST."
    fi
    if [ "$STATUS" = "success" ]; then
      echo "[OK]  DONE         Workflow status: success"
    else
      echo "[!!] FAILED       Workflow status: $STATUS"
    fi
    break
  fi

  if [ "$ELAPSED" -ge "$POLL_SECS" ]; then
    echo "[..] TIMEOUT      Still running — check n8n UI"
    break
  fi

  sleep "$POLL_INTERVAL"
done

echo ""
bash scripts/execution-report.sh "$EXEC_ID" 2>/dev/null || {
  echo "(execution-report.sh missing — run git pull)"
}

python3 << PY
import json, re, sys
from pathlib import Path
sys.path.insert(0, str(Path("scripts").resolve()))
from n8n_exec_parse import extract_execution_error, runtime_publish_ok
try:
    root = json.load(open("/tmp/exec.json"))
    raw = Path("/tmp/exec.json").read_text(encoding="utf-8")
    errs = extract_execution_error(root, raw)
    text = " ".join(errs)
    if "WEBHOOK_TEST_NO_POST_" in text or "WEBHOOK_TEST_NO_POST_" in raw:
        print("\n[!!] NO POST — read 'data.error' / Trace above")
        if "ROUTE_FAILED" in text or "NO_SLOT_WAIT" in text or "webhookDirectToSlot" not in open("data/reports/pipeline.log", encoding="utf-8", errors="replace").read() if __import__("os").path.isfile("data/reports/pipeline.log") else "":
            print("    Likely fix: bash scripts/server-deploy.sh (need v8 webhookDirectToSlot)")
        elif "SKIP_TOKEN_INVALID" in text or "TOKEN_INVALID" in text or "parseFBToken: valid=false" in text:
            print("    Likely fix: renew FB_ACCESS_TOKEN in .env, then docker compose up -d")
        elif "BLOCKED_PUBLISH" in text:
            print("    Likely fix: caption/LLM keys (ANTHROPIC/GROQ/GEMINI) or image gate")
    elif runtime_publish_ok(raw):
        print("\n[OK]  POST SUCCEEDED (PUBLISH_OK postId= in execution)")
    elif "${STATUS}" == "error":
        print("\n[!!] Execution ERROR — see data.error in report above")
    elif int("${ELAPSED:-99}") < 8:
        print("\n[!!] Fast finish — token skip, blocked publish, or empty articles")
except Exception as e:
    print("\n[!!] Could not parse trace:", e)
PY
