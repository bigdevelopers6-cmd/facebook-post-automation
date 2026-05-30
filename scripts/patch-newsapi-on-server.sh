#!/bin/bash
# Run on Ubuntu server inside ~/awraaq_sgid — no git pull required.
# Adds NewsAPI User-Agent header to workflow JSON and re-imports into n8n.

set -e
cd "$(dirname "$0")/.."
WF="workflow/facebook-us-news-automation.json"

if [ ! -f "$WF" ]; then
  echo "Missing $WF — run this from ~/awraaq_sgid"
  exit 1
fi

python3 << 'PY'
import json

path = "workflow/facebook-us-news-automation.json"
with open(path, encoding="utf-8") as f:
    wf = json.load(f)

ua = {
    "name": "User-Agent",
    "value": "FacebookUSNewsBot/1.0 (n8n; contact=bigdevelopers6@gmail.com)",
}
patched = 0
for n in wf.get("nodes", []):
    p = n.get("parameters") or {}
    url = p.get("url") or ""
    if "newsapi.org" not in url:
        continue
    p["sendHeaders"] = True
    hp = p.setdefault("headerParameters", {"parameters": []})
    params = hp["parameters"]
    names = {x.get("name") for x in params}
    if "User-Agent" not in names:
        params.append(ua)
        patched += 1
    if "X-Api-Key" not in names:
        params.insert(
            0,
            {"name": "X-Api-Key", "value": "={{ $env.NEWSAPI_KEY }}"},
        )

    # Stricter production gate check for NewsAPI
    if n.get("name") == "evaluateProductionApis":
        code = p.get("jsCode", "")
        old = "j && j.status === 'ok' && !j.error"
        new = "j && j.status === 'ok' && Array.isArray(j.articles) && !j.error"
        if old in code and new not in code:
            p["jsCode"] = code.replace(old, new)

with open(path, "w", encoding="utf-8") as f:
    json.dump(wf, f, indent=2)
    f.write("\n")

print(f"Patched {patched} NewsAPI node(s) in {path}")
PY

echo "Importing workflow into n8n..."
docker cp "$WF" facebook-news-n8n:/tmp/workflow.json
docker exec facebook-news-n8n n8n import:workflow --input=/tmp/workflow.json
docker exec facebook-news-n8n n8n publish:workflow --id=facebook-us-news-001
docker restart facebook-news-n8n
echo "Done. Wait 15s then run: ./scripts/run-now.sh"
