#!/bin/bash
# Full post-run report: pipeline.log, execution API, docker logs.
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
echo "=== 1. pipeline.log (file trace — most reliable) ==="
if [ -f data/reports/pipeline.log ]; then
  if [ -s data/reports/pipeline.log ]; then
    cat data/reports/pipeline.log
  else
    echo "(empty — workflow did not write logs; wrong build or nodes never ran)"
  fi
else
  echo "(missing — mkdir data/reports and redeploy workflow)"
fi

echo ""
echo "=== 2. Workflow build on disk ==="
grep -E 'workflowBuild|function pipelineLog' workflow/facebook-us-news-automation.json | head -3

echo ""
echo "=== 3. Execution API ==="
curl -s -c /tmp/n8n-cookies.txt -X POST http://localhost:5678/rest/login \
  -H "Content-Type: application/json" \
  -d "{\"emailOrLdapLoginId\":\"$N8N_EMAIL\",\"password\":\"$N8N_PASSWORD\"}" > /dev/null 2>&1 || true
curl -s -b /tmp/n8n-cookies.txt \
  "http://localhost:5678/rest/executions/${EXEC_ID}?includeData=true" -o /tmp/exec.json

python3 << PY
import json, re, sys
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
if hints.get("errors"):
    print("Raw errors found:")
    for e in hints["errors"][:8]:
        print(" ", e[:200])
if hints.get("pipeline_lines"):
    print("Raw [PIPELINE] in JSON:", len(hints["pipeline_lines"]))
node_hits = hints.get("node_hits", {})
if node_hits:
    print("Node name hits in raw JSON:", ", ".join(f"{k}={v}" for k,v in sorted(node_hits.items())[:20]))
PY

echo ""
echo "=== 4. Docker logs (3 min) ==="
docker logs facebook-news-n8n --since 3m 2>&1 | grep -iE '\[PIPELINE\]|FILTER|MERGE_|No articles|error|Error in node' | tail -40 || echo "(no matching lines)"

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
