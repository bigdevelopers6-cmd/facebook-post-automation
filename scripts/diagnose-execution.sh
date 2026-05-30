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
import sys
from pathlib import Path

sys.path.insert(0, str(Path("scripts").resolve()))
from n8n_exec_parse import parse_execution, format_node_list

with open("/tmp/exec.json") as f:
    root = json.load(f)

run, last, status, _ = parse_execution(root)
print("Status:", status)
print("Last node:", last)
print("Nodes ran:", len(run))
print(format_node_list(run))
if not run:
    import re
    raw = Path("/tmp/exec.json").read_text(encoding="utf-8")
    names = re.findall(r'"lastNodeExecuted"\s*:\s*"([^"]+)"', raw)
    if names:
        print("Last node (raw JSON hint):", names[-1])
PY

echo ""
echo "=== Pipeline log lines (docker, last 3 min) ==="
docker logs facebook-news-n8n --since 3m 2>&1 | grep -iE 'FILTER_ARTICLES|MERGE_NEWS|MERGE_SCHEDULE|PIPELINE|No articles' | tail -15 || echo "(none)"

echo ""
echo "=== Nodes from docker logs (last 3 min) ==="
docker logs facebook-news-n8n --since 3m 2>&1 | grep -iE 'executing node|finished node|Start executing|Workflow execution' | tail -25 || echo "(none)"

echo ""
echo "=== Recent log errors ==="
docker logs facebook-news-n8n --tail 50 2>&1 | grep -iE 'error|failed|exception|webhook' | tail -15 || echo "(none)"
