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
WORKFLOW_BUILD_EXPECT="${WORKFLOW_BUILD_EXPECT:-2026-05-30-trace-v13-viral-image}"

n8n_login() {
  local code
  code=$(curl -s -o /tmp/n8n-login.json -w "%{http_code}" -c /tmp/n8n-cookies.txt \
    -X POST http://localhost:5678/rest/login \
    -H "Content-Type: application/json" \
    -d "{\"emailOrLdapLoginId\":\"$N8N_EMAIL\",\"password\":\"$N8N_PASSWORD\"}")
  if [ "$code" != "200" ]; then
    echo "[!!] FAILED  n8n login HTTP $code (check N8N_EMAIL / N8N_PASSWORD)"
    cat /tmp/n8n-login.json 2>/dev/null || true
    exit 1
  fi
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

# shellcheck source=scripts/lib-grep-count.sh
source "$(dirname "$0")/lib-grep-count.sh"

preflight() {
  local wf=workflow/facebook-us-news-automation.json
  local markers v13
  markers=$(grep_count 'function pipelineLog' "$wf")
  v13=$(grep_count 'trace-v13-viral-image' "$wf")
  echo "Workflow: trace-v13=$v13 pipelineLog-fn=$markers (want v13>=1, fn=0)"
  if [ "${v13:-0}" -lt 1 ]; then
    echo "[!!] FAILED  OLD workflow JSON on server (need trace-v13-viral-image)."
    echo "        Run: bash scripts/server-pull.sh && bash scripts/server-deploy.sh"
    exit 1
  fi
  echo "[OK]  Trace will be in execution JSON (staticData.pipelineLog)"
}

ensure_n8n_up() {
  if curl -sf http://localhost:5678/healthz >/dev/null 2>&1; then
    return 0
  fi
  echo "[!!] FAILED  n8n is not running on http://localhost:5678"
  echo "        Fix: bash scripts/server-restart.sh"
  echo "        (Do not use 'docker compose up -d --force-recreate' alone — it can leave a name conflict.)"
  exit 1
}

echo "=============================================="
echo " Facebook US News Bot — Manual test post"
echo " Build expect: $WORKFLOW_BUILD_EXPECT"
echo "=============================================="
echo ""

preflight
ensure_n8n_up
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
from n8n_exec_parse import extract_execution_error, runtime_publish_ok, extract_publish_post_id, read_pipeline_log
try:
    root = json.load(open("/tmp/exec.json"))
    raw = Path("/tmp/exec.json").read_text(encoding="utf-8")
    log_text = read_pipeline_log()
    errs = extract_execution_error(root, raw)
    text = " ".join(errs)
    post_id = extract_publish_post_id(log_text) or extract_publish_post_id(raw)
    status = (root.get("data") or {}).get("status") or "${STATUS}"
    if post_id or runtime_publish_ok(raw):
        print("\n[OK]  POST SUCCEEDED — Facebook post id:", post_id or "(see pipeline.log)")
        print("     Page: https://www.facebook.com/${FB_PAGE}")
    elif status == "success" and log_text:
        print("\n[OK]  Workflow succeeded — see data/reports/pipeline.log for trace")
    elif status == "error" and ("WEBHOOK_TEST_NO_POST_" in text or "WEBHOOK_TEST_NO_POST_" in raw) and not runtime_publish_ok(raw):
        print("\n[!!] NO POST — read pipeline.log / Trace above")
        if "ROUTE_FAILED" in text or "NO_WEBHOOK_SLOT_FAST" in text:
            print("    Likely fix: bash scripts/server-deploy.sh (need v9 webhookSlotFast)")
        elif "NO_WEBHOOK_PREPARE" in text or "NO_TOKEN_CHECK" in text:
            print("    Likely fix: v9 deploy + valid FB_ACCESS_TOKEN in .env")
        elif "pages_manage_posts" in text or "pages_read_engagement" in text or ("PUBLISH_FAIL" in log_text and "403" in log_text):
            print("    Fix: Page token missing publish permissions.")
            print("    Run: bash scripts/check-fb-token.sh")
        elif "SKIP_TOKEN_INVALID" in text or "TOKEN_INVALID" in text or "parseFBToken: valid=false" in text:
            print("    Likely fix: renew FB_ACCESS_TOKEN in .env, then docker compose up -d")
        elif "BLOCKED_PUBLISH" in text:
            print("    Likely fix: caption/LLM keys (ANTHROPIC/GROQ/GEMINI) or image gate")
    elif "${STATUS}" == "error":
        print("\n[!!] Execution ERROR — see data.error in report above")
    elif int("${ELAPSED:-99}") < 8:
        print("\n[!!] Fast finish — token skip, blocked publish, or empty articles")
except Exception as e:
    print("\n[!!] Could not parse trace:", e)
PY
