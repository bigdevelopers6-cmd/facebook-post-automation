# Facebook US News Automation Agent

Production-ready, self-hosted n8n workflow for automated Facebook news posting targeting a US audience.

## Architecture

Six sub-systems in one workflow:

| Sub-System | Function |
|------------|----------|
| **Production Cost Guard** | Pings all 4 APIs before any paid work; halts + emails you to **stop the server** if any key fails |
| **Scheduler** | Computes 10 randomized ET posting times daily at 6:45 AM |
| **News Fetcher** | Pulls US news from NewsAPI, filters, deduplicates |
| **Content Generator** | Claude writes captions, OpenAI generates images |
| **Self-Review Agent** | Mandatory AI review layers before publish; post-publish audit |
| **Publisher** | Posts to Facebook only after `finalPublishGate` passes |

See [docs/POSTING-LAYERS.md](docs/POSTING-LAYERS.md) for the full layer diagram.

**SMTP:** All post and alert emails use credential `SMTP_NOTIFICATIONS` — see [docs/SMTP-NOTIFICATIONS.md](docs/SMTP-NOTIFICATIONS.md).

**Recommended hosting:** Hetzner CX22 in Ashburn, VA (~$6–8/mo). Full page naming and VPS steps: [docs/SETUP-GUIDE.md](docs/SETUP-GUIDE.md).

## Quick Start

```bash
# 1. Start n8n
docker compose up -d

# 2. Open http://localhost:5678
# 3. Import workflow/facebook-us-news-automation.json
# 4. Configure credentials (see docs/SETUP-GUIDE.md)
# 5. Test with /auto test-one
# 6. Activate workflow
```

## Deliverables

| File | Description |
|------|-------------|
| [workflow/facebook-us-news-automation.json](workflow/facebook-us-news-automation.json) | Importable n8n workflow (80 nodes) |
| [docs/NODE-MAP.md](docs/NODE-MAP.md) | Complete node list with connections |
| [docs/SETUP-GUIDE.md](docs/SETUP-GUIDE.md) | Step-by-step deployment guide |
| [docs/AUTO-COMMANDS.md](docs/AUTO-COMMANDS.md) | `/auto` slash command reference |
| [docs/TROUBLESHOOTING.md](docs/TROUBLESHOOTING.md) | 10 failure scenarios with fixes |
| [docs/EXECUTION-TRACE.md](docs/EXECUTION-TRACE.md) | Sample end-to-end execution log |
| [docker-compose.yml](docker-compose.yml) | Self-hosted n8n with ET timezone |

## Credentials Required

| Name | Type |
|------|------|
| NEWSAPI_KEY | Header Auth |
| ANTHROPIC_API_KEY | Header Auth |
| OPENAI_API_KEY | Header Auth |
| FB_PAGE_ID | Environment Variable |
| FB_PAGE_ACCESS_TOKEN | Header Auth |
| TIMEZONE | America/New_York (Docker env) |
| SMTP_NOTIFICATIONS | SMTP credential (all email alerts) |

## Schedule

- **6:45 AM ET** — Daily scheduler computes 10 post times (7:00 AM – 9:45 PM ET windows)
- **11:00 PM ET** — Daily summary report email + file

## /auto Commands

```
/auto run-now       /auto test-one      /auto review-log
/auto check-token   /auto pause         /auto resume
/auto flush-cache   /auto daily-report  /auto health-check
/auto reset-errors
```

See [docs/AUTO-COMMANDS.md](docs/AUTO-COMMANDS.md) for full reference.

## Regenerate Workflow

If you modify the generator script:

```bash
py scripts/generate_workflow.py
```

## Stop server when APIs fail

```bash
./scripts/stop-server.sh   # docker compose down
```

Triggered automatically by email when production cost guard halts the workflow.

## Constraints Verified

- All 10 posts fall between 7:00 AM – 10:00 PM ET
- **No post without AI pre-publish review + finalPublishGate**
- **Workflow halts if any API key is invalid** (stop server to save cost)
- Minimum 40-minute gap, maximum 90-minute gap between consecutive posts
- Pre-publish review required before every Facebook post
- No API keys hardcoded in workflow JSON
- Error in one slot does not stop remaining slots
- Dedup store updates after every successful post
- Daily summary runs independently at 11 PM ET
