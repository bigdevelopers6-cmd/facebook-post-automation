# Node Map — Facebook US News Automation Agent

Complete list of every workflow node in execution order, grouped by sub-system.

**Total: 100 nodes** (93 functional + 7 sticky notes). See also [POSTING-LAYERS.md](POSTING-LAYERS.md).

## PRODUCTION COST GUARD SUB-SYSTEM

| Node Name | Type | Purpose | Connected To |
|-----------|------|---------|--------------|
| productionGateNewsAPI | HTTP Request | Validates NewsAPI key before any fetch | productionGateAnthropic |
| productionGateAnthropic | HTTP Request | Validates Anthropic key | productionGateOpenAI |
| productionGateOpenAI | HTTP Request | Validates OpenAI key | productionGateMeta |
| productionGateMeta | HTTP Request | Validates Facebook token | evaluateProductionApis |
| evaluateProductionApis | Code | Sets `productionHalted` if any API fails | productionGatePass |
| productionGatePass | IF | All healthy → continue; else halt | prepareCategory / haltProduction |
| haltProduction | Code | Halts workflow, logs PRODUCTION_COST_GUARD | alertStopServer |
| alertStopServer | Email Send | Tells you to run `docker compose down` | (end) |
| slotApiGateAnthropic | HTTP Request | Per-slot Anthropic check before caption $ | evaluateSlotAnthropic |
| evaluateSlotAnthropic | Code | Marks slot unhealthy if reviewer API down | slotAnthropicPass |
| slotAnthropicPass | IF | OK → generateCaption; fail → haltProduction | generateCaption / haltProduction |
| slotApiGateOpenAI | HTTP Request | Per-slot OpenAI check before image $ | evaluateSlotOpenAI |
| evaluateSlotOpenAI | Code | Halts if OpenAI down | slotOpenAIPass |
| slotOpenAIPass | IF | OK → generateImage; fail → haltProduction | generateImage / haltProduction |

## MANDATORY REVIEW GATES (before publish)

| Node Name | Type | Purpose | Connected To |
|-----------|------|---------|--------------|
| markCaptionReviewPassed | Code | Sets `aiCaptionApproved`, `prePublishReviewPassed` | captionReviewReadyGate |
| captionReviewReadyGate | IF | Blocks if caption review flag missing | buildImagePrompt / logBlockedPublish |
| finalPublishGate | IF | Requires caption + image review flags + URLs | publishToFacebook / logBlockedPublish |
| logBlockedPublish | Code | Logs PUBLISH_BLOCKED_MISSING_REVIEW | loopBack |

## SCHEDULER SUB-SYSTEM

| Node Name | Type | Purpose | Connected To |
|-----------|------|---------|--------------|
| scheduleTrigger645AM | Schedule Trigger | Fires daily at 6:45 AM ET (America/New_York) | computePostTimes |
| computePostTimes | Code | Generates 10 randomized ET post times with 40–90 min gaps, stores in static data | storeTodaySchedule |
| storeTodaySchedule | Code | Persists `todaySchedule` array to n8n static workflow data | prepareCategory |

## NEWS FETCHER SUB-SYSTEM

| Node Name | Type | Purpose | Connected To |
|-----------|------|---------|--------------|
| prepareCategory | Code | Rotates daily NewsAPI category (technology/business/health/science/entertainment) | fetchUSNews |
| fetchUSNews | HTTP Request | Fetches US top headlines from NewsAPI (pageSize=30) | tagCategory (success), error output continues |
| tagCategory | Code | Tags response with category for audit trail | filterArticles |
| filterArticles | Code | Filters noise domains, deduplicates against `postedURLs`, prioritizes premium sources, outputs up to 10 articles | checkNeedsFallback |
| checkNeedsFallback | IF | Routes to fallback if fewer than 10 articles pass filters | fetchFallbackNews (true), passthroughNoFallback (false) |
| fetchFallbackNews | HTTP Request | Fallback fetch: everything?q=US+news | fillRemainingSlots |
| fillRemainingSlots | Code | Fills remaining slots from fallback; marks [REPOST] if still short | mergeScheduleWithArticles |
| passthroughNoFallback | Code | Passes 10 filtered articles when no fallback needed | mergeScheduleWithArticles |
| mergeScheduleWithArticles | Code | Combines each article with its schedule slot (epochMs, windowLabel) | splitInBatches |

## POST CYCLE LOOP (per slot 1–10)

| Node Name | Type | Purpose | Connected To |
|-----------|------|---------|--------------|
| splitInBatches | Split In Batches | Iterates one article/slot at a time (batch size 1) | prepareSlotWait (batch), loopBack (done) |
| prepareSlotWait | Code | Computes `waitMs = epochMs - Date.now()`, checks circuit breaker | checkHalted |
| checkHalted | IF | Skips slot if circuit breaker halted remaining posts | skipHalted (true), waitForSlot (false) |
| skipHalted | Code | Logs CIRCUIT_BREAKER_HALTED skip | loopBack |
| waitForSlot | Wait | Waits until scheduled epochMs (resumeAfter milliseconds) | checkFBToken |
| checkFBToken | HTTP Request | Hits Meta debug_token endpoint before posting | parseFBToken |
| parseFBToken | Code | Parses token validity and expiry (7-day guard) | tokenGate |
| tokenGate | IF | Skips posting if token invalid or expiring within 7 days | skipInvalidToken + alertTokenExpiry (true), generateCaption (false) |
| skipInvalidToken | Code | Logs TOKEN_INVALID skip | loopBack |
| alertTokenExpiry | Email Send | Emails page owner about token expiry | loopBack |

## CONTENT GENERATOR SUB-SYSTEM

| Node Name | Type | Purpose | Connected To |
|-----------|------|---------|--------------|
| generateCaption | HTTP Request | Claude Haiku writes Facebook caption (max 350 tokens) | extractCaption |
| extractCaption | Code | Extracts caption text from Anthropic response | prePublishReview |

## SELF-REVIEW AGENT SUB-SYSTEM — Pre-Publish

| Node Name | Type | Purpose | Connected To |
|-----------|------|---------|--------------|
| prePublishReview | HTTP Request | Claude compliance review of caption (JSON schema) | parsePrePublishReview |
| parsePrePublishReview | Code | Parses review JSON; handles non-JSON gracefully | reviewGate |
| reviewGate | IF | Approved + risk ≠ high → proceed; else rewrite or skip | markCaptionReviewPassed (true), incrementRewriteAttempt (false) |
| incrementRewriteAttempt | Code | Tracks rewrite attempt count (max 2) | checkRewriteAttempts |
| checkRewriteAttempts | IF | After 2 failed rewrites → skip | logSkippedCompliance (true), rewriteCaption (false) |
| rewriteCaption | HTTP Request | Claude rewrites caption with flags appended | rewriteCaptionExtract |
| rewriteCaptionExtract | Code | Extracts rewritten caption | prePublishReview (re-review loop) |
| logSkippedCompliance | Code | Logs SKIPPED_COMPLIANCE to errorLog | loopBack |

## SELF-REVIEW AGENT SUB-SYSTEM — Image Review

| Node Name | Type | Purpose | Connected To |
|-----------|------|---------|--------------|
| buildImagePrompt | Code | Builds OpenAI image generation prompt from article title | imageReview |
| imageReview | HTTP Request | Claude reviews image prompt for Meta policy compliance | parseImageReview |
| parseImageReview | Code | Parses image review JSON | imageReviewGate |
| imageReviewGate | IF | Approved → AI image; rejected → NewsAPI fallback | generateImage (true), applyImageFallback (false) |
| generateImage | HTTP Request | OpenAI gpt-image-1 generates 1536×1024 editorial photo | extractImageUrl |
| extractImageUrl | Code | Extracts `data[0].url` from OpenAI response | mergeImagePaths |
| applyImageFallback | Code | Uses article `urlToImage`; logs IMAGE_FALLBACK_USED | mergeImagePaths |
| mergeImagePaths | Code | Sets `aiImageCleared`; normalizes image path | finalPublishGate |

## PUBLISHER SUB-SYSTEM

| Node Name | Type | Purpose | Connected To |
|-----------|------|---------|--------------|
| publishToFacebook | HTTP Request | POST to Graph API v19.0 `/{page_id}/photos` | handlePublishSuccess (success), handlePublishError (error) |
| handlePublishSuccess | Code | Extracts Facebook post_id | postPublishAudit |
| handlePublishError | Code | Logs error, increments consecutiveFailures | checkCircuitAfterError |
| checkCircuitAfterError | IF | >4 consecutive failures → halt + alert | alertCircuitBreaker (true), loopBack (false) |
| alertCircuitBreaker | Email Send | Notifies owner that posting halted for the day | loopBack |

## SELF-REVIEW AGENT SUB-SYSTEM — Post-Publish

| Node Name | Type | Purpose | Connected To |
|-----------|------|---------|--------------|
| postPublishAudit | HTTP Request | Claude audits published post quality/compliance | parsePostPublishAudit |
| parsePostPublishAudit | Code | Parses audit JSON (quality_score, compliance_status) | appendAuditLog |
| appendAuditLog | Code | Appends to static `auditLog` (max 100 entries) | checkFlaggedAudit |
| checkFlaggedAudit | IF | compliance_status === 'flagged' → alert | alertFlaggedPost (true), updatePostedURLs (false) |
| alertFlaggedPost | Email Send | Immediate owner alert for flagged post | updatePostedURLs |
| updatePostedURLs | Code | Appends URL to `postedURLs` FIFO (max 200), resets consecutiveFailures | loopBack |
| loopBack | No Op | Returns to splitInBatches for next slot | splitInBatches |

## DAILY SUMMARY SUB-SYSTEM

| Node Name | Type | Purpose | Connected To |
|-----------|------|---------|--------------|
| scheduleTrigger11PM | Schedule Trigger | Fires daily at 11:00 PM ET | dailySummary |
| dailySummary | Code | Computes daily stats from auditLog/errorLog, clears today's auditLog | sendDailyReport |
| sendDailyReport | Email Send | Sends plain-text daily report email | writeDailyReportFile |
| writeDailyReportFile | Code | Writes report to `/data/reports/daily_YYYY-MM-DD.txt` | (end) |

## /auto COMMAND SUB-SYSTEM

| Node Name | Type | Purpose | Connected To |
|-----------|------|---------|--------------|
| manualTrigger | Manual Trigger | On-demand workflow execution entry point | setAutoCommand |
| setAutoCommand | Set | Reads `command` field (default: run-now) | commandRouter |
| commandRouter | Switch | Routes to handler by command string | autoRunNow, autoTestOne, autoReviewLog, autoCheckToken, autoFlushCache, dailySummary, autoHealthCheck, autoResetErrors, autoPause, autoResume |
| autoRunNow | Code | Bypass scheduler; sets 10 immediate slots (5 min apart) | prepareCategory |
| autoTestOne | Code | Single slot test (slot 1, 5s wait) | prepareCategory |
| autoReviewLog | Code | Outputs auditLog to execution log | (end) |
| autoCheckToken | Code | Triggers FB token check only | checkFBToken |
| autoFlushCache | Code | Clears `postedURLs` dedup store | (end) |
| autoResetErrors | Code | Clears errorLog and circuit breaker state | (end) |
| autoHealthCheck | Code | Initiates API health ping sequence | healthNewsAPI |
| autoPause | Code | Documents pause instruction (deactivate workflow) | (end) |
| autoResume | Code | Documents resume instruction (activate workflow) | (end) |
| healthNewsAPI | HTTP Request | Pings NewsAPI | healthAnthropic |
| healthAnthropic | HTTP Request | Pings Anthropic models endpoint | healthOpenAI |
| healthOpenAI | HTTP Request | Pings OpenAI models endpoint | healthMeta |
| healthMeta | HTTP Request | Pings Meta debug_token | healthAggregate |
| healthAggregate | Code | Aggregates all API health results | (end) |

## Sticky Notes (visual labels only)

| Node Name | Type | Purpose |
|-----------|------|---------|
| SCHEDULER SUB-SYSTEM | Sticky Note | Labels scheduler section |
| NEWS FETCHER SUB-SYSTEM | Sticky Note | Labels news fetcher section |
| CONTENT GENERATOR SUB-SYSTEM | Sticky Note | Labels content generator section |
| SELF-REVIEW AGENT SUB-SYSTEM | Sticky Note | Labels self-review section |
| PUBLISHER SUB-SYSTEM | Sticky Note | Labels publisher section |
| DAILY SUMMARY | Sticky Note | Labels daily summary section |
| /auto COMMANDS | Sticky Note | Labels manual command section |

**Total nodes: 100** (93 functional + 7 sticky notes)
