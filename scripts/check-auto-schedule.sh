#!/bin/bash
# Verify daily 10-post automation (6:45 AM ET schedule) vs manual webhook test.
set -e
cd "$(dirname "$0")/.."

N8N_EMAIL="${N8N_EMAIL:-bigdevelopers6@gmail.com}"
N8N_PASSWORD="${N8N_PASSWORD:-Admin@12345}"
WF_ID="${WF_ID:-facebook-us-news-001}"
FB_PAGE="${FB_PAGE_ID:-1191676374021102}"

echo "=============================================="
echo " Auto schedule health check"
echo " Workflow: $WF_ID"
echo "=============================================="
echo ""

if ! curl -sf http://localhost:5678/healthz >/dev/null 2>&1; then
  echo "[!!] n8n is not running — bash scripts/server-restart.sh"
  exit 1
fi

curl -s -o /tmp/n8n-login.json -c /tmp/n8n-cookies.txt \
  -X POST http://localhost:5678/rest/login \
  -H "Content-Type: application/json" \
  -d "{\"emailOrLdapLoginId\":\"$N8N_EMAIL\",\"password\":\"$N8N_PASSWORD\"}" >/dev/null

python3 << 'PY'
import json, os, subprocess
from datetime import datetime, timezone
from zoneinfo import ZoneInfo

wf_id = os.environ.get("WF_ID", "facebook-us-news-001")
fb_page = os.environ.get("FB_PAGE_ID", "1191676374021102")

def curl_json(url):
    r = subprocess.run(
        ["curl", "-s", "-b", "/tmp/n8n-cookies.txt", url],
        capture_output=True, text=True,
    )
    if r.returncode != 0 or not r.stdout.strip():
        return {}
    try:
        return json.loads(r.stdout)
    except json.JSONDecodeError:
        return {"raw": r.stdout[:500]}

wf = curl_json(f"http://localhost:5678/rest/workflows/{wf_id}")
data = wf.get("data") or wf
active = data.get("active")
name = data.get("name", wf_id)
print(f"Workflow name: {name}")
print(f"Workflow ACTIVE (required for auto posts): {active}")
if active is not True:
    print("")
    print("[!!] Auto posting is OFF until the workflow is Active in n8n UI.")
    print("    Open http://YOUR_IP:5678 → workflow → toggle Active (top right).")
print("")

execs = curl_json(f"http://localhost:5678/rest/executions?limit=50&workflowId={wf_id}")
results = (execs.get("data") or {}).get("results") or execs.get("results") or []

def parse_ts(s):
    if not s:
        return None
    try:
        return datetime.fromisoformat(s.replace("Z", "+00:00"))
    except Exception:
        return None

by_mode = {}
schedule_runs = []
webhook_runs = []
for e in results:
    mode = e.get("mode") or "unknown"
    by_mode[mode] = by_mode.get(mode, 0) + 1
    started = parse_ts(e.get("startedAt"))
    row = {
        "id": e.get("id"),
        "mode": mode,
        "status": e.get("status"),
        "started": e.get("startedAt"),
    }
    if mode == "trigger":
        schedule_runs.append(row)
    elif mode == "webhook":
        webhook_runs.append(row)

print("Recent executions (last 50) by mode:")
for m, c in sorted(by_mode.items(), key=lambda x: -x[1]):
    print(f"  {m}: {c}")

print("")
print("--- Daily scheduler (mode=trigger) ---")
if not schedule_runs:
    print("[!!] No schedule-trigger executions found in the last 50 runs.")
    print("    Either the workflow was inactive, or 6:45 AM ET has not fired since deploy.")
else:
    for r in schedule_runs[:5]:
        print(f"  id={r['id']} status={r['status']} started={r['started']}")

print("")
print("--- Manual webhook test (run-now.sh) ---")
if webhook_runs:
    w = webhook_runs[0]
    print(f"  Latest: id={w['id']} status={w['status']} started={w['started']}")
else:
    print("  (none in last 50)")

# Server + container timezone
try:
    et = datetime.now(ZoneInfo("America/New_York"))
    print("")
    print(f"Server time now (ET): {et.strftime('%Y-%m-%d %H:%M %Z')}")
    print("Daily auto run fires at: 06:45 America/New_York (scheduleTrigger645AM)")
    if et.hour < 6 or (et.hour == 6 and et.minute < 45):
        print("  → Today's batch has not started yet (waits until 6:45 AM ET).")
    elif et.hour >= 22:
        print("  → Today's posting window is mostly over; check Page for posts or tomorrow 6:45 AM.")
    else:
        print("  → Today's batch should be running or in progress (slots until ~10 PM ET).")
except Exception as ex:
    print(f"(timezone hint skipped: {ex})")

print("")
print("--- Pipeline log (scheduled vs webhook) ---")
log_path = "data/reports/pipeline.log"
if os.path.isfile(log_path):
    text = open(log_path, encoding="utf-8", errors="replace").read()
    lines = [ln for ln in text.splitlines() if ln.strip()][-40:]
    publish = [ln for ln in lines if "PUBLISH_OK" in ln]
    scheduled = [ln for ln in lines if "gateScheduledPath" in ln or "waitMs=" in ln]
    webhook = [ln for ln in lines if "webhookDirectToSlot" in ln or "webhookSlotFast" in ln]
    print(f"  pipeline.log lines (tail): {len(lines)}")
    print(f"  PUBLISH_OK in tail: {len(publish)}")
    if publish:
        print(f"  Last publish: {publish[-1][-120:]}")
    print(f"  Scheduled markers in tail: {len(scheduled)}")
    print(f"  Webhook markers in tail: {len(webhook)}")
    if webhook and not scheduled:
        print("  [i] Log looks like manual/webhook tests only — not proof of 6:45 AM auto.")
else:
    print("  (no data/reports/pipeline.log)")

print("")
print("--- Facebook Page (quick) ---")
token = os.environ.get("FB_ACCESS_TOKEN", "")
if not token:
    try:
        with open(".env") as f:
            for line in f:
                if line.startswith("FB_ACCESS_TOKEN="):
                    token = line.split("=", 1)[1].strip().strip('"').strip("'")
                    break
    except Exception:
        pass
if token:
    import urllib.request
    url = f"https://graph.facebook.com/v19.0/{fb_page}/published_posts?limit=5&fields=created_time,message&access_token={token}"
    try:
        with urllib.request.urlopen(url, timeout=15) as resp:
            posts = json.loads(resp.read()).get("data", [])
        print(f"  Last {len(posts)} published posts on Page:")
        for p in posts[:5]:
            msg = (p.get("message") or "")[:60].replace("\n", " ")
            print(f"    {p.get('created_time')}  {msg}...")
    except Exception as e:
        print(f"  (could not read Page posts: {e})")
else:
    print("  (set FB_ACCESS_TOKEN in .env to list recent Page posts)")

print("")
print("==============================================")
print(" Summary")
print("==============================================")
ok = active is True
if ok and schedule_runs:
    print("[OK]  Workflow is Active and schedule executions exist.")
elif ok and not schedule_runs:
    print("[??]  Workflow is Active but no schedule runs in last 50 executions.")
    print("      Wait for 6:45 AM ET or run a full-day test: n8n Manual → command run-now")
else:
    print("[!!]  Turn workflow ACTIVE in n8n to enable daily auto posting.")
print("")
print("Manual test (webhook):  bash scripts/run-now.sh")
print("Full 10-slot test now:  n8n → Manual Trigger → setAutoCommand command=run-now")
print("Page:                   https://www.facebook.com/" + fb_page)
PY
