# ShipStack AI — Dispatch Status Log

---
**[2026-06-01] AutoDS Status Check**
- API Key present: NO
- API reachable: SKIPPED (no key)
- Status: 🔴 OFFLINE — AutoDS API key not configured. Add AUTODS_API_KEY to .env at https://app.autods.com/settings, then rerun.

---
**[2026-06-01] TikTok Shop Status Check**
- Client Key present: YES (aw4sop8857ntgwi2)
- Access Token present: NO (empty value in .env line 44)
- Shop authorized: NOT_CHECKED (no access token to verify)
- Status: 🔴 PENDING — TikTok Shop seller account awaiting approval. 
  * Visit https://seller-us.tiktok.com to check approval status
  * Once approved, complete OAuth at: https://auth.tiktok.com/v2/auth?client_key=aw4sop8857ntgwi2&scope=video.publish&response_type=code&redirect_uri=https://dropship-os-gamma.vercel.app/api/tiktok-callback
  * Then copy the access token to TIKTOK_ACCESS_TOKEN in .env and Vercel dashboard
  * See timeline: Application pending ~2 weeks for video.publish scope approval

**Action required:** Check seller account status at seller-us.tiktok.com. Once approved, complete OAuth flow and update .env + Vercel.

---
