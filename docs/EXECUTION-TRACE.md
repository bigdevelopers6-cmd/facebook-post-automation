# Sample End-to-End Execution Trace

One complete post cycle (Slot 3 of 10) as it appears in n8n's execution log. Timestamps are illustrative for a run on **2026-05-29** with workflow activated at 6:45 AM ET.

---

## Context: Daily Run Initiated

```
[06:45:01 ET] scheduleTrigger645AM        SUCCESS  (0.1s)
  Output: { "timestamp": "2026-05-29T10:45:01.000Z" }

[06:45:01 ET] computePostTimes            SUCCESS  (0.3s)
  Input:  trigger pulse
  Output: {
    "todaySchedule": [
      { "slotIndex": 1, "epochMs": 1748514300000, "windowLabel": "morning_rush", "scheduledEt": "07:12" },
      { "slotIndex": 2, "epochMs": 1748518620000, "windowLabel": "mid_morning", "scheduledEt": "09:37" },
      { "slotIndex": 3, "epochMs": 1748520600000, "windowLabel": "late_morning", "scheduledEt": "11:03" },
      ...
    ],
    "slotCount": 10
  }

[06:45:02 ET] storeTodaySchedule          SUCCESS  (0.1s)
  Static data updated: todaySchedule[10]

[06:45:02 ET] prepareCategory             SUCCESS  (0.1s)
  Output: { "category": "health" }   // day index % 5 = 2

[06:45:03 ET] fetchUSNews                 SUCCESS  (1.2s)
  Request: GET /v2/top-headlines?country=us&language=en&pageSize=30&category=health
  Output: { "status": "ok", "totalResults": 28, "articles": [...30 items] }

[06:45:04 ET] filterArticles              SUCCESS  (0.2s)
  Output: { "articles": [10 items], "needed": 0, "category": "health" }

[06:45:04 ET] checkNeedsFallback          SUCCESS  (0.1s)
  Condition: needed > 0 → FALSE → passthrough branch

[06:45:04 ET] passthroughNoFallback       SUCCESS  (0.1s)
  Output: 10 items emitted

[06:45:05 ET] mergeScheduleWithArticles   SUCCESS  (0.2s)
  Output: 10 items, each with article + slot schedule merged
```

---

## Slot 3 Post Cycle (Article Index 3)

**Selected Article:**
```json
{
  "slotIndex": 3,
  "epochMs": 1748520600000,
  "windowLabel": "late_morning",
  "scheduledEt": "11:03",
  "title": "FDA Approves New Treatment for Type 2 Diabetes",
  "description": "The FDA granted approval to a once-weekly injectable that showed significant A1C reduction in clinical trials involving 4,000 patients nationwide.",
  "url": "https://apnews.com/article/fda-diabetes-treatment-2026",
  "urlToImage": "https://storage.googleapis.com/afp-media/apnews/2026/diabetes.jpg",
  "source": { "name": "AP News" },
  "isRepost": false
}
```

---

### Step-by-Step Node Trace

```
[11:03:00 ET] splitInBatches              SUCCESS  (0.1s)
  Batch 3 of 10 dispatched

[11:03:00 ET] prepareSlotWait             SUCCESS  (0.1s)
  Input:  slot 3 article
  Output: { ..., "waitMs": 0, "halted": false }
  Note:   waitMs=0 because epochMs reached

[11:03:00 ET] checkHalted                 SUCCESS  (0.1s)
  Condition: halted === true → FALSE → continue

[11:03:00 ET] waitForSlot                 SUCCESS  (0.1s)
  Resume: timeInterval 0ms (immediate)

[11:03:01 ET] checkFBToken                SUCCESS  (0.8s)
  Request: GET /debug_token?input_token=***&access_token=***
  Output: { "data": { "is_valid": true, "expires_at": 0, "scopes": ["pages_manage_posts"] } }

[11:03:02 ET] parseFBToken                SUCCESS  (0.1s)
  Output: { ..., "tokenValid": true, "expiresInDays": 999, "skipPosting": false }

[11:03:02 ET] tokenGate                   SUCCESS  (0.1s)
  Condition: skipPosting === true → FALSE → proceed to generateCaption

[11:03:03 ET] generateCaption             SUCCESS  (2.4s)
  Request: POST /v1/messages (claude-haiku-4-5-20251001, max_tokens: 350)
  Output: {
    "content": [{
      "text": "Americans spend billions on diabetes care every year — so when the FDA signs off on something new, people pay attention. A once-weekly injection just got the green light after trials with 4,000 patients showed real A1C improvements. Would you switch from a daily routine to one shot a week? #DiabetesAwareness #FDAApproval #HealthNews"
    }]
  }

[11:03:05 ET] extractCaption              SUCCESS  (0.1s)
  Output: { ..., "caption": "Americans spend billions...", "rewriteAttempt": 0 }

[11:03:06 ET] prePublishReview            SUCCESS  (1.8s)
  Request: POST /v1/messages (compliance review)
  Output: {
    "content": [{
      "text": "{\"approved\": true, \"risk_level\": \"low\", \"flags\": [], \"rewrite_needed\": false, \"reason\": \"\"}"
    }]
  }

[11:03:08 ET] parsePrePublishReview       SUCCESS  (0.1s)
  Output: { ..., "review": { "approved": true, "risk_level": "low", "flags": [], "rewrite_needed": false, "reason": "" } }

[11:03:08 ET] reviewGate                  SUCCESS  (0.1s)
  Condition: approved=true AND risk_level≠high → TRUE → proceed

[11:03:08 ET] buildImagePrompt            SUCCESS  (0.1s)
  Output: {
    "imagePrompt": "Photorealistic editorial news photograph illustrating: FDA Approves New Treatment for Type 2 Diabetes. Professional news photography style, natural lighting, no text, no logos..."
  }

[11:03:09 ET] imageReview                 SUCCESS  (1.5s)
  Output: { "content": [{ "text": "{\"approved\": true, \"reason\": \"\"}" }] }

[11:03:10 ET] parseImageReview            SUCCESS  (0.1s)
  Output: { ..., "imageReview": { "approved": true, "reason": "" } }

[11:03:10 ET] imageReviewGate             SUCCESS  (0.1s)
  Condition: approved === true → TRUE → generateImage

[11:03:11 ET] generateImage               SUCCESS  (45.2s)
  Request: POST /v1/images/generations (gpt-image-1, 1536x1024, quality: high)
  Output: {
    "data": [{ "url": "https://oaidalleapiprodscus.blob.core.windows.net/private/org-xxx/img-abc123.png?se=2026..." }]
  }

[11:03:56 ET] extractImageUrl             SUCCESS  (0.1s)
  Output: {
    "finalImageUrl": "https://oaidalleapiprodscus.blob.core.windows.net/...",
    "imageSource": "openai_generated",
    "useFallbackImage": false
  }

[11:03:56 ET] mergeImagePaths             SUCCESS  (0.1s)
  Output: unified item with caption + finalImageUrl

[11:03:57 ET] publishToFacebook           SUCCESS  (3.1s)
  Request: POST /v19.0/{PAGE_ID}/photos
  Body: url=<ai-image>, message=<caption>, access_token=***
  Output: { "id": "123456789012345_9876543210987654321", "post_id": "123456789012345_9876543210987654321" }

[11:04:00 ET] handlePublishSuccess        SUCCESS  (0.1s)
  Output: {
    "post_id": "123456789012345_9876543210987654321",
    "publishSuccess": true,
    "publishTimestamp": "2026-05-29T15:04:00.000Z"
  }

[11:04:01 ET] postPublishAudit            SUCCESS  (2.1s)
  Output: {
    "content": [{
      "text": "{\"post_id\": \"123456789012345_9876543210987654321\", \"timestamp_et\": \"11:04 AM\", \"category\": \"health\", \"tone\": \"informative\", \"compliance_status\": \"clean\", \"quality_score\": 8, \"notes\": \"Strong hook referencing US healthcare costs. Question invites engagement. Hashtags relevant.\"}"
    }]
  }

[11:04:03 ET] parsePostPublishAudit       SUCCESS  (0.1s)
  Output: { ..., "audit": { "compliance_status": "clean", "quality_score": 8, ... } }

[11:04:03 ET] appendAuditLog              SUCCESS  (0.1s)
  Static data: auditLog appended (entry 3 of day)

[11:04:03 ET] checkFlaggedAudit           SUCCESS  (0.1s)
  Condition: compliance_status === 'flagged' → FALSE → skip alert

[11:04:03 ET] updatePostedURLs            SUCCESS  (0.1s)
  Static data: postedURLs.push("https://apnews.com/article/fda-diabetes-treatment-2026")
  consecutiveFailures reset to 0

[11:04:03 ET] loopBack                    SUCCESS  (0.1s)
  → splitInBatches (awaiting slot 4)
```

---

## Slot 3 Summary

| Metric | Value |
|--------|-------|
| Total duration | ~63 seconds |
| Scheduled time | 11:03 AM ET |
| Actual publish time | 11:04 AM ET |
| Status | SUCCESS |
| Image source | openai_generated |
| Compliance | clean |
| Quality score | 8/10 |
| Rewrites needed | 0 |
| Facebook post ID | 123456789012345_9876543210987654321 |

---

## Alternate Trace: Compliance Rejection → Rewrite → Success

```
[15:22:00 ET] prePublishReview            SUCCESS  (1.9s)
  Output: { "approved": false, "risk_level": "medium", "flags": ["prohibited_word: crucial"], "rewrite_needed": true }

[15:22:02 ET] reviewGate                  SUCCESS  (0.1s)
  → FALSE branch → incrementRewriteAttempt

[15:22:02 ET] incrementRewriteAttempt     SUCCESS  (0.1s)
  Output: { "rewriteAttempt": 1 }

[15:22:02 ET] checkRewriteAttempts        SUCCESS  (0.1s)
  rewriteAttempt (1) > 2 → FALSE → rewriteCaption

[15:22:03 ET] rewriteCaption              SUCCESS  (2.6s)
  Output: caption without prohibited words

[15:22:05 ET] rewriteCaptionExtract       SUCCESS  (0.1s)

[15:22:06 ET] prePublishReview            SUCCESS  (1.7s)
  Output: { "approved": true, "risk_level": "low" }

[15:22:08 ET] reviewGate                  SUCCESS  (0.1s)
  → TRUE → continue to buildImagePrompt
```

---

## Alternate Trace: Skipped After Max Rewrites

```
[19:45:00 ET] checkRewriteAttempts        SUCCESS  (0.1s)
  rewriteAttempt (3) > 2 → TRUE

[19:45:00 ET] logSkippedCompliance        SUCCESS  (0.1s)
  errorLog entry: { error_code: "SKIPPED_COMPLIANCE", article_url: "..." }

[19:45:00 ET] loopBack                    SUCCESS  (0.1s)
  Status: SKIPPED — no Facebook post made
  → splitInBatches (slot 8 continues)
```

---

## Alternate Trace: Publish Error → Circuit Breaker

```
[20:30:00 ET] publishToFacebook           ERROR    (2.3s)
  Error: (#200) Permissions error

[20:30:02 ET] handlePublishError          SUCCESS  (0.1s)
  consecutiveFailures: 5, circuitBreakerHalted: true

[20:30:02 ET] checkCircuitAfterError      SUCCESS  (0.1s)
  consecutiveFailures (5) > 4 → TRUE

[20:30:02 ET] alertCircuitBreaker         SUCCESS  (1.5s)
  Email sent to owner@yourdomain.com

[20:30:04 ET] loopBack                    SUCCESS  (0.1s)
  → splitInBatches slot 10

[20:30:04 ET] prepareSlotWait             SUCCESS  (0.1s)
  Output: { "halted": true, "skipReason": "CIRCUIT_BREAKER" }

[20:30:04 ET] skipHalted                  SUCCESS  (0.1s)
  Status: SKIPPED — remaining slots 10 halted for the day
```

---

## Daily Summary (11:00 PM ET)

```
[23:00:01 ET] scheduleTrigger11PM         SUCCESS  (0.1s)

[23:00:01 ET] dailySummary                SUCCESS  (0.3s)
  Output: {
    "report": "Facebook US News Daily Report — 2026-05-29\n========================================\nTotal posts attempted: 10\nTotal published: 8\nTotal skipped (compliance): 1\nTotal image fallbacks: 1\nAverage quality score: 7.6\nFlagged posts: 0\n========================================",
    "date": "2026-05-29"
  }

[23:00:02 ET] sendDailyReport             SUCCESS  (2.1s)
  Email delivered

[23:00:04 ET] writeDailyReportFile        SUCCESS  (0.2s)
  File: /data/reports/daily_2026-05-29.txt
```

This trace demonstrates the full lifecycle: schedule → wait → token check → caption → pre-review → image → publish → post-audit → dedup update → loop, with alternate paths for rewrite, skip, and circuit breaker scenarios.
