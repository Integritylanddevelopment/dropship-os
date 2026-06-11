# Dropship OS — Complete Build Plan
**Owner:** Alex Alexander  
**Last updated:** 2026-04-22  
**Status:** In progress

---

## The System in One Sentence
Product listing in → AI creates video → repurposed to 6 channels → posted automatically → orders fulfilled → revenue tracked live.

---

## Phase 1 — Live Data Infrastructure
**Goal:** Kill every fake number. Everything on the dashboard is real.

- [ ] `/api/metrics.js` — Vercel edge function pulling live data:
  - Stripe → today's revenue, total orders, avg order value
  - Qdrant via Quinn bridge → real collection counts (sessions, files, agents)
  - `metrics.json` → decision engine scores, channel rankings, product combos
- [ ] `/stats` route added to `quinn_web_bridge.py` — exposes Qdrant collection counts over ngrok
- [ ] `metrics.json` schema created in `dropship-os/` — populated by `decision_engine.py` on each run
- [ ] `decision_engine.py` updated to write `metrics.json` after scoring

**APIs needed:** Stripe (already connected), Quinn bridge running + ngrok active

---

## Phase 2 — Strip All Fake Data from Dashboard Pages
**Goal:** Every number on every page is either live or shows "—". No placeholders, no fake numbers, ever.

### index.html
- [ ] Ticker bar → pulls from `metrics.json` (CPM, margin, scores) — live or "—"
- [ ] KPI cards → Stripe revenue, Qdrant counts, decision engine score
- [ ] Channel ranking scores → from `metrics.json`
- [ ] Product combo rankings → from `metrics.json`
- [ ] Product margins → from supplier APIs or manual entry (no fake %)
- [ ] Add Reddit to channel list everywhere it appears

### roi.html
- [ ] Product dropdown → real products from supplier APIs (Zendrop/AutoDS)
- [ ] Margin calculations → real data, not static options

### hormozi.html / ecom-king.html
- [ ] CPM/ROAS table rows → real data from `metrics.json` or "—" until connected

---

## Phase 3 — Product Cards with Supplier Wizard + Push to Production
**Goal:** Come to the product page, find a product with good margin, get the supplier link, push it live.

Each product card contains:
- Product name, margin %, decision score, best channel
- **[Get Supplier Link]** button → wizard:
  - Step 1: Choose supplier (Zendrop / AutoDS / AliExpress / CJ Dropshipping)
  - Step 2: Opens direct product search URL for that niche on chosen supplier
  - Step 3: Paste your product link back → saves to card
- **[▶ Push to Production]** button → triggers pipeline:
  1. Confirm: product + channel combo
  2. Quinn generates content (hook, caption, platform copy)
  3. Fires to `social_ai_agent` → posts to channel
  4. Card updates: "LIVE — posted [timestamp]"
- Channel selector (Pinterest / TikTok / IG / YT Shorts / X / Reddit / Email)

**APIs needed:** Zendrop API, AutoDS API, CJ Dropshipping API, AliExpress affiliate API

---

## Phase 4 — Prometheus Creation Studio (`/content` page)
**Goal:** Paste a product listing URL. Walk out with 6 pieces of platform-ready content approved and queued to the calendar.

### Step 0 — Pillar Builder
- Paste product listing URL (Zendrop, AliExpress, Amazon, etc.)
- Scrapes: title, description, all product images, price, features
- Searches internet for additional images ranked:
  - **#1 Funny** — memes, comedy, relatable (Reddit, Giphy)
  - **#2 Emotional** — heartwarming, tearjerker (Google Images, Pexels)
  - **#3 Amazing** — wow factor, impressive results (Google Images, Unsplash)
  - **#4 Practical** — how-it-works, demo, before/after (YouTube, Google)
- Quinn/Ollama writes pillar video script + hooks + ad copy
- Preview: all assets + script before recording

### Step 1 — Upload Pillar Video
- Platform selector: [IG ▼] (Instagram is default pillar source)
- Browse button → upload recorded video
- Preview uploaded video

### Step 2 — Run Pipeline
- **[▶ Run Pipeline]** button
- Generates 6 platform-specific pieces:
  - TikTok (9:16, 15–60 sec, trending hook)
  - YouTube Shorts (9:16, up to 60 sec)
  - Pinterest (9:16 or 2:3, pin description auto-written)
  - Instagram Reel (9:16)
  - X/Twitter thread (text + clip)
  - Email (copy + thumbnail)
- Progress shown per clip as generated
- Engine: Opus Clip API (temporary) → replaced by local FFmpeg + Whisper + Ollama pipeline

### Step 3 — Approve & Schedule
- Preview each piece inline
- **[✓ Approve]** or **[✏ Edit]** per piece
- Edit mode: trim points, swap hook, change caption
- Shows: 5/6 approved, 1 pending

### Step 4 — Push to Calendar
- **[🚀 Push All to Calendar]** → schedules all approved pieces
- Auto-assigns best posting times per platform
- Calendar shows 1–2 weeks ahead
- Status updates as each piece posts live

**APIs needed:** Opus Clip API (interim), Google Custom Search API, Pexels API, Unsplash API, Reddit API, Giphy API

---

## Phase 5 — Prometheus Studio Engine (Replace Opus Clip)
**Goal:** Build our own video repurposing pipeline. $0/month at 800 videos/day vs $5,000+/month for Opus Clip.

- [ ] FFmpeg pipeline: video in → detect scenes → cut clips → resize per platform
- [ ] Whisper integration: transcribe pillar video → find best moments by content
- [ ] Ollama scoring: rank moments by viral potential → select top clips
- [ ] Auto-captions: Whisper timestamps → FFmpeg subtitle burn
- [ ] Platform resize engine: 9:16 (TikTok/Reels/Shorts), 2:3 (Pinterest), 16:9 (YouTube)
- [ ] Queue system: handle 800 videos/day throughput
- [ ] Seedance 2.0 API (Atlas Cloud): text + images → AI-generated video (for Pillar Builder output)
- [ ] Suno AI API: original background music per video
- [ ] ElevenLabs API: voiceover generation from Ollama-written scripts
- [ ] HeyGen API (optional): AI avatar spokesperson

**Timeline with parallel agents:** 3–4 weeks  
**Cost at scale:** ~$1,600/month vs $5,000–8,000/month for Opus Clip

---

## Phase 6 — Content Calendar
**Goal:** See everything queued, know what's going out and when, never miss a post.

- [ ] Calendar view on Command Center (`index.html`)
- [ ] 1–2 week ahead view per channel
- [ ] Drag-to-reschedule
- [ ] Status per post: Queued / Posting / Live / Failed
- [ ] Auto-fire: scheduled posts sent to platform APIs at publish time
- [ ] Retry logic on failure

---

## Phase 7 — Social Distribution (Auto-Posting)
**Goal:** Approve content → it goes live automatically. Zero manual posting.

- [ ] Pinterest API: auto-post pins with description + link
- [ ] TikTok API: auto-post videos (apply for API access now — 2 week wait)
- [ ] Instagram/Meta Graph API: auto-post Reels + Stories
- [ ] YouTube Data API: auto-upload Shorts
- [ ] X/Twitter API v2: auto-post threads + video clips
- [ ] Email: integrate with email provider (Klaviyo or Mailchimp API)

**APIs needed:** Pinterest token, Meta token, TikTok token (apply NOW), YouTube token, Twitter/X token, Klaviyo/Mailchimp API

---

## Phase 8 — Decision Engine Live
**Goal:** System tells you every morning: what to push, what to kill, where to double down.

- [ ] `decision_engine.py` runs daily via Windows Task Scheduler
- [ ] Scores every product × channel combo: Margin% × (100/CPM) × ViralCoeff
- [ ] Score ≥ 70 for 2 weeks → "SCALE NOW" signal
- [ ] Score < 30 for 2 weeks → "KILL" signal
- [ ] Writes results to `metrics.json` → auto-committed to GitHub → Vercel serves live
- [ ] Dashboard shows rankings updated each morning

---

## Phase 9 — Revenue & ROI Live Dashboard
**Goal:** Know exactly how much money is coming in, from what, from where.

- [ ] Stripe live: today's revenue, orders, avg order value, refunds
- [ ] ROAS by channel: revenue / ad spend per platform
- [ ] CPM live: Pinterest API, Meta Ads API, TikTok Ads API (when connected)
- [ ] Margin by product: cost (supplier) vs sell price (Stripe)
- [ ] Best combo live: what's making money right now

---

## Phase 10 — Full Automation Loop
**Goal:** System runs itself. Wake up to posts already live and orders already fulfilled.

- [ ] Daily cycle: `run_dropship_os.py` orchestrates everything
  1. Pull CPM data from all connected channels
  2. Run decision engine → update `metrics.json`
  3. Generate content for top-scored combos via Prometheus
  4. Push to calendar for next 7 days
  5. Auto-post anything scheduled for today
  6. Zendrop webhook: new orders auto-fulfilled
  7. Update dashboard with fresh data
- [ ] Windows Task Scheduler: runs `run_dropship_os.py` at 6am daily
- [ ] Alert system: Slack/email if score changes dramatically or order spikes

---

## API Keys — Full Shopping List
Go sign up for all of these. Free tiers first, upgrade when you hit limits.

| API | Service | Priority | Status |
|---|---|---|---|
| STRIPE_SECRET_KEY | Stripe | 🔴 1 — revenue | Connected via MCP |
| ANTHROPIC_API_KEY | Anthropic Claude | 🔴 1 — chat + Quinn | Needed in Vercel |
| QUINN_BRIDGE_SECRET | Quinn bridge auth | 🔴 1 — chat routing | Set |
| PINTEREST_ACCESS_TOKEN | Pinterest API | 🔴 2 — cheapest CPM | Get now |
| ZENDROP_API_KEY | Zendrop | 🔴 3 — fulfillment | Get now |
| META_ACCESS_TOKEN | Instagram/Meta | 🟡 4 — posting + CPM | Get now |
| ATLAS_CLOUD_API_KEY | Atlas Cloud (Seedance/Kling/Veo) | 🟡 4 — AI video gen | Get now |
| ELEVENLABS_API_KEY | ElevenLabs voiceover | 🟡 4 — voice | Get now |
| SUNO_API_KEY | Suno AI music | 🟡 4 — music | Get now ($30/mo) |
| HEYGEN_API_KEY | HeyGen avatar video | 🟡 5 — avatar | Get now ($99/mo) |
| GOOGLE_SEARCH_API_KEY | Google Custom Search | 🟡 5 — image search | Get now |
| GOOGLE_CSE_ID | Custom Search Engine ID | 🟡 5 — image search | With above |
| PEXELS_API_KEY | Pexels stock images | 🟢 5 — free | Get now (free) |
| UNSPLASH_ACCESS_KEY | Unsplash stock images | 🟢 5 — free | Get now (free) |
| GIPHY_API_KEY | Giphy funny GIFs | 🟢 5 — free | Get now (free) |
| REDDIT_CLIENT_ID | Reddit API | 🟢 5 — free | Get now (free) |
| REDDIT_CLIENT_SECRET | Reddit API | 🟢 5 — free | With above |
| TIKTOK_ACCESS_TOKEN | TikTok API | 🟡 6 — apply now | Apply TODAY (2 wk wait) |
| YOUTUBE_REFRESH_TOKEN | YouTube Data API | 🟡 6 — Shorts posting | Get now |
| TWITTER_BEARER_TOKEN | X/Twitter API v2 | 🟡 6 — threads | Get now |
| AUTODS_API_KEY | AutoDS products | 🟡 6 — product import | Get now |
| CJ_API_KEY | CJ Dropshipping | 🟡 7 — supplier | Get now |
| OPUS_CLIP_API_KEY | Opus Clip (interim only) | 🟡 interim | Get ($19/mo, cancel when Phase 5 done) |
| KLAVIYO_API_KEY | Email marketing | 🟢 8 — email channel | Get now (free tier) |
| RUNWAY_API_KEY | Runway Gen-4 (hero ads) | 🟢 8 — premium video | Get now |

---

## Build Queue — Agent Assignments

Each phase can run as a separate Claude Cowork session in parallel:

| Agent | Task | Phase |
|---|---|---|
| Agent 1 | `/api/metrics.js` + `/stats` Quinn route + `metrics.json` | Phase 1 |
| Agent 2 | Strip index.html fake data → live JS fetch | Phase 2 |
| Agent 3 | Strip roi/hormozi/ecom-king fake data | Phase 2 |
| Agent 4 | Product cards: supplier wizard + Push to Production | Phase 3 |
| Agent 5 | `/content` page UI: Pillar Builder + 4-step pipeline | Phase 4 |
| Agent 6 | Pillar Builder backend: listing scraper + image search ranker | Phase 4 |
| Agent 7 | FFmpeg + Whisper video pipeline (replace Opus Clip) | Phase 5 |
| Agent 8 | Seedance/Suno/ElevenLabs API integrations | Phase 5 |
| Agent 9 | Content calendar + auto-scheduler | Phase 6 |
| Agent 10 | Social distribution API connectors | Phase 7 |

---

## Live URLs
| Page | URL |
|---|---|
| Command Center | https://dropship-os-togetherwe-hobby.vercel.app |
| Playbook | https://dropship-os-togetherwe-hobby.vercel.app/playbook |
| Hormozi | https://dropship-os-togetherwe-hobby.vercel.app/hormozi |
| Ecom King | https://dropship-os-togetherwe-hobby.vercel.app/ecom-king |
| Pinterest | https://dropship-os-togetherwe-hobby.vercel.app/pinterest |
| ROI Agent | https://dropship-os-togetherwe-hobby.vercel.app/roi |
| Content Studio | https://dropship-os-togetherwe-hobby.vercel.app/content *(Phase 4)* |
