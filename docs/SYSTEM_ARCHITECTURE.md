# ShipStack AI — System Architecture & Operational Guide

**Date:** 2026-06-02  
**Owner:** Alex Alexander  
**Status:** All 10 phases complete + local Express.js deployment + launcher system

---

## Executive Summary

ShipStack AI is a **fully local, standalone drop shipping intelligence system** that runs on your machine without cloud dependencies (except optional Anthropic fallback).

- **Codebase:** Completely independent in `dropship-os/` folder
- **Server:** Express.js on port 3000
- **External Services:** Quinn Bridge + Qdrant + Ollama (managed separately)
- **Launch:** One PowerShell script (`LAUNCH_SHIPSTACK.ps1`)
- **Deployment:** GitHub push via `PUSH_SHIPSTACK_TO_GITHUB.ps1`

---

## Port Registry (Single Source of Truth)

All ShipStack and Quinn infrastructure ports defined in `.env` files:

### ShipStack Ports (dropship-os/.env)
```
PORT=3000                          ← Express.js server
QUINN_BRIDGE_PORT=8765            ← Reference to Quinn service
PROMETHEUS_ENGINE_PORT=8766       ← Video generation
DASHBOARD_PORT=8888               ← Analytics dashboard (future)
```

### Quinn Infrastructure Ports (C:\Users\integ\quinn-proxy\.env)
```
QUINN_BRIDGE_PORT=8765            ← HTTP bridge
QDRANT_HOST=127.0.0.1
QDRANT_PORT=6333                  ← Vector database
OLLAMA_HOST=127.0.0.1
OLLAMA_PORT=11434                 ← Local LLMs
```

**Rule:** If services compete for ports, check these .env files — they're the single source of truth.

---

## Architecture: Three Layers

### Layer 1: User Interface (Browser)
```
http://127.0.0.1:3000
├─ index.html              Dashboard UI
├─ launcher_os.html        Service monitor
└─ api/                    REST endpoints
```

### Layer 2: ShipStack Backend (Express.js, Node.js)
```
SHIPSTACK (port 3000)
├─ server.js               Entry point (import 'dotenv/config.js')
├─ api/
│  ├─ metrics.js          Qdrant stats + Stripe revenue
│  ├─ discover.js         Product research (Phase 2)
│  ├─ engine.js           Decision engine (Phase 3)
│  ├─ chat.js             Quinn Bridge router
│  ├─ prometheus.js       Video generation (Phase 4)
│  ├─ search.js           General search
│  ├─ supplier.js         Supplier integration
│  ├─ health.js           Service health check
│  └─ webhook.js          Stripe webhooks
├─ .env                   Infrastructure config (git-tracked)
├─ .env.local             API keys (git-ignored)
└─ package.json           npm dependencies (ES modules)

Dependencies:
- express 4.18.2
- dotenv 16.0.3
- axios 1.6.0
- @qdrant/js-client-rest 1.7.0
```

### Layer 3: External Services (Managed by Quinn)
```
QUINN BRIDGE (port 8765)
├─ Qdrant (port 6333)        Vector search
├─ Ollama (port 11434)       Local inference
└─ Python backend            Embeddings + RAG

Manages:
✓ dropship_intel collection     (ShipStack uses this)
✓ strategy_books collection     (Separated for other uses)
✓ Qdrant API for vector search
✓ Ollama local models
✓ File-based queue polling
```

---

## Launching the System

### Step 1: Launch Quinn (Infrastructure)

Double-click:
```
C:\Users\integ\quinn-proxy\LAUNCH_QUINN.ps1
```

This starts:
- Docker (if not running)
- Ollama container (port 11434)
- Qdrant container (port 6333)
- Quinn HTTP Bridge service (port 8765)

**Time:** 30-45 seconds  
**Keep window open:** Services run in background

### Step 2: Launch ShipStack (Application)

Double-click:
```
C:\Users\integ\Documents\Claude\Projects\Drop shipping\LAUNCH_SHIPSTACK.ps1
```

This:
1. Checks Quinn Bridge on port 8765
2. Auto-launches Quinn if not running (offers prompt)
3. Cleans stale processes on port 3000
4. Installs npm dependencies (if needed)
5. Starts Express.js server
6. Opens browser to http://127.0.0.1:3000

**Time:** 10-15 seconds (if Quinn already running)

### Verify All Services

Once both launchers complete, all services should be responding:

```powershell
# Test each service
curl http://127.0.0.1:3000/api/health          # ShipStack
curl http://127.0.0.1:8765/health              # Quinn Bridge
curl http://127.0.0.1:6333/collections         # Qdrant
curl http://127.0.0.1:11434/api/tags           # Ollama
```

---

## API Endpoints & Functionality

### Metrics (Phase 9 - Revenue Intelligence)
```
GET /api/metrics
- Returns: Qdrant stats + Stripe revenue data
- Requires: Quinn Bridge + Qdrant responding
- Source: dropship_intel collection only (no cross-contamination)
```

### Product Discovery (Phase 2)
```
POST /api/discover
- Body: { niche: "pet accessories", budget: 100 }
- Returns: Product list + margin estimates
- Source: Research via Quinn Bridge
```

### Decision Engine (Phase 3)
```
GET /api/engine/score?product_id=brush_123&channel=pinterest
- Returns: 6-criterion score (0-100)
  - Sales proof: 25%
  - Demand: 20%
  - Supply: 15%
  - Saturation: 15%
  - Margin: 15%
  - Velocity: 10%
- Powers: Content routing decisions
```

### Chat/Intelligence (All Phases)
```
POST /api/chat
- Body: { message: "What's trending in pet niche?" }
- Routing: Quinn Bridge (port 8765)
  - Try: Local Ollama inference
  - Fallback: Anthropic Claude
- Collection: dropship_intel (partition-enforced)
```

### Video Generation (Phase 4 - Prometheus)
```
POST /api/prometheus/generate
- Body: { hook: "90% of pet owners...", product_name: "Self-Cleaning Brush", price: 29.99, offer: "Buy 2 get 10% off" }
- Returns: Video URL in prometheus_output/
- Requires: FFmpeg installed locally
```

### Social Posting (Phase 7)
```
POST /api/pinterest       (Phase 7a - Auto-poster)
- Requires: PINTEREST_ACCESS_TOKEN in .env.local
- Body: { pin_title, description, image_url, link_url }

POST /api/tiktok          (Phase 7b - TikTok auto-poster)
- Requires: TIKTOK_ACCESS_TOKEN
- Body: { video_url, caption, hashtags }
```

---

## Configuration & Environment Variables

### .env (Git-Tracked Infrastructure Config)
```bash
# ShipStack Services
PORT=3000
NODE_ENV=development

# Quinn Bridge
QUINN_ENDPOINT=http://localhost:8765
QUINN_BRIDGE_SECRET=dropship-os-quinn-2026-alex

# External Ports (Reference)
QDRANT_HOST=127.0.0.1
QDRANT_PORT=6333
OLLAMA_HOST=127.0.0.1
OLLAMA_PORT=11434

# Fallback AI
FALLBACK_ENABLED=true
FALLBACK_API_URL=https://api.anthropic.com/v1/messages
FALLBACK_MODEL=claude-sonnet-4-6

# Paths
SHIPSTACK_DIR=C:\Users\integ\Documents\Claude\Projects\Drop shipping\dropship-os
LOG_DIR=C:\Users\integ\Documents\Claude\Projects\Drop shipping\logs
```

**Location:** `dropship-os/.env` (committed to git)

### .env.local (Git-Ignored API Keys)
```bash
# Real API keys — NEVER committed
STRIPE_SECRET_KEY=sk_live_YOUR_KEY
ANTHROPIC_API_KEY=sk-ant-YOUR_KEY
PINTEREST_ACCESS_TOKEN=YOUR_TOKEN
TIKTOK_ACCESS_TOKEN=YOUR_TOKEN
META_ACCESS_TOKEN=YOUR_TOKEN
ZENDROP_API_KEY=YOUR_KEY
AUTODS_API_KEY=YOUR_KEY
```

**Location:** `dropship-os/.env.local` (git-ignored)  
**Setup:** User adds real keys locally post-clone

---

## Operational Procedures

### Daily Startup

```powershell
# Terminal 1: Start Quinn services
LAUNCH_QUINN.ps1
# Keep window open (runs services in background)

# Terminal 2: Start ShipStack
LAUNCH_SHIPSTACK.ps1
# Auto-launches Quinn if needed
# Opens browser to dashboard
```

### Pushing Changes

```powershell
PUSH_SHIPSTACK_TO_GITHUB.ps1
# Stages all changes
# Prompts for commit message
# Pushes to github.com/Integritylanddevelopment/dropship-os main branch
```

### Checking Service Health

```powershell
# All services responding
Invoke-WebRequest http://127.0.0.1:3000/api/health
Invoke-WebRequest http://127.0.0.1:8765/health
Invoke-WebRequest http://127.0.0.1:6333/collections
Invoke-WebRequest http://127.0.0.1:11434/api/tags
```

### Viewing Logs

```
ShipStack:  C:\Users\integ\Documents\Claude\Projects\Drop shipping\logs\shipstack.log
Quinn:      C:\Users\integ\quinn-proxy\logs\quinn_http_bridge.log
npm:        C:\Users\integ\Documents\Claude\Projects\Drop shipping\logs\npm-install.log
```

---

## Codebase Boundaries

### ShipStack (Independent)
✓ Can be deployed anywhere Node.js + port 3000 is available  
✓ Only calls Quinn Bridge over HTTP (port 8765)  
✓ Zero file-system references to Quinn codebase  
✓ Partition-enforced: dropship_intel collection only  
✓ Standalone GitHub repo  

### Quinn (External Service)
✓ Manages: Qdrant, Ollama, HTTP bridge  
✓ ShipStack CALLS it, doesn't depend on its code  
✓ Separate launcher, separate logs, separate configuration  
✓ Can be restarted independently  

### Why This Matters
If Quinn code changes or updates, ShipStack still works (as long as port 8765 HTTP API stays compatible). If ShipStack needs updates, Quinn services don't need touching.

---

## Security & Secrets

### Secrets Management
- **Real keys:** `dropship-os/.env.local` (git-ignored, local only)
- **Infrastructure config:** `dropship-os/.env` (git-tracked, no secrets)
- **GitHub secret scanning:** Enabled (blocks commits with real secrets)
- **Bridge secret:** `QUINN_BRIDGE_SECRET=dropship-os-quinn-2026-alex` (public test value, safe in .env)

### Git Protection
```
.gitignore contains:
.env.local              ← Never committed
.env.*.local            ← Never committed
*credentials.json       ← Never committed
*.pem, *.key, *.crt     ← Never committed
```

---

## Troubleshooting Matrix

| Problem | Cause | Solution |
|---------|-------|----------|
| ShipStack won't start | Quinn Bridge not running | Run LAUNCH_QUINN.ps1 first |
| Port 3000 in use | Stale process | Launcher auto-kills (or manually: Stop-Process -Id <PID> -Force) |
| /api/metrics returns empty | Qdrant not running | Check Quinn launcher window, check logs |
| npm install fails | Missing dependencies | npm install --verbose, check npm-install.log |
| Quinn Bridge not responding | Docker not running | Quinn launcher starts Docker automatically |
| Secret scanning blocks push | Real API key committed | Use PLACEHOLDER values only, add real keys locally |

---

## Development Workflow

1. **Edit code:** Modify files in `dropship-os/`
2. **Test locally:** `LAUNCH_SHIPSTACK.ps1` tests changes
3. **Commit:** `PUSH_SHIPSTACK_TO_GITHUB.ps1` with clear message
4. **Verify GitHub:** Check dropship-os repo main branch

---

## Performance Notes

- **Startup time:** 30-45s (first time) / 10-15s (subsequent)
- **Memory:** ~200MB (Node.js) + Docker services
- **Network:** Local only (no cloud except optional Anthropic fallback)
- **Scaling:** Designed for local development. Production deployment separate.

---

## References

- **Project:** ShipStack AI (Drop Shipping Intelligence)
- **Git:** github.com/Integritylanddevelopment/dropship-os
- **Team:** togetherwe (Vercel project — for optional cloud deployment)
- **Architecture:** Local-first with optional Vercel integration
- **Contact:** integritylanddevelopment@gmail.com

---

**Last Updated:** 2026-06-02  
**Version:** 1.0.0 (Local Express.js + Launcher System)
