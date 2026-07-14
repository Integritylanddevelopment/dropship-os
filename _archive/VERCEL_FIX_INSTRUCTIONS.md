# Vercel Build Fix — Manual Push Required

## Problem
Deployment dpl_HYYR4xuPXCoZanJUJTU2i85DkfPw failed because vercel.json was misconfigured.
- Old: only `rewrites` array (incorrect for Vercel)
- New: proper `functions` config + `routes` array (correct)

## What Changed
File: `dropship-os/vercel.json`

**Old (broken):**
```json
{
  "devCommand": "...",
  "rewrites": [...]
}
```

**New (correct):**
```json
{
  "devCommand": "npx serve . --listen 3000 --no-clipboard",
  "functions": {
    "api/**/*.js": {
      "memory": 512,
      "maxDuration": 60
    }
  },
  "routes": [
    { "src": "^/api/(.*)", "dest": "/api/$1" },
    ... (all static HTML routes)
    { "src": "^/(.*)$", "dest": "/index.html" }
  ]
}
```

## Why This Fixes It
- **functions**: Tells Vercel which files are serverless functions and their config
- **routes**: Regex-based routing that properly maps API requests + static files + SPA fallback
- Removed old `rewrites` (Vercel deprecated format)

## Manual Push Steps
1. Open Terminal in dropship-os/ directory
2. Run:
   ```bash
   git add vercel.json
   git commit -m "Fix: vercel.json — add functions config and routes for serverless API + static HTML"
   git push origin main
   ```
3. Vercel will auto-deploy. Next build should succeed.

## Files Affected
- `dropship-os/vercel.json` ✓ Updated locally, pending push

## Status After Push
- All API endpoints: `/api/chat`, `/api/discover`, `/api/discover-deepdive`, `/api/engine`, `/api/prometheus`, `/api/health`, `/api/webhook`, `/api/supplier`, `/api/search`, `/api/metrics`
- All HTML pages: `/`, `/playbook`, `/hormozi`, `/ecom-king`, `/pinterest`, `/roi`, `/content`, `/privacy`, `/store`, `/thank-you` + 5 product pages
- SPA fallback: Unknown routes → `/index.html`
