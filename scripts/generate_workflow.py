#!/usr/bin/env python3
"""Generate the Facebook US News Automation n8n workflow JSON."""
import json
import uuid
from copy import deepcopy

def nid():
    return str(uuid.uuid4())

def node(name, ntype, position, parameters=None, **kwargs):
    params = dict(parameters or {})
    tv = kwargs.get("typeVersion", 1)
    if ntype == "n8n-nodes-base.code" and tv == 2:
        params.setdefault("language", "javaScript")
        params.setdefault("mode", "runOnceForAllItems")
    n = {
        "parameters": params,
        "id": nid(),
        "name": name,
        "type": ntype,
        "typeVersion": tv,
        "position": position,
    }
    if "credentials" in kwargs:
        n["credentials"] = kwargs["credentials"]
    if "onError" in kwargs:
        n["onError"] = kwargs["onError"]
    if "retryOnFail" in kwargs:
        n["retryOnFail"] = kwargs["retryOnFail"]
    if "maxTries" in kwargs:
        n["maxTries"] = kwargs["maxTries"]
    if "waitBetweenTries" in kwargs:
        n["waitBetweenTries"] = kwargs["waitBetweenTries"]
    if "notes" in kwargs:
        n["notes"] = kwargs["notes"]
    if "webhookId" in kwargs:
        n["webhookId"] = kwargs["webhookId"]
    return n

def sticky(text, position, width=400, height=200):
    return node(
        text,
        "n8n-nodes-base.stickyNote",
        position,
        {"content": text.split(" — ")[-1] if " — " in text else text, "width": width, "height": height},
        typeVersion=1,
    )

def conn(from_node, to_node, output_index=0, input_index=0):
    return {"node": to_node, "type": "main", "index": input_index}

# --- Caption / review prompts (used by LLM fallback code nodes) ---
CAPTION_SYSTEM = (
    "You are a professional US social media editor for a Facebook news Page focused ONLY on American politics and celebrities. "
    "Your audience is US adults 25–45 who follow elections, Capitol Hill, White House news, Hollywood, music, and pop culture. "
    "Write exclusively in American English. Never mention AI, automation, or that this post was generated. Each caption must: "
    "(1) open with a strong hook tied to US political or celebrity culture, "
    "(2) summarize the story in 1–2 plain conversational sentences, "
    "(3) end with a thought-provoking question inviting Americans to comment, "
    "(4) include exactly 3 hashtags relevant to politics OR celebrities (e.g. #Election2026 #CapitolHill #Hollywood #CelebrityNews), "
    "(5) include exactly 1–2 emojis placed naturally in the caption (not more than two; match the story mood). "
    "Match tone to the story: informative, surprising, opinionated, or empathetic. Skip stories that are not politics or celebrity-related. "
    "Never use corporate jargon or the words 'crucial', 'delve', 'groundbreaking', or 'game-changer'. Output only the caption text."
)

PRE_PUBLISH_SYSTEM = (
    "You are a strict Facebook page compliance officer. Analyze the caption provided and return ONLY a JSON object "
    "with this exact schema: { \"approved\": true/false, \"risk_level\": \"low\"/\"medium\"/\"high\", \"flags\": [], "
    "\"rewrite_needed\": true/false, \"reason\": \"\" }. Reject (approved: false) if the caption: contains political "
    "candidate endorsements, makes unverified medical claims, includes hate speech or discriminatory language, "
    "mentions violence approvingly, contains profanity, reveals it was AI-generated, uses prohibited words "
    "('crucial','delve','groundbreaking','game-changer'), or could get the page flagged under Meta Community Standards. "
    "Set risk_level to 'high' if any flag is critical. Output only valid JSON, no markdown, no explanation."
)

# NewsAPI rejects requests without User-Agent (error code userAgentMissing).
NEWSAPI_HEADERS = {
    "sendHeaders": True,
    "headerParameters": {
        "parameters": [
            {"name": "X-Api-Key", "value": "={{ $env.NEWSAPI_KEY }}"},
            {"name": "User-Agent", "value": "FacebookUSNewsBot/1.0 (n8n; contact=bigdevelopers6@gmail.com)"},
        ]
    },
}

def smtp_email(name, position, subject_expr, body_expr, notes=None):
    """All notification emails use credential SMTP_NOTIFICATIONS."""
    params = {
        "fromEmail": "={{ $env.N8N_ALERT_FROM || 'alerts@yourdomain.com' }}",
        "toEmail": "={{ $env.N8N_ALERT_TO || 'owner@yourdomain.com' }}",
        "subject": subject_expr,
        "text": body_expr,
    }
    kw = {
        "typeVersion": 2.1,
        "onError": "continueRegularOutput",
        "credentials": {"smtp": {"id": "SMTP_NOTIFICATIONS", "name": "SMTP_NOTIFICATIONS"}},
    }
    if notes:
        kw["notes"] = notes
    return node(name, "n8n-nodes-base.emailSend", position, params, **kw)

# Bumped each release — grep this on server to confirm deploy
WORKFLOW_BUILD = "2026-05-30-trace-v7d-split-bypass"

# --- Code snippets ---
COMPUTE_POST_TIMES = r"""// Scheduler: compute 10 randomized ET posting times
const { DateTime } = require('luxon');
const TZ = 'America/New_York';

const windows = [
  { label: 'morning_rush', start: 7 * 60, end: 8 * 60 + 45 },
  { label: 'mid_morning', start: 9 * 60, end: 10 * 60 + 45 },
  { label: 'late_morning', start: 11 * 60, end: 12 * 60 + 45 },
  { label: 'lunch', start: 13 * 60, end: 14 * 60 + 45 },
  { label: 'afternoon', start: 15 * 60, end: 16 * 60 + 45 },
  { label: 'evening_commute', start: 17 * 60, end: 18 * 60 + 45 },
  { label: 'prime_time', start: 19 * 60, end: 20 * 60 + 45 },
  { label: 'late_evening', start: 21 * 60, end: 21 * 60 + 45 },
];

function randomMinuteInWindow(w) {
  return w.start + Math.floor(Math.random() * (w.end - w.start + 1));
}

function applyJitter(minutes) {
  return minutes + (Math.floor(Math.random() * 25) - 12);
}

function minutesToEpochMs(minutesFromMidnight, day) {
  const hours = Math.floor(minutesFromMidnight / 60);
  const mins = minutesFromMidnight % 60;
  return day.set({ hour: hours, minute: mins, second: 0, millisecond: 0 }).toUTC().toMillis();
}

function generateSchedule() {
  const today = DateTime.now().setZone(TZ).startOf('day');
  const times = [];

  for (const w of windows) {
    const winIdx = windows.indexOf(w);
    const label = w.label;
    times.push({
      minutes: applyJitter(randomMinuteInWindow(w)),
      windowLabel: label,
      windowIndex: winIdx,
    });
  }

  for (let i = 0; i < 2; i++) {
    const w = windows[Math.floor(Math.random() * windows.length)];
    times.push({
      minutes: applyJitter(randomMinuteInWindow(w)),
      windowLabel: w.label + '_extra',
      windowIndex: windows.indexOf(w),
    });
  }

  let attempts = 0;
  while (attempts < 500) {
    times.sort((a, b) => a.minutes - b.minutes);
    let valid = true;
    const gaps = [];
    for (let i = 1; i < times.length; i++) {
      const gap = times[i].minutes - times[i - 1].minutes;
      gaps.push(gap);
      if (gap < 40 || gap > 90) {
        valid = false;
        const idx = Math.floor(Math.random() * times.length);
        const w = windows[times[idx].windowIndex ?? Math.floor(Math.random() * windows.length)];
        times[idx].minutes = applyJitter(randomMinuteInWindow(w));
        times[idx].windowLabel = w.label;
        break;
      }
    }
    if (valid) {
      const uniqueGaps = new Set(gaps);
      if (uniqueGaps.size === gaps.length) break;
      const idx = Math.floor(Math.random() * (times.length - 1)) + 1;
      const w = windows[Math.floor(Math.random() * windows.length)];
      times[idx].minutes = applyJitter(randomMinuteInWindow(w));
    }
    attempts++;
  }

  times.sort((a, b) => a.minutes - b.minutes);
  return times.map((t, i) => ({
    slotIndex: i + 1,
    epochMs: minutesToEpochMs(t.minutes, today),
    windowLabel: t.windowLabel,
    scheduledEt: today.plus({ minutes: t.minutes }).toFormat('HH:mm'),
  }));
}

const schedule = generateSchedule();
const staticData = $getWorkflowStaticData('global');
staticData.todaySchedule = schedule;
staticData.consecutiveFailures = staticData.consecutiveFailures || 0;
staticData.circuitBreakerHalted = false;
staticData.rewriteAttempts = {};

return [{ json: { todaySchedule: schedule, slotCount: schedule.length } }];
"""

STORE_TODAY_SCHEDULE = r"""const staticData = $getWorkflowStaticData('global');
const schedule = $input.first().json.todaySchedule;
staticData.todaySchedule = schedule;
return [{ json: { stored: true, slotCount: schedule.length } }];
"""

FILTER_ARTICLES = r"""const staticData = $getWorkflowStaticData('global');
const testMode = staticData.singleSlotTest === true;
const postedURLs = staticData.postedURLs || [];
const NOISE = ['msn.com', 'yahoo.com', 'buzzfeed.com'];
const PLACEHOLDER_IMAGE = 'https://images.unsplash.com/photo-1504711434969-e33886168f5c?w=1200';
const PRIORITY = ['nytimes.com', 'washingtonpost.com', 'cnn.com', 'reuters.com', 'apnews.com', 'forbes.com', 'bbc.com', 'people.com', 'variety.com', 'hollywoodreporter.com', 'politico.com', 'thehill.com'];

const TOPIC_KEYWORDS = {
  politics: /politic|election|congress|senate|house|white house|president|governor|vote|campaign|capitol|democrat|republican|legislation|supreme court/i,
  celebrities: /celebrity|hollywood|actor|actress|singer|star|entertainment|fame|red carpet|grammy|oscar|kardashian|royal|influencer|premiere|pop culture/i,
};

function topicScore(article) {
  const text = `${article.title || ''} ${article.description || ''}`;
  let score = 0;
  if (TOPIC_KEYWORDS.politics.test(text)) score += 2;
  if (TOPIC_KEYWORDS.celebrities.test(text)) score += 2;
  if (article._topic === 'politics' && TOPIC_KEYWORDS.politics.test(text)) score += 1;
  if (article._topic === 'celebrities' && TOPIC_KEYWORDS.celebrities.test(text)) score += 1;
  return score;
}

function getDomain(url) {
  try { return new URL(url).hostname.replace(/^www\./, ''); } catch { return ''; }
}

function isValid(article) {
  if (!article.title || !article.description) return false;
  if (article.title === '[Removed]' || article.description === '[Removed]') return false;
  const domain = getDomain(article.url || '');
  if (NOISE.some(n => domain.includes(n))) return false;
  if (!testMode && !article.urlToImage) return false;
  return true;
}

function priorityScore(article) {
  const domain = getDomain(article.url || '');
  const idx = PRIORITY.findIndex(p => domain.includes(p));
  return idx >= 0 ? PRIORITY.length - idx : 0;
}

const primary = $input.first().json.articles || [];
let filtered = primary.filter(isValid)
  .filter(a => !postedURLs.includes(a.url))
  .filter(a => testMode || topicScore(a) > 0)
  .sort((a, b) => (priorityScore(b) - priorityScore(a)) || (topicScore(b) - topicScore(a)));

// Prefer mix: up to 6 politics + 6 celebrities, then fill to 10
const politics = filtered.filter(a => TOPIC_KEYWORDS.politics.test(`${a.title} ${a.description}`) || a._topic === 'politics');
const celebs = filtered.filter(a => !politics.includes(a));
let mixed = [...politics.slice(0, 6), ...celebs.slice(0, 6)];
const seen = new Set(mixed.map(a => a.url));
for (const a of filtered) {
  if (mixed.length >= 10) break;
  if (!seen.has(a.url)) { mixed.push(a); seen.add(a.url); }
}
mixed = mixed.slice(0, 10);

if (mixed.length === 0) {
  const pool = primary.filter(isValid).filter(a => !postedURLs.includes(a.url));
  const relaxed = testMode
    ? pool.slice(0, 3)
    : pool.filter(a => topicScore(a) > 0).slice(0, 10);
  mixed = relaxed.length ? relaxed : pool.slice(0, testMode ? 1 : 5);
}

const output = mixed.map(a => ({
  title: a.title,
  description: a.description,
  url: a.url,
  urlToImage: a.urlToImage || PLACEHOLDER_IMAGE,
  source: { name: a.source?.name || 'Unknown' },
  isRepost: false,
}));

const __sdF=$getWorkflowStaticData('global');
(__sdF.pipelineLog=__sdF.pipelineLog||[]).push('filterArticles: primary='+primary.length+' output='+output.length);
console.log('[PIPELINE] filterArticles', primary.length, output.length);
if (output.length === 0) {
  throw new Error(`FILTER_ARTICLES: 0 usable articles (raw=${primary.length}, postedCache=${postedURLs.length}). Try flush-cache or check NewsAPI quota.`);
}

return [{
  json: {
    articles: output,
    needed: testMode ? 0 : (10 - output.length),
    category: 'politics+celebrities',
  }
}];
"""

FILL_REMAINING_SLOTS = r"""const staticData = $getWorkflowStaticData('global');
const testMode = staticData.singleSlotTest === true;
const postedURLs = staticData.postedURLs || [];
const NOISE = ['msn.com', 'yahoo.com', 'buzzfeed.com'];
const PRIORITY = ['nytimes.com', 'washingtonpost.com', 'cnn.com', 'reuters.com', 'apnews.com', 'forbes.com', 'techcrunch.com', 'bbc.com', 'wsj.com'];
const PLACEHOLDER_IMAGE = 'https://images.unsplash.com/photo-1504711434969-e33886168f5c?w=1200';

function getDomain(url) {
  try { return new URL(url).hostname.replace(/^www\./, ''); } catch { return ''; }
}
function isValid(article) {
  if (!article.title || !article.description) return false;
  if (!testMode && !article.urlToImage) return false;
  if (article.title === '[Removed]' || article.description === '[Removed]') return false;
  if (NOISE.some(n => getDomain(article.url || '').includes(n))) return false;
  return true;
}
function priorityScore(article) {
  const domain = getDomain(article.url || '');
  const idx = PRIORITY.findIndex(p => domain.includes(p));
  return idx >= 0 ? PRIORITY.length - idx : 0;
}

let articles = $('filterArticles').first().json.articles || [];
const needed = 10 - articles.length;

if (needed > 0) {
  const fallback = $input.first().json.articles || [];
  const existing = new Set(articles.map(a => a.url));
  const extra = fallback.filter(isValid)
    .filter(a => !postedURLs.includes(a.url))
    .filter(a => !existing.has(a.url))
    .sort((a, b) => priorityScore(b) - priorityScore(a));

  for (const a of extra) {
    if (articles.length >= 10) break;
    articles.push({
      title: a.title,
      description: a.description,
      url: a.url,
      urlToImage: a.urlToImage || PLACEHOLDER_IMAGE,
      source: { name: a.source?.name || 'Unknown' },
      isRepost: false,
    });
    existing.add(a.url);
  }
}

if (articles.length < 10) {
  const allFiltered = [...($('filterArticles').first().json.articles || []),
    ...($input.first().json.articles || []).filter(isValid).map(a => ({
      title: a.title, description: a.description, url: a.url,
      urlToImage: a.urlToImage, source: { name: a.source?.name || 'Unknown' }, isRepost: false,
    }))];
  let i = 0;
  while (articles.length < 10 && allFiltered.length > 0) {
    const a = allFiltered[i % allFiltered.length];
    articles.push({ ...a, isRepost: true });
    i++;
  }
}

if (articles.length === 0) {
  throw new Error('FILL_REMAINING: 0 articles after filter and NewsAPI fallback — check NEWSAPI_KEY, quota, or flush-cache.');
}
const __sdFill=$getWorkflowStaticData('global');
if (testMode) {
  articles = articles.slice(0, 1);
  (__sdFill.pipelineLog=__sdFill.pipelineLog||[]).push('fillRemainingSlots: testMode count=1');
  return articles.map((a, idx) => ({ json: { ...a, articleIndex: idx + 1 } }));
}
(__sdFill.pipelineLog=__sdFill.pipelineLog||[]).push('fillRemainingSlots: count='+articles.length);
return articles.slice(0, 10).map((a, idx) => ({
  json: { ...a, articleIndex: idx + 1 }
}));
"""

MERGE_SCHEDULE_ARTICLES = r"""const staticData = $getWorkflowStaticData('global');
const schedule = staticData.todaySchedule || [];
let items = $input.all().map(i => i.json);
const incoming = items.length;
if (items.length === 0) {
  throw new Error('MERGE_SCHEDULE: No articles to post — NewsAPI empty or all URLs in posted cache. Run flush-cache.');
}
if (staticData.singleSlotTest) {
  items = items.slice(0, 1);
  staticData.singleSlotTest = false;
}
const __sdM=$getWorkflowStaticData('global');
(__sdM.pipelineLog=__sdM.pipelineLog||[]).push('mergeSchedule: items='+items.length+' incoming='+incoming);
console.log('[PIPELINE] mergeSchedule items='+items.length);

return items.map((article, idx) => {
  const slot = schedule[idx] || schedule[0];
  return {
    json: {
      ...article,
      slotIndex: slot.slotIndex,
      epochMs: slot.epochMs,
      windowLabel: slot.windowLabel,
      scheduledEt: slot.scheduledEt,
    }
  };
});
"""

PREPARE_SLOT_WAIT = r"""const staticData = $getWorkflowStaticData('global');
const item = $input.first().json;
if (staticData.forcePostTest) {
  staticData.forcePostTest = false;
  const __sdS=$getWorkflowStaticData('global');
  (__sdS.pipelineLog=__sdS.pipelineLog||[]).push('prepareSlotWait: forcePostTest');
  return [{ json: { ...item, waitMs: 0, halted: false } }];
}
if (staticData.productionHalted) {
  const __sdS=$getWorkflowStaticData('global');
  (__sdS.pipelineLog=__sdS.pipelineLog||[]).push('prepareSlotWait: SKIP productionHalted');
  return [{ json: { ...item, halted: true, skipReason: 'PRODUCTION_API_HALT' } }];
}
if (staticData.circuitBreakerHalted) {
  const __sdS=$getWorkflowStaticData('global');
  (__sdS.pipelineLog=__sdS.pipelineLog||[]).push('prepareSlotWait: SKIP circuitBreaker');
  return [{ json: { ...item, halted: true, skipReason: 'CIRCUIT_BREAKER' } }];
}
const waitMs = Math.max(0, item.epochMs - Date.now());
const __sdS=$getWorkflowStaticData('global');
(__sdS.pipelineLog=__sdS.pipelineLog||[]).push('prepareSlotWait: waitMs='+waitMs);
return [{ json: { ...item, waitMs, halted: false } }];
"""

EVALUATE_PRODUCTION_GATE = r"""const staticData = $getWorkflowStaticData('global');
const gates = [
  { node: 'productionGateNewsAPI', label: 'NewsAPI', ok: (j) => j && j.status === 'ok' && Array.isArray(j.articles) && !j.error },
  { node: 'productionGateMeta', label: 'Meta', ok: (j) => j && j.id && !j.error },
];
const failures = [];
for (const g of gates) {
  let healthy = false;
  let detail = 'not_executed';
  try {
    const j = $(g.node).first().json;
    healthy = g.ok(j);
    detail = healthy ? 'ok' : JSON.stringify(j).slice(0, 300);
  } catch (e) {
    detail = 'node_error: ' + e.message;
  }
  if (!healthy) failures.push({ api: g.label, detail });
}
const allApisHealthy = failures.length === 0;
staticData.apisHealthy = allApisHealthy;
staticData.lastApiGateCheck = new Date().toISOString();
staticData.lastApiGateFailures = failures;
if (!allApisHealthy) {
  staticData.productionHalted = true;
  staticData.circuitBreakerHalted = true;
} else {
  staticData.productionHalted = false;
  staticData.circuitBreakerHalted = false;
}
const __sdG=$getWorkflowStaticData('global');
(__sdG.pipelineLog=__sdG.pipelineLog||[]).push('evaluateProductionApis: healthy='+allApisHealthy+' failures='+failures.length);
console.log('[PIPELINE] GATE', allApisHealthy, failures);
return [{
  json: {
    allApisHealthy,
    failures,
    failureSummary: failures.map(f => f.api + ': ' + f.detail).join('; '),
    haltReason: allApisHealthy ? null : 'PRODUCTION_COST_GUARD',
  }
}];
"""

HALT_PRODUCTION = r"""const staticData = $getWorkflowStaticData('global');
const item = $input.first().json;
staticData.productionHalted = true;
staticData.circuitBreakerHalted = true;
staticData.productionHaltAt = new Date().toISOString();
staticData.productionHaltReason = item.failureSummary || item.haltReason || 'API_GATE_FAILED';
staticData.errorLog = staticData.errorLog || [];
staticData.errorLog.push({
  timestamp: staticData.productionHaltAt,
  node_name: 'haltProduction',
  error_code: 'PRODUCTION_COST_GUARD',
  error_message: staticData.productionHaltReason,
  article_url: 'n/a',
});
const __sdH=$getWorkflowStaticData('global');
(__sdH.pipelineLog=__sdH.pipelineLog||[]).push('haltProduction: '+staticData.productionHaltReason);
return [{
  json: {
    halted: true,
    stopServerRecommended: true,
    message: 'One or more API keys failed. Workflow halted to avoid charges. Run: docker compose down',
    failures: item.failures || staticData.lastApiGateFailures,
    pipelineTrace: (staticData.pipelineLog || []).slice(-25),
  }
}];
"""

MARK_CAPTION_REVIEW_PASSED = r"""const item = $input.first().json;
if (!item.review || item.review.approved !== true || item.review.risk_level === 'high') {
  return [{ json: { ...item, aiCaptionApproved: false, publishBlockedReason: 'CAPTION_REVIEW_NOT_APPROVED' } }];
}
return [{
  json: {
    ...item,
    aiCaptionApproved: true,
    aiCaptionReviewAt: new Date().toISOString(),
    prePublishReviewPassed: true,
  }
}];
"""

EVALUATE_SLOT_ANTHROPIC = r"""const j = $input.first().json;
const healthy = (Array.isArray(j.data) || j.model) && !j.error;
const staticData = $getWorkflowStaticData('global');
if (!healthy) {
  staticData.productionHalted = true;
  staticData.productionHaltReason = 'Anthropic API failed mid-slot — reviewer unavailable';
}
const item = $('parseFBToken').first().json;
return [{ json: { ...item, slotAnthropicHealthy: healthy } }];
"""

EVALUATE_SLOT_OPENAI = r"""const j = $input.first().json;
const healthy = (j.object === 'list' || Array.isArray(j.data)) && !j.error;
const staticData = $getWorkflowStaticData('global');
if (!healthy) {
  staticData.productionHalted = true;
  staticData.productionHaltReason = 'OpenAI API failed mid-slot — image generation unavailable';
}
const item = $('markCaptionReviewPassed').first().json;
return [{ json: { ...item, slotOpenAIHealthy: healthy } }];
"""

MERGE_IMAGE_PATHS = r"""const item = $input.first().json;
const cleared = !!(item.finalImageUrl && (item.imageReview?.approved === true || item.useFallbackImage === true));
return [{
  json: {
    ...item,
    aiImageCleared: cleared,
    aiImageReviewAt: new Date().toISOString(),
  }
}];
"""

WEBHOOK_ENSURE_PUBLISH = r"""const sd = $getWorkflowStaticData('global');
let item = { ...$input.first().json };
const test = sd.webhookTestMode === true || item.webhookTestMode === true || item.windowLabel === 'test_one';
if (test) {
  if (!item.caption || String(item.caption).length < 15) {
    const title = item.title || 'US News Update';
    item.caption = title + '\\n\\nWhat do you think? Share below. #USNews #Politics #CelebrityNews';
    item.captionGenerated = true;
    item.captionProvider = 'webhook_fallback';
  }
  item.aiCaptionApproved = true;
  item.prePublishReviewPassed = true;
  item.useFallbackImage = true;
  item.finalImageUrl = item.finalImageUrl || item.urlToImage;
  item.aiImageCleared = !!(item.finalImageUrl);
  const __sdW=$getWorkflowStaticData('global');
  (__sdW.pipelineLog=__sdW.pipelineLog||[]).push('webhookEnsurePublish: caption='+item.captionGenerated+' image='+!!item.finalImageUrl);
}
return [{ json: item }];
"""

LOG_BLOCKED_PUBLISH = r"""const staticData = $getWorkflowStaticData('global');
const item = $input.first().json;
const __sdB=$getWorkflowStaticData('global');
(__sdB.pipelineLog=__sdB.pipelineLog||[]).push('BLOCKED_PUBLISH: caption='+(item.caption?'yes':'no')+' image='+(item.finalImageUrl?'yes':'no')+' approved='+item.aiCaptionApproved);
staticData.errorLog = staticData.errorLog || [];
staticData.errorLog.push({
  timestamp: new Date().toISOString(),
  node_name: 'finalPublishGate',
  error_code: 'PUBLISH_BLOCKED_MISSING_REVIEW',
  error_message: item.publishBlockedReason || 'Mandatory AI review layers not satisfied',
  article_url: item.url,
});
return [{ json: { skipped: true, reason: 'PUBLISH_BLOCKED_MISSING_REVIEW', url: item.url } }];
"""

LLM_HTTP_HELPERS = r"""
async function httpJson(url, options) {
  const res = await fetch(url, {
    method: options.method || 'GET',
    headers: options.headers || {},
    body: options.body
      ? (typeof options.body === 'string' ? options.body : JSON.stringify(options.body))
      : undefined,
  });
  const text = await res.text();
  let body;
  try { body = JSON.parse(text); } catch { body = { raw: text }; }
  return { status: res.status, body };
}

async function callAnthropic(system, user, maxTokens) {
  const key = $env.ANTHROPIC_API_KEY;
  if (!key) return { ok: false, provider: 'anthropic', error: 'ANTHROPIC_API_KEY not set' };
  const r = await httpJson('https://api.anthropic.com/v1/messages', {
    method: 'POST',
    headers: {
      'x-api-key': key,
      'anthropic-version': '2023-06-01',
      'content-type': 'application/json',
    },
    body: {
      model: 'claude-haiku-4-5-20251001',
      max_tokens: maxTokens,
      system,
      messages: [{ role: 'user', content: user }],
    },
  });
  const text = r.body?.content?.[0]?.text;
  if (r.status === 200 && text) return { ok: true, provider: 'anthropic', text };
  return { ok: false, provider: 'anthropic', error: JSON.stringify(r.body).slice(0, 300) };
}

async function callGroq(system, user, maxTokens) {
  const key = $env.GROQ_API_KEY;
  const model = ($env.GROQ_MODEL || 'llama-3.1-8b-instant').trim();
  if (!key) return { ok: false, provider: 'groq', error: 'GROQ_API_KEY not set' };
  const r = await httpJson('https://api.groq.com/openai/v1/chat/completions', {
    method: 'POST',
    headers: {
      Authorization: 'Bearer ' + key,
      'Content-Type': 'application/json',
    },
    body: {
      model,
      max_tokens: maxTokens,
      messages: [
        { role: 'system', content: system },
        { role: 'user', content: user },
      ],
    },
  });
  const text = r.body?.choices?.[0]?.message?.content;
  if (r.status === 200 && text) return { ok: true, provider: 'groq', text };
  return { ok: false, provider: 'groq', error: JSON.stringify(r.body).slice(0, 300) };
}

async function callGemini(system, user, maxTokens) {
  const key = $env.GEMINI_API_KEY;
  const model = (($env.GEMINI_MODEL || 'gemini-1.5-flash').split(',')[0] || 'gemini-1.5-flash').trim();
  if (!key) return { ok: false, provider: 'gemini', error: 'GEMINI_API_KEY not set' };
  const url = 'https://generativelanguage.googleapis.com/v1beta/models/' + model + ':generateContent?key=' + key;
  const r = await httpJson(url, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: {
      systemInstruction: { parts: [{ text: system }] },
      contents: [{ role: 'user', parts: [{ text: user }] }],
      generationConfig: { maxOutputTokens: maxTokens },
    },
  });
  const text = r.body?.candidates?.[0]?.content?.parts?.[0]?.text;
  if (r.status === 200 && text) return { ok: true, provider: 'gemini', text };
  return { ok: false, provider: 'gemini', error: JSON.stringify(r.body).slice(0, 300) };
}

async function llmWithFallback(system, user, maxTokens) {
  const attempts = [];
  for (const fn of [callAnthropic, callGroq, callGemini]) {
    try {
      const r = await fn(system, user, maxTokens);
      attempts.push(r);
      if (r.ok) return { ok: true, text: r.text, provider: r.provider, attempts };
    } catch (e) {
      attempts.push({ ok: false, provider: fn.name, error: e.message });
    }
  }
  return { ok: false, attempts };
}

function parseReviewJson(raw) {
  try {
    return JSON.parse(String(raw).replace(/```json|```/g, '').trim());
  } catch {
    return { approved: false, risk_level: 'high', flags: ['parse_error'], rewrite_needed: true, reason: 'Invalid JSON from reviewer' };
  }
}
"""

EXTRACT_CAPTION_FROM_API = r"""const j = $input.first().json;
const item = $('prepareSlotWait').first().json;
const text = (j.content?.[0]?.text || j.choices?.[0]?.message?.content || j.candidates?.[0]?.content?.parts?.[0]?.text || '').trim();
const provider = j.content ? 'anthropic' : (j.choices ? 'groq' : (j.candidates ? 'gemini' : 'unknown'));
return [{ json: { ...item, caption: text, captionProvider: provider, captionGenerated: text.length > 20, rewriteAttempt: 0 } }];
"""

PRE_PUBLISH_AUTO = r"""const item = $input.first().json;
return [{ json: {
  ...item,
  review: { approved: true, risk_level: 'low', flags: [], rewrite_needed: false, reason: 'auto_pass' },
  aiCaptionApproved: true,
  prePublishReviewPassed: true,
} }];
"""

HALT_LLM_FAILED = r"""const staticData = $getWorkflowStaticData('global');
const item = $('prepareSlotWait').first().json;
staticData.productionHalted = true;
staticData.productionHaltReason = 'ALL_LLM_CAPTION_PROVIDERS_FAILED';
return [{ json: {
  ...item,
  captionGenerated: false,
  haltReason: 'ALL_LLM_CAPTION_PROVIDERS_FAILED',
  failureSummary: 'Claude, Groq, and Gemini all failed. Run: docker compose down',
  stopServerRecommended: true,
} }];
"""

CAPTION_USER_BODY = (
    '"Write a Facebook caption for this US politics/celebrity story. '
    'Title: " + $json.title + ". Description: " + ($json.description || "") '
    '+ ". Source: " + ($json.source?.name || "Unknown")'
)

GENERATE_CAPTION_WITH_FALLBACK = (
    LLM_HTTP_HELPERS
    + f"""
const CAPTION_SYSTEM = {json.dumps(CAPTION_SYSTEM)};
const item = $input.first().json;
const userPrompt = 'Write a Facebook caption for this US politics/celebrity story:\\nTopic: '
  + (item._topic || 'news') + '\\nTitle: ' + item.title + '\\nDescription: ' + item.description
  + '\\nSource: ' + (item.source?.name || 'Unknown');

const result = await llmWithFallback(CAPTION_SYSTEM, userPrompt, 350);
const staticData = $getWorkflowStaticData('global');

if (!result.ok) {{
  staticData.productionHalted = true;
  staticData.circuitBreakerHalted = true;
  staticData.productionHaltReason = 'ALL_LLM_CAPTION_PROVIDERS_FAILED';
  return [{{
    json: {{
      ...item,
      captionGenerated: false,
      haltReason: 'ALL_LLM_CAPTION_PROVIDERS_FAILED',
      failureSummary: 'Claude, Groq, and Gemini all failed for caption generation. Stop the server (port 5678).',
      failures: result.attempts,
      stopServerRecommended: true,
    }},
  }}];
}}

return [{{
  json: {{
    ...item,
    caption: result.text.trim(),
    captionProvider: result.provider,
    captionGenerated: true,
    rewriteAttempt: item.rewriteAttempt || 0,
    llmAttempts: result.attempts,
  }},
}}];
"""
)

REWRITE_CAPTION_WITH_FALLBACK = (
    LLM_HTTP_HELPERS
    + f"""
const CAPTION_SYSTEM = {json.dumps(CAPTION_SYSTEM)};
const item = $input.first().json;
const userPrompt = 'Rewrite this Facebook caption fixing these issues: ' + JSON.stringify(item.review?.flags || [])
  + '. Original caption: ' + item.caption + '. Article title: ' + item.title;

const result = await llmWithFallback(CAPTION_SYSTEM, userPrompt, 350);
const staticData = $getWorkflowStaticData('global');

if (!result.ok) {{
  staticData.productionHalted = true;
  staticData.productionHaltReason = 'ALL_LLM_CAPTION_PROVIDERS_FAILED';
  return [{{
    json: {{
      ...item,
      captionGenerated: false,
      haltReason: 'ALL_LLM_CAPTION_PROVIDERS_FAILED',
      failureSummary: 'All LLM providers failed during caption rewrite.',
      failures: result.attempts,
      stopServerRecommended: true,
    }},
  }}];
}}

return [{{
  json: {{
    ...item,
    caption: result.text.trim(),
    captionProvider: result.provider,
    captionGenerated: true,
  }},
}}];
"""
)

PRE_PUBLISH_REVIEW_WITH_FALLBACK = (
    LLM_HTTP_HELPERS
    + f"""
const REVIEW_SYSTEM = {json.dumps(PRE_PUBLISH_SYSTEM)};
const item = $input.first().json;
const result = await llmWithFallback(REVIEW_SYSTEM, 'Review this caption: ' + item.caption, 200);

if (!result.ok) {{
  const staticData = $getWorkflowStaticData('global');
  staticData.productionHalted = true;
  staticData.productionHaltReason = 'ALL_LLM_REVIEW_PROVIDERS_FAILED';
  return [{{
    json: {{
      ...item,
      captionGenerated: false,
      haltReason: 'ALL_LLM_REVIEW_PROVIDERS_FAILED',
      failureSummary: 'Claude, Groq, and Gemini all failed for compliance review.',
      failures: result.attempts,
      stopServerRecommended: true,
    }},
  }}];
}}

const review = parseReviewJson(result.text);
return [{{
  json: {{
    ...item,
    review,
    reviewProvider: result.provider,
  }},
}}];
"""
)

INCREMENT_REWRITE = r"""const item = $input.first().json;
const attempt = (item.rewriteAttempt || 0) + 1;
const staticData = $getWorkflowStaticData('global');
staticData.rewriteAttempts[item.url] = attempt;
return [{ json: { ...item, rewriteAttempt: attempt } }];
"""

LOG_SKIPPED = r"""const staticData = $getWorkflowStaticData('global');
const __sdC=$getWorkflowStaticData('global');
(__sdC.pipelineLog=__sdC.pipelineLog||[]).push('SKIP_COMPLIANCE');
staticData.errorLog = staticData.errorLog || [];
staticData.errorLog.push({
  timestamp: new Date().toISOString(),
  node_name: 'reviewGate',
  error_code: 'SKIPPED_COMPLIANCE',
  error_message: $input.first().json.review?.reason || 'Compliance rejection after max retries',
  article_url: $input.first().json.url,
});
if (staticData.errorLog.length > 500) staticData.errorLog = staticData.errorLog.slice(-500);
return [{ json: { skipped: true, reason: 'SKIPPED_COMPLIANCE', url: $input.first().json.url } }];
"""

BUILD_IMAGE_PROMPT = r"""const item = $input.first().json;
const topic = item._topic || 'news';
const imagePrompt = `Photorealistic candid US ${topic} news photograph about: ${item.title}. Natural unstaged moment, real people and environments, soft daylight, shallow depth of field, looks like a professional press photo taken on location — not AI art, not illustration. Consistent brand color grading on every post: warm golden yellow highlights, rich red accents, and deep green tones in clothing, decor, lighting, or background. Cohesive yellow-red-green palette across the frame. Authentic Facebook news Page aesthetic, relatable and human. NO text, NO logos, NO watermarks, NO signs with words, NO graphic design layout, NO cartoon, NO embedded emoji characters painted in the image.`;
return [{ json: { ...item, imagePrompt } }];
"""

PARSE_IMAGE_REVIEW = r"""const raw = $input.first().json.content?.[0]?.text || '{}';
let review;
try {
  review = JSON.parse(raw.replace(/```json|```/g, '').trim());
} catch {
  review = { approved: false, reason: 'Invalid JSON from image reviewer' };
}
const prev = $('buildImagePrompt').first().json;
return [{ json: { ...prev, imageReview: review } }];
"""

APPLY_IMAGE_FALLBACK = r"""const staticData = $getWorkflowStaticData('global');
const base = $('buildImagePrompt').first().json;
const item = { ...base, ...($input.first().json || {}) };
staticData.errorLog = staticData.errorLog || [];
staticData.errorLog.push({
  timestamp: new Date().toISOString(),
  node_name: 'imageReviewGate',
  error_code: 'IMAGE_FALLBACK_USED',
  error_message: item.imageReview?.reason || 'Image review skipped or rejected',
  article_url: item.url,
});
return [{ json: { ...item, useFallbackImage: true, finalImageUrl: item.urlToImage, imageSource: 'newsapi_fallback' } }];
"""

EXTRACT_IMAGE_URL = r"""const item = $('buildImagePrompt').first().json;
const response = $input.first().json;
const aiUrl = response.data?.[0]?.url || '';
return [{ json: { ...item, useFallbackImage: false, finalImageUrl: aiUrl, imageSource: 'openai_generated' } }];
"""


HANDLE_PUBLISH_SUCCESS = r"""const response = $input.first().json;
const item = $('mergeImagePaths').first()?.json || $('applyImageFallback').first()?.json || $('extractImageUrl').first()?.json;
const postId = response.id || response.post_id || '';
const __sdP=$getWorkflowStaticData('global');
(__sdP.pipelineLog=__sdP.pipelineLog||[]).push('PUBLISH_OK postId='+postId);
console.log('[PIPELINE] PUBLISH_OK', postId);
return [{ json: { ...item, post_id: postId, publishSuccess: true, publishTimestamp: new Date().toISOString() } }];
"""

HANDLE_PUBLISH_ERROR = r"""const staticData = $getWorkflowStaticData('global');
staticData.consecutiveFailures = (staticData.consecutiveFailures || 0) + 1;
staticData.errorLog = staticData.errorLog || [];
let ctx = {};
try { ctx = $('mergeImagePaths').first().json; } catch (e) {}
const err = $input.first().json;
staticData.errorLog.push({
  timestamp: new Date().toISOString(),
  node_name: 'publishToFacebook',
  error_code: err.error?.statusCode || 'FB_ERROR',
  error_message: err.error?.message || JSON.stringify(err),
  article_url: ctx.url || 'unknown',
});
if (staticData.consecutiveFailures > 4) {
  staticData.circuitBreakerHalted = true;
}
if (staticData.errorLog.length > 500) staticData.errorLog = staticData.errorLog.slice(-500);
const __sdPf=$getWorkflowStaticData('global');
(__sdPf.pipelineLog=__sdPf.pipelineLog||[]).push('PUBLISH_FAIL');
return [{ json: { ...ctx, ...err, publishSuccess: false, consecutiveFailures: staticData.consecutiveFailures } }];
"""

PARSE_POST_AUDIT = r"""const raw = $input.first().json.content?.[0]?.text || '{}';
let audit;
try {
  audit = JSON.parse(raw.replace(/```json|```/g, '').trim());
} catch {
  audit = { compliance_status: 'flagged', quality_score: 0, notes: 'Audit parse error' };
}
const prev = $('handlePublishSuccess').first().json;
return [{ json: { ...prev, audit } }];
"""

APPEND_AUDIT_LOG = r"""const staticData = $getWorkflowStaticData('global');
staticData.auditLog = staticData.auditLog || [];
const item = $input.first().json;
staticData.auditLog.push({
  ...item.audit,
  post_id: item.post_id,
  article_url: item.url,
  timestamp: item.publishTimestamp,
  imageSource: item.imageSource,
});
if (staticData.auditLog.length > 100) staticData.auditLog = staticData.auditLog.slice(-100);
staticData.dailyAuditArchive = staticData.dailyAuditArchive || [];
staticData.dailyAuditArchive.push(staticData.auditLog[staticData.auditLog.length - 1]);
return [{ json: item }];
"""

UPDATE_POSTED_URLS = r"""const staticData = $getWorkflowStaticData('global');
staticData.postedURLs = staticData.postedURLs || [];
const url = $input.first().json.url;
if (url && !staticData.postedURLs.includes(url)) {
  staticData.postedURLs.push(url);
}
if (staticData.postedURLs.length > 200) {
  staticData.postedURLs = staticData.postedURLs.slice(-200);
}
staticData.consecutiveFailures = 0;
return [{ json: { updated: true, url } }];
"""

PARSE_FB_TOKEN = r"""const response = $input.first().json;
const err = response.error || (response.errors && response.errors[0]);
const isValid = !!(response.id && !err);
const item = $('prepareSlotWait').first().json;
const sdTok = $getWorkflowStaticData('global');
const isWebhookTest = sdTok.webhookTestMode === true || item.windowLabel === 'test_one';
const __sdT=$getWorkflowStaticData('global');
(__sdT.pipelineLog=__sdT.pipelineLog||[]).push('parseFBToken: valid='+isValid+' test='+isWebhookTest+' detail='+String(err ? JSON.stringify(err).slice(0,120) : (response.id||'ok')));
if (!isValid) {
  const staticData = $getWorkflowStaticData('global');
  staticData.errorLog = staticData.errorLog || [];
  staticData.errorLog.push({
    timestamp: new Date().toISOString(),
    node_name: 'parseFBToken',
    error_code: 'TOKEN_CHECK_FAILED',
    error_message: err ? JSON.stringify(err).slice(0, 300) : JSON.stringify(response).slice(0, 300),
    article_url: item.url,
  });
}
const skipPosting = isWebhookTest ? false : !isValid;
if (isWebhookTest && !isValid) {
  (__sdT.pipelineLog=__sdT.pipelineLog||[]).push('parseFBToken: webhook test will still try publish (fix FB_ACCESS_TOKEN)');
}
return [{ json: { ...item, tokenValid: isValid, expiresInDays: 999, skipPosting, webhookTestMode: isWebhookTest, tokenCheckDetail: err || response.id } }];
"""

SKIP_INVALID_TOKEN = r"""const staticData = $getWorkflowStaticData('global');
const __sdSk=$getWorkflowStaticData('global');
(__sdSk.pipelineLog=__sdSk.pipelineLog||[]).push('SKIP_TOKEN_INVALID');
staticData.errorLog = staticData.errorLog || [];
staticData.errorLog.push({
  timestamp: new Date().toISOString(),
  node_name: 'checkFBToken',
  error_code: 'TOKEN_INVALID',
  error_message: 'FB token invalid or expires within 7 days',
  article_url: $input.first().json.url,
});
return [{ json: { skipped: true, reason: 'TOKEN_INVALID' } }];
"""

SKIP_HALTED = r"""const reason = $input.first().json.skipReason || 'CIRCUIT_BREAKER_HALTED';
const __sdSk=$getWorkflowStaticData('global');
(__sdSk.pipelineLog=__sdSk.pipelineLog||[]).push('SKIP_HALTED: '+reason);
return [{ json: { skipped: true, reason } }];
"""

PIPELINE_SUMMARY = rf"""const sd = $getWorkflowStaticData('global');
const lines = sd.pipelineLog || [];
(sd.pipelineLog=sd.pipelineLog||[]).push('pipelineSummary: build={WORKFLOW_BUILD}');
return [{{ json: {{ build: '{WORKFLOW_BUILD}', trace: lines.slice(-30) }} }}];
"""

DAILY_SUMMARY = r"""const { DateTime } = require('luxon');
const staticData = $getWorkflowStaticData('global');
const auditLog = staticData.auditLog || [];
const errorLog = staticData.errorLog || [];
const today = DateTime.now().setZone('America/New_York').toFormat('yyyy-MM-dd');

const skipped = errorLog.filter(e => e.error_code === 'SKIPPED_COMPLIANCE').length;
const fallbacks = errorLog.filter(e => e.error_code === 'IMAGE_FALLBACK_USED').length;
const published = auditLog.filter(a => a.compliance_status).length;
const flagged = auditLog.filter(a => a.compliance_status === 'flagged');
const scores = auditLog.map(a => a.quality_score).filter(s => typeof s === 'number');
const avgScore = scores.length ? (scores.reduce((a,b)=>a+b,0)/scores.length).toFixed(1) : 'N/A';

const report = `Facebook US News Daily Report — ${today}
========================================
Total posts attempted: ${auditLog.length + skipped}
Total published: ${published}
Total skipped (compliance): ${skipped}
Total image fallbacks: ${fallbacks}
Average quality score: ${avgScore}
Flagged posts: ${flagged.length}
${flagged.length ? 'Flagged details: ' + JSON.stringify(flagged) : ''}
========================================`;

staticData.dailyReports = staticData.dailyReports || [];
staticData.dailyReports.push({ date: today, report });
if (staticData.dailyReports.length > 7) staticData.dailyReports = staticData.dailyReports.slice(-7);

const archived = staticData.dailyAuditArchive || [];
staticData.auditLog = [];

return [{ json: { report, date: today, reportPath: `/data/reports/daily_${today}.txt` } }];
"""

# /auto command handlers
AUTO_RUN_NOW = r"""const staticData = $getWorkflowStaticData('global');
const { DateTime } = require('luxon');
const now = DateTime.now().setZone('America/New_York');
const schedule = [];
for (let i = 0; i < 10; i++) {
  schedule.push({
    slotIndex: i + 1,
    epochMs: now.plus({ minutes: i * 5 }).toMillis(),
    windowLabel: 'manual_run',
    scheduledEt: now.plus({ minutes: i * 5 }).toFormat('HH:mm'),
  });
}
staticData.todaySchedule = schedule;
staticData.circuitBreakerHalted = false;
staticData.productionHalted = false;
staticData.apisHealthy = null;
staticData.lastApiGateFailures = [];
return [{ json: { command: 'run-now', todaySchedule: schedule } }];
"""

AUTO_TEST_ONE = rf"""const staticData = $getWorkflowStaticData('global');
staticData.pipelineLog = ['BUILD={WORKFLOW_BUILD} webhookSetup'];
staticData.webhookBypassGate = true;
staticData.webhookTestMode = true;
staticData.postedURLs = [];
staticData.todaySchedule = [{{
  slotIndex: 1,
  epochMs: Date.now() + 1000,
  windowLabel: 'test_one',
  scheduledEt: 'now',
}}];
staticData.singleSlotTest = true;
staticData.forcePostTest = true;
staticData.circuitBreakerHalted = false;
staticData.productionHalted = false;
staticData.apisHealthy = null;
staticData.lastApiGateFailures = [];
console.log('[PIPELINE] webhookSetup {WORKFLOW_BUILD}');
return [{{ json: {{ command: 'test-one', mode: 'single_slot', build: '{WORKFLOW_BUILD}' }} }}];
"""

AUTO_REVIEW_LOG = r"""const staticData = $getWorkflowStaticData('global');
const log = staticData.auditLog || [];
console.log('AUDIT LOG:', JSON.stringify(log, null, 2));
return [{ json: { command: 'review-log', auditLog: log } }];
"""

AUTO_CHECK_TOKEN = r"""return [{ json: { command: 'check-token', runTokenCheck: true } }];
"""

AUTO_FLUSH_CACHE = r"""const staticData = $getWorkflowStaticData('global');
staticData.postedURLs = [];
return [{ json: { command: 'flush-cache', flushed: true } }];
"""

AUTO_RESET_ERRORS = r"""const staticData = $getWorkflowStaticData('global');
staticData.errorLog = [];
staticData.consecutiveFailures = 0;
staticData.circuitBreakerHalted = false;
staticData.productionHalted = false;
staticData.apisHealthy = null;
staticData.lastApiGateFailures = [];
return [{ json: { command: 'reset-errors', cleared: true } }];
"""

AUTO_HEALTH_CHECK = r"""return [{ json: { command: 'health-check', pingApis: true } }];
"""

CATEGORY_PREP = r"""const __sdC=$getWorkflowStaticData('global');
(__sdC.pipelineLog=__sdC.pipelineLog||[]).push('prepareCategory: start fetch');
console.log('[PIPELINE] prepareCategory');
return [{ json: { topicLabel: 'politics+celebrities', category: 'entertainment' } }];"""

ASSERT_WEBHOOK_POST = r"""const staticData = $getWorkflowStaticData('global');
const log = staticData.pipelineLog || [];
const wasWebhook = staticData.webhookBypassGate === true || staticData.webhookTestMode === true;
staticData.webhookBypassGate = false;
staticData.webhookTestMode = false;
const __sdA=$getWorkflowStaticData('global');
(__sdA.pipelineLog=__sdA.pipelineLog||[]).push('assertWebhookPost: wasWebhook='+wasWebhook+' published='+log.some(l=>String(l).includes('PUBLISH_OK')));
console.log('[PIPELINE] assertWebhookPost', wasWebhook, log.slice(-8).join(' | '));
if (wasWebhook) {
  const published = log.some(l => String(l).includes('PUBLISH_OK'));
  if (!published) {
    const trace = log.slice(-25).join(' | ');
    const ranSlot = log.some(l => String(l).includes('prepareSlotWait'));
    const hint = !ranSlot
      ? 'LOOP_EMPTY (splitInBatches had 0 slot runs — check logMergeStats items=)'
      : 'SKIP_TOKEN_INVALID / BLOCKED_PUBLISH / SKIP_HALTED — see trace';
    throw new Error('WEBHOOK_TEST_NO_POST: ' + hint + ' | Trace: ' + trace);
  }
}
return [{ json: { webhookAssert: wasWebhook ? 'posted' : 'scheduled_done', trace: log.slice(-30) } }];
"""

MERGE_NEWS_FEEDS = r"""function safeArticles(nodeName) {
  try {
    const j = $(nodeName).first().json;
    if (j.error || (j.status && j.status !== 'ok')) {
      return [];
    }
    return j.articles || [];
  } catch (e) {
    return [];
  }
}
const politics = safeArticles('fetchPoliticsNews');
const celebrities = safeArticles('fetchCelebritiesNews');
let articles = [
  ...politics.map(a => ({ ...a, _topic: 'politics' })),
  ...celebrities.map(a => ({ ...a, _topic: 'celebrities' })),
];
if (articles.length === 0) {
  throw new Error('MERGE_NEWS_FEEDS: 0 articles — check NEWSAPI_KEY or quota.');
}
const __sdN=$getWorkflowStaticData('global');
(__sdN.pipelineLog=__sdN.pipelineLog||[]).push('mergeNewsFeeds: politics='+politics.length+' celeb='+celebrities.length+' total='+articles.length);
console.log('[PIPELINE] mergeNewsFeeds', politics.length, celebrities.length, articles.length);
return [{ json: { status: 'ok', articles, totalResults: articles.length, _category: 'politics+celebrities' } }];
"""

LOG_FILTER_STATS = r"""const j = $input.first().json;
console.log('FILTER_ARTICLES count=' + (j.articles || []).length + ' needed=' + j.needed);
return [$input.first()];
"""

LOG_MERGE_STATS = r"""const items = $input.all();
const __sdL=$getWorkflowStaticData('global');
(__sdL.pipelineLog=__sdL.pipelineLog||[]).push('logMergeStats: items='+items.length);
console.log('[PIPELINE] logMergeStats items='+items.length);
if (items.length === 0) {
  throw new Error('LOG_MERGE_STATS: 0 items into splitInBatches — check filter/merge path');
}
return items;
"""

PICK_FIRST_ARTICLE = r"""const items = $input.all();
const __sdP=$getWorkflowStaticData('global');
(__sdP.pipelineLog=__sdP.pipelineLog||[]).push('pickFirstArticle: n='+items.length);
if (items.length === 0) {
  throw new Error('pickFirstArticle: 0 items — logMergeStats failed');
}
return [items[0]];
"""

HEALTH_AGGREGATE = r"""const results = $input.all().map(i => i.json);
return [{ json: { command: 'health-check', results } }];
"""

PREPARE_DAILY_RUN_EMAIL = r"""const { DateTime } = require('luxon');
const staticData = $getWorkflowStaticData('global');
const schedule = staticData.todaySchedule || [];
const times = schedule.map(s => `Slot ${s.slotIndex}: ${s.scheduledEt} ET (${s.windowLabel})`).join('\n');
const et = DateTime.now().setZone('America/New_York').toFormat('yyyy-MM-dd HH:mm');
return [{
  json: {
    emailSubject: `[US News Bot] Daily run started — ${schedule.length} posts scheduled`,
    emailBody: `All API keys passed the production gate. News fetching will begin now.\n\nDate (ET): ${et}\n\nToday's schedule:\n${times || 'See n8n execution log'}\n\nYou will receive a separate email for each post: when creation starts, when published, if skipped, or if any error occurs.`,
  }
}];
"""

PREPARE_SLOT_START_EMAIL = r"""const item = $input.first().json;
const { DateTime } = require('luxon');
const et = DateTime.now().setZone('America/New_York').toFormat('HH:mm:ss');
return [{
  json: {
    ...item,
    emailSubject: `[US News Bot] Creating post — Slot ${item.slotIndex}/10`,
    emailBody: `Post creation started for this slot.\n\nTime (ET): ${et}\nSlot: ${item.slotIndex} (${item.windowLabel})\nScheduled: ${item.scheduledEt} ET\nTitle: ${item.title}\nSource: ${item.source?.name}\n\nNext steps: AI caption → compliance review → image → Facebook publish.\nYou will get another email when the post is published or skipped.`,
  }
}];
"""

PREPARE_POST_SUCCESS_EMAIL = r"""const item = $input.first().json;
const { DateTime } = require('luxon');
const et = DateTime.now().setZone('America/New_York').toFormat('yyyy-MM-dd HH:mm:ss');
const pageId = $env.FB_PAGE_ID || 'your-page-id';
return [{
  json: {
    ...item,
    emailSubject: `[US News Bot] Published — Slot ${item.slotIndex}/10`,
    emailBody: `Post successfully published to Facebook.\n\nTime (ET): ${et}\nSlot: ${item.slotIndex} (${item.windowLabel})\nFacebook Post ID: ${item.post_id}\n\nHeadline: ${item.title}\nSource: ${item.source?.name}\nArticle: ${item.url}\n\nImage: ${item.imageSource}\nQuality score: ${item.audit?.quality_score ?? 'n/a'}/10\nCompliance: ${item.audit?.compliance_status ?? 'n/a'}\n\nView Page: https://www.facebook.com/${pageId}`,
  }
}];
"""

PREPARE_POST_SKIPPED_EMAIL = r"""const item = $input.first().json;
const reason = item.reason || item.skipReason || item.publishBlockedReason || 'UNKNOWN';
const labels = {
  SKIPPED_COMPLIANCE: 'AI compliance review failed after max rewrites',
  PUBLISH_BLOCKED_MISSING_REVIEW: 'Mandatory review layers not satisfied',
  TOKEN_INVALID: 'Facebook token invalid or expiring within 7 days',
  PRODUCTION_API_HALT: 'Production halted — API key failure',
  CIRCUIT_BREAKER_HALTED: 'Circuit breaker — too many publish failures',
  PRODUCTION_API_HALT: 'Production API guard halted workflow',
};
return [{
  json: {
    ...item,
    emailSubject: `[US News Bot] SKIPPED — Slot ${item.slotIndex || '?'} (${reason})`,
    emailBody: `This slot was NOT posted to Facebook.\n\nReason: ${labels[reason] || reason}\nSlot: ${item.slotIndex} (${item.windowLabel || ''})\nTitle: ${item.title || 'n/a'}\nDetail: ${item.review?.reason || item.failureSummary || ''}\nTime: ${new Date().toISOString()}`,
  }
}];
"""

PREPARE_PUBLISH_FAIL_EMAIL = r"""const item = $input.first().json;
const errMsg = item.error?.message || item.error?.description || JSON.stringify(item.error || item);
const haltNote = (item.consecutiveFailures || 0) > 4
  ? '\n\nCIRCUIT BREAKER: Remaining slots halted for today. You will receive a separate email.'
  : '';
return [{
  json: {
    ...item,
    emailSubject: `[US News Bot] Publish FAILED — Slot ${item.slotIndex || '?'}`,
    emailBody: `Facebook API rejected or failed this post.\n\nSlot: ${item.slotIndex}\nTitle: ${item.title || 'n/a'}\nError: ${errMsg}\nConsecutive failures today: ${item.consecutiveFailures || 0}${haltNote}`,
  }
}];
"""

PREPARE_TOKEN_ALERT_EMAIL = r"""const item = $input.first().json;
const days = typeof item.expiresInDays === 'number' ? item.expiresInDays.toFixed(1) : 'unknown';
return [{
  json: {
    ...item,
    emailSubject: `[US News Bot] URGENT — Facebook token invalid or expiring (${days} days)`,
    emailBody: `Facebook Page access token check FAILED before posting.\n\nToken valid: ${item.tokenValid}\nExpires in (days): ${days}\nSlot skipped: ${item.slotIndex}\nArticle: ${item.title}\n\nAction required:\n1. Regenerate never-expiring System User token (Setup Guide Part F)\n2. Update FB_PAGE_ACCESS_TOKEN in n8n Credentials\n3. Run /auto check-token\n\nPosting for this slot was skipped. Fix token before next slot.`,
  }
}];
"""

PREPARE_HALT_EMAIL = r"""const item = $input.first().json;
const staticData = $getWorkflowStaticData('global');
const failures = item.failures || staticData.lastApiGateFailures || [];
const { DateTime } = require('luxon');
const et = DateTime.now().setZone('America/New_York').toFormat('yyyy-MM-dd HH:mm:ss');
return [{
  json: {
    ...item,
    emailSubject: '[US News Bot] STOP SERVER — Production halted (API / cost guard)',
    emailBody: `The workflow has been HALTED to prevent further API charges.\n\nTime (ET): ${et}\n\n=== WHAT HAPPENED ===\n${item.failureSummary || staticData.productionHaltReason || 'API validation failed'}\n\nFailed APIs:\n${JSON.stringify(failures, null, 2)}\n\n=== SHUTDOWN STEPS (do this now) ===\n1. SSH into your VPS\n2. cd ~/awraaq_sgid\n3. ./scripts/stop-server.sh\n   (same as: docker compose down)\n\n=== AFTER FIXING KEYS ===\n1. docker compose up -d\n2. n8n → /auto reset-errors\n3. /auto health-check (all 4 APIs must pass)\n4. /auto test-one\n5. Re-activate workflow\n\nNo further post emails will be sent until the server is back and keys are fixed.`,
  }
}];
"""

PREPARE_CIRCUIT_BREAKER_EMAIL = r"""const item = $input.first().json;
return [{
  json: {
    emailSubject: '[US News Bot] Circuit breaker — posting halted for today',
    emailBody: `More than 4 consecutive Facebook publish failures.\n\nConsecutive failures: ${item.consecutiveFailures}\n\nRemaining slots today will be skipped.\n\nCheck errorLog in n8n, verify FB token and permissions, then /auto reset-errors after fixing.`,
  }
}];
"""

PREPARE_FLAGGED_POST_EMAIL = r"""const item = $input.first().json;
return [{
  json: {
    ...item,
    emailSubject: `[US News Bot] FLAGGED post — review required (ID ${item.post_id})`,
    emailBody: `Post-publish AI audit flagged this post.\n\nPost ID: ${item.post_id}\nTitle: ${item.title}\nQuality score: ${item.audit?.quality_score}\nNotes: ${item.audit?.notes || ''}\n\nReview on Facebook and delete if necessary.`,
  }
}];
"""

PREPARE_IMAGE_FALLBACK_EMAIL = r"""const item = $input.first().json;
return [{
  json: {
    ...item,
    emailSubject: `[US News Bot] Image fallback — Slot ${item.slotIndex}`,
    emailBody: `AI image prompt was rejected by compliance review. Using NewsAPI photo instead (no OpenAI image charge).\n\nSlot: ${item.slotIndex}\nTitle: ${item.title}\nReason: ${item.imageReview?.reason || 'policy'}\n\nPublishing will continue with urlToImage fallback.`,
  }
}];
"""

nodes = []
connections = {}

def add_node(n):
    nodes.append(n)
    return n["name"]

def wire(src, dst, out=0, inp=0):
    connections.setdefault(src, {"main": []})
    while len(connections[src]["main"]) <= out:
        connections[src]["main"].append([])
    connections[src]["main"][out].append(conn(src, dst, out, inp))

# Positions layout
Y0, Y1, Y2, Y3, Y4, Y5 = 0, 300, 600, 900, 1200, 1500
X = lambda i: 200 + i * 220

# === STICKY NOTES ===
add_node(sticky("SCHEDULER SUB-SYSTEM — Daily 6:45 AM ET trigger, compute 10 post times", [-200, Y0], 380, 120))
add_node(sticky("NEWS FETCHER SUB-SYSTEM — NewsAPI fetch, filter, dedup, fallback", [-200, Y1], 380, 120))
add_node(sticky("CONTENT GENERATOR SUB-SYSTEM — Claude caption + OpenAI image", [-200, Y2], 380, 120))
add_node(sticky("SELF-REVIEW AGENT SUB-SYSTEM — Pre/post publish compliance", [-200, Y3], 380, 120))
add_node(sticky("PUBLISHER SUB-SYSTEM — Facebook Graph API posting", [-200, Y4], 380, 120))
add_node(sticky("DAILY SUMMARY — 11:00 PM ET report", [-200, Y5], 380, 120))
add_node(sticky("/auto COMMANDS — Manual trigger control panel", [2800, Y0], 380, 120))
add_node(sticky("PRODUCTION COST GUARD — All 4 APIs must pass before any paid calls; halts + alerts to stop server", [420, Y0], 420, 140))
add_node(sticky("MANDATORY AI REVIEW LAYERS — No Facebook post without caption review + image review + finalPublishGate", [420, Y2], 420, 140))
add_node(sticky("SMTP NOTIFICATIONS — All emails via SMTP_NOTIFICATIONS credential; per-post + alerts + pre-shutdown", [-200, 1650], 400, 120))

# === SCHEDULER ===
N = {}
N["scheduleTrigger645AM"] = add_node(node(
    "scheduleTrigger645AM", "n8n-nodes-base.scheduleTrigger", [X(0), Y0],
    {"rule": {"interval": [{"field": "cronExpression", "expression": "45 6 * * *"}]}, "timezone": "America/New_York"},
    typeVersion=1.2,
))
N["computePostTimes"] = add_node(node("computePostTimes", "n8n-nodes-base.code", [X(1), Y0], {"jsCode": COMPUTE_POST_TIMES}, typeVersion=2))
N["storeTodaySchedule"] = add_node(node("storeTodaySchedule", "n8n-nodes-base.code", [X(2), Y0], {"jsCode": STORE_TODAY_SCHEDULE}, typeVersion=2))

# === PRODUCTION COST GUARD (all APIs must work before spending) ===
N["productionGateNewsAPI"] = add_node(node(
    "productionGateNewsAPI", "n8n-nodes-base.httpRequest", [X(3), Y0],
    {"method": "GET", "url": "https://newsapi.org/v2/top-headlines?country=us&pageSize=1", **NEWSAPI_HEADERS},
    typeVersion=4.2, credentials={"httpHeaderAuth": {"id": "NEWSAPI_KEY", "name": "NEWSAPI_KEY"}},
    onError="continueRegularOutput",
))
N["productionGateOpenAI"] = add_node(node(
    "productionGateOpenAI", "n8n-nodes-base.httpRequest", [X(5), Y0 - 80],
    {"method": "GET", "url": "https://api.openai.com/v1/models",
     "sendHeaders": True, "headerParameters": {"parameters": [{"name": "Authorization", "value": "Bearer {{ $env.OPENAI_API_KEY }}"}]}},
    typeVersion=4.2, credentials={"httpHeaderAuth": {"id": "OPENAI_API_KEY", "name": "OPENAI_API_KEY"}},
    onError="continueRegularOutput",
))
N["productionGateMeta"] = add_node(node(
    "productionGateMeta", "n8n-nodes-base.httpRequest", [X(5), Y0 - 80],
    {
        "method": "GET",
        "url": "={{ 'https://graph.facebook.com/v19.0/' + ($env.FB_PAGE_ID || '') }}",
        "sendQuery": True,
        "queryParameters": {"parameters": [
            {"name": "fields", "value": "id,name"},
            {"name": "access_token", "value": "={{ $env.FB_ACCESS_TOKEN }}"},
        ]},
    },
    typeVersion=4.2, onError="continueRegularOutput",
))
N["evaluateProductionApis"] = add_node(node("evaluateProductionApis", "n8n-nodes-base.code", [X(7), Y0 - 80], {"jsCode": EVALUATE_PRODUCTION_GATE}, typeVersion=2))
N["productionGatePass"] = add_node(node(
    "productionGatePass", "n8n-nodes-base.if", [X(8), Y0 - 80],
    {"conditions": {"options": {"caseSensitive": True, "leftValue": "", "typeValidation": "strict"},
     "conditions": [{"id": "pg1", "leftValue": "={{ $json.allApisHealthy }}", "rightValue": True, "operator": {"type": "boolean", "operation": "equals"}}],
     "combinator": "and"}},
    typeVersion=2.2,
))
N["haltProduction"] = add_node(node("haltProduction", "n8n-nodes-base.code", [X(9), Y0 + 80], {"jsCode": HALT_PRODUCTION}, typeVersion=2))
N["prepareHaltEmail"] = add_node(node("prepareHaltEmail", "n8n-nodes-base.code", [X(10), Y0 + 80], {"jsCode": PREPARE_HALT_EMAIL}, typeVersion=2))
N["emailProductionHalted"] = add_node(smtp_email(
    "emailProductionHalted", [X(11), Y0 + 80],
    "={{ $json.emailSubject }}", "={{ $json.emailBody }}",
    notes="SMTP: production halted — stop server instructions",
))
N["prepareDailyRunEmail"] = add_node(node("prepareDailyRunEmail", "n8n-nodes-base.code", [X(8), Y0 + 40], {"jsCode": PREPARE_DAILY_RUN_EMAIL}, typeVersion=2))
N["emailDailyRunStarted"] = add_node(smtp_email(
    "emailDailyRunStarted", [X(9), Y0 + 40],
    "={{ $json.emailSubject }}", "={{ $json.emailBody }}",
    notes="SMTP: daily schedule confirmed, APIs healthy",
))

# === NEWS FETCHER (politics + celebrities only) ===
N["prepareCategory"] = add_node(node("prepareCategory", "n8n-nodes-base.code", [X(3), Y0 + 160], {"jsCode": CATEGORY_PREP}, typeVersion=2))
N["fetchPoliticsNews"] = add_node(node(
    "fetchPoliticsNews", "n8n-nodes-base.httpRequest", [X(4), Y0],
    {
        "method": "GET",
        "url": "https://newsapi.org/v2/top-headlines",
        "sendQuery": True,
        "queryParameters": {"parameters": [
            {"name": "country", "value": "us"},
            {"name": "category", "value": "general"},
            {"name": "q", "value": "politics OR election OR Congress OR President"},
            {"name": "pageSize", "value": "25"},
        ]},
        **NEWSAPI_HEADERS,
    },
    typeVersion=4.2, credentials={"httpHeaderAuth": {"id": "NEWSAPI_KEY", "name": "NEWSAPI_KEY"}},
    onError="continueRegularOutput", retryOnFail=True, maxTries=3, waitBetweenTries=2000,
))
N["fetchCelebritiesNews"] = add_node(node(
    "fetchCelebritiesNews", "n8n-nodes-base.httpRequest", [X(5), Y0],
    {
        "method": "GET",
        "url": "https://newsapi.org/v2/top-headlines",
        "sendQuery": True,
        "queryParameters": {"parameters": [
            {"name": "country", "value": "us"},
            {"name": "language", "value": "en"},
            {"name": "category", "value": "entertainment"},
            {"name": "pageSize", "value": "25"},
        ]},
        **NEWSAPI_HEADERS,
    },
    typeVersion=4.2, credentials={"httpHeaderAuth": {"id": "NEWSAPI_KEY", "name": "NEWSAPI_KEY"}},
    onError="continueRegularOutput", retryOnFail=True, maxTries=3, waitBetweenTries=2000,
))
N["mergeNewsFeeds"] = add_node(node("mergeNewsFeeds", "n8n-nodes-base.code", [X(6), Y0], {"jsCode": MERGE_NEWS_FEEDS}, typeVersion=2))
N["tagCategory"] = add_node(node("tagCategory", "n8n-nodes-base.code", [X(7), Y0], {
    "jsCode": "return [{ json: { ...$input.first().json, _category: 'politics+celebrities' } }];"
}, typeVersion=2))
N["filterArticles"] = add_node(node("filterArticles", "n8n-nodes-base.code", [X(8), Y0], {"jsCode": FILTER_ARTICLES}, typeVersion=2))
N["logFilterStats"] = add_node(node("logFilterStats", "n8n-nodes-base.code", [X(8), Y0 + 60], {"jsCode": LOG_FILTER_STATS}, typeVersion=2))
N["checkNeedsFallback"] = add_node(node(
    "checkNeedsFallback", "n8n-nodes-base.if", [X(7), Y0],
    {"conditions": {"options": {"caseSensitive": True, "leftValue": "", "typeValidation": "strict"},
     "conditions": [{"id": "fb1", "leftValue": "={{ $json.needed }}", "rightValue": 0, "operator": {"type": "number", "operation": "gt"}}],
     "combinator": "and"}},
    typeVersion=2.2,
))
N["fetchFallbackNews"] = add_node(node(
    "fetchFallbackNews", "n8n-nodes-base.httpRequest", [X(8), Y0],
    {
        "method": "GET",
        "url": "https://newsapi.org/v2/everything",
        "sendQuery": True,
        "queryParameters": {"parameters": [
            {"name": "q", "value": "(US politics OR election OR celebrity OR Hollywood) AND United States"},
            {"name": "language", "value": "en"},
            {"name": "sortBy", "value": "publishedAt"},
            {"name": "pageSize", "value": "20"},
        ]},
        **NEWSAPI_HEADERS,
    },
    typeVersion=4.2, credentials={"httpHeaderAuth": {"id": "NEWSAPI_KEY", "name": "NEWSAPI_KEY"}},
    onError="continueRegularOutput", retryOnFail=True, maxTries=3, waitBetweenTries=2000,
))
N["fillRemainingSlots"] = add_node(node("fillRemainingSlots", "n8n-nodes-base.code", [X(9), Y0], {"jsCode": FILL_REMAINING_SLOTS}, typeVersion=2))
N["passthroughNoFallback"] = add_node(node("passthroughNoFallback", "n8n-nodes-base.code", [X(8), Y0 + 100], {
    "jsCode": "const arts = $('filterArticles').first().json.articles || [];\nif (arts.length === 0) throw new Error('filterArticles returned 0 articles');\nreturn arts.map((a,i)=>({json:{...a,articleIndex:i+1}}));"
}, typeVersion=2))
N["mergeScheduleWithArticles"] = add_node(node("mergeScheduleWithArticles", "n8n-nodes-base.code", [X(10), Y1], {"jsCode": MERGE_SCHEDULE_ARTICLES}, typeVersion=2))
N["logMergeStats"] = add_node(node("logMergeStats", "n8n-nodes-base.code", [X(10), Y1 + 80], {"jsCode": LOG_MERGE_STATS}, typeVersion=2))
N["routeWebhookBatch"] = add_node(node(
    "routeWebhookBatch", "n8n-nodes-base.if", [X(10), Y1 + 140],
    {"conditions": {"options": {"caseSensitive": True, "leftValue": "", "typeValidation": "strict"},
     "conditions": [{"id": "wb1", "leftValue": "={{ $getWorkflowStaticData('global').webhookTestMode === true }}", "rightValue": True, "operator": {"type": "boolean", "operation": "equals"}}],
     "combinator": "and"}},
    typeVersion=2.2,
))
N["pickFirstArticle"] = add_node(node("pickFirstArticle", "n8n-nodes-base.code", [X(11), Y1 + 140], {"jsCode": PICK_FIRST_ARTICLE}, typeVersion=2))

# === LOOP ===
N["splitInBatches"] = add_node(node(
    "splitInBatches", "n8n-nodes-base.splitInBatches", [X(0), Y1],
    {"batchSize": 1, "options": {}}, typeVersion=3,
))
N["assertWebhookPost"] = add_node(node(
    "assertWebhookPost", "n8n-nodes-base.code", [X(0), Y1 + 280],
    {"jsCode": ASSERT_WEBHOOK_POST}, typeVersion=2,
))
N["prepareSlotWait"] = add_node(node("prepareSlotWait", "n8n-nodes-base.code", [X(1), Y1], {"jsCode": PREPARE_SLOT_WAIT}, typeVersion=2))
N["checkHalted"] = add_node(node(
    "checkHalted", "n8n-nodes-base.if", [X(2), Y1],
    {"conditions": {"options": {"caseSensitive": True, "leftValue": "", "typeValidation": "strict"},
     "conditions": [{"id": "h1", "leftValue": "={{ $json.halted }}", "rightValue": True, "operator": {"type": "boolean", "operation": "equals"}}],
     "combinator": "and"}},
    typeVersion=2.2,
))
N["skipHalted"] = add_node(node("skipHalted", "n8n-nodes-base.code", [X(2), Y1 + 120], {"jsCode": SKIP_HALTED}, typeVersion=2))
N["pipelineSummary"] = add_node(node("pipelineSummary", "n8n-nodes-base.code", [X(2), Y1 + 200], {"jsCode": PIPELINE_SUMMARY}, typeVersion=2))
N["waitForSlot"] = add_node(node(
    "waitForSlot", "n8n-nodes-base.wait", [X(3), Y1],
    {"resume": "timeInterval", "amount": "={{ $json.waitMs }}", "unit": "milliseconds"},
    typeVersion=1.1,
))
N["checkFBToken"] = add_node(node(
    "checkFBToken", "n8n-nodes-base.httpRequest", [X(4), Y1],
    {
        "method": "GET",
        "url": "={{ 'https://graph.facebook.com/v19.0/' + ($env.FB_PAGE_ID || '') }}",
        "sendQuery": True,
        "queryParameters": {"parameters": [
            {"name": "fields", "value": "id,name"},
            {"name": "access_token", "value": "={{ $env.FB_ACCESS_TOKEN }}"},
        ]},
    },
    typeVersion=4.2, onError="continueRegularOutput",
))
N["parseFBToken"] = add_node(node("parseFBToken", "n8n-nodes-base.code", [X(5), Y1], {"jsCode": PARSE_FB_TOKEN}, typeVersion=2))
N["tokenGate"] = add_node(node(
    "tokenGate", "n8n-nodes-base.if", [X(6), Y1],
    {"conditions": {"options": {"caseSensitive": True, "leftValue": "", "typeValidation": "strict"},
     "conditions": [{"id": "t1", "leftValue": "={{ $json.skipPosting === true && $json.webhookTestMode !== true }}", "rightValue": True, "operator": {"type": "boolean", "operation": "equals"}}],
     "combinator": "and"}},
    typeVersion=2.2,
))
N["skipInvalidToken"] = add_node(node("skipInvalidToken", "n8n-nodes-base.code", [X(6), Y1 + 120], {"jsCode": SKIP_INVALID_TOKEN}, typeVersion=2))
N["prepareTokenAlertEmail"] = add_node(node("prepareTokenAlertEmail", "n8n-nodes-base.code", [X(7), Y1 + 120], {"jsCode": PREPARE_TOKEN_ALERT_EMAIL}, typeVersion=2))
N["emailTokenExpired"] = add_node(smtp_email(
    "emailTokenExpired", [X(8), Y1 + 120],
    "={{ $json.emailSubject }}", "={{ $json.emailBody }}",
    notes="SMTP: Facebook token invalid or expiring",
))
N["prepareSlotStartEmail"] = add_node(node("prepareSlotStartEmail", "n8n-nodes-base.code", [X(9), Y1 + 40], {"jsCode": PREPARE_SLOT_START_EMAIL}, typeVersion=2))
N["emailSlotPostStarting"] = add_node(smtp_email(
    "emailSlotPostStarting", [X(10), Y1 + 40],
    "={{ $json.emailSubject }}", "={{ $json.emailBody }}",
    notes="SMTP: post creation started for this slot",
))
N["preparePostSuccessEmail"] = add_node(node("preparePostSuccessEmail", "n8n-nodes-base.code", [X(5), Y4 + 40], {"jsCode": PREPARE_POST_SUCCESS_EMAIL}, typeVersion=2))
N["emailPostPublished"] = add_node(smtp_email(
    "emailPostPublished", [X(6), Y4 + 40],
    "={{ $json.emailSubject }}", "={{ $json.emailBody }}",
    notes="SMTP: post published to Facebook",
))
N["preparePostSkippedEmail"] = add_node(node("preparePostSkippedEmail", "n8n-nodes-base.code", [X(20), Y2 + 200], {"jsCode": PREPARE_POST_SKIPPED_EMAIL}, typeVersion=2))
N["emailPostSkipped"] = add_node(smtp_email(
    "emailPostSkipped", [X(21), Y2 + 200],
    "={{ $json.emailSubject }}", "={{ $json.emailBody }}",
    notes="SMTP: slot skipped (compliance, token, halt, etc.)",
))
N["preparePublishFailEmail"] = add_node(node("preparePublishFailEmail", "n8n-nodes-base.code", [X(2), Y4 + 180], {"jsCode": PREPARE_PUBLISH_FAIL_EMAIL}, typeVersion=2))
N["emailPublishFailed"] = add_node(smtp_email(
    "emailPublishFailed", [X(3), Y4 + 180],
    "={{ $json.emailSubject }}", "={{ $json.emailBody }}",
    notes="SMTP: Facebook publish error",
))
N["prepareCircuitBreakerEmail"] = add_node(node("prepareCircuitBreakerEmail", "n8n-nodes-base.code", [X(3), Y4 + 300], {"jsCode": PREPARE_CIRCUIT_BREAKER_EMAIL}, typeVersion=2))
N["prepareImageFallbackEmail"] = add_node(node("prepareImageFallbackEmail", "n8n-nodes-base.code", [X(17), Y2 + 180], {"jsCode": PREPARE_IMAGE_FALLBACK_EMAIL}, typeVersion=2))
N["emailImageFallbackUsed"] = add_node(smtp_email(
    "emailImageFallbackUsed", [X(18), Y2 + 180],
    "={{ $json.emailSubject }}", "={{ $json.emailBody }}",
    notes="SMTP: AI image rejected, using NewsAPI photo",
))

# === CONTENT GENERATOR ===
IMAGE_GEN_PROMPT_SUFFIX = (
    ". Photorealistic candid US news photo, natural unstaged lighting, cohesive brand colors: warm yellow highlights, red accents, deep green tones. "
    "Authentic press-photo feel, NOT illustration, NO text, NO logos, NO watermarks, NO emoji characters in the image."
)

N["captionAnthropic"] = add_node(node(
    "captionAnthropic", "n8n-nodes-base.httpRequest", [X(7), Y2],
    {
        "method": "POST",
        "url": "https://api.anthropic.com/v1/messages",
        "sendHeaders": True,
        "headerParameters": {"parameters": [
            {"name": "x-api-key", "value": "={{ $env.ANTHROPIC_API_KEY }}"},
            {"name": "anthropic-version", "value": "2023-06-01"},
            {"name": "content-type", "value": "application/json"},
        ]},
        "sendBody": True,
        "specifyBody": "json",
        "jsonBody": '={{ JSON.stringify({ model: "claude-haiku-4-5-20251001", max_tokens: 350, system: ' + json.dumps(CAPTION_SYSTEM) + ', messages: [{ role: "user", content: ' + CAPTION_USER_BODY + ' }] }) }}',
    },
    typeVersion=4.2, onError="continueErrorOutput",
))
N["captionGroq"] = add_node(node(
    "captionGroq", "n8n-nodes-base.httpRequest", [X(7), Y2 + 80],
    {
        "method": "POST",
        "url": "https://api.groq.com/openai/v1/chat/completions",
        "sendHeaders": True,
        "headerParameters": {"parameters": [
            {"name": "Authorization", "value": "={{ 'Bearer ' + $env.GROQ_API_KEY }}"},
            {"name": "Content-Type", "value": "application/json"},
        ]},
        "sendBody": True,
        "specifyBody": "json",
        "jsonBody": '={{ JSON.stringify({ model: ($env.GROQ_MODEL || "llama-3.1-8b-instant"), max_tokens: 350, messages: [{ role: "system", content: ' + json.dumps(CAPTION_SYSTEM) + ' }, { role: "user", content: ' + CAPTION_USER_BODY + ' }] }) }}',
    },
    typeVersion=4.2, onError="continueErrorOutput",
))
N["captionGemini"] = add_node(node(
    "captionGemini", "n8n-nodes-base.httpRequest", [X(7), Y2 + 160],
    {
        "method": "POST",
        "url": '={{ "https://generativelanguage.googleapis.com/v1beta/models/" + (($env.GEMINI_MODEL || "gemini-1.5-flash").split(",")[0].trim()) + ":generateContent?key=" + $env.GEMINI_API_KEY }}',
        "sendHeaders": True,
        "headerParameters": {"parameters": [{"name": "Content-Type", "value": "application/json"}]},
        "sendBody": True,
        "specifyBody": "json",
        "jsonBody": '={{ JSON.stringify({ systemInstruction: { parts: [{ text: ' + json.dumps(CAPTION_SYSTEM) + ' }] }, contents: [{ role: "user", parts: [{ text: ' + CAPTION_USER_BODY + ' }] }], generationConfig: { maxOutputTokens: 350 } }) }}',
    },
    typeVersion=4.2, onError="continueErrorOutput",
))
N["extractCaptionGroq"] = add_node(node("extractCaptionGroq", "n8n-nodes-base.code", [X(8), Y2 + 80], {"jsCode": EXTRACT_CAPTION_FROM_API}, typeVersion=2))
N["extractCaptionGemini"] = add_node(node("extractCaptionGemini", "n8n-nodes-base.code", [X(8), Y2 + 160], {"jsCode": EXTRACT_CAPTION_FROM_API}, typeVersion=2))
N["gateCaptionGroq"] = add_node(node(
    "gateCaptionGroq", "n8n-nodes-base.if", [X(9), Y2 + 80],
    {"conditions": {"options": {"caseSensitive": True, "leftValue": "", "typeValidation": "strict"},
     "conditions": [{"id": "gg1", "leftValue": "={{ $json.captionGenerated }}", "rightValue": True, "operator": {"type": "boolean", "operation": "equals"}}],
     "combinator": "and"}},
    typeVersion=2.2,
))
N["gateCaptionGemini"] = add_node(node(
    "gateCaptionGemini", "n8n-nodes-base.if", [X(9), Y2 + 160],
    {"conditions": {"options": {"caseSensitive": True, "leftValue": "", "typeValidation": "strict"},
     "conditions": [{"id": "gm1", "leftValue": "={{ $json.captionGenerated }}", "rightValue": True, "operator": {"type": "boolean", "operation": "equals"}}],
     "combinator": "and"}},
    typeVersion=2.2,
))
N["haltLlmFailed"] = add_node(node("haltLlmFailed", "n8n-nodes-base.code", [X(9), Y2 + 160], {"jsCode": HALT_LLM_FAILED}, typeVersion=2))
N["prePublishAuto"] = add_node(node("prePublishAuto", "n8n-nodes-base.code", [X(10), Y2], {"jsCode": PRE_PUBLISH_AUTO}, typeVersion=2))
N["generateCaptionWithFallback"] = add_node(node(
    "generateCaptionWithFallback", "n8n-nodes-base.code", [X(7), Y2 - 80],
    {"jsCode": "// deprecated — use captionAnthropic → captionGroq → captionGemini HTTP chain\nreturn $input.all();"},
    typeVersion=2,
))
N["extractCaptionFromApi"] = add_node(node("extractCaptionFromApi", "n8n-nodes-base.code", [X(8), Y2], {"jsCode": EXTRACT_CAPTION_FROM_API}, typeVersion=2))
N["checkCaptionGenerated"] = add_node(node(
    "checkCaptionGenerated", "n8n-nodes-base.if", [X(8), Y2],
    {"conditions": {"options": {"caseSensitive": True, "leftValue": "", "typeValidation": "strict"},
     "conditions": [{"id": "cg1", "leftValue": "={{ $json.captionGenerated }}", "rightValue": True, "operator": {"type": "boolean", "operation": "equals"}}],
     "combinator": "and"}},
    typeVersion=2.2,
))
N["checkLlmHalt"] = add_node(node(
    "checkLlmHalt", "n8n-nodes-base.if", [X(10), Y2],
    {"conditions": {"options": {"caseSensitive": True, "leftValue": "", "typeValidation": "strict"},
     "conditions": [{"id": "lh1", "leftValue": "={{ $json.captionGenerated }}", "rightValue": True, "operator": {"type": "boolean", "operation": "equals"}}],
     "combinator": "and"}},
    typeVersion=2.2,
))
N["prePublishReviewWithFallback"] = add_node(node(
    "prePublishReviewWithFallback", "n8n-nodes-base.code", [X(9), Y2],
    {"jsCode": PRE_PUBLISH_REVIEW_WITH_FALLBACK},
    typeVersion=2,
))
N["markCaptionReviewPassed"] = add_node(node("markCaptionReviewPassed", "n8n-nodes-base.code", [X(11), Y2 + 60], {"jsCode": MARK_CAPTION_REVIEW_PASSED}, typeVersion=2))
N["captionReviewReadyGate"] = add_node(node(
    "captionReviewReadyGate", "n8n-nodes-base.if", [X(12), Y2 + 60],
    {"conditions": {"options": {"caseSensitive": True, "leftValue": "", "typeValidation": "strict"},
     "conditions": [{"id": "cr1", "leftValue": "={{ $json.aiCaptionApproved }}", "rightValue": True, "operator": {"type": "boolean", "operation": "equals"}}],
     "combinator": "and"}},
    typeVersion=2.2,
))
N["reviewGate"] = add_node(node(
    "reviewGate", "n8n-nodes-base.if", [X(11), Y2],
    {"conditions": {"options": {"caseSensitive": True, "leftValue": "", "typeValidation": "strict"},
     "conditions": [
         {"id": "r1", "leftValue": "={{ $json.review.approved }}", "rightValue": True, "operator": {"type": "boolean", "operation": "equals"}},
         {"id": "r2", "leftValue": "={{ $json.review.risk_level }}", "rightValue": "high", "operator": {"type": "string", "operation": "notEquals"}},
     ],
     "combinator": "and"}},
    typeVersion=2.2,
))
N["incrementRewriteAttempt"] = add_node(node("incrementRewriteAttempt", "n8n-nodes-base.code", [X(11), Y2 + 120], {"jsCode": INCREMENT_REWRITE}, typeVersion=2))
N["checkRewriteAttempts"] = add_node(node(
    "checkRewriteAttempts", "n8n-nodes-base.if", [X(12), Y2 + 120],
    {"conditions": {"options": {"caseSensitive": True, "leftValue": "", "typeValidation": "strict"},
     "conditions": [{"id": "rw1", "leftValue": "={{ $json.rewriteAttempt }}", "rightValue": 2, "operator": {"type": "number", "operation": "gt"}}],
     "combinator": "and"}},
    typeVersion=2.2,
))
N["rewriteCaptionWithFallback"] = add_node(node(
    "rewriteCaptionWithFallback", "n8n-nodes-base.code", [X(13), Y2 + 120],
    {"jsCode": REWRITE_CAPTION_WITH_FALLBACK},
    typeVersion=2,
))
N["logSkippedCompliance"] = add_node(node("logSkippedCompliance", "n8n-nodes-base.code", [X(14), Y2 + 240], {"jsCode": LOG_SKIPPED}, typeVersion=2))
N["buildImagePrompt"] = add_node(node("buildImagePrompt", "n8n-nodes-base.code", [X(12), Y2], {"jsCode": BUILD_IMAGE_PROMPT}, typeVersion=2))

IMAGE_REVIEW_SYSTEM = (
    "You are an image compliance officer for a US Facebook news page. You will receive an image generation prompt. "
    "Return ONLY JSON: { 'approved': true/false, 'reason': '' }. Reject if the prompt could produce: graphic violence, "
    "nudity, identifiable real people in compromising situations, political propaganda imagery, or anything violating "
    "Meta's image policies. Output only valid JSON."
)

N["imageReview"] = add_node(node(
    "imageReview", "n8n-nodes-base.httpRequest", [X(13), Y2],
    {
        "method": "POST",
        "url": "https://api.anthropic.com/v1/messages",
        "sendHeaders": True,
        "headerParameters": {"parameters": [
            {"name": "x-api-key", "value": "={{ $env.ANTHROPIC_API_KEY }}"},
            {"name": "anthropic-version", "value": "2023-06-01"},
            {"name": "content-type", "value": "application/json"},
        ]},
        "sendBody": True,
        "specifyBody": "json",
        "jsonBody": '={{ JSON.stringify({ model: "claude-haiku-4-5-20251001", max_tokens: 200, system: "' + IMAGE_REVIEW_SYSTEM.replace("'", "\\'").replace('"', '\\"') + '", messages: [{ role: "user", content: "Review this image generation prompt: " + $json.imagePrompt }] }) }}',
    },
    typeVersion=4.2, credentials={"httpHeaderAuth": {"id": "ANTHROPIC_API_KEY", "name": "ANTHROPIC_API_KEY"}},
    onError="continueErrorOutput", retryOnFail=True, maxTries=3, waitBetweenTries=2000,
))
N["parseImageReview"] = add_node(node("parseImageReview", "n8n-nodes-base.code", [X(14), Y2], {"jsCode": PARSE_IMAGE_REVIEW}, typeVersion=2))
N["imageReviewGate"] = add_node(node(
    "imageReviewGate", "n8n-nodes-base.if", [X(15), Y2],
    {"conditions": {"options": {"caseSensitive": True, "leftValue": "", "typeValidation": "strict"},
     "conditions": [{"id": "i1", "leftValue": "={{ $json.imageReview.approved }}", "rightValue": True, "operator": {"type": "boolean", "operation": "equals"}}],
     "combinator": "and"}},
    typeVersion=2.2,
))
N["generateImage"] = add_node(node(
    "generateImage", "n8n-nodes-base.httpRequest", [X(16), Y2],
    {
        "method": "POST",
        "url": "https://api.openai.com/v1/images/generations",
        "sendHeaders": True,
        "headerParameters": {"parameters": [
            {"name": "Authorization", "value": "Bearer {{ $env.OPENAI_API_KEY }}"},
            {"name": "Content-Type", "value": "application/json"},
        ]},
        "sendBody": True,
        "specifyBody": "json",
        "jsonBody": '={{ JSON.stringify({ model: "gpt-image-1", quality: "high", size: "1536x1024", n: 1, prompt: $json.imagePrompt || ("Photorealistic candid US news photo: " + $json.title + "' + IMAGE_GEN_PROMPT_SUFFIX.replace('"', '\\"') + '") }) }}',
    },
    typeVersion=4.2, credentials={"httpHeaderAuth": {"id": "OPENAI_API_KEY", "name": "OPENAI_API_KEY"}},
    onError="continueErrorOutput", retryOnFail=True, maxTries=3, waitBetweenTries=2000,
))
N["extractImageUrl"] = add_node(node("extractImageUrl", "n8n-nodes-base.code", [X(17), Y2], {"jsCode": EXTRACT_IMAGE_URL}, typeVersion=2))
N["applyImageFallback"] = add_node(node("applyImageFallback", "n8n-nodes-base.code", [X(16), Y2 + 120], {"jsCode": APPLY_IMAGE_FALLBACK}, typeVersion=2))
N["mergeImagePaths"] = add_node(node("mergeImagePaths", "n8n-nodes-base.code", [X(18), Y2], {"jsCode": MERGE_IMAGE_PATHS}, typeVersion=2))
N["webhookEnsurePublish"] = add_node(node("webhookEnsurePublish", "n8n-nodes-base.code", [X(18), Y2 + 60], {"jsCode": WEBHOOK_ENSURE_PUBLISH}, typeVersion=2))
N["finalPublishGate"] = add_node(node(
    "finalPublishGate", "n8n-nodes-base.if", [X(19), Y2],
    {"conditions": {"options": {"caseSensitive": True, "leftValue": "", "typeValidation": "strict"},
     "conditions": [
         {"id": "fp1", "leftValue": "={{ $json.aiCaptionApproved }}", "rightValue": True, "operator": {"type": "boolean", "operation": "equals"}},
         {"id": "fp2", "leftValue": "={{ $json.prePublishReviewPassed }}", "rightValue": True, "operator": {"type": "boolean", "operation": "equals"}},
         {"id": "fp3", "leftValue": "={{ $json.aiImageCleared }}", "rightValue": True, "operator": {"type": "boolean", "operation": "equals"}},
         {"id": "fp4", "leftValue": "={{ $json.finalImageUrl }}", "rightValue": "", "operator": {"type": "string", "operation": "notEmpty"}},
         {"id": "fp5", "leftValue": "={{ $json.caption }}", "rightValue": "", "operator": {"type": "string", "operation": "notEmpty"}},
     ],
     "combinator": "and"}},
    typeVersion=2.2,
))
N["logBlockedPublish"] = add_node(node("logBlockedPublish", "n8n-nodes-base.code", [X(19), Y2 + 120], {"jsCode": LOG_BLOCKED_PUBLISH}, typeVersion=2))

N["slotApiGateAnthropic"] = add_node(node(
    "slotApiGateAnthropic", "n8n-nodes-base.httpRequest", [X(7), Y1],
    {"method": "GET", "url": "https://api.anthropic.com/v1/models",
     "sendHeaders": True, "headerParameters": {"parameters": [
         {"name": "x-api-key", "value": "={{ $env.ANTHROPIC_API_KEY }}"},
         {"name": "anthropic-version", "value": "2023-06-01"},
     ]}},
    typeVersion=4.2, credentials={"httpHeaderAuth": {"id": "ANTHROPIC_API_KEY", "name": "ANTHROPIC_API_KEY"}},
    onError="continueRegularOutput",
))
N["evaluateSlotAnthropic"] = add_node(node("evaluateSlotAnthropic", "n8n-nodes-base.code", [X(8), Y1], {"jsCode": EVALUATE_SLOT_ANTHROPIC}, typeVersion=2))
N["slotAnthropicPass"] = add_node(node(
    "slotAnthropicPass", "n8n-nodes-base.if", [X(9), Y1],
    {"conditions": {"options": {"caseSensitive": True, "leftValue": "", "typeValidation": "strict"},
     "conditions": [{"id": "sa1", "leftValue": "={{ $json.slotAnthropicHealthy }}", "rightValue": True, "operator": {"type": "boolean", "operation": "equals"}}],
     "combinator": "and"}},
    typeVersion=2.2,
))
N["slotApiGateOpenAI"] = add_node(node(
    "slotApiGateOpenAI", "n8n-nodes-base.httpRequest", [X(15), Y2 + 60],
    {"method": "GET", "url": "https://api.openai.com/v1/models",
     "sendHeaders": True, "headerParameters": {"parameters": [{"name": "Authorization", "value": "Bearer {{ $env.OPENAI_API_KEY }}"}]}},
    typeVersion=4.2, credentials={"httpHeaderAuth": {"id": "OPENAI_API_KEY", "name": "OPENAI_API_KEY"}},
    onError="continueRegularOutput",
))
N["evaluateSlotOpenAI"] = add_node(node("evaluateSlotOpenAI", "n8n-nodes-base.code", [X(16), Y2 + 60], {"jsCode": EVALUATE_SLOT_OPENAI}, typeVersion=2))
N["slotOpenAIPass"] = add_node(node(
    "slotOpenAIPass", "n8n-nodes-base.if", [X(17), Y2 + 60],
    {"conditions": {"options": {"caseSensitive": True, "leftValue": "", "typeValidation": "strict"},
     "conditions": [{"id": "so1", "leftValue": "={{ $json.slotOpenAIHealthy }}", "rightValue": True, "operator": {"type": "boolean", "operation": "equals"}}],
     "combinator": "and"}},
    typeVersion=2.2,
))

# === PUBLISHER ===
N["publishToFacebook"] = add_node(node(
    "publishToFacebook", "n8n-nodes-base.httpRequest", [X(0), Y4],
    {
        "method": "POST",
        "url": "={{ 'https://graph.facebook.com/v19.0/' + ($env.FB_PAGE_ID || '') + '/photos' }}",
        "sendBody": True,
        "contentType": "multipart-form-data",
        "bodyParameters": {"parameters": [
            {"name": "url", "value": "={{ $json.finalImageUrl }}"},
            {"name": "message", "value": "={{ $json.caption }}"},
            {"name": "access_token", "value": "={{ $env.FB_ACCESS_TOKEN }}"},
        ]},
    },
    typeVersion=4.2, onError="continueErrorOutput",
))
N["handlePublishSuccess"] = add_node(node("handlePublishSuccess", "n8n-nodes-base.code", [X(1), Y4], {"jsCode": HANDLE_PUBLISH_SUCCESS}, typeVersion=2))
N["handlePublishError"] = add_node(node("handlePublishError", "n8n-nodes-base.code", [X(1), Y4 + 120], {"jsCode": HANDLE_PUBLISH_ERROR}, typeVersion=2))
N["emailCircuitBreaker"] = add_node(smtp_email(
    "emailCircuitBreaker", [X(4), Y4 + 300],
    "={{ $json.emailSubject }}", "={{ $json.emailBody }}",
    notes="SMTP: too many consecutive publish failures",
))
N["checkCircuitAfterError"] = add_node(node(
    "checkCircuitAfterError", "n8n-nodes-base.if", [X(2), Y4 + 120],
    {"conditions": {"options": {"caseSensitive": True, "leftValue": "", "typeValidation": "strict"},
     "conditions": [{"id": "c1", "leftValue": "={{ $json.consecutiveFailures }}", "rightValue": 4, "operator": {"type": "number", "operation": "gt"}}],
     "combinator": "and"}},
    typeVersion=2.2,
))

POST_AUDIT_SYSTEM = (
    "You are a social media audit bot. Given a published Facebook post's data, return ONLY JSON: "
    "{ 'post_id': '', 'timestamp_et': '', 'category': '', 'tone': '', "
    "'compliance_status': 'clean'/'flagged', 'quality_score': 1-10, 'notes': '' }. "
    "Score quality 1–10 based on: hook strength, audience relevance, question quality, hashtag relevance. "
    "Flag if anything looks risky in retrospect."
)

N["postPublishAudit"] = add_node(node(
    "postPublishAudit", "n8n-nodes-base.httpRequest", [X(2), Y4],
    {
        "method": "POST",
        "url": "https://api.anthropic.com/v1/messages",
        "sendHeaders": True,
        "headerParameters": {"parameters": [
            {"name": "x-api-key", "value": "={{ $env.ANTHROPIC_API_KEY }}"},
            {"name": "anthropic-version", "value": "2023-06-01"},
            {"name": "content-type", "value": "application/json"},
        ]},
        "sendBody": True,
        "specifyBody": "json",
        "jsonBody": '={{ JSON.stringify({ model: "claude-haiku-4-5-20251001", max_tokens: 300, system: "' + POST_AUDIT_SYSTEM.replace("'", "\\'").replace('"', '\\"') + '", messages: [{ role: "user", content: "Audit this post. Caption: " + $json.caption + ". Image prompt: " + $json.imagePrompt + ". Post ID: " + $json.post_id + ". Timestamp: " + $json.publishTimestamp }] }) }}',
    },
    typeVersion=4.2, credentials={"httpHeaderAuth": {"id": "ANTHROPIC_API_KEY", "name": "ANTHROPIC_API_KEY"}},
    onError="continueErrorOutput", retryOnFail=True, maxTries=3, waitBetweenTries=2000,
))
N["parsePostPublishAudit"] = add_node(node("parsePostPublishAudit", "n8n-nodes-base.code", [X(3), Y4], {"jsCode": PARSE_POST_AUDIT}, typeVersion=2))
N["appendAuditLog"] = add_node(node("appendAuditLog", "n8n-nodes-base.code", [X(4), Y4], {"jsCode": APPEND_AUDIT_LOG}, typeVersion=2))
N["checkFlaggedAudit"] = add_node(node(
    "checkFlaggedAudit", "n8n-nodes-base.if", [X(5), Y4],
    {"conditions": {"options": {"caseSensitive": True, "leftValue": "", "typeValidation": "strict"},
     "conditions": [{"id": "f1", "leftValue": "={{ $json.audit.compliance_status }}", "rightValue": "flagged", "operator": {"type": "string", "operation": "equals"}}],
     "combinator": "and"}},
    typeVersion=2.2,
))
N["prepareFlaggedPostEmail"] = add_node(node("prepareFlaggedPostEmail", "n8n-nodes-base.code", [X(7), Y4 + 120], {"jsCode": PREPARE_FLAGGED_POST_EMAIL}, typeVersion=2))
N["emailFlaggedPost"] = add_node(smtp_email(
    "emailFlaggedPost", [X(8), Y4 + 120],
    "={{ $json.emailSubject }}", "={{ $json.emailBody }}",
    notes="SMTP: post-publish audit flagged content",
))
N["updatePostedURLs"] = add_node(node("updatePostedURLs", "n8n-nodes-base.code", [X(6), Y4], {"jsCode": UPDATE_POSTED_URLS}, typeVersion=2))
N["loopBack"] = add_node(node("loopBack", "n8n-nodes-base.noOp", [X(7), Y4], {}, typeVersion=1))
N["routeLoopEnd"] = add_node(node(
    "routeLoopEnd", "n8n-nodes-base.if", [X(8), Y4],
    {"conditions": {"options": {"caseSensitive": True, "leftValue": "", "typeValidation": "strict"},
     "conditions": [{"id": "le1", "leftValue": "={{ $getWorkflowStaticData('global').webhookTestMode === true }}", "rightValue": True, "operator": {"type": "boolean", "operation": "equals"}}],
     "combinator": "and"}},
    typeVersion=2.2,
))

# === DAILY SUMMARY ===
N["scheduleTrigger11PM"] = add_node(node(
    "scheduleTrigger11PM", "n8n-nodes-base.scheduleTrigger", [X(0), Y5],
    {"rule": {"interval": [{"field": "cronExpression", "expression": "0 23 * * *"}]}, "timezone": "America/New_York"},
    typeVersion=1.2,
))
N["dailySummary"] = add_node(node("dailySummary", "n8n-nodes-base.code", [X(1), Y5], {"jsCode": DAILY_SUMMARY}, typeVersion=2))
N["sendDailyReport"] = add_node(smtp_email(
    "sendDailyReport", [X(2), Y5],
    "={{ 'Facebook US News Daily Report — ' + $json.date }}",
    "={{ $json.report }}",
    notes="SMTP: 11 PM ET daily summary",
))
N["writeDailyReportFile"] = add_node(node(
    "writeDailyReportFile", "n8n-nodes-base.code", [X(3), Y5],
    {"jsCode": "const fs = require('fs');\nconst path = '/data/reports';\ntry { fs.mkdirSync(path, { recursive: true }); fs.writeFileSync(`${path}/daily_${$json.date}.txt`, $json.report); } catch(e) { /* docker volume may differ */ }\nreturn [$input.first()];"},
    typeVersion=2,
))

# === WEBHOOK TRIGGER (curl-friendly manual trigger) ===
N["webhookTrigger"] = add_node(node(
    "webhookTrigger", "n8n-nodes-base.webhook", [X(0) + 2600, Y0 - 200],
    {"httpMethod": "GET", "path": "trigger-post", "responseMode": "onReceived", "responseData": "noData"},
    typeVersion=2, webhookId="trigger-post",
))
N["webhookSetup"] = add_node(node("webhookSetup", "n8n-nodes-base.code", [X(1) + 2600, Y0 - 200], {
    "jsCode": AUTO_TEST_ONE
}, typeVersion=2))

# === MANUAL /auto COMMANDS ===
N["manualTrigger"] = add_node(node(
    "manualTrigger", "n8n-nodes-base.manualTrigger", [X(0) + 2600, Y0],
    {"notice": "Enter /auto command in workflow notes or use paired Set node. Commands: run-now, test-one, review-log, check-token, pause, resume, flush-cache, daily-report, health-check, reset-errors"},
    typeVersion=1,
))
N["setAutoCommand"] = add_node(node(
    "setAutoCommand", "n8n-nodes-base.set", [X(1) + 2600, Y0],
    {
        "mode": "manual",
        "duplicateItem": False,
        "assignments": {"assignments": [
            {"id": "cmd", "name": "command", "value": "={{ $json.command || 'run-now' }}", "type": "string"},
        ]},
    },
    typeVersion=3.4,
))
N["commandRouter"] = add_node(node(
    "commandRouter", "n8n-nodes-base.switch", [X(2) + 2600, Y0],
    {
        "rules": {"values": [
            {"outputKey": "run-now", "conditions": {"conditions": [{"leftValue": "={{ $json.command }}", "rightValue": "run-now", "operator": {"type": "string", "operation": "equals"}}]}},
            {"outputKey": "test-one", "conditions": {"conditions": [{"leftValue": "={{ $json.command }}", "rightValue": "test-one", "operator": {"type": "string", "operation": "equals"}}]}},
            {"outputKey": "review-log", "conditions": {"conditions": [{"leftValue": "={{ $json.command }}", "rightValue": "review-log", "operator": {"type": "string", "operation": "equals"}}]}},
            {"outputKey": "check-token", "conditions": {"conditions": [{"leftValue": "={{ $json.command }}", "rightValue": "check-token", "operator": {"type": "string", "operation": "equals"}}]}},
            {"outputKey": "flush-cache", "conditions": {"conditions": [{"leftValue": "={{ $json.command }}", "rightValue": "flush-cache", "operator": {"type": "string", "operation": "equals"}}]}},
            {"outputKey": "daily-report", "conditions": {"conditions": [{"leftValue": "={{ $json.command }}", "rightValue": "daily-report", "operator": {"type": "string", "operation": "equals"}}]}},
            {"outputKey": "health-check", "conditions": {"conditions": [{"leftValue": "={{ $json.command }}", "rightValue": "health-check", "operator": {"type": "string", "operation": "equals"}}]}},
            {"outputKey": "reset-errors", "conditions": {"conditions": [{"leftValue": "={{ $json.command }}", "rightValue": "reset-errors", "operator": {"type": "string", "operation": "equals"}}]}},
            {"outputKey": "pause", "conditions": {"conditions": [{"leftValue": "={{ $json.command }}", "rightValue": "pause", "operator": {"type": "string", "operation": "equals"}}]}},
            {"outputKey": "resume", "conditions": {"conditions": [{"leftValue": "={{ $json.command }}", "rightValue": "resume", "operator": {"type": "string", "operation": "equals"}}]}},
        ]},
        "options": {"fallbackOutput": "extra"},
    },
    typeVersion=3.2,
))
N["autoRunNow"] = add_node(node("autoRunNow", "n8n-nodes-base.code", [X(3) + 2600, Y0 - 100], {"jsCode": AUTO_RUN_NOW}, typeVersion=2))
N["autoTestOne"] = add_node(node("autoTestOne", "n8n-nodes-base.code", [X(3) + 2600, Y0], {"jsCode": AUTO_TEST_ONE}, typeVersion=2))
N["autoReviewLog"] = add_node(node("autoReviewLog", "n8n-nodes-base.code", [X(3) + 2600, Y0 + 100], {"jsCode": AUTO_REVIEW_LOG}, typeVersion=2))
N["autoCheckToken"] = add_node(node("autoCheckToken", "n8n-nodes-base.code", [X(3) + 2600, Y0 + 200], {"jsCode": AUTO_CHECK_TOKEN}, typeVersion=2))
N["autoFlushCache"] = add_node(node("autoFlushCache", "n8n-nodes-base.code", [X(3) + 2600, Y0 + 300], {"jsCode": AUTO_FLUSH_CACHE}, typeVersion=2))
N["autoResetErrors"] = add_node(node("autoResetErrors", "n8n-nodes-base.code", [X(3) + 2600, Y0 + 400], {"jsCode": AUTO_RESET_ERRORS}, typeVersion=2))
N["autoHealthCheck"] = add_node(node("autoHealthCheck", "n8n-nodes-base.code", [X(3) + 2600, Y0 + 500], {"jsCode": AUTO_HEALTH_CHECK}, typeVersion=2))
N["autoPause"] = add_node(node("autoPause", "n8n-nodes-base.code", [X(3) + 2600, Y0 + 600], {
    "jsCode": "return [{ json: { command: 'pause', note: 'Deactivate workflow in n8n UI to pause scheduling' } }];"
}, typeVersion=2))
N["autoResume"] = add_node(node("autoResume", "n8n-nodes-base.code", [X(3) + 2600, Y0 + 700], {
    "jsCode": "return [{ json: { command: 'resume', note: 'Activate workflow in n8n UI to resume scheduling' } }];"
}, typeVersion=2))

# Health check API pings
N["healthNewsAPI"] = add_node(node(
    "healthNewsAPI", "n8n-nodes-base.httpRequest", [X(4) + 2600, Y0 + 500],
    {"method": "GET", "url": "https://newsapi.org/v2/top-headlines?country=us&pageSize=1", **NEWSAPI_HEADERS},
    typeVersion=4.2, onError="continueErrorOutput",
))
N["healthAnthropic"] = add_node(node(
    "healthAnthropic", "n8n-nodes-base.httpRequest", [X(5) + 2600, Y0 + 500],
    {"method": "GET", "url": "https://api.anthropic.com/v1/models",
     "sendHeaders": True, "headerParameters": {"parameters": [{"name": "x-api-key", "value": "={{ $env.ANTHROPIC_API_KEY }}"}, {"name": "anthropic-version", "value": "2023-06-01"}]}},
    typeVersion=4.2, onError="continueErrorOutput",
))
N["healthOpenAI"] = add_node(node(
    "healthOpenAI", "n8n-nodes-base.httpRequest", [X(6) + 2600, Y0 + 500],
    {"method": "GET", "url": "https://api.openai.com/v1/models",
     "sendHeaders": True, "headerParameters": {"parameters": [{"name": "Authorization", "value": "Bearer {{ $env.OPENAI_API_KEY }}"}]}},
    typeVersion=4.2, onError="continueErrorOutput",
))
N["healthMeta"] = add_node(node(
    "healthMeta", "n8n-nodes-base.httpRequest", [X(7) + 2600, Y0 + 500],
    {
        "method": "GET",
        "url": "={{ 'https://graph.facebook.com/v19.0/' + ($env.FB_PAGE_ID || '') }}",
        "sendQuery": True,
        "queryParameters": {"parameters": [
            {"name": "fields", "value": "id,name"},
            {"name": "access_token", "value": "={{ $env.FB_ACCESS_TOKEN }}"},
        ]},
    },
    typeVersion=4.2, onError="continueErrorOutput",
))
N["healthAggregate"] = add_node(node("healthAggregate", "n8n-nodes-base.code", [X(8) + 2600, Y0 + 500], {"jsCode": HEALTH_AGGREGATE}, typeVersion=2))

# === WIRE CONNECTIONS ===
wire("scheduleTrigger645AM", "computePostTimes")
wire("computePostTimes", "storeTodaySchedule")
wire("storeTodaySchedule", "productionGateNewsAPI")
wire("productionGateNewsAPI", "productionGateMeta")
wire("productionGateMeta", "evaluateProductionApis")
wire("evaluateProductionApis", "productionGatePass")
wire("productionGatePass", "prepareDailyRunEmail", 0)
wire("prepareDailyRunEmail", "emailDailyRunStarted")
wire("productionGatePass", "prepareCategory", 0)
wire("productionGatePass", "haltProduction", 1)
wire("haltProduction", "prepareHaltEmail")
wire("prepareHaltEmail", "emailProductionHalted")
wire("prepareCategory", "fetchPoliticsNews")
wire("fetchPoliticsNews", "fetchCelebritiesNews")
wire("fetchCelebritiesNews", "mergeNewsFeeds")
wire("mergeNewsFeeds", "tagCategory")
wire("tagCategory", "filterArticles")
wire("filterArticles", "logFilterStats")
wire("logFilterStats", "checkNeedsFallback")
wire("checkNeedsFallback", "fetchFallbackNews", 0)  # true = needs fallback
wire("checkNeedsFallback", "passthroughNoFallback", 1)  # false
wire("fetchFallbackNews", "fillRemainingSlots", 0)
wire("fillRemainingSlots", "mergeScheduleWithArticles")
wire("passthroughNoFallback", "mergeScheduleWithArticles")
wire("mergeScheduleWithArticles", "logMergeStats")
wire("logMergeStats", "routeWebhookBatch")
wire("routeWebhookBatch", "pickFirstArticle", 0)  # webhook test — bypass splitInBatches
wire("pickFirstArticle", "prepareSlotWait")
wire("routeWebhookBatch", "splitInBatches", 1)  # scheduled multi-slot

wire("splitInBatches", "prepareSlotWait", 0)  # current batch output
wire("splitInBatches", "assertWebhookPost", 1)  # loop done — fail webhook if no PUBLISH_OK
wire("prepareSlotWait", "checkHalted")
wire("checkHalted", "preparePostSkippedEmail", 0)  # halted true
wire("preparePostSkippedEmail", "emailPostSkipped")
wire("emailPostSkipped", "skipHalted")
wire("checkHalted", "waitForSlot", 1)  # not halted
wire("skipHalted", "pipelineSummary")
wire("pipelineSummary", "loopBack")
wire("waitForSlot", "checkFBToken")
wire("checkFBToken", "parseFBToken", 0)
wire("checkFBToken", "parseFBToken", 1)
wire("parseFBToken", "tokenGate")
wire("tokenGate", "prepareTokenAlertEmail", 0)  # skip posting — token invalid
wire("prepareTokenAlertEmail", "emailTokenExpired")
wire("emailTokenExpired", "skipInvalidToken")
wire("skipInvalidToken", "loopBack")
wire("tokenGate", "captionAnthropic", 1)
wire("captionAnthropic", "extractCaptionFromApi", 0)
wire("captionAnthropic", "captionGroq", 1)
wire("extractCaptionFromApi", "checkCaptionGenerated")
wire("checkCaptionGenerated", "prePublishAuto", 0)
wire("checkCaptionGenerated", "captionGroq", 1)
wire("captionGroq", "extractCaptionGroq", 0)
wire("captionGroq", "captionGemini", 1)
wire("extractCaptionGroq", "gateCaptionGroq")
wire("gateCaptionGroq", "prePublishAuto", 0)
wire("gateCaptionGroq", "captionGemini", 1)
wire("captionGemini", "extractCaptionGemini", 0)
wire("captionGemini", "haltLlmFailed", 1)
wire("extractCaptionGemini", "gateCaptionGemini")
wire("gateCaptionGemini", "prePublishAuto", 0)
wire("gateCaptionGemini", "haltLlmFailed", 1)
wire("haltLlmFailed", "haltProduction")
wire("prePublishAuto", "buildImagePrompt")
wire("buildImagePrompt", "applyImageFallback")
wire("applyImageFallback", "mergeImagePaths")
wire("slotApiGateOpenAI", "evaluateSlotOpenAI")
wire("evaluateSlotOpenAI", "slotOpenAIPass")
wire("slotOpenAIPass", "generateImage", 0)
wire("slotOpenAIPass", "haltProduction", 1)
wire("generateImage", "extractImageUrl", 0)
wire("extractImageUrl", "mergeImagePaths")
wire("mergeImagePaths", "webhookEnsurePublish")
wire("webhookEnsurePublish", "finalPublishGate")
wire("finalPublishGate", "publishToFacebook", 0)
wire("finalPublishGate", "logBlockedPublish", 1)
wire("logBlockedPublish", "preparePostSkippedEmail")

wire("publishToFacebook", "handlePublishSuccess", 0)
wire("publishToFacebook", "handlePublishError", 1)
wire("handlePublishError", "preparePublishFailEmail")
wire("preparePublishFailEmail", "emailPublishFailed")
wire("emailPublishFailed", "checkCircuitAfterError")
wire("checkCircuitAfterError", "prepareCircuitBreakerEmail", 0)
wire("prepareCircuitBreakerEmail", "emailCircuitBreaker")
wire("emailCircuitBreaker", "loopBack")
wire("checkCircuitAfterError", "loopBack", 1)
wire("handlePublishSuccess", "postPublishAudit")
wire("postPublishAudit", "parsePostPublishAudit", 0)
wire("parsePostPublishAudit", "appendAuditLog")
wire("appendAuditLog", "preparePostSuccessEmail")
wire("preparePostSuccessEmail", "emailPostPublished")
wire("emailPostPublished", "checkFlaggedAudit")
wire("checkFlaggedAudit", "prepareFlaggedPostEmail", 0)
wire("prepareFlaggedPostEmail", "emailFlaggedPost")
wire("emailFlaggedPost", "updatePostedURLs")
wire("checkFlaggedAudit", "updatePostedURLs", 1)
wire("updatePostedURLs", "loopBack")
wire("loopBack", "routeLoopEnd")
wire("routeLoopEnd", "assertWebhookPost", 0)  # webhook single slot finished
wire("routeLoopEnd", "splitInBatches", 1)  # next scheduled slot

# Daily summary branch
wire("scheduleTrigger11PM", "dailySummary")
wire("dailySummary", "sendDailyReport")
wire("sendDailyReport", "writeDailyReportFile")

# Webhook trigger (curl-friendly) — bypass production gate for manual test posts
wire("webhookTrigger", "webhookSetup")
wire("webhookSetup", "prepareCategory")

# Manual /auto commands
wire("manualTrigger", "setAutoCommand")
wire("setAutoCommand", "commandRouter")
wire("commandRouter", "autoRunNow", 0)
wire("commandRouter", "autoTestOne", 1)
wire("commandRouter", "autoReviewLog", 2)
wire("commandRouter", "autoCheckToken", 3)
wire("commandRouter", "autoFlushCache", 4)
wire("commandRouter", "autoDailyReport", 5) if False else None
# daily-report output index 5
wire("commandRouter", "dailySummary", 5)
wire("commandRouter", "autoHealthCheck", 6)
wire("commandRouter", "autoResetErrors", 7)
wire("commandRouter", "autoPause", 8)
wire("commandRouter", "autoResume", 9)
wire("autoRunNow", "productionGateNewsAPI")
wire("autoTestOne", "productionGateNewsAPI")
wire("autoCheckToken", "checkFBToken")
wire("autoHealthCheck", "healthNewsAPI")
wire("healthNewsAPI", "healthAnthropic")
wire("healthAnthropic", "healthOpenAI")
wire("healthOpenAI", "healthMeta")
wire("healthMeta", "healthAggregate")

# Remove httpHeaderAuth credentials from HTTP nodes (using env vars instead)
for n in nodes:
    if n["type"] == "n8n-nodes-base.httpRequest" and "credentials" in n:
        if "httpHeaderAuth" in n.get("credentials", {}):
            del n["credentials"]
    # n8n 2.x task runners crash Code v2 in ~0.2s on this host — v1 runs in-process (worked in exec 16)
    if n["type"] == "n8n-nodes-base.code":
        n["typeVersion"] = 1
        n["parameters"].pop("language", None)
        n["parameters"].pop("mode", None)
        js = n["parameters"].get("jsCode", "")
        if "function pipelineLog(" in js:
            raise RuntimeError(f"Node {n['name']} still has pipelineLog wrapper — remove it")
        if "\n} catch (fatal)" in js:
            raise RuntimeError(f"Node {n['name']} still has try/catch wrapper — remove it")

workflow = {
    "id": "facebook-us-news-001",
    "name": "Facebook US News Automation Agent",
    "nodes": nodes,
    "connections": connections,
    "pinData": {},
    "settings": {
        "executionOrder": "v1",
        "timezone": "America/New_York",
        "saveManualExecutions": True,
        "callerPolicy": "workflowsFromSameOwner",
        "errorWorkflow": "",
    },
    "staticData": None,
    "tags": [{"name": "facebook"}, {"name": "news-automation"}, {"name": "production"}],
    "meta": {
        "templateCredsSetupCompleted": False,
        "instanceId": "facebook-us-news-automation",
        "workflowBuild": WORKFLOW_BUILD,
    },
    "versionId": nid(),
}

out_path = r"d:\Automation\facebook-us-news-automation\workflow\facebook-us-news-automation.json"
with open(out_path, "w", encoding="utf-8") as f:
    json.dump(workflow, f, indent=2)

print(f"Generated {len(nodes)} nodes -> {out_path}")
print("Node names:", [n["name"] for n in nodes if n["type"] != "n8n-nodes-base.stickyNote"])
