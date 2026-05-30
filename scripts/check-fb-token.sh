#!/bin/bash
# Facebook Page token: read + publish permission check (run on EC2 with .env).
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

if [ -z "$TOKEN" ]; then
  echo "[!!] FB_ACCESS_TOKEN is empty in .env"
  exit 1
fi

echo "=============================================="
echo " Facebook Page token check — page $PAGE"
echo "=============================================="
echo ""

# 1) Can we read the page? (weak check — passes without publish perms)
echo "[1/3] Page identity (GET /{page}?fields=id,name)..."
RESP=$(curl -s "https://graph.facebook.com/${API_VER}/${PAGE}?fields=id,name&access_token=${TOKEN}")
python3 -c "
import sys, json
j = json.load(sys.stdin)
if j.get('id'):
    print('[OK]  Read page:', j.get('name'), '(id', j.get('id'), ')')
else:
    print('[!!] Cannot read page:', j.get('error', j))
    sys.exit(1)
" <<< "$RESP"

# 2) Engagement read (pages_read_engagement)
echo ""
echo "[2/3] Read engagement (GET /{page}/published_posts?limit=1)..."
READ_RESP=$(curl -s "https://graph.facebook.com/${API_VER}/${PAGE}/published_posts?limit=1&access_token=${TOKEN}")
python3 -c "
import sys, json
j = json.load(sys.stdin)
err = j.get('error', {})
if err:
    code = err.get('code', '')
    msg = err.get('message', err)
    print('[!!] pages_read_engagement likely missing')
    print('     ', msg[:300])
    if code == 200 or 'pages_read_engagement' in str(msg):
        print('')
        print('     Fix: Regenerate Page token with pages_read_engagement')
    sys.exit(1)
print('[OK]  Can read published_posts (pages_read_engagement)')
" <<< "$READ_RESP"

# 3) Publish probe (pages_manage_posts) — unpublished post, then delete if created
echo ""
echo "[3/3] Publish permission (POST /{page}/feed published=false)..."
POST_RESP=$(curl -s -X POST "https://graph.facebook.com/${API_VER}/${PAGE}/feed" \
  -d "message=US News Bot permission probe — safe to delete" \
  -d "published=false" \
  -d "access_token=${TOKEN}")

POST_ID=$(python3 -c "
import sys, json
j = json.load(sys.stdin)
err = j.get('error', {})
if err:
    msg = err.get('message', '')
    print('FAIL', file=sys.stderr)
    print(msg[:500], file=sys.stderr)
    if 'pages_manage_posts' in msg or 'pages_read_engagement' in msg or err.get('code') == 200:
        print('', file=sys.stderr)
        print('REQUIRED Page token permissions:', file=sys.stderr)
        print('  - pages_manage_posts', file=sys.stderr)
        print('  - pages_read_engagement', file=sys.stderr)
        print('', file=sys.stderr)
        print('How to fix (Meta Business):', file=sys.stderr)
        print('  1. business.facebook.com → Settings → System users', file=sys.stderr)
        print('  2. Select your system user → Generate token', file=sys.stderr)
        print('  3. App: US News Automation → check BOTH permissions above', file=sys.stderr)
        print('  4. Assign Page asset with Full control', file=sys.stderr)
        print('  5. Paste token into ~/awraaq_sgid/.env as FB_ACCESS_TOKEN', file=sys.stderr)
        print('  6. docker compose up -d && bash scripts/run-now.sh', file=sys.stderr)
    sys.exit(1)
print(j.get('id', ''))
" <<< "$POST_RESP" 2>&1) || {
  echo "[!!] Cannot publish to Page — this is why run-now fails with PUBLISH_FAIL 403"
  exit 1
}

echo "[OK]  Can publish (pages_manage_posts) — probe post id: $POST_ID"

if [ -n "$POST_ID" ]; then
  curl -s -X DELETE "https://graph.facebook.com/${API_VER}/${POST_ID}?access_token=${TOKEN}" > /dev/null 2>&1 || true
  echo "[OK]  Deleted probe post"
fi

echo ""
echo "[OK]  Token is ready for automation."
