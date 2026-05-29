# /auto Command Reference

On-demand control commands for the Facebook US News Automation Agent. Use via the **manualTrigger** node in n8n.

## How to Run a Command

1. Open workflow **Facebook US News Automation Agent**
2. Click **Manual Trigger** (`manualTrigger` node)
3. In the **setAutoCommand** node, set the `command` field to one of the values below
4. Click **Execute Workflow**

Alternatively, document these in workflow notes and pass as JSON input:
```json
{ "command": "test-one" }
```

---

## Commands

### `/auto run-now`

**Handler:** `autoRunNow` → `prepareCategory`

Bypasses the daily 6:45 AM scheduler. Immediately schedules all 10 post slots spaced 5 minutes apart starting now. Resets circuit breaker. Runs the full news fetch → generate → review → publish → audit cycle for all 10 slots.

**Use when:** You want to run a full day of posts immediately for testing or catch-up.

---

### `/auto test-one`

**Handler:** `autoTestOne` → `prepareCategory`

Runs a **single post cycle** (slot 1 only) with a 5-second wait. Fetches news, generates caption and image, runs full compliance review, publishes to Facebook, and runs post-publish audit.

**Use when:** Validating credentials, API connectivity, and Facebook posting without waiting for scheduled times.

---

### `/auto review-log`

**Handler:** `autoReviewLog`

Reads `auditLog` from n8n static workflow data and outputs the full JSON array to the execution log. Does not modify any data.

**Use when:** Inspecting today's post audit history, quality scores, and compliance flags.

**Output example:**
```json
{
  "command": "review-log",
  "auditLog": [
    {
      "post_id": "123456789_987654321",
      "quality_score": 8,
      "compliance_status": "clean",
      "timestamp": "2026-05-29T14:32:00.000Z"
    }
  ]
}
```

---

### `/auto check-token`

**Handler:** `autoCheckToken` → `checkFBToken` → `parseFBToken`

Runs the Facebook token validity check only. Hits `https://graph.facebook.com/debug_token` and reports:
- `tokenValid` (boolean)
- `expiresInDays` (number)
- `skipPosting` (true if invalid or expires within 7 days)

**Use when:** Proactively verifying Page Access Token health before scheduled posts.

---

### `/auto pause`

**Handler:** `autoPause`

Returns instruction to deactivate the workflow in n8n UI. Scheduling stops when workflow is inactive — no posts will fire today or until reactivated.

**Action required:** Toggle workflow **Inactive** in n8n UI top-right switch.

---

### `/auto resume`

**Handler:** `autoResume`

Returns instruction to re-activate the workflow. Re-enables both schedule triggers (6:45 AM and 11:00 PM ET).

**Action required:** Toggle workflow **Active** in n8n UI top-right switch.

---

### `/auto flush-cache`

**Handler:** `autoFlushCache`

Clears the `postedURLs` deduplication array in static workflow data. Allows previously posted articles to be selected again.

**Use when:** Intentionally resetting dedup after a long pause, or during development/testing.

**Warning:** May cause duplicate posts if run in production.

---

### `/auto daily-report`

**Handler:** `commandRouter` → `dailySummary` → `sendDailyReport` → `writeDailyReportFile`

Manually triggers the daily summary report (normally fires at 11:00 PM ET). Computes stats, sends email, writes file to `/data/reports/daily_YYYY-MM-DD.txt`.

**Report includes:**
- Total posts attempted / published / skipped
- Image fallback count
- Average quality score
- Flagged posts list

---

### `/auto health-check`

**Handler:** `autoHealthCheck` → `healthNewsAPI` → `healthAnthropic` → `healthOpenAI` → `healthMeta` → `healthAggregate`

Pings all 4 external APIs sequentially and returns aggregated status:

| API | Endpoint |
|-----|----------|
| NewsAPI | `/v2/top-headlines?country=us&pageSize=1` |
| Anthropic | `/v1/models` |
| OpenAI | `/v1/models` |
| Meta | `/debug_token` |

**Use when:** Diagnosing connectivity issues or verifying credentials after rotation.

---

### `/auto reset-errors`

**Handler:** `autoResetErrors`

Clears `errorLog` from static data. Resets `consecutiveFailures` to 0, `circuitBreakerHalted` to false, and **`productionHalted`** to false (required after API key fixes).

**Use when:** Recovering from a circuit breaker or **production cost guard** halt after fixing credentials and running `docker compose up -d` again.

---

### Stop server (when you get cost-guard email)

Not an n8n command — run on your VPS:

```bash
cd ~/awraaq_sgid
./scripts/stop-server.sh
```

Stops Docker so n8n cannot call paid APIs until you fix keys.

---

## Command Router Mapping

| Command | Switch Output Index | Handler Node |
|---------|-------------------|--------------|
| run-now | 0 | autoRunNow |
| test-one | 1 | autoTestOne |
| review-log | 2 | autoReviewLog |
| check-token | 3 | autoCheckToken |
| flush-cache | 4 | autoFlushCache |
| daily-report | 5 | dailySummary |
| health-check | 6 | autoHealthCheck |
| reset-errors | 7 | autoResetErrors |
| pause | 8 | autoPause |
| resume | 9 | autoResume |

## Quick Reference Card

```
/auto run-now       → Full 10-post cycle now
/auto test-one      → Single test post
/auto review-log    → Show audit log
/auto check-token   → FB token health
/auto pause         → Deactivate workflow
/auto resume        → Activate workflow
/auto flush-cache   → Clear dedup URLs
/auto daily-report  → Generate report now
/auto health-check  → Ping all 4 APIs
/auto reset-errors  → Clear errors + circuit breaker
```
