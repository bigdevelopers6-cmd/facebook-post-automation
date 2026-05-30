#!/bin/bash
# Full post-run report: pipeline trace, execution API, docker logs.
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

echo "=============================================="
echo " Execution report — ID $EXEC_ID"
echo "=============================================="

echo ""
echo "=== 1. Pipeline trace (staticData — saved in execution JSON) ==="
curl -s -c /tmp/n8n-cookies.txt -X POST http://localhost:5678/rest/login \
  -H "Content-Type: application/json" \
  -d "{\"emailOrLdapLoginId\":\"$N8N_EMAIL\",\"password\":\"$N8N_PASSWORD\"}" > /dev/null 2>&1 || true
curl -s -b /tmp/n8n-cookies.txt \
  "http://localhost:5678/rest/executions/${EXEC_ID}?includeData=true" -o /tmp/exec.json

python3 << 'PY'
import json, sys
from pathlib import Path
sys.path.insert(0, str(Path("scripts").resolve()))
from n8n_exec_parse import extract_execution_error

root = json.load(open("/tmp/exec.json"))
raw = Path("/tmp/exec.json").read_text(encoding="utf-8")
errs = extract_execution_error(root, raw)
if errs:
    for e in errs:
        print(e)
else:
    print("(no trace/errors found in execution JSON — open execution in n8n UI)")
PY

echo ""
echo "=== 2. Workflow build on disk ==="
grep -o 'workflowBuild[^,}]*' workflow/facebook-us-news-automation.json | head -1 || echo "(no workflowBuild meta)"
echo "pipelineLog fn count: $(grep -c 'function pipelineLog' workflow/facebook-us-news-automation.json || echo 0)"

echo ""
echo "=== 3. Execution API summary ==="
python3 << 'PY'
import json, sys
from pathlib import Path
sys.path.insert(0, str(Path("scripts").resolve()))
from n8n_exec_parse import parse_execution, format_node_list, scan_raw_execution

root = json.load(open("/tmp/exec.json"))
run, last, status, _ = parse_execution(root)
print("Status:", status, "| lastNode:", last, "| runData nodes:", len(run))
print(format_node_list(run))
raw = Path("/tmp/exec.json").read_text(encoding="utf-8")
hints = scan_raw_execution(raw)
if hints.get("last_nodes"):
    print("Raw lastNodeExecuted:", hints["last_nodes"][-3:])
PY

echo ""
echo "=== 4. Docker logs (5 min) ==="
docker logs facebook-news-n8n --since 5m 2>&1 | grep -iE '\[PIPELINE\]|Problem in node|Error in node|MERGE_|FILTER_|haltProduction|evaluateProduction' | tail -50 || echo "(no matching lines — try: docker logs facebook-news-n8n --tail 80)"

echo ""
echo "=== 5. Recent executions ==="
curl -s -b /tmp/n8n-cookies.txt \
  "http://localhost:5678/rest/executions?limit=5&workflowId=$WF_ID" | python3 -c "
import sys, json
from datetime import datetime
for e in json.load(sys.stdin).get('data', {}).get('results', []):
    s, f = e.get('startedAt'), e.get('stoppedAt')
    dur = ''
    if s and f:
        a = datetime.fromisoformat(s.replace('Z', '+00:00'))
        b = datetime.fromisoformat(f.replace('Z', '+00:00'))
        dur = f' {(b-a).total_seconds():.1f}s'
    print(e.get('id'), e.get('status') + dur, 'mode=' + str(e.get('mode')))
"
