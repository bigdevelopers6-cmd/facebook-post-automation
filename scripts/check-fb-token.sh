#!/bin/bash
# Facebook Page token: diagnose + verify publish permissions (run on EC2 with .env).
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
echo " Token fingerprint: ${TOKEN:0:12}...${TOKEN: -8}"
echo "=============================================="
echo ""

# Optional: show granted scopes (needs App ID + App Secret in .env)
if [ -n "${FB_APP_ID:-}" ] && [ -n "${FB_APP_SECRET:-}" ]; then
  echo "[debug] Token scopes (debug_token)..."
  DBG=$(curl -s "https://graph.facebook.com/${API_VER}/debug_token?input_token=${TOKEN}&access_token=${FB_APP_ID}%7C${FB_APP_SECRET}")
  python3 -c "
import sys, json
j = json.load(sys.stdin).get('data', {})
if not j:
    print('     debug_token failed:', json.load(open('/dev/stdin')) if False else sys.stdin)
    sys.exit(0)
print('     type:', j.get('type'), '| app_id:', j.get('app_id'))
scopes = j.get('scopes') or []
print('     scopes:', ', '.join(scopes) if scopes else '(none listed)')
for need in ('pages_manage_posts', 'pages_read_engagement'):
    ok = need in scopes
    print('     ', need + ':', 'YES' if ok else 'MISSING')
if j.get('type') == 'USER':
    print('')
    print('[!!] This is a USER token, not a PAGE token.')
    print('     Use scripts/extract-page-token.sh to get the Page token string.')
" <<< "$DBG" 2>/dev/null || true
  echo ""
fi

# 1) Page identity
echo "[1/4] Page identity (GET /{page}?fields=id,name)..."
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

# 2) Is this a User token? Offer Page token from me/accounts
echo ""
echo "[2/4] Token type (GET /me — user token check)..."
ME=$(curl -s "https://graph.facebook.com/${API_VER}/me?fields=id,name&access_token=${TOKEN}")
IS_USER=$(python3 -c "
import sys, json
j = json.load(sys.stdin)
if j.get('id') and not j.get('error'):
    print('yes')
    print('[!!]  Token is a USER token (me=', j.get('name'), 'id=', j.get('id'), ')', sep='')
    print('     POST /{page}/feed needs the PAGE access_token from me/accounts, not this string.')
    sys.exit(0)
print('no')
" <<< "$ME" 2>/dev/null | head -1 || echo "no")

if [ "$IS_USER" = "yes" ]; then
  echo ""
  echo "     Fetching Page tokens from me/accounts..."
  ACC=$(curl -s "https://graph.facebook.com/${API_VER}/me/accounts?fields=id,name,access_token&access_token=${TOKEN}")
  python3 -c "
import sys, json
page = '$PAGE'
j = json.load(sys.stdin)
data = j.get('data') or []
if not data:
    print('[!!]  me/accounts empty:', j.get('error', j))
    sys.exit(1)
for p in data:
    mark = ' <-- USE THIS IN .env' if str(p.get('id')) == page else ''
    print('     Page', p.get('name'), 'id=', p.get('id'), mark)
    if str(p.get('id')) == page and p.get('access_token'):
        tok = p['access_token']
        print('')
        print('[FIX] Replace FB_ACCESS_TOKEN in .env with this PAGE token:')
        print('FB_ACCESS_TOKEN=' + tok)
        sys.exit(2)
print('[!!]  Page', page, 'not in me/accounts — assign Page to your app/user in Meta Business')
sys.exit(1)
" <<< "$ACC" || USER_EXIT=$?
  if [ "${USER_EXIT:-0}" = "2" ]; then
    echo ""
    echo "     After updating .env: docker compose up -d --force-recreate && bash scripts/check-fb-token.sh"
    exit 1
  fi
else
  echo "[OK]  Not a user /me token (likely Page token)"
fi

# 3) Read engagement
echo ""
echo "[3/4] Read engagement (GET /{page}/published_posts?limit=1)..."
READ_RESP=$(curl -s "https://graph.facebook.com/${API_VER}/${PAGE}/published_posts?limit=1&access_token=${TOKEN}")
python3 -c "
import sys, json
j = json.load(sys.stdin)
err = j.get('error', {})
if err:
    print('[!!] pages_read_engagement likely missing')
    print('     ', str(err.get('message', err))[:350])
    sys.exit(1)
print('[OK]  published_posts readable')
" <<< "$READ_RESP"

# 4) Publish probe
echo ""
echo "[4/4] Publish permission (POST /{page}/feed published=false)..."
POST_RESP=$(curl -s -X POST "https://graph.facebook.com/${API_VER}/${PAGE}/feed" \
  -d "message=US News Bot permission probe — safe to delete" \
  -d "published=false" \
  -d "access_token=${TOKEN}")

POST_ID=$(python3 -c "
import sys, json
j = json.load(sys.stdin)
err = j.get('error', {})
if err:
    msg = str(err.get('message', ''))
    print(msg[:600], file=sys.stderr)
    print('', file=sys.stderr)
    print('COMMON FIXES:', file=sys.stderr)
    print('  1. Adding permissions in Meta does NOT update an old token string.', file=sys.stderr)
    print('     You must click Generate Token again and paste the NEW string.', file=sys.stderr)
    print('  2. Use the PAGE token from me/accounts (run: bash scripts/extract-page-token.sh)', file=sys.stderr)
    print('  3. System User token needs: pages_manage_posts + pages_read_engagement', file=sys.stderr)
    print('     and Page asset assigned with Full control.', file=sys.stderr)
    print('  4. After .env change: docker compose up -d --force-recreate', file=sys.stderr)
    sys.exit(1)
print(j.get('id', ''))
" <<< "$POST_RESP" 2>&1) || {
  echo "[!!] Publish check FAILED"
  exit 1
}

echo "[OK]  Can publish — probe id: $POST_ID"
if [ -n "$POST_ID" ]; then
  curl -s -X DELETE "https://graph.facebook.com/${API_VER}/${POST_ID}?access_token=${TOKEN}" > /dev/null 2>&1 || true
  echo "[OK]  Deleted probe post"
fi

# Docker env sanity
echo ""
echo "[docker] FB_ACCESS_TOKEN inside n8n container:"
docker exec facebook-news-n8n sh -c 'echo "${FB_ACCESS_TOKEN:0:12}...${FB_ACCESS_TOKEN: -8}"' 2>/dev/null || echo "(container not running)"

echo ""
echo "[OK]  Token is ready for automation."
