#!/bin/bash
# If you have a USER token, print the PAGE access_token for FB_PAGE_ID (paste into .env).
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
API_VER="${FB_API_VERSION:-v19.0}"
CURL_OPTS=(--max-time 45 --connect-timeout 15 -sS)

if [ -z "$TOKEN" ]; then
  echo "[!!] Set FB_ACCESS_TOKEN in .env first (can be a short-lived user token)"
  exit 1
fi

echo "Fetching Page tokens (me/accounts) for ${TOKEN:0:12}..."
RESP=$(curl "${CURL_OPTS[@]}" "https://graph.facebook.com/${API_VER}/me/accounts?fields=id,name,access_token,tasks&access_token=${TOKEN}") || {
  echo "[!!] curl failed — check network / DNS to graph.facebook.com"
  exit 1
}

python3 -c "
import sys, json
page = '$PAGE'
j = json.load(sys.stdin)
if j.get('error'):
    print('[!!]', j['error'])
    sys.exit(1)
data = j.get('data') or []
if not data:
    print('[!!] No pages returned. Grant your app access to the Page in Meta Business.')
    sys.exit(1)
found = None
for p in data:
    print('Page:', p.get('name'), '| id:', p.get('id'), '| tasks:', p.get('tasks'))
    if str(p.get('id')) == page:
        found = p.get('access_token')
if not found:
    print('[!!] Page id', page, 'not in list above')
    sys.exit(1)
print('')
print('Put this in .env (PAGE token, not user token):')
print('FB_ACCESS_TOKEN=' + found)
" <<< "$RESP"
