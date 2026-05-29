# Setup Guide — Facebook US News Automation Agent

Follow this guide **in order**. Every field name, page name pattern, and hosting choice is specified so you can copy values directly.

---

## What you are building

| Item | Value |
|------|--------|
| **Product** | Automated US news Facebook Page (10 posts/day, 7 AM–10 PM ET) |
| **Engine** | Self-hosted **n8n** in Docker |
| **Safety** | **Mandatory AI review** before every post; **no post** if review fails |
| **Cost control** | If **any** API key fails (NewsAPI, Anthropic, OpenAI, Meta), workflow **halts** and you **stop the server** so you are not charged for broken runs |

---

## Part A — Where to run the server (pick one)

You need a machine that is **on 24/7** in a US-friendly timezone and can run Docker. Do **not** run production on your laptop.

### Recommended: **Hetzner Cloud** (best price for 24/7)

| Setting | Exact value |
|---------|-------------|
| Provider | [https://www.hetzner.com/cloud](https://www.hetzner.com/cloud) |
| Plan | **CX22** (2 vCPU, 4 GB RAM, 40 GB disk) |
| Region | **Ashburn, VA** (US East — close to Meta/US APIs) |
| OS | **Ubuntu 22.04** |
| Monthly cost | ~**$6–8/month** |
| Why | Cheapest reliable 24/7 VPS; enough for n8n + Docker |

### Alternative: **DigitalOcean**

| Setting | Exact value |
|---------|-------------|
| Provider | [https://www.digitalocean.com](https://www.digitalocean.com) |
| Plan | **Basic Droplet** — 2 GB RAM / 1 vCPU |
| Region | **NYC1** or **NYC3** |
| OS | **Ubuntu 22.04** |
| Monthly cost | ~**$12/month** |

### Alternative: **AWS Lightsail** (if you already use AWS)

| Setting | Exact value |
|---------|-------------|
| Plan | **$10/month** instance (2 GB RAM) |
| Region | **us-east-1** (N. Virginia) |
| OS | Ubuntu 22.04 |

### Do **not** use for production

- Your Windows/Mac laptop (sleeps, wrong timezone, insecure)
- Free tiers that sleep after idle (Render free, etc.)
- Shared hosting without Docker

### After you create the VPS

1. SSH in: `ssh root@YOUR_SERVER_IP`
2. Create a non-root user (optional but recommended): `adduser n8nadmin && usermod -aG sudo n8nadmin`
3. Continue with **Part B** on that server.

---

## Part B — Install Docker on Ubuntu 22.04

Run on the server:

```bash
sudo apt update && sudo apt upgrade -y
sudo apt install -y ca-certificates curl gnupg lsb-release git

sudo mkdir -p /etc/apt/keyrings
curl -fsSL https://download.docker.com/linux/ubuntu/gpg | sudo gpg --dearmor -o /etc/apt/keyrings/docker.gpg

echo "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.gpg] https://download.docker.com/linux/ubuntu $(lsb_release -cs) stable" | sudo tee /etc/apt/sources.list.d/docker.list > /dev/null

sudo apt update
sudo apt install -y docker-ce docker-ce-cli containerd.io docker-compose-plugin
sudo usermod -aG docker $USER
newgrp docker
```

---

## Step 2 — Clone on AWS server (rename to `awraaq_sgid`)

SSH into your EC2 instance and run **in this order**:

```bash
cd ~

# Clone from GitHub
git clone https://github.com/bigdevelopers6-cmd/facebook-post-automation.git

# Rename project folder (use this name for all commands below)
mv facebook-post-automation awraaq_sgid

cd ~/awraaq_sgid
mkdir -p data/reports
```

Confirm files exist:

```bash
ls -la
# docker-compose.yml  workflow/  scripts/  docs/
```

---

## Part C — Deploy n8n

On the server (always work inside **`~/awraaq_sgid`**):

```bash
cd ~/awraaq_sgid
mkdir -p data/reports
```

Required files in this folder:

- `docker-compose.yml`
- `workflow/facebook-us-news-automation.json`
- `scripts/stop-server.sh`

Edit `docker-compose.yml` — set **your real values**:

```yaml
environment:
  - TZ=America/New_York
  - GENERIC_TIMEZONE=America/New_York
  - N8N_ALERT_FROM=alerts@YOURDOMAIN.com
  - N8N_ALERT_TO=YOUR_EMAIL@gmail.com
  - FB_PAGE_ID=          # fill after Part F (numeric only)
```

Start:

```bash
chmod +x scripts/stop-server.sh
docker compose up -d
docker compose logs -f n8n
```

Open in browser: `http://YOUR_SERVER_IP:5678`  
(Optional: put Caddy/Nginx in front with HTTPS later.)

In n8n: **Settings → Personal → Timezone** → `America/New_York`.

---

## Part D — Create your Facebook Page (exact names & fields)

You need a **Facebook Page** (not a personal profile). The automation posts **as this Page**.

### D.1 Page name (display name)

This automation posts **US politics + celebrity news only**. See **[BRAND-GUIDE.md](BRAND-GUIDE.md)** for recommended names, @usernames, colors, and emoji rules.

**Top picks:**

| Display name | @username |
|--------------|-----------|
| **Power & Fame Daily** | `powerfamedaily` |
| **Capitol & Spotlight** | `capitolspotlight` |
| **Awraaq Power & Fame** | `awraaqpowerfame` |

Pick **one** pattern and use it consistently:

| Style | Example page name |
|--------|-------------------|
| Politics + celebrities | **Power & Fame Daily** |
| DC + Hollywood | **Capitol & Spotlight** |
| Branded | **Awraaq Power & Fame** |

**Rules:**
- 0–75 characters
- No “Facebook”, “Meta”, or “Official” in the name unless you are authorized
- Clear US news positioning for audience trust

**Write your chosen name here before continuing:**  
`Page display name: _______________________________`

### D.2 Page username (@ handle)

Facebook calls this **Page username** (your `@` link).

| Rule | Example |
|------|---------|
| Lowercase, no spaces | `usdailybrief` |
| 5+ characters | `americanewsdesk` |
| Must be unique globally | try `usdailybriefnews` if taken |

**URL will be:** `https://www.facebook.com/YourUsername`

**Write yours:** `@_______________________________`

### D.3 Category (required)

In Page settings → **Category**, choose:

**Primary:** `Media/News Company`  
**Secondary (optional):** `News & media website`

### D.4 Page bio (About → Description)

Copy and customize (max ~255 chars visible):

```
Independent US news for American adults. Daily updates on politics, business, tech, health, and culture. We summarize trusted sources — join the conversation.
```

### D.5 Contact & trust fields

| Field | What to enter |
|-------|----------------|
| Website | Your domain or `https://www.facebook.com/YourUsername` |
| Email | A real inbox you monitor |
| Location | **United States** (city optional: e.g. New York, NY) |

### D.6 Profile & cover images

| Asset | Size | Content |
|-------|------|---------|
| **Profile picture** | 400×400 px min | Logo or “US” monogram; no copyrighted logos |
| **Cover photo** | 820×312 px | Clean newsroom / US skyline; **no text** that will be cropped |

### D.7 Create the Page (step-by-step)

1. Log into **your personal Facebook account** (admin of the Page).
2. Go to [https://www.facebook.com/pages/create](https://www.facebook.com/pages/create).
3. Choose **Business or Brand**.
4. Enter **Page name** (from D.1) → **Create**.
5. Add **Category** (D.3), **bio** (D.4), **username** (D.2) under **Settings → General → Username**.
6. Upload profile + cover (D.6).
7. Under **Settings → Page roles**, confirm you are **Admin**.

### D.8 Meta Business Portfolio (required for never-expiring token)

1. Go to [https://business.facebook.com/](https://business.facebook.com/).
2. **Create account** (or use existing) → name it e.g. `US News Automation Portfolio`.
3. **Add assets → Pages** → add the Page you just created.
4. You will connect the **System User** token here in Part F.

---

## Part E — Facebook Developer App (for posting API)

| Field | Your value |
|-------|------------|
| App display name | `US News Automation` (internal; users don’t see this) |
| App type | **Business** |
| Use case | **Manage everything on your Page** |

Steps:

1. [https://developers.facebook.com/apps/](https://developers.facebook.com/apps/) → **Create App**.
2. App name: **`US News Automation`**.
3. Add **Facebook Login for Business** or use **Graph API** product.
4. **App roles → Administrators** — add your Facebook account.
5. Permissions needed (for your own Page as admin, no review required initially):
   - `pages_manage_posts`
   - `pages_read_engagement`

**Write down:**

| Item | Value |
|------|--------|
| App ID | `________________` |
| App Secret | `________________` (keep private) |

---

## Part F — Page ID & never-expiring access token

### F.1 Get Page ID (numeric)

After you have a Page token (temporary is OK for this call):

```bash
curl -s "https://graph.facebook.com/v19.0/me/accounts?access_token=YOUR_PAGE_ACCESS_TOKEN"
```

Find your Page in JSON:

```json
{
  "data": [{
    "name": "US Daily Brief",
    "id": "123456789012345",
    "access_token": "..."
  }]
}
```

Put **`id`** into `docker-compose.yml`:

```yaml
- FB_PAGE_ID=123456789012345
```

Restart: `docker compose up -d`

### F.2 System User token (recommended — does not expire)

1. [https://business.facebook.com/settings/system-users](https://business.facebook.com/settings/system-users)
2. **Add** → Name: `n8n-poster` → Role: **Admin**.
3. **Add assets** → **Pages** → select **your Page** → **Full control**.
4. **Generate token** → select app **`US News Automation`**.
5. Permissions: `pages_manage_posts`, `pages_read_engagement`.
6. Expiration: **Never**.
7. Copy token → n8n credential **`FB_PAGE_ACCESS_TOKEN`** (Part G).

---

## Part G — n8n credentials (exact names)

In n8n: **Credentials → Add credential**. Names must match so the workflow finds them.

| Credential name in n8n | Type | Header / field | Value |
|------------------------|------|----------------|--------|
| `NEWSAPI_KEY` | Header Auth | Name: `X-Api-Key` | From [newsapi.org](https://newsapi.org/register) |
| `ANTHROPIC_API_KEY` | Header Auth | Name: `x-api-key` | From [console.anthropic.com](https://console.anthropic.com/) |
| `OPENAI_API_KEY` | Header Auth | Name: `Authorization` | `Bearer sk-...` from [platform.openai.com](https://platform.openai.com/api-keys) |
| `FB_PAGE_ACCESS_TOKEN` | Header Auth | Name: `access_token` | System User token (Part F.2) |
| **`SMTP_NOTIFICATIONS`** | **SMTP** | See Part G2 below | **Required for all emails** |
| *(env)* `FB_PAGE_ID` | docker-compose | — | Numeric Page ID (Part F.1) |
| *(env)* `N8N_ALERT_FROM` | docker-compose | — | Sender address |
| *(env)* `N8N_ALERT_TO` | docker-compose | — | Your inbox (all notifications) |
| *(env)* `TIMEZONE` | docker-compose | `TZ=America/New_York` | Already set |

---

## Part G2 — SMTP setup (required)

Every notification uses credential name **`SMTP_NOTIFICATIONS`**. Without it, you will not get post updates, token alerts, or shutdown emails.

### G2.1 Choose an SMTP provider

| Provider | Best for | Cost |
|----------|----------|------|
| **Gmail** (App Password) | Solo operator, quick start | Free |
| **SendGrid** | Production volume | Free tier 100 emails/day |
| **Amazon SES** | AWS users | ~$0.10 / 1k emails |
| **Mailgun** | Developers | Free tier limited |

**Recommended for beginners:** Gmail with App Password.

### G2.2 Gmail SMTP (step-by-step)

1. Use a Google account you check on your phone.
2. Enable 2FA: [https://myaccount.google.com/security](https://myaccount.google.com/security)
3. Create App Password: [https://myaccount.google.com/apppasswords](https://myaccount.google.com/apppasswords) → Mail → Other → name `n8n-us-news`
4. Copy the 16-character password.

In n8n → **Credentials → Add credential → SMTP**:

| Field | Value |
|-------|--------|
| **Credential name** | `SMTP_NOTIFICATIONS` (exact) |
| **User** | your.email@gmail.com |
| **Password** | 16-char app password (no spaces) |
| **Host** | smtp.gmail.com |
| **Port** | 587 |
| **SSL/TLS** | STARTTLS (or TLS) |

5. Click **Test** — must show success.

### G2.3 SendGrid SMTP (production)

1. [https://signup.sendgrid.com](https://signup.sendgrid.com) → verify sender email/domain.
2. **Settings → API Keys** → create key with Mail Send.
3. n8n SMTP credential:

| Field | Value |
|-------|--------|
| Name | `SMTP_NOTIFICATIONS` |
| Host | smtp.sendgrid.net |
| Port | 587 |
| User | apikey |
| Password | your SendGrid API key |

### G2.4 Set From / To in Docker

```yaml
- N8N_ALERT_FROM=alerts@yourdomain.com   # must be allowed sender (Gmail = your gmail)
- N8N_ALERT_TO=youremail@gmail.com       # receives ALL bot emails
```

Restart: `docker compose up -d`

### G2.5 Connect SMTP to workflow (after import)

Open workflow → select any email node (e.g. `emailPostPublished`) → **Credential** → `SMTP_NOTIFICATIONS`.

Repeat for each email node, or use n8n’s credential picker once per node group:

| Email node | What you get notified about |
|------------|----------------------------|
| `emailDailyRunStarted` | Day started, 10 slot times, APIs OK |
| `emailSlotPostStarting` | Each post **creation** started |
| `emailPostPublished` | Each successful **Facebook post** |
| `emailPostSkipped` | Skipped (compliance, review, halt) |
| `emailPublishFailed` | Facebook publish error |
| `emailTokenExpired` | **Key expiring / invalid** (Facebook) |
| `emailImageFallbackUsed` | AI image rejected, using NewsAPI photo |
| `emailFlaggedPost` | Post-publish audit flagged |
| `emailCircuitBreaker` | Too many failures, posting stopped |
| `emailProductionHalted` | **API keys failed — stop server** instructions |
| `sendDailyReport` | 11 PM ET summary |

Full list: [SMTP-NOTIFICATIONS.md](SMTP-NOTIFICATIONS.md)

### G2.6 Test SMTP

1. Manual workflow run → `health-check` (no email).
2. `test-one` — you should receive:
   - Daily run OR slot starting (if APIs run)
   - Creating post
   - Published OR Skipped
3. If no email: check spam, SMTP test in credentials, and `N8N_ALERT_TO`.

---

## Part H — Import workflow & connect nodes

1. **Workflows → Import from File** → `workflow/facebook-us-news-automation.json`
2. Open workflow → assign credentials:

| Nodes | Credential |
|-------|------------|
| fetchUSNews, fetchFallbackNews, productionGate*, healthNewsAPI | NEWSAPI_KEY |
| generateCaption, prePublishReview, rewriteCaption, imageReview, postPublishAudit, productionGateAnthropic, slotApiGateAnthropic | ANTHROPIC_API_KEY |
| generateImage, productionGateOpenAI, slotApiGateOpenAI, healthOpenAI | OPENAI_API_KEY |
| publishToFacebook, checkFBToken, productionGateMeta, healthMeta | FB_PAGE_ACCESS_TOKEN |
| **All 11 `email*` and `sendDailyReport` nodes** | **SMTP_NOTIFICATIONS** |

3. Confirm **Active** is OFF until testing is done (Part K).

---

## Part I — Mandatory layers (how posting is protected)

No post reaches Facebook unless **all** layers pass:

```
┌─────────────────────────────────────────────────────────────┐
│ LAYER 0 — Production Cost Guard (start of day + /auto runs) │
│   Ping NewsAPI + Anthropic + OpenAI + Meta                  │
│   ANY fail → haltProduction → email → STOP SERVER           │
└─────────────────────────────────────────────────────────────┘
                              ↓ all OK
┌─────────────────────────────────────────────────────────────┐
│ LAYER 1 — Per slot: Anthropic alive (slotApiGateAnthropic)  │
│   Fail → halt production (no caption $)                     │
└─────────────────────────────────────────────────────────────┘
                              ↓
┌─────────────────────────────────────────────────────────────┐
│ LAYER 2 — Generate caption (Claude)                         │
└─────────────────────────────────────────────────────────────┘
                              ↓
┌─────────────────────────────────────────────────────────────┐
│ LAYER 3 — prePublishReview (Claude compliance JSON)         │
│   reviewGate: approved=true AND risk_level ≠ high           │
│   Max 2 rewrites → else SKIPPED_COMPLIANCE                  │
└─────────────────────────────────────────────────────────────┘
                              ↓
┌─────────────────────────────────────────────────────────────┐
│ LAYER 4 — markCaptionReviewPassed + captionReviewReadyGate  │
└─────────────────────────────────────────────────────────────┘
                              ↓
┌─────────────────────────────────────────────────────────────┐
│ LAYER 5 — imageReview (Claude reviews image prompt)         │
│   Reject → NewsAPI urlToImage fallback (no OpenAI $)        │
└─────────────────────────────────────────────────────────────┘
                              ↓
┌─────────────────────────────────────────────────────────────┐
│ LAYER 6 — slotApiGateOpenAI (only if AI image)              │
└─────────────────────────────────────────────────────────────┘
                              ↓
┌─────────────────────────────────────────────────────────────┐
│ LAYER 7 — finalPublishGate                                  │
│   Requires: aiCaptionApproved, prePublishReviewPassed,      │
│   aiImageCleared, caption, finalImageUrl                    │
└─────────────────────────────────────────────────────────────┘
                              ↓
│ LAYER 8 — publishToFacebook → postPublishAudit              │
└─────────────────────────────────────────────────────────────┘
```

---

## Part J — If API keys fail: stop the server (save money)

When **any** production gate fails, you receive SMTP email from **`emailProductionHalted`**: subject **`[US News Bot] STOP SERVER — Production halted`**. It includes what failed and exact shutdown commands **before** you should leave the server running.

On the server, run:

```bash
cd ~/awraaq_sgid
./scripts/stop-server.sh
# same as: docker compose down
```

This stops n8n so scheduled runs do not keep calling paid APIs.

**Recovery:**

1. Fix the broken credential in n8n (or billing on provider site).
2. `docker compose up -d`
3. In n8n, manual trigger with command **`reset-errors`** (see AUTO-COMMANDS.md).
4. Run **`health-check`** then **`test-one`**.

---

## Part K — Test before going live

| Step | Action |
|------|--------|
| 1 | Manual trigger → `setAutoCommand` → `command` = **`health-check`** |
| 2 | All 4 APIs must show healthy in execution log |
| 3 | `command` = **`test-one`** → one full cycle with all review layers |
| 4 | Confirm post on your Page at `facebook.com/YourUsername` |
| 5 | Toggle workflow **Active** |

---

## Part L — Production checklist

- [ ] VPS running Ubuntu 22.04 (Hetzner Ashburn or equivalent)
- [ ] `TZ=America/New_York` in Docker
- [ ] Facebook Page created with name, @username, category, bio, images
- [ ] Meta Business Portfolio owns the Page
- [ ] Developer app + System User never-expiring token
- [ ] `FB_PAGE_ID` in docker-compose
- [ ] All 5 API credentials + **`SMTP_NOTIFICATIONS`** tested (Part G2)
- [ ] Test email received from `test-one` (Creating post + Published)
- [ ] `health-check` passes all 4 APIs
- [ ] `test-one` publishes one reviewed post
- [ ] You know how to run `./scripts/stop-server.sh` if alert email arrives
- [ ] Workflow **Active**

---

## Quick reference — your project worksheet

Fill this in and keep it private:

```
Hosting provider:     _______________  IP: _______________
Page display name:    _______________
Page @username:       _______________
Page numeric ID:      _______________
Meta Business name:   _______________
Developer app name:   US News Automation
Developer app ID:     _______________
Alert email:          _______________
n8n URL:              http://_______________:5678
```

You are production-ready when Part L is complete.
