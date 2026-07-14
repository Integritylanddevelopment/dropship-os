# ShipStack AI - Quick Start Guide

## One-Command Launch

Double-click this file:
```
LAUNCH_SHIPSTACK.ps1
```

That's it. The launcher will:
1. ✓ Check if Quinn Bridge is running (required)
2. ✓ Auto-launch Quinn if needed (Qdrant + Ollama + Quinn Bridge)
3. ✓ Kill any stale processes on port 3000
4. ✓ Install npm dependencies if needed
5. ✓ Start ShipStack Express server
6. ✓ Open your browser to http://127.0.0.1:3000

## What's Running (After Launch)

| Service | Port | Purpose |
|---------|------|---------|
| ShipStack Dashboard | 3000 | Web UI for drop shipping commands |
| Quinn Bridge | 8765 | Local AI + research + decision engine |
| Qdrant | 6333 | Vector database for embeddings |
| Ollama | 11434 | Local inference (qwen, llama, etc.) |

## Architecture

```
Your Browser (http://localhost:3000)
    ↓
ShipStack Express.js Server (port 3000)
    ├→ API routes (metrics, discover, engine, chat, etc.)
    └→ Calls Quinn Bridge (port 8765) for AI/research
        ├→ Qdrant (port 6333) for vector search
        └→ Ollama (port 11434) for local LLMs
```

ShipStack is **completely standalone codebase** in `dropship-os/`. It does NOT depend on Quinn's code — it just calls Quinn's services over HTTP.

## Environment Setup

### Local Keys (.env.local)

After cloning, add your real API keys to:
```
dropship-os/.env.local
```

File is git-ignored (not committed). Example:
```
STRIPE_SECRET_KEY=sk_live_YOUR_REAL_KEY
ANTHROPIC_API_KEY=sk-ant-YOUR_REAL_KEY
PINTEREST_ACCESS_TOKEN=YOUR_TOKEN
...
```

### Infrastructure Config (.env)

Global infrastructure settings in:
```
dropship-os/.env
```

This file defines all ports, URLs, Quinn Bridge secret — **one source of truth**. Committed to git with no secrets.

## File Structure

```
Drop shipping/
├── dropship-os/                  ← ShipStack codebase (independent)
│   ├── server.js                 ← Express entry point
│   ├── package.json              ← npm dependencies
│   ├── .env                       ← Infrastructure config (git)
│   ├── .env.local                ← Your API keys (git-ignored)
│   ├── api/                       ← API route handlers
│   │   ├── metrics.js            ← Qdrant stats
│   │   ├── discover.js           ← Product discovery
│   │   ├── engine.js             ← Decision engine scoring
│   │   ├── chat.js               ← Quinn Bridge router
│   │   ├── prometheus.js         ← Video generation
│   │   └── ...
│   ├── index.html                ← Dashboard UI
│   └── launcher_os.html          ← Desktop launcher
│
├── LAUNCH_SHIPSTACK.ps1          ← Double-click to launch
├── PUSH_SHIPSTACK_TO_GITHUB.ps1  ← GitHub push tool
├── prometheus_engine.py          ← Video AI pipeline (Phase 4)
└── logs/                          ← Service logs

```

## GitHub Push

To push changes:

Double-click:
```
PUSH_SHIPSTACK_TO_GITHUB.ps1
```

Script will:
1. Clean lock files
2. Show git status
3. Prompt for commit message
4. Stage, commit, push to `origin main`

Pushes to: `github.com/Integritylanddevelopment/dropship-os`

## Troubleshooting

### Quinn Bridge won't start
```
C:\Users\integ\quinn-proxy\LAUNCH_QUINN.ps1
```
This manages Docker (Qdrant, Ollama) and Quinn services separately.

### Port already in use
Launcher auto-kills stale processes on port 3000. If not working:
```powershell
Get-NetTCPConnection -LocalPort 3000
Stop-Process -Id <PID> -Force
```

### npm install fails
```powershell
cd dropship-os
npm install --verbose
```
Check logs in `logs/npm-install.log`

### ShipStack server won't start
Check logs:
```
C:\Users\integ\Documents\Claude\Projects\Drop shipping\logs\shipstack.log
C:\Users\integ\Documents\Claude\Projects\Drop shipping\logs\shipstack.log.err
```

### Can't connect to Quinn Bridge
Make sure Quinn launcher window is still open. It keeps services running in background. Logs:
```
C:\Users\integ\quinn-proxy\logs\
```

## Next Steps

1. Launch ShipStack: `LAUNCH_SHIPSTACK.ps1`
2. Check dashboard: http://127.0.0.1:3000
3. Add API keys: `dropship-os/.env.local`
4. Test endpoints: `/api/metrics`, `/api/discover`, `/api/engine/score`
5. Push changes: `PUSH_SHIPSTACK_TO_GITHUB.ps1`

## API Endpoints

| Endpoint | Method | Purpose |
|----------|--------|---------|
| `/api/metrics` | GET | Qdrant stats + revenue data |
| `/api/discover` | POST | Find products (phase 2) |
| `/api/engine/score` | GET | Decision engine scoring |
| `/api/chat` | POST | Quinn Bridge router |
| `/api/prometheus/generate` | POST | Video generation |
| `/api/health` | GET | Service health check |

## No Quinn Bridge Code Inside

**Important:** ShipStack codebase contains ZERO references to:
- Quinn's directory structure
- Quinn's Python files
- Quinn's collections or databases
- Quinn's MCP tools

ShipStack **only calls Quinn over HTTP** (port 8765). This ensures complete independence for future deployment elsewhere.

---

**Last updated:** 2026-06-02  
**Owner:** Alex Alexander (integritylanddevelopment@gmail.com)
