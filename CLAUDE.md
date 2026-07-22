# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Critical Boundary

**This is the ShipStack project.** Do not read, write, or touch any file in `C:\Users\integ\quinn-proxy\`. Quinn's `.env` contains the Anthropic API key -- ShipStack has no key of its own. All LLM calls go through the Quinn HTTP bridge at `http://127.0.0.1:8765/v1/chat/completions`. Never call Anthropic directly, never import `anthropic`, never set `ANTHROPIC_API_KEY` in ShipStack code. `grep -r "api.anthropic.com\|ANTHROPIC_API_KEY" .` must return zero results.

If ShipStack needs something Quinn doesn't do, write `HANDOFF_TO_QUINN_<YYYY-MM-DD>_<TOPIC>.md` in `ShipStack/handoffs/` and wait for Alex's approval.

## Commands

### Launch all services
```powershell
.\scripts\LAUNCH_SHIPSTACK.ps1
```
Kills stale processes on ports 8889/8766/8867/8890, then starts all 4 Python services.

### Start individual services
```powershell
python engines/shipstack_engine.py       # :8889
python engines/prometheus_engine.py      # :8766
python agents/social_ai_agent.py         # :8867
python engines/shipstack_dashboard.py    # :8890
```

### Run tests
```bash
python tests/test_integration.py         # 7 unit test suites (badge, health, scoring, research, analytics, auth, leak audit)
python tests/test_mvp_pipeline.py        # 10 E2E smoke tests (services, discovery, scoring, posting, leak audit)
python tests/verify_stack.py             # quick service health check
```
No pytest -- uses Python unittest and custom test runners.

### Frontend dev server (Vercel local)
```bash
npx serve . --listen 3000 --no-clipboard
```

### Node backend
```bash
npm start          # node server.js
npm run dev        # nodemon server.js
```

### Deploy
```powershell
.\scripts\DEPLOY.ps1
.\scripts\PUSH_SHIPSTACK_TO_GITHUB.ps1
python scripts/set_vercel_envs.py
```

### Environment setup
Copy `.env.example` to `.env` and fill in API keys. Local overrides go in `.env.local`. Both are git-ignored.

## Architecture

ShipStack is a dropshipping discovery and automation platform with a dual-stack architecture:

**Python/Flask microservices** (the primary runtime):
- `engines/shipstack.py` (21KB) + `engines/shipstack_engine.py` -- main engine on :8889, product scoring and research APIs
- `engines/prometheus_engine.py` -- video production on :8766 (ffmpeg, edge_tts, pexels, pixabay). Max 3 concurrent jobs, state in `engines/prometheus_state/jobs.json`. Library code in `engines/prometheus_lib/`
- `agents/social_ai_agent.py` -- social media orchestration on :8867 (TikTok, Instagram, Pinterest, YouTube)
- `engines/shipstack_dashboard.py` -- monitoring dashboard on :8890
- `dashboard/pipeline_dashboard.py` (27KB) -- pipeline dashboard on :8891

**Node.js/Express + Vercel serverless** (frontend + API layer):
- `api/*.js` -- ES module serverless functions deployed to Vercel (`dropship-os-gamma.vercel.app`)
- `api/_quinnRouter.js` -- Quinn-first LLM router: tries Quinn bridge, falls back to Anthropic
- `api/_config.js` -- shared env config
- `api/engine.js` -- product scoring + channel recommendations
- `frontend/index.html` (154KB) -- main landing page, static HTML
- Routing defined in `vercel.json`

**Pipeline glue** (`engines/pipeline_glue.py`): Orchestrates the full MVP loop -- discover products, score them, generate content (image cards + video), post to social platforms. CLI: `python engines/pipeline_glue.py --query "..." --limit 5 --post`

**LLM routing pattern:** All AI calls go to Quinn HTTP bridge at `http://127.0.0.1:8765`, which routes to Ollama (local models) or Anthropic (fallback). The `api/_quinnRouter.js` and `api/_fallbackController.js` handle this chain for the JS layer.

**Authentication:** Badge protocol via `badge/shipstack_badge.py` -- one-shot SHA256 tokens with 60-second TTL. Every tool call gets a fresh badge, then logs via `badge/shipstack_log_action.py` to `logs/shipstack_actions.jsonl` (JSONL format).

**Data stores:**
- SQLite at `agents/data/products.db` -- product cache with 24-hour TTL
- Qdrant collections: `dropship_intel`, `project_ship_stack_ai` -- managed by Quinn
- JSONL action log: `logs/shipstack_actions.jsonl`
- Job state: `engines/prometheus_state/jobs.json`

**Key internal agents** (no HTTP ports, called by the engines):
- `agents/decision_engine.py` -- product scoring (cost/margin, niche, competition, reviews)
- `agents/product_research.py` -- supplier aggregation (Zendrop live, AutoDS gated, AliExpress scraper). SQLite cache with 24-hour TTL
- `agents/analytics_engine.py` -- KPI computation from action logs
- `agents/product_onboarding_agent.py` (46KB) -- product onboarding workflow
- `agents/db.py` (41KB) -- SQLite operations

**Integrations** (`integrations/`): `aliexpress_connector.py`, `supplier_connector.py`, `social_poster.py`, `stripe_checkout.py`, plus JS scrapers `amazon-api.js` and `tiktok-shopify-scraper.js`.

**Social AI** (`social_ai_agent/`): Full automation tree with `main.py`, platform-specific posters (`pinterest_poster.py`, `tiktok_poster.py`), scheduler, content generation, and research modules. The Flask service on :8867 wraps these into HTTP endpoints (`/post/pinterest`, `/post/youtube`, `/post/tiktok`, `/post/auto`, `/generate-card`).

**Discovery Engine** (`discovery_engine/`): Product discovery pipeline with `pipeline.py`, `cli.py`, scoring and signals subsystems. Scrapes Reddit, YouTube, Etsy, Pinterest, Amazon -- no API keys needed.

**Platform credential status:** Pinterest (ready -- token + board ID set), YouTube (ready -- all OAuth creds set), TikTok (needs OAuth token -- run `python scripts/tiktok_oauth.py`), Meta/Instagram (not configured).

## Port Registry

| Port | Service | Owner |
|------|---------|-------|
| 3000 | Vercel frontend | Vercel |
| 8765 | Quinn HTTP bridge | Quinn (do not bind) |
| 8766 | Prometheus Engine | ShipStack |
| 8867 | Social AI Agent | ShipStack |
| 8889 | ShipStack Engine | ShipStack |
| 8890 | ShipStack Dashboard | ShipStack |
| 8891 | Pipeline Dashboard | ShipStack |

## Project Rules

1. **Quinn-only LLM access.** All inference through `http://127.0.0.1:8765`. No direct Anthropic calls.
2. **Lane enforcement.** All files stay under this project directory. Writes outside refuse with path validation error.
3. **Badge per tool call.** Call `shipstack_badge()` before each tool use, `shipstack_log_action()` after.
4. **HTTP, not MCP.** ShipStack exposes HTTP routes. Quinn is the MCP server.
5. **Kill before launch.** Before binding a port, kill anything stale on it: `netstat -ano | find ":PORT"` then kill PID.
6. **No scheduled tasks.** Never use `Register-ScheduledTask` or `schtasks.exe /create`. Add to `LAUNCH_SHIPSTACK.ps1` instead.
7. **UTF-8 everywhere.** First line of every Python script: `import sys; sys.stdout.reconfigure(encoding='utf-8', errors='replace')`.
8. **No secrets in code.** Patterns `sk-ant-`, `sk_live_`, `ghp_` etc. in source files cause write refusal. Only `.env`/`.env.local` are exempt (git-ignored).
9. **Handoff protocol.** Quinn to ShipStack to Quinn. Write `HANDOFF_TO_QUINN_<YYYY-MM-DD>_<TOPIC>.md` in `handoffs/`. Never initiate `HANDOFF_FROM_SHIPSTACK_*`.

## Naming Conventions

- Top-level docs: `UPPER_SNAKE_CASE.md`
- Handoffs: `HANDOFF_<DIRECTION>_<YYYY-MM-DD>[_<TOPIC>].md`
- Python modules: `lower_snake_case.py`
- PowerShell scripts: `UPPER_SNAKE_CASE.ps1`
- Dates: ISO-8601 only (`2026-06-03`), never `JUNE_03`

## Session Startup Ritual

1. Confirm working directory is ShipStack (not quinn-proxy)
2. Confirm Quinn bridge is reachable at :8765
3. Read this CLAUDE.md
4. Read `memory/working/current_goal.md` for current mission state
5. Restate goal/state/next action/blockers to Alex before starting work

## Known Gaps

- TikTok OAuth token not yet obtained -- run `python scripts/tiktok_oauth.py` to complete the flow
- Meta/Instagram API credentials empty -- not configured for MVP
- AutoDS supplier API gated (returns [] gracefully) -- no API key available
- Vercel serverless functions can't reach local Python services without an ngrok/Cloudflare tunnel -- falls back to static data in production

## Do Not Recreate

- Quinn-owned files (seed_strategy_books.py, sync_cowork_sessions.py, quinn_fs_interceptor.py, verify_qdrant_partitions.py, ingest_now.py)
- Scheduled task scripts (SCHEDULE_DAILY.ps1, SCHEDULE_CALENDAR.ps1)
- MCP server attempt (shipstack_mcp.py)
- Direct Claude Code modifications (disable_claude_code.ps1 and variants)

## Tech Stack

- **Backend:** Python 3 (Flask), Node.js 18+ (Express, ES modules)
- **Frontend:** Static HTML, deployed via Vercel
- **LLM:** Quinn bridge to Ollama (qwen2.5:7b) with Anthropic fallback
- **Database:** SQLite (product cache), Qdrant (vector search)
- **Video:** ffmpeg, edge_tts, Pexels/Pixabay APIs, Runway ML, ElevenLabs
- **Deployment:** Vercel (frontend/API), PowerShell launchers (local services)
- **Package managers:** npm (Node deps), pip (Python deps via requirements.txt)

## Mission Control (added 2026-07-21)

One-button UI at **http://127.0.0.1:8889/** (served by shipstack_engine.py). Desktop shortcut: "ShipStack Mission Control.lnk" → LAUNCH_MISSION_CONTROL.pyw (kills stale ports, starts engine+social+prometheus locally, opens browser). Backend: `engines/mission_pipeline.py` background thread; routes `/api/pipeline/start`, `/api/pipeline/status`, `/api/services`, `/cards/<file>`. Stages: services → discover → pick → content → host → post. UI runs use `fast=True` discovery (Reddit+Trends only, ~90-110s). Card images pushed to public GitHub repo via `integrations/github_image_host.py` → raw.githubusercontent.com URLs for Pinterest.

**Blockers needing Alex's accounts (code cannot fix):**
- Pinterest app is TRIAL tier → API error code 29 blocks production pins. Request Standard access at developers.pinterest.com/apps.
- Reddit blocks unauthenticated JSON (403) and Pullpush data is frozen ~2023 → need Reddit OAuth app for live trend signals.
- TikTok OAuth incomplete; Meta/Instagram credentials empty.

## Retail Pipeline (added 2026-07-21, evening)

Content stage now produces BUYER-facing ads, not internal scorecards. Flow per winner: CJ supplier match (photo + true cost) → margin_calc retail pricing (.99) → `social_ai_agent/retail_ad_card.py` (photo hero, benefit line, price + SAVE pill, SHOP NOW) → `integrations/landing_pages.py` creates Stripe payment link (REST, no SDK) + one-pager on GitHub Pages (integritylanddevelopment.github.io/dropship-os/landing/<id>.html) → pin links to the store page. Product title = cleaned supplier listing title. Old scorecard generator (pinterest_poster.generate_product_card) left intact but no longer used by Mission Control. Winners deduped by product_id. NEVER put scores/margins on buyer-facing content.

## Marketing Collateral Engine (added 2026-07-21, night)

`asset_machine/collateral_engine.py` — turns gathered internet data (product, photos, buyer quotes, signals) into 10 ORIGINAL graded ad cards per product, all pointing at that product's ONE sales page. Built on the stored advisor workbook (`agents/advisors/garyvee.json`, `hormozi.json`, `kamil.json`).

- 10 copy archetypes from the playbooks (hormozi_dream/offer/stop/secret, kamil_pov/tested/viral, garyvee_hot/question, proof_direct)
- AI chain: Quinn bridge → **ALIEN GPU Ollama (100.66.135.31:11434, qwen2.5:7b)** → local Ollama → formula fallback. ALIEN is the standing copy generator per Alex's order.
- **Hormozi Grader** with custom weights: offer_strength .30, emotional .20, problem_solution .20, cta_clarity .15, logical .15. Grades 0-100 + letter. Weak offers auto-improved (add guarantee, price anchor) then re-graded. AI rewrites only ship if they OUT-GRADE the formula version AND are ≥5 words (small models over-compress into caveman grammar otherwise).
- 5 rotating visual layouts × 5 palettes = ads look like different creatives (Kamil multi-angle testing).
- Pipeline posts the top-3 graded ads per product per run (anti-spam), all → same landing page.

## Business Identity (added 2026-07-22)

- **Main website domain:** integrityproductsusa.com — THE home of the public site. Attached to Vercel project prj_uFSUtfgA5yC8puLDMzAZig8Ik30a (+ www).
- **Vercel: PRO side ONLY.** Everything deploys on the Pro team (team_qd9zTuDQ41euDNXJwHVVPocq). Nothing lives on hobby accounts — retire/ignore any *-hobby.vercel.app deployments.
- **Deploy workflow:** push to GitHub → Vercel auto-deploys. Site repo: integrity-products-site (GitHub, Integritylanddevelopment).
- **Public business name:** Integrity Products USA (Stripe checkout + statement descriptor INTEGRITY PRODUCTS)
- **Public business phone:** 945-312-6709 — use this on ALL websites, listings, policies, and public content. NEVER publish the 808 number anywhere public.
- **Support email (planned):** support@ the new domain (GoDaddy purchase in progress)
- Legal pages (privacy policy, terms of service, legal footer) hosted with the landing pages; Stripe public details must point at them.

## Orders + Auto-Fulfillment (added 2026-07-21, late night)

`integrations/order_fulfillment.py` — the last mile. Engine background loop polls Stripe checkout sessions every 5 min; each PAID session becomes an order in `data/orders.json`, matched to the library product, then AUTO-ordered at CJ (buyer's address, CJPacket) via `shopping/order/createOrder`. Money-safety fuse → NEEDS REVIEW instead of auto-order when: multi-variant price spread >20%, CJ cost > FULFILL_MAX_COST ($30 default), no phone, or no confident CJ match. Orders panel in Mission Control: status chips (NEW/ORDERED/SHIPPED/NEEDS YOUR OK), one-click "Ship it", tracking numbers auto-pulled. New payment links collect buyer phone (CJ needs it); SHIPSTACK_FULFILL_PHONE in .env is the fallback for old links. `cj_pid` now saved per product for exact supplier matching. AUTO_FULFILL=0 in .env disables auto mode.

## CREATIVE SOLUTION LOG - 2026-07-21 (Mission Control session)
- Pinterest fake-success bug: API errors return {"code":29,"message":...} with HTTP 200 path through poster; social agent checked only for "error" key. Rule: a real pin ALWAYS has "id" — no id = failure. Fixed in agents/social_ai_agent.py + engines/mission_pipeline.py.
- Pullpush.io (Pushshift mirror) data frozen ~2023 (421+ day old posts). trend_velocity falls back to engagement-based scoring (avg score/comments, capped 0.4) when no signal is <14d old.
- Pinterest needs PUBLIC image URLs: upload cards via GitHub Contents API (PUT /repos/{u}/{r}/contents/...) to the public dropship-os repo; raw.githubusercontent.com URL is instantly fetchable.
- Junk cluster keywords ("Wrong", "Tried Bunch"): _is_valid_keyword() in clusterer.py requires bigram OR known PRODUCT_TERM OR ≥5-char token appearing in ≥2 titles; KEYWORD_JUNK blocklist kills platform words.
- Query-scoped discovery: when the UI gets a niche query, skip generic subreddits entirely and search only query variants — stops "Tickle Toes" polluting "pet accessories" runs.
- Quinn PS calls that take >~8s often return MCP timeout even though the command RAN. Pattern: fire Start-Process (it launches despite the timeout), then verify with a short follow-up call instead of retrying the launch.

## CREATIVE SOLUTION LOG - 2026-07-12 (Dockerization session)
- ALIEN worker (quinn_worker_exec) returned fabricated file-write receipts; nothing executed. Interim rule: worker_exec = text drafting only; ALL execution via quinn_run_powershell + PSRemote to ALIEN with disk verification afterward.
- Docker Desktop credential helper (docker-credential-desktop) fails in non-interactive PSRemote sessions ('logon session does not exist'). Workaround: build FROM locally cached python:3.12-slim with DOCKER_BUILDKIT=0; never rely on registry pulls from remote sessions.
- Set-Content -Encoding UTF8 writes a BOM that breaks Dockerfiles; write files with [System.IO.File]::WriteAllText + UTF8Encoding(false).
- Context Injector had been down since 2026-06-24: BOM in config.json crashed injector.py json.load at boot. Fixed with encoding='utf-8-sig'.
- Flask/socketserver services must bind 0.0.0.0 inside containers (mapped ports refuse external connections on 127.0.0.1 binds).
