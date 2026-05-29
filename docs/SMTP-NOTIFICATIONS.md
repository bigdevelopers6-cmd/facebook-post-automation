# SMTP Email Notifications

All workflow emails use one n8n credential: **`SMTP_NOTIFICATIONS`**.

Set recipients in `docker-compose.yml`:

```yaml
- N8N_ALERT_FROM=alerts@yourdomain.com
- N8N_ALERT_TO=your-phone-email@gmail.com
```

## Emails you will receive

| Email node | When it sends | Subject prefix |
|------------|---------------|----------------|
| `emailDailyRunStarted` | All 4 APIs pass; daily schedule locked in | `[US News Bot] Daily run started` |
| `emailSlotPostStarting` | Each slot begins (caption + review pipeline) | `[US News Bot] Creating post` |
| `emailPostPublished` | Facebook publish + audit succeeded | `[US News Bot] Published` |
| `emailPostSkipped` | Compliance, review block, halt, or token skip | `[US News Bot] SKIPPED` |
| `emailPublishFailed` | Facebook API error on publish | `[US News Bot] Publish FAILED` |
| `emailTokenExpired` | FB token invalid or &lt; 7 days left | `[US News Bot] URGENT — Facebook token` |
| `emailImageFallbackUsed` | AI image rejected; NewsAPI photo used | `[US News Bot] Image fallback` |
| `emailFlaggedPost` | Post-publish audit flagged content | `[US News Bot] FLAGGED post` |
| `emailCircuitBreaker` | 4+ consecutive publish failures | `[US News Bot] Circuit breaker` |
| `emailProductionHalted` | API key failure — **stop server** instructions | `[US News Bot] STOP SERVER` |
| `sendDailyReport` | 11:00 PM ET daily summary | `Facebook US News Daily Report` |

## Typical day (~12–25 emails)

- 1× daily run started  
- Up to 10× “Creating post”  
- Up to 10× “Published” or “SKIPPED”  
- 0–n× alerts (token, fallback, flagged, failures)  
- 1× daily report at 11 PM ET  

## Setup

See **Part G — SMTP** in [SETUP-GUIDE.md](SETUP-GUIDE.md).

After import, open each email node → select **`SMTP_NOTIFICATIONS`** if shown as missing.
