# ShipStack Codebase Audit Report

**Date:** 2026-07-10
**Auditor:** EAGLE
**Scope:** Full directory structure, imports, routes, duplicates, archives

---

## 1. Broken Imports

### api/discover.js (CRITICAL)
- Line 12: `import { EbayAPI, AliexpressAPI, ... } from '../integrations/stub-apis.js'`
  - **stub-apis.js does NOT exist** in integrations/. Missing entirely.
- Line 13: `import { DecisionEngine } from '../decision-engine/decision-engine.js'`
  - decision-engine/ was moved to `_archived/decision-engine-js/`. Import path broken.
- **Impact:** /api/discover endpoint crashes on cold start. This is the product discovery MVP entry point.
- **Fix:** Restore stub-apis.js or rewrite discover.js to use Python discovery_engine/ pipeline.

---

## 2. Vercel Route Gaps

### API files with NO route in vercel.json:
| API File | Route Needed | Status |
|----------|-------------|--------|
| api/discover.js | /api/discover | MISSING |
| api/discover-deepdive.js | /api/discover-deepdive | MISSING |
| api/chat.js | /api/chat | MISSING |
| api/search.js | /api/search | MISSING |
| api/metrics.js | /api/metrics | MISSING |
| api/prometheus.js | /api/prometheus | MISSING |

### HTML routes pointing to _archive/ (will 404):
- /store, /playbook, /hormozi, /ecom-king, /pinterest, /roi, /content
- These HTML files are in `_archive/` not `frontend/`
- Frontend only has: index.html, launcher_os.html, privacy.html, thank-you.html

### Valid routes:
- /api/health, /api/quinn/local-chat, /api/webhook, /api/supplier, /api/engine/(.*)
- /thank-you, /privacy

---

## 3. Duplicate Files (12 .bak files in dashboard/)

| File | Action |
|------|--------|
| pipeline_dashboard.py.bak_20260607 | ARCHIVE |
| pipeline_dashboard.py.bak_20260608_063610 | ARCHIVE |
| pipeline_dashboard.py.bak_20260608_070121 | ARCHIVE |
| pipeline_dashboard.py.bak_20260608_073225 | ARCHIVE |
| pipeline_dashboard.py.bak_post_20260608_073303 | ARCHIVE |
| pipeline_dashboard.py.bak_t15_20260608 | ARCHIVE |
| _pipe_dash.css.bak_20260608_070121 | ARCHIVE |
| _pipe_dash.html.bak_20260607 | ARCHIVE |
| _pipe_dash.html.bak_stage6_20260608 | ARCHIVE |
| _pipe_dash.html.bak_tabs_20260608_060937 | ARCHIVE |
| _pipe_dash.js.bak_20260608_063610 | ARCHIVE |
| _pipe_dash.js.bak_20260608_070121 | ARCHIVE |

**Move all to:** `_archive/dashboard_baks_20260608/`

---

## 4. Archive Summary

### _archive/ contents:
- hormozi.html, pinterest.html, playbook.html, roi.html, store.html (old landing pages)
- pet-hair-remover.html, posture-corrector.html, resistance-bands.html (product pages)
- index.html.bak, profiles.html, social_ai_agent.env.bak
- Handoff docs, session summaries

### _archived/ contents:
- decision-engine-js/decision-engine.js (10560 bytes)

**Issue:** Two archive dirs (_archive and _archived). Consolidate into one.

---

## 5. Directory Structure

### KEEP:
- api/ (10 JS endpoints + quinn/ subdir)
- agents/ (7 Python agents; product_onboarding 46KB, db.py 41KB, social_ai 24KB)
- engines/ (12 Python engines/launchers)
- discovery_engine/ (standalone pipeline with CLI, scoring, signals, suppliers)
- integrations/ (6 connectors)
- frontend/ (4 files)
- social_ai_agent/ (standalone agent with own .env)
- dashboard/ (active files only)

### REVIEW:
- engines/RUN_STACK.py vs run_dropship_os.py vs launch_shipstack.py -- 3 launchers, likely 1 canonical
- social_ai_agent/ has own .env (3198B) separate from root -- config drift risk
- agents/db.py at 41KB -- unusually large for a DB module

---

## 6. Agents Inventory

| Agent | Size | Purpose |
|-------|------|---------|
| analytics_engine.py | - | Analytics processing |
| content_calendar_builder.py | - | Content scheduling |
| content_pipeline.py | - | Content generation |
| db.py | 41KB | Database ops (REVIEW: oversized) |
| post_scheduler.py | - | Social post scheduling |
| product_onboarding_agent.py | 46KB | Product onboarding |
| product_research.py | - | Product research |
| social_ai_agent.py | 24KB | Social media AI |

---

## 7. Priority Fixes

1. **P0:** Fix api/discover.js broken imports (blocks discovery MVP)
2. **P1:** Add 6 missing API routes to vercel.json
3. **P1:** Restore/redirect archived HTML pages for vercel routes
4. **P2:** Archive 12 dashboard .bak files
5. **P2:** Consolidate _archive/ and _archived/
6. **P3:** Audit 3 duplicate launcher scripts in engines/
7. **P3:** Review agents/db.py (41KB)

---

## Smoke Test

- Directory tree: READ via PRIME file API (200 OK)
- vercel.json: READ and parsed (verified)
- api/discover.js: READ, imports confirmed broken
- stub-apis.js: Confirmed NOT FOUND in integrations/
- decision-engine.js: Confirmed in _archived/decision-engine-js/ (10560 bytes)
- api/quinn/local-chat.js: Confirmed exists (2360 bytes)
