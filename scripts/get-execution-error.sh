#!/bin/bash
# Extract error details for an n8n execution (works when REST API has no runData).
set -e
cd "$(dirname "$0")/.."
EXEC_ID="${1:-}"

N8N_EMAIL="${N8N_EMAIL:-bigdevelopers6@gmail.com}"
N8N_PASSWORD="${N8N_PASSWORD:-Admin@12345}"
WF_ID="${WF_ID:-facebook-us-news-001}"

if [ -z "$EXEC_ID" ]; then
  curl -s -c /tmp/n8n-cookies.txt -X POST http://localhost:5678/rest/login \
    -H "Content-Type: application/json" \
    -d "{\"emailOrLdapLoginId\":\"$N8N_EMAIL\",\"password\":\"$N8N_PASSWORD\"}" > /dev/null
  EXEC_ID=$(curl -s -b /tmp/n8n-cookies.txt \
    "http://localhost:5678/rest/executions?limit=1&workflowId=$WF_ID" | \
    python3 -c "import sys,json; print(json.load(sys.stdin)['data']['results'][0]['id'])")
fi

echo "=== Execution $EXEC_ID error dump ==="

curl -s -c /tmp/n8n-cookies.txt -X POST http://localhost:5678/rest/login \
  -H "Content-Type: application/json" \
  -d "{\"emailOrLdapLoginId\":\"$N8N_EMAIL\",\"password\":\"$N8N_PASSWORD\"}" > /dev/null 2>&1 || true

curl -s -b /tmp/n8n-cookies.txt \
  "http://localhost:5678/rest/executions/${EXEC_ID}?includeData=true" -o /tmp/exec.json

python3 << 'PY'
import json, sys
from pathlib import Path

sys.path.insert(0, str(Path("scripts").resolve()))
from n8n_exec_parse import extract_execution_error, parse_execution, scan_raw_execution, runtime_publish_ok

root = json.load(open("/tmp/exec.json"))
raw = Path("/tmp/exec.json").read_text(encoding="utf-8")
data = root.get("data", {})
print("Top-level keys:", list(root.keys()))
print("data.status:", data.get("status"))
print("data.stoppedAt:", data.get("stoppedAt"))
if data.get("error"):
    print("data.error:", json.dumps(data["error"], indent=2)[:2000])

run, last, status, _ = parse_execution(root)
print("runData nodes:", len(run), "| lastNode:", last)

errs = extract_execution_error(root, raw)
if errs:
    print("\n--- Parsed errors / trace ---")
    for e in errs:
        print(" ", e[:500])
else:
    print("\n(no structured errors — check docker [PIPELINE] logs)")

hints = scan_raw_execution(raw)
if hints.get("pipeline_lines"):
    print("\n[PIPELINE] in execution blob:")
    for ln in hints["pipeline_lines"][-12:]:
        print(" ", ln[:200])
if "WEBHOOK_TEST_NO_POST" in raw:
    print("\n[!!] WEBHOOK_TEST_NO_POST — loop finished without Facebook publish")
    print("    (PUBLISH_OK in blob below is often workflow JSON — ignore unless postId= digits)")
if runtime_publish_ok(raw):
    print("\n[OK] Real publish: PUBLISH_OK postId=<numeric> in execution data")
PY

echo ""
echo "=== SQLite (if available) ==="
docker exec facebook-news-n8n sh -c '
  DB=/home/node/.n8n/database.sqlite
  if [ -f "$DB" ]; then
    sqlite3 "$DB" "SELECT id, status, startedAt, stoppedAt FROM execution_entity WHERE id='"$EXEC_ID"' LIMIT 1;" 2>/dev/null || echo "sqlite query failed"
  else
    echo "no sqlite at $DB"
  fi
' 2>/dev/null || echo "(docker exec failed)"

echo ""
echo "=== Pipeline file log ==="
if [ -f data/reports/pipeline.log ]; then
  tail -35 data/reports/pipeline.log
else
  echo "(no data/reports/pipeline.log — deploy v8 and run test)"
fi

echo ""
echo "=== Last docker [PIPELINE] lines ==="
docker logs facebook-news-n8n --tail 60 2>&1 | grep -iE '\[PIPELINE\]|WEBHOOK_TEST|Problem in node|assertWebhook' | tail -20 || true
