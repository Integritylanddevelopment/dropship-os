# ShipStack AI — Handoff to Next Session
**Date:** 2026-05-08
**Owner:** Alex Alexander (integritylanddevelopment@gmail.com)

---

## ✅ COMPLETED (as of 2026-05-08)

### YouTube API — DONE ✅
- **Client ID:** `398437665708-ouu0feesb1qgenphjun7c0ubb34ra7fc.apps.googleusercontent.com`
- **Client Secret:** `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`
- **Refresh Token:** `1//04qnl8cdr-tMACgYIARAAGAQSNwF-L9IrP4KvLRyOQWdCJC2QasHt-GoUYjUK60ZlzWtlHLdu_H7o0YyTa6Sv0fMLMFcRSGaAWns`
- Saved to `.env` + pushed to Vercel production (all 3 vars, HTTP 201) ✅
- Vercel redeployed and READY ✅
- GCP Project: `primal-device-495102-h1` | OAuth Client: `398437665708-ouu0feesb1qgenphjun7c0ubb34ra7fc`
- Test user `integritylanddevelopment@gmail.com` added to Google Auth Platform audience ✅

### Pinterest Developer App — DONE ✅
- **App ID:** `1566204` | **Access Token:** in `.env`
- Trial access was pending as of 2026-04-29

### Stripe — DONE ✅
- Keys in `.env`

---

## 🔜 PENDING (in order of priority)

### 1. Quinn Bridge + ngrok (LOCAL — must run on your PC)
- **One command to paste in PowerShell:**
  ```
  winget install --id Gyan.FFmpeg --accept-package-agreements --accept-source-agreements; & "C:\Users\integ\Documents\Claude\Projects\Drop shipping\START_QUINN_TUNNEL.bat"
  ```
- Installs FFmpeg, then starts Quinn bridge on port 8765 + opens ngrok tunnel
- When ngrok shows the `https://` URL → paste it in chat → Claude pushes it to Vercel as `QUINN_ENDPOINT`

### 2. TikTok Access Token — SCHEDULED CHECK RUNNING ✅
- **NOTE:** A daily scheduled check is already running to monitor approval status
- Scope requested: `video.publish` — approval takes ~2 weeks from application date
- **Client Key:** `aw4sop8857ntgwi2` | **Client Secret:** `rNfkn1jvEC1EARjjV83lDyiha3n35XY4` (both in `.env`)
- When approved: log into developers.tiktok.com → ping Claude → complete OAuth → get `TIKTOK_ACCESS_TOKEN`

### 3. Meta / Instagram
- Go to: https://developers.facebook.com/apps/ → log in
- Ping Claude once logged in — will complete full setup:
  `META_ACCESS_TOKEN`, `META_APP_ID`, `META_APP_SECRET`, `META_IG_ACCOUNT_ID`, `META_PAGE_ID`

### 4. Prometheus Engine (AI Video Pipeline)
- FFmpeg install is step 1 of the PowerShell command above
- After Quinn is running: double-click `START_PROMETHEUS.bat`
- Needs: `ELEVENLABS_API_KEY` ✅ (already in `.env`) | `RUNWAY_API_KEY` ✅ | `HEYGEN_API_KEY` ✅

### 5. GCP Secret Cleanup (low priority)
- Old secret `****hM-G` on YouTube OAuth client — value unknown
- Once YouTube posting is confirmed working, disable it in Google Cloud Console → OAuth 2.0 Client Credentials

---

## ARCHITECTURE

```
Content → Prometheus Engine (8766) ← Quinn Bridge (8765) ← Vercel
              ↓
    YouTube / TikTok / Pinterest / Meta auto-post
              ↓
    Traffic → Vercel landing page → Stripe checkout → Zendrop ships
```

**Live site:** https://dropship-os-hazel.vercel.app
**Vercel project:** `prj_n2WcwKIhw3eagVoSeqHeyHyH7TZL` | team: `team_qd9zTuDQ41euDNXJwHVVPocq`
**GitHub:** github.com/Integritylanddevelopment/dropship-os
**Deploy:** GitHub push only (never use deploy_to_vercel MCP)

---

## LOCAL STACK
- Qdrant: http://127.0.0.1:6333
- Ollama: http://127.0.0.1:11434 (model: qwen2.5:7b)
- Quinn Bridge: `START_QUINN_TUNNEL.bat` → ngrok port 8765
- Prometheus Engine: `START_PROMETHEUS.bat` → port 8766

---

## .ENV STATUS
| Key | Status |
|-----|--------|
| STRIPE_SECRET_KEY | ✅ Set |
| STRIPE_PUBLISHABLE_KEY | ✅ Set |
| YOUTUBE_CLIENT_ID | ✅ Set |
| YOUTUBE_CLIENT_SECRET | ✅ Set |
| YOUTUBE_REFRESH_TOKEN | ✅ Set |
| PINTEREST_ACCESS_TOKEN | ✅ Set |
| PINTEREST_APP_ID | ✅ 1566204 |
| TIKTOK_CLIENT_KEY | ✅ Set |
| TIKTOK_CLIENT_SECRET | ✅ Set |
| TIKTOK_ACCESS_TOKEN | ⏳ Awaiting scope approval (daily check scheduled) |
| ELEVENLABS_API_KEY | ✅ Set |
| RUNWAY_API_KEY | ✅ Set |
| HEYGEN_API_KEY | ✅ Set |
| ZENDROP_API_KEY | ✅ Set |
| NGROK_AUTHTOKEN | ✅ Set |
| VERCEL_TOKEN | ✅ Set |
| META_ACCESS_TOKEN | ❌ Pending login |
| META_APP_ID | ❌ Pending login |
| META_APP_SECRET | ❌ Pending login |
| META_IG_ACCOUNT_ID | ❌ Pending login |
| META_PAGE_ID | ❌ Pending login |
| QUINN_ENDPOINT | ❌ Set after Quinn tunnel starts |

---

## CLAUDE RULES
1. Search `dropship_intel` for dropshipping questions
2. `strategy_books` = out of scope, ignore it
3. Deploy = GitHub push only
4. Quinn bridge + ngrok must be running for live chat on deployed pages
5. Vercel env updates → use JavaScript fetch from Chrome with VERCEL_TOKEN (bash sandbox has no outbound network)
