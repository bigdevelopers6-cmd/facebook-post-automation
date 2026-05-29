# Troubleshooting Playbook

Ten failure scenarios with root cause and fix for the Facebook US News Automation Agent.

---

## 1. Facebook Token Expired Mid-Day

**Symptoms:**
- Posts succeed in the morning but fail after ~12:00 PM
- `checkFBToken` shows `tokenValid: false` or `expiresInDays < 7`
- `errorLog` entries with `error_code: TOKEN_INVALID`
- Alert email: "Facebook Token Alert — Action Required"

**Cause:**
Short-lived Page Access Token (60-day Graph API Explorer token) expired, or System User token was revoked when page permissions changed.

**Fix:**
1. Run `/auto check-token` to confirm token status
2. Generate new never-expiring System User token (see Setup Guide Step 7.3)
3. Update `FB_PAGE_ACCESS_TOKEN` credential in n8n
4. Run `/auto reset-errors` to clear circuit breaker
5. Run `/auto test-one` to verify posting works
6. Re-activate workflow if paused

**Prevention:** Use Meta Business Suite System User tokens with "Never" expiration. Set calendar reminder to run `/auto check-token` weekly.

---

## 2. NewsAPI 429 Rate Limit Hit

**Symptoms:**
- `fetchUSNews` or `fetchFallbackNews` fails with HTTP 429
- Execution log shows retry attempts (2s, 4s, 8s backoff)
- Fewer than 10 articles fetched; `[REPOST]` flags appear in output

**Cause:**
Free NewsAPI tier allows 100 requests/day. Multiple manual `/auto run-now` tests plus daily fetches exceeded quota.

**Fix:**
1. Check usage at [newsapi.org/account](https://newsapi.org/account)
2. Wait until quota resets (midnight UTC)
3. Upgrade to Developer plan ($449/mo) for production volume, OR reduce test runs
4. Run `/auto health-check` — NewsAPI should return 200 after reset
5. Workflow will use fallback + repost logic to fill slots; no manual intervention needed for partial failure

**Prevention:** Limit `/auto run-now` during development. One daily fetch + one fallback = 2 API calls per day in production.

---

## 3. OpenAI Image URL Expired Before Facebook Fetched It

**Symptoms:**
- `generateImage` succeeds (returns URL)
- `publishToFacebook` fails with image fetch error
- Facebook error: "Failed to fetch the image from the URL"

**Cause:**
OpenAI DALL-E/gpt-image-1 URLs expire within ~60 minutes. Long `waitForSlot` delays (posts scheduled hours after image generation) can cause expiry if image is generated before the wait completes.

**Fix:**
1. Verify workflow order: image generation happens **after** `waitForSlot`, not before — this is the correct design in the imported workflow
2. If modified: move `generateImage` to after the Wait node
3. On failure: workflow error handler logs to `errorLog` and continues to next slot
4. Re-run failed slot with `/auto test-one`

**Prevention:** Never cache AI image URLs in static data. Generate image immediately before Facebook publish call.

---

## 4. Claude Returns Non-JSON in Review Nodes

**Symptoms:**
- `parsePrePublishReview` or `parseImageReview` sets `approved: false, risk_level: 'high'`
- `flags: ['parse_error']` in review output
- Posts skipped with `SKIPPED_COMPLIANCE` after rewrite attempts

**Cause:**
Claude occasionally wraps JSON in markdown code fences or adds explanatory text despite system prompt instructions.

**Fix:**
1. Check execution log for raw Claude response in review nodes
2. The workflow already strips ` ```json ` fences in parse nodes — if still failing, tighten system prompt
3. Run `/auto reset-errors` and retry with `/auto test-one`
4. If persistent: reduce `max_tokens` to 150 for review nodes to discourage extra text
5. Skipped posts are logged — no Facebook post was made (safe failure)

**Prevention:** Monitor `SKIPPED_COMPLIANCE` count in daily report. If >2/day, review Claude prompt formatting.

---

## 5. Workflow Posts Outside US Hours Due to Timezone Misconfiguration

**Symptoms:**
- Posts appear at 2:00 AM or 3:00 AM Eastern
- `todaySchedule` epochMs values don't match expected ET windows
- Daily report timestamps show UTC instead of ET

**Cause:**
Docker container `TZ` not set to `America/New_York`, or n8n instance timezone differs from schedule trigger timezone.

**Fix:**
1. Verify docker-compose.yml has:
   ```yaml
   - TZ=America/New_York
   - GENERIC_TIMEZONE=America/New_York
   ```
2. Restart container: `docker compose down && docker compose up -d`
3. In n8n: **Settings → Personal → Timezone → America/New_York**
4. Verify schedule triggers show timezone `America/New_York`
5. Run scheduler manually and inspect `todaySchedule.scheduledEt` values — all should be 07:00–21:45 ET

**Prevention:** Never run n8n with default UTC timezone for US-targeted content.

---

## 6. Duplicate Articles Posted Despite Dedup Logic

**Symptoms:**
- Same news story appears twice on Facebook page within 24 hours
- `postedURLs` in static data doesn't contain the duplicate URL

**Cause:**
(a) URL changed between fetches (tracking params, redirects), (b) `/auto flush-cache` was run, (c) `[REPOST]` flag articles intentionally reused when fewer than 10 unique articles available, (d) static data lost on workflow re-import.

**Fix:**
1. Run `/auto review-log` — check if `isRepost: true` on duplicate
2. Inspect `postedURLs` via execution log in `updatePostedURLs` node
3. Normalize URLs in `filterArticles` (strip query params) if tracking URLs differ:
   ```javascript
   url = url.split('?')[0];
   ```
4. Avoid `/auto flush-cache` in production
5. After workflow re-import, static data resets — dedup history is lost

**Prevention:** Don't re-import workflow in production without exporting static data first. Accept `[REPOST]` behavior on slow news days.

---

## 7. Meta API Rejects Post — (#200) Permissions Error

**Symptoms:**
- `publishToFacebook` returns HTTP 403 or error code 200
- Error message: "(#200) Requires extended permission: pages_manage_posts"
- `handlePublishError` logs to errorLog

**Cause:**
Page Access Token missing `pages_manage_posts` permission, token generated for wrong page, or app not approved for production use with non-admin accounts.

**Fix:**
1. Verify token permissions:
   ```bash
   curl "https://graph.facebook.com/debug_token?input_token=TOKEN&access_token=TOKEN"
   ```
2. Check `scopes` includes `pages_manage_posts`
3. Regenerate System User token with correct permissions (Setup Guide Step 7.3)
4. Confirm `FB_PAGE_ID` matches the page the token has access to:
   ```bash
   curl "https://graph.facebook.com/v19.0/me/accounts?access_token=TOKEN"
   ```
5. Update credentials and run `/auto test-one`

**Prevention:** Use System User with Full Control on the specific page asset.

---

## 8. n8n Execution Timeout on Long Image Generation

**Symptoms:**
- Workflow execution shows "Execution timed out"
- `generateImage` node was running when timeout occurred
- OpenAI gpt-image-1 can take 30–120 seconds

**Cause:**
Default n8n execution timeout (1 hour on self-hosted, but some configs set lower), or Docker resource limits.

**Fix:**
1. Increase execution timeout in docker-compose.yml:
   ```yaml
   - EXECUTIONS_TIMEOUT=7200
   - EXECUTIONS_TIMEOUT_MAX=7200
   ```
2. Increase Docker memory: `deploy.resources.limits.memory: 2g`
3. Restart n8n
4. Failed slot logs to errorLog and loop continues — other slots unaffected

**Prevention:** Ensure server has adequate RAM. Don't run other heavy workloads on the n8n host during post windows.

---

## 9. Circuit Breaker Fires Incorrectly Due to Transient Errors

**Symptoms:**
- Alert: "Circuit Breaker Triggered — Facebook Posting Halted"
- Only 2–3 posts attempted but `consecutiveFailures > 4`
- Transient network blips caused false consecutive failure count

**Cause:**
Circuit breaker counts all publish failures consecutively without distinguishing transient (503, timeout) from permanent (401, 403) errors. A single slot retrying doesn't reset the counter — only success in `updatePostedURLs` resets it.

**Fix:**
1. Run `/auto reset-errors` to clear circuit breaker state
2. Run `/auto health-check` to verify all APIs healthy
3. Run `/auto check-token` to verify Facebook token
4. Resume with `/auto resume` (activate workflow)
5. Remaining slots will process on next execution

**Improvement (optional):** Modify `handlePublishError` to only increment counter on 4xx errors, not 5xx/timeouts.

**Prevention:** Monitor `errorLog` after any circuit breaker alert before resetting.

---

## 10. Daily Report Not Sending Due to Email Node Misconfiguration

**Symptoms:**
- `scheduleTrigger11PM` fires (visible in Executions)
- `dailySummary` completes but no email received
- No file at `/data/reports/daily_YYYY-MM-DD.txt`

**Cause:**
(a) SMTP credential not connected to `sendDailyReport` node, (b) `N8N_ALERT_TO` env var not set, (c) `/data/reports` volume not mounted, (d) email caught in spam.

**Fix:**
1. Open `sendDailyReport` node → verify SMTP credential is selected (not red warning)
2. Check docker-compose environment variables:
   ```yaml
   - N8N_ALERT_FROM=alerts@yourdomain.com
   - N8N_ALERT_TO=owner@yourdomain.com
   ```
3. Test email manually: run `/auto daily-report` and watch execution log
4. Verify volume mount:
   ```bash
   docker compose exec n8n ls -la /data/reports/
   ```
5. Check spam/junk folder
6. For Gmail SMTP: use App Password, not account password

**Prevention:** Include email test in initial `/auto test-one` setup validation. Confirm daily report after first full day of operation.

---

## Emergency Quick Actions

| Situation | Command |
|-----------|---------|
| Stop all posting immediately | `/auto pause` + deactivate workflow |
| Check if APIs are up | `/auto health-check` |
| Check Facebook token | `/auto check-token` |
| See what posted today | `/auto review-log` |
| Reset after fixing issues | `/auto reset-errors` |
| Verify single post works | `/auto test-one` |
