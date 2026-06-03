# ShipStack AI — Agent Handoff
**Date:** 2026-05-20
**Handoff from:** Session 2 (Stripe webhook deploy + Quinn launcher work)
**Handoff to:** Next agent — finish Quinn wiring, Zendrop product map, DB migration

> **GROUND RULE — DATABASE IS SOURCE OF TRUTH.**
> All state, config, product map, env, vectors, and operational data live in the DB (Qdrant + Supabase/Postgres). Files are **backups/exports only**. Stop writing logic that reads from JSON/MD files. If you find file-based reads in code, port them to DB calls.

---

## Current live state

- **URL:** https://dropship-os-hazel.vercel.app
- **Repo:** github.com/Integritylanddevelopment/dropship-os
- **Vercel project:** shipstack-ai (prj_uFSUtfgA5yC8puLDMzAZig8Ik30a), team: TogetherWe-pro
- **Stripe:** 5 live payment links created (mirrored in DB; `data/stripe_links.json` is backup only)
- **Revenue:** $0 (store live, no traffic yet)

---

## ✅ COMPLETED THIS SESSION

| Item | Status | Notes |
|---|---|---|
| `api/stripe-webhook.js` written + deployed | ✅ DONE | Live at `https://dropship-os-hazel.vercel.app/api/stripe-webhook`. Pushed via GitHub REST API (status 201). Vercel auto-deployed. |
| Webhook handles `checkout.session.completed` | ✅ DONE | Verifies signature, extracts customer/address/items, routes to Zendrop. Skips suppliers flagged `aliexpress` and logs them for manual handling (Ab Roller Wheel). |
| Desktop launcher bat | ✅ DONE | `LAUNCH QUINN + SHIPSTACK.bat` on desktop. Launches Quinn Command Center (`quinn_live_dashboard.py` at localhost:8888) AND opens ShipStack dashboard. Two separate systems. |
| `SETUP_ALL.ps1` (one-shot env setup) | ✅ DONE | Fixed `&` parser bug, hashtable for Stripe body, skips bridge if already running. |
| Quinn bridge confirmed running | ✅ DONE | Visible in user's taskbar |

---

## ⏳ IN PROGRESS / BLOCKED ON USER

### Quinn Bridge → Vercel wiring
- Quinn bridge: ✅ running on port 8765
- ngrok tunnel: ⏳ user needs to run `ngrok http 8765` (or use `LAUNCH QUINN + SHIPSTACK.bat` which does it automatically)
- `QUINN_ENDPOINT` Vercel env var: ⏳ not yet set — bat file will auto-push it once ngrok URL is captured
- Qdrant indexing: ⏳ 0 vectors — needs decision engine run or manual seed

### Stripe webhook activation (3 user steps left)
1. Stripe dashboard → Webhooks → Add endpoint
   - URL: `https://dropship-os-hazel.vercel.app/api/stripe-webhook`
   - Event: `checkout.session.completed`
   - Copy `whsec_...` signing secret
2. Vercel → Env vars → add `STRIPE_WEBHOOK_SECRET`
3. Get Zendrop product IDs from `app.zendrop.com/products` → load into DB `product_map` table (NOT into the file)

---

## 🔴 NEW PRIORITY — Migrate file-based state to DB

User directive: stop working from files. Everything operational must live in the DB.

Audit & migrate these file reads to DB:
- `data/stripe_links.json` → `stripe_links` table (product_name, stripe_link_id, price, zendrop_product_id, supplier)
- `PRODUCT_MAP` constant inside `api/stripe-webhook.js` → query `product_map` table at runtime
- `DISPATCH_STATUS.md` appends from scheduled tasks → `dispatch_status` table (timestamp, source, status, message)
- `.env` values that change (QUINN_ENDPOINT, ngrok URL) → keep in Vercel env, but mirror current ngrok URL into a `runtime_config` table for observability
- Any other JSON/MD reads in `dropship-os/api/*.js`

Files remain on disk as **read-only backups/exports** — never the source of truth.

---

## PRIORITY 1 — Finish Quinn Bridge + Qdrant

1. User runs `LAUNCH QUINN + SHIPSTACK.bat` (handles bridge + ngrok + Vercel env push)
2. Verify `QUINN_ENDPOINT` is live in Vercel
3. Run decision engine to seed Qdrant with product vectors
4. Test dashboard chat → confirm memory responses with context
5. Verify Quinn Command Center at `localhost:8888` shows bridge/Qdrant/Ollama/watchdog/health-agent all green

---

## PRIORITY 2 — Activate Stripe → Zendrop

1. User completes 3 Stripe activation steps above
2. Populate `product_map` DB table with Zendrop product IDs
3. Refactor `api/stripe-webhook.js` to query DB instead of hardcoded `PRODUCT_MAP`
4. Test with Stripe CLI: `stripe trigger checkout.session.completed`
5. Confirm Zendrop receives the order

---

## 🚫 BLOCKED — Do not work on

| Item | Reason |
|---|---|
| AutoDS API key | TikTok Shop seller account not approved. Daily check scheduled. |
| AliExpress | Out of scope. Webhook skips and logs for manual handling. |
| TikTok access token | Pending OAuth approval (~2 weeks) |

---

## Scheduled tasks (running)

- **autods-status-check** — daily 9AM (writes to DB `dispatch_status` table going forward, currently appends to DISPATCH_STATUS.md — needs migration)
- **tiktok-shop-status-check** — daily 9AM (same migration needed)

---

## Key credentials

| Key | Status |
|---|---|
| STRIPE_SECRET_KEY | ✅ Live in Vercel |
| ANTHROPIC_API_KEY | ✅ Live in Vercel |
| ZENDROP_API_KEY | ✅ Set in Vercel |
| GITHUB_TOKEN | ✅ Present |
| STRIPE_WEBHOOK_SECRET | ⏳ Needs user to add after registering endpoint |
| QUINN_ENDPOINT | ⏳ Auto-set by bat file once ngrok runs |
| AUTODS_API_KEY | ❌ Blocked |
| TIKTOK_ACCESS_TOKEN | ❌ Pending |

---

## Quinn Command Center (separate from ShipStack)

- **File:** `quinn_live_dashboard.py` at localhost:8888
- **Purpose:** Infrastructure monitor — Qdrant, Ollama, Quinn bridge stats, watchdog, health agent
- **DO NOT confuse with ShipStack** (Vercel business dashboard at dropship-os-hazel.vercel.app)
- Health Agent (separate chat) is actively refactoring this file — do not edit it from here without coordinating

---

## Deployment method (CLI times out — use this)

Git/Vercel CLI both timeout via MCP. Push via GitHub REST API in browser console:

```js
fetch('https://api.github.com/repos/Integritylanddevelopment/dropship-os/contents/FILE', {
  method: 'PUT',
  headers: { 'Authorization': 'Bearer GITHUB_TOKEN', 'Content-Type': 'application/json' },
  body: JSON.stringify({ message: 'msg', content: btoa(content), sha: 'CURRENT_SHA' })
})
```

Vercel auto-deploys on push.

---

## Where we stand — one-line summary

Stripe webhook is **deployed and live**, waiting on 3 user clicks to activate. Quinn bridge is **running locally**, waiting on ngrok + Vercel env push (one bat file does both). Next big lift: **migrate all file-based state to DB tables** so the system stops depending on JSON/MD files for runtime decisions.
