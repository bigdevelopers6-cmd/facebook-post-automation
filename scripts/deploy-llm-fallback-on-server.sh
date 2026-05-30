#!/bin/bash
# Run on Ubuntu server in ~/awraaq_sgid after updating workflow JSON + .env
set -e
cd "$(dirname "$0")/.."

# Patch NewsAPI User-Agent if missing
python3 << 'PY'
import json
path = "workflow/facebook-us-news-automation.json"
with open(path, encoding="utf-8") as f:
    wf = json.load(f)
ua = {"name": "User-Agent", "value": "FacebookUSNewsBot/1.0 (n8n)"}
for node in wf.get("nodes", []):
    p = node.get("parameters") or {}
    if "newsapi.org" not in (p.get("url") or ""):
        continue
    p["sendHeaders"] = True
    params = p.setdefault("headerParameters", {"parameters": []})["parameters"]
    if not any(x.get("name") == "User-Agent" for x in params):
        params.append(ua)
with open(path, "w", encoding="utf-8") as f:
    json.dump(wf, f, indent=2)
print("Workflow ready:", path)
PY

docker compose down
docker compose up -d
sleep 12
docker cp workflow/facebook-us-news-automation.json facebook-news-n8n:/tmp/workflow.json
docker exec facebook-news-n8n n8n import:workflow --input=/tmp/workflow.json
docker exec facebook-news-n8n n8n publish:workflow --id=facebook-us-news-001
docker restart facebook-news-n8n
sleep 15
echo "Deploy done. Test: ./scripts/run-now.sh"
