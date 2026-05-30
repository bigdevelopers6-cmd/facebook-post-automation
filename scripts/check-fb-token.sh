#!/bin/bash
# Quick Facebook Page token check (run on EC2 in project dir with .env loaded).
set -e
cd "$(dirname "$0")/.."

if [ -f .env ]; then
  set -a
  # shellcheck disable=SC1091
  source .env
  set +a
fi

PAGE="${FB_PAGE_ID:-1191676374021102}"
TOKEN="${FB_ACCESS_TOKEN:-}"

if [ -z "$TOKEN" ]; then
  echo "[!!] FB_ACCESS_TOKEN is empty in .env"
  exit 1
fi

echo "Checking token for page $PAGE ..."
RESP=$(curl -s "https://graph.facebook.com/v19.0/${PAGE}?fields=id,name&access_token=${TOKEN}")
echo "$RESP" | python3 -c "
import sys, json
j = json.load(sys.stdin)
if j.get('id'):
    print('[OK]  Token valid — page:', j.get('name'), 'id:', j.get('id'))
else:
    print('[!!] Token invalid:', j.get('error', j))
    sys.exit(1)
"
