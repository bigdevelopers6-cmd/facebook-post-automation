#!/bin/bash
# Show recent n8n executions with node-level detail (run on server in ~/awraaq_sgid)
set -e
cd "$(dirname "$0")/.."

N8N_EMAIL="${N8N_EMAIL:-bigdevelopers6@gmail.com}"
N8N_PASSWORD="${N8N_PASSWORD:-Admin@12345}"
WF_ID="${WF_ID:-facebook-us-news-001}"

curl -s -c /tmp/n8n-cookies.txt -X POST http://localhost:5678/rest/login \
  -H "Content-Type: application/json" \
  -d "{\"emailOrLdapLoginId\":\"$N8N_EMAIL\",\"password\":\"$N8N_PASSWORD\"}" > /dev/null

echo "=== Last 5 executions ==="
curl -s -b /tmp/n8n-cookies.txt \
  "http://localhost:5678/rest/executions?limit=5&workflowId=$WF_ID" | python3 -c "
import sys, json
from datetime import datetime
d = json.load(sys.stdin)
for e in d.get('data', {}).get('results', []):
    s, f = e.get('startedAt'), e.get('stoppedAt')
    dur = ''
    if s and f:
        a = datetime.fromisoformat(s.replace('Z', '+00:00'))
        b = datetime.fromisoformat(f.replace('Z', '+00:00'))
        dur = f' {(b-a).total_seconds():.1f}s'
    print(e.get('id'), e.get('status') + dur, 'mode=' + str(e.get('mode')))
"

EXEC_ID="${1:-$(curl -s -b /tmp/n8n-cookies.txt "http://localhost:5678/rest/executions?limit=1&workflowId=$WF_ID" | python3 -c "import sys,json; print(json.load(sys.stdin)['data']['results'][0]['id'])")}"

echo ""
echo "=== Execution $EXEC_ID ==="
curl -s -b /tmp/n8n-cookies.txt \
  "http://localhost:5678/rest/executions/${EXEC_ID}?includeData=true" -o /tmp/exec.json

python3 << 'PY'
import json
from pathlib import Path

with open("/tmp/exec.json") as f:
    root = json.load(f)

data = root.get("data", root)
inner = data.get("data")
if isinstance(inner, str):
    inner = json.loads(inner)

rd = {}
if isinstance(inner, dict):
    rd = inner.get("resultData") or inner
elif isinstance(inner, list):
    for item in inner:
        if isinstance(item, dict) and (item.get("runData") or item.get("resultData")):
            rd = item.get("resultData") or item
            break
elif isinstance(data.get("resultData"), dict):
    rd = data["resultData"]

run = rd.get("runData", {}) if isinstance(rd, dict) else {}

if run:
    print("Last node:", rd.get("lastNodeExecuted"))
    print("Nodes ran:", len(run))
    for n, runs in run.items():
        r = runs[0] if runs else {}
        st = r.get("executionStatus", "?")
        err = r.get("error")
        line = f"  [{st}] {n}"
        if err:
            msg = err.get("message", str(err))[:120] if isinstance(err, dict) else str(err)[:120]
            line += f"  ERR: {msg}"
        print(line)
else:
    import re
    raw = Path("/tmp/exec.json").read_text(encoding="utf-8")
    names = re.findall(r'"lastNodeExecuted"\s*:\s*"([^"]+)"', raw)
    if names:
        print("Last node (from raw JSON):", names[-1])
    found = re.findall(r'"node"\s*:\s*"([^"]+)"', raw)
    if found:
        print("Node refs in file:", len(set(found)))
        for n in sorted(set(found))[-25:]:
            print("  [?]", n)
    else:
        print("No runData in API response — use docker logs below")
PY

echo ""
echo "=== Nodes from docker logs (last 3 min) ==="
docker logs facebook-news-n8n --since 3m 2>&1 | grep -oE '(Finished|Executing|Started) (node|workflow) "[^"]+"|"name": "[^"]+"' | tail -25 || echo "(none)"

echo ""
echo "=== Recent log errors ==="
docker logs facebook-news-n8n --tail 50 2>&1 | grep -iE 'error|failed|exception|webhook' | tail -15 || echo "(none)"
