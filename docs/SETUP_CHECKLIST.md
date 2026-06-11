# Dropship OS — Setup Checklist
**Owner:** Alex Alexander | **Last updated:** 2026-04-22
**Site:** https://dropship-os-togetherwe-hobby.vercel.app

All 10 phases are built. This checklist walks you from zero to fully automated in order of ROI priority.

---

## Step 0 — Push All Code to Vercel (DO THIS FIRST)

The Linux sandbox cannot delete the `index.lock` file. You must do this on Windows:

```powershell
# Open PowerShell and paste:
cd "C:\Users\integ\Documents\Claude\Projects\Drop shipping\dropship-os"

# Delete the stale lock file
Remove-Item -Path ".git\index.lock" -ErrorAction SilentlyContinue

# Stage and push everything
git add -A
git commit -m "Phase 3-10: Revenue dashboard, Prometheus, Pinterest/TikTok auto-posting, scheduler"
git push origin main
```

Vercel auto-deploys on push. Takes ~60 seconds. Check: https://dropship-os-togetherwe-hobby.vercel.app

---

## Step 1 — Stripe (Priority 1 — Revenue)

1. Go to https://stripe.com → Sign up / Log in
2. Dashboard → Developers → API Keys
3. Copy your **Secret key** (starts with `sk_live_...` or `sk_test_...`)
4. Open `C:\Users\integ\Documents\Claude\Projects\Drop shipping\.env`
5. Add or update: `STRIPE_SECRET_KEY=sk_live_your_key_here`
6. Create a product + payment link in Stripe for your first product
7. Test: Dashboard → Products → Create → set price → Payment Links → share URL

**Verify:** Go to 💰 Revenue tab on your live site → Stripe dot turns green

---

## Step 2 — Pinterest API (Priority 2 — Cheapest Attention $0.28 CPM)

1. Go to https://developers.pinterest.com/apps/
2. Click **Create App** → Name: "DropshipOS"
3. Under Scopes, request: `boards:read`, `boards:write`, `pins:read`, `pins:write`
4. Generate access token → copy it
5. Add to `.env`: `PINTEREST_ACCESS_TOKEN=your_token_here`
6. Find your board ID:
   ```
   cd "C:\Users\integ\Documents\Claude\Projects\Drop shipping"
   python social_ai_agent/pinterest_poster.py --list-boards
   ```
7. Add to `.env`: `PINTEREST_BOARD_ID=your_board_id`
8. Test auto-post (dry run):
   ```
   python run_dropship_os.py --pinterest --dry-run
   ```

---

## Step 3 — Zendrop (Priority 3 — Fulfillment)

1. Go to https://zendrop.com → Sign up for Plus or Pro plan
2. Account Settings → API → Generate API key
3. Add to `.env`: `ZENDROP_API_KEY=your_key_here`

When an order comes in via Stripe, `run_dropship_os.py --monitor` auto-sends to Zendrop.

---

## Step 4 — TikTok API (Priority 4 — $0 CPM Viral)

**Note: ~2 week approval wait. Apply now, post manually in the meantime.**

1. Go to https://developers.tiktok.com/apps/
2. Click **Create App** → Name: "DropshipOS"
3. Request scopes: `video.publish`, `video.list`, `user.info.basic`
4. While waiting, post manually via https://tiktok.com/creator
5. When approved, run: `python social_ai_agent/tiktok_poster.py --setup`
6. Follow OAuth instructions → add to `.env`: `TIKTOK_ACCESS_TOKEN=your_token`

---

## Step 5 — Prometheus Engine (AI Video Pipeline)

Requires FFmpeg installed on Windows.

**Install FFmpeg:**
1. https://ffmpeg.org/download.html → Windows builds → extract to `C:\ffmpeg\`
2. Add `C:\ffmpeg\bin` to Windows PATH
3. Test: PowerShell → `ffmpeg -version`

**API Keys for full pipeline:**
```
ATLAS_API_KEY=your_key          # Seedance 2.0 video gen
ELEVENLABS_API_KEY=your_key     # Voiceover — $5/mo Starter
SUNO_API_KEY=your_key           # Music — $30/mo Pro
```

**Start the engine:**
```
Double-click: START_PROMETHEUS.bat
```

---

## Step 6 — Daily Automation (Windows Task Scheduler)

Run ONCE in PowerShell as Administrator:
```powershell
Set-ExecutionPolicy -ExecutionPolicy RemoteSigned -Scope CurrentUser
& "C:\Users\integ\Documents\Claude\Projects\Drop shipping\SCHEDULE_DAILY.ps1"
```

This schedules:
- **6:00 AM daily** → Decision Engine (scores all product × channel combos)
- **6:05 AM daily** → metrics.json → GitHub → Vercel auto-deploys
- **Monday 7:00 AM** → Full trend research cycle

---

## Step 7 — First Full Cycle (Manual Test Run)

```powershell
cd "C:\Users\integ\Documents\Claude\Projects\Drop shipping"

# Check all connections
python run_dropship_os.py --status

# Dry run preview
python run_dropship_os.py --full --dry-run

# Run for real
python run_dropship_os.py --full
```

---

## Revenue Flow

```
Pinterest/TikTok content (FREE organic)
    ↓  click
Landing page (GitHub Pages one-pager)
    ↓  buy button
Stripe payment link
    ↓  order confirmed
run_dropship_os.py --monitor (auto-detects)
    ↓
Zendrop API → fulfills + ships
    ↓
You keep: Sale price − supplier cost = MARGIN
```

**Decision rule (automated):**
- Score ≥ 70 for 2 weeks → double content volume
- Score < 30 for 2 weeks → kill that combo

---

## Current Build Status

| Component | Status | Action Needed |
|---|---|---|
| Vercel site (6 pages live) | ✅ Built | Push code (Step 0) |
| Decision Engine | ✅ Built | Run daily or via scheduler |
| Prometheus Studio UI (/content) | ✅ Live | — |
| Prometheus Engine (backend) | ✅ Built | START_PROMETHEUS.bat |
| Pinterest Auto-Poster | ✅ Built | Add PINTEREST_ACCESS_TOKEN |
| TikTok Auto-Poster | ✅ Built | Apply for API (~2 wk wait) |
| Revenue Dashboard (💰 tab) | ✅ Live | Add STRIPE_SECRET_KEY |
| Daily Scheduler | ✅ Built | Run SCHEDULE_DAILY.ps1 as Admin |
| Full Automation Loop | ✅ Built | python run_dropship_os.py --full |
| Stripe | ⚠️ Key needed | Step 1 |
| Pinterest OAuth | ⚠️ Token needed | Step 2 |
| Zendrop | ⚠️ Key needed | Step 3 |
| TikTok | ⚠️ Apply now | Step 4 (~2 wk) |
| FFmpeg | ⚠️ Install | Step 5 |
| Atlas/ElevenLabs/Suno | ⚠️ Keys needed | Step 5 |

---

## .env Template (save as project root `.env`)

```
# C:\Users\integ\Documents\Claude\Projects\Drop shipping\.env

# REQUIRED
ANTHROPIC_API_KEY=sk-ant-...
STRIPE_SECRET_KEY=sk_live_...
PINTEREST_ACCESS_TOKEN=...
PINTEREST_BOARD_ID=...
ZENDROP_API_KEY=...

# VIDEO PIPELINE
ATLAS_API_KEY=...
ELEVENLABS_API_KEY=...
SUNO_API_KEY=...

# PHASE 2+
META_ACCESS_TOKEN=...
TIKTOK_ACCESS_TOKEN=...
TIKTOK_CLIENT_KEY=...
TIKTOK_CLIENT_SECRET=...
YOUTUBE_REFRESH_TOKEN=...
GITHUB_TOKEN=...

# LANDING PAGE
LANDING_PAGE_URL=https://linktr.ee/dropshipos

# VERCEL (set in Vercel dashboard, not here)
# QUINN_ENDPOINT=https://your-ngrok-url.ngrok.io
# QUINN_BRIDGE_SECRET=dropship-os-quinn-2026-alex
```
