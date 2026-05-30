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
import json, re
from pathlib import Path

root = json.load(open("/tmp/exec.json"))
raw = Path("/tmp/exec.json").read_text(encoding="utf-8")
print("Top-level keys:", list(root.keys()))
data = root.get("data", {})
print("data.status:", data.get("status"))
print("data.stoppedAt:", data.get("stoppedAt"))
if data.get("error"):
    print("data.error:", json.dumps(data["error"], indent=2)[:2000])

for pat in [
    r'"message"\s*:\s*"([^"]{20,500})"',
    r'"description"\s*:\s*"([^"]{20,500})"',
    r'"stack"\s*:\s*"([^"]{20,800})"',
    r'"lastNodeExecuted"\s*:\s*"([^"]+)"',
    r'"node"\s*:\s*"([^"]+)"[^}]{0,200}"error"',
]:
    hits = re.findall(pat, raw)
    if hits:
        print(f"\nPattern {pat[:40]}... ({len(hits)} hits):")
        for h in hits[:6]:
            text = h if isinstance(h, str) else h[0]
            print(" ", text[:300].replace("\\n", " "))

if "pipelineLog" in raw:
    logs = re.findall(r'"([^"]*prepareCategory[^"]*)"', raw)
    if logs:
        print("\npipelineLog snippets:", logs[:10])
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
echo "=== Last docker errors ==="
docker logs facebook-news-n8n --tail 30 2>&1 | grep -iE 'error|Error|execution|webhook|Code' | tail -15 || true
