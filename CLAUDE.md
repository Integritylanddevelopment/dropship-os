# ShipStack AI — Project Context for ShipStack Agent

**Owner:** ShipStack agent  
**Last updated:** 2026-06-03  
**Status:** Active — cleanup completed, canonical files ready  
**Infrastructure:** Quinn (local AI stack, port 8765)

---

## The Rule

ShipStack agent is the exclusive owner of `dropship-os/`. Quinn is infrastructure — I depend on it, I do not modify it. All LLM calls route through Quinn HTTP bridge `:8765`. All knowledge gets logged back to Quinn via `quinn_add_context(project='ship_stack_ai', ...)`.

---

## Current State

- **Vercel deployment:** https://dropship-os-gamma.vercel.app (live)
- **Local Express.js:** port 3000 (via LAUNCH_SHIPSTACK.ps1)
- **Quinn bridge:** http://127.0.0.1:8765 (HTTP only, local inference fallback)
- **Project bucket:** `project_ship_stack_ai` (530 chunks in Quinn Qdrant)
- **Cleanup:** Overreach files deleted. Parent folder partially cleaned. Lanes restored.

---

## Current Architecture

```
ShipStack Agent (Cowork Claude session)
    ↓
Quinn MCP tools (badge-protected)
    ↓
Quinn HTTP Bridge :8765
    ├─ /embed    → all-MiniLM-L6-v2 embeddings
    ├─ /search   → Qdrant project_ship_stack_ai
    ├─ /chat     → Ollama llama3.2:3b (local) or Anthropic (fallback)
    └─ /health   → bridge alive check
    ↓
Qdrant (port 6333, Docker, multi-project partitions)
Ollama (port 11434, local LLM)
Chrome DB (directives + metadata)
```

---

## Canonical Folders in dropship-os/

| Folder | Purpose |
|--------|---------|
| `api/` | Express.js route handlers |
| `src/` | ShipStack core business logic |
| `tests/` | Unit + integration tests |
| `logs/` | ShipStack runtime logs (NOT quinn-proxy/logs) |
| `decision-engine/` | Product x channel scoring |
| `social_ai_agent/` | Pinterest/TikTok automation stubs |
| `integrations/` | Stripe, suppliers, etc. |

---

## Service Registry (ShipStack owns port 3000)

| Service | Port | Status | Command |
|---------|------|--------|---------|
| ShipStack Express | 3000 | planned | `npm start` in dropship-os/ |
| ShipStack engine | 8889 | planned | `shipstack_engine.py` |
| Quinn bridge | 8765 | active | Quinn manages |
| Prometheus | 8766 | planned | Quinn manages |

---

## Communications with Quinn

### Via Quinn HTTP Bridge (when ShipStack app is running)
```javascript
import axios from 'axios';
const response = await axios.post('http://127.0.0.1:8765/chat', {
  messages: [{role: 'user', content: 'classify: ' + productDesc}],
  model: 'llama3.2:3b'
});
```

### Via Quinn MCP Tools (when I'm a Claude agent in Cowork)
```
1. Call quinn_badge() → get fresh token
2. Call quinn_search(query, project='ship_stack_ai', badge_token)
3. Call quinn_add_context(..., badge_token) to write knowledge back
4. Call quinn_web_fetch / quinn_run_powershell as needed
```

### Via HANDOFF_TO_QUINN.md (for infrastructure requests)
Write requests for new endpoints, MCP tools, or directive changes at end of session.

---

## What I Don't Do

- ❌ Edit anything in `quinn-proxy/` or `.chatgpt-copilot/`
- ❌ Create new files in Quinn's codebase
- ❌ Call `api.anthropic.com` directly (only through Quinn bridge)
- ❌ Kill Quinn processes or modify Docker/Qdrant
- ❌ Write ShipStack logs to `quinn-proxy/logs/`
- ❌ Modify Chroma/Qdrant directly

---

## TIER 2 Task List (where next session picks up)

- [ ] Create `dropship-os/SHIPSTACK_DIRECTIVES.md` (project-specific rules on top of Quinn's 17 global directives)
- [ ] Build `shipstack_engine.py` (decision engine wrapper, port 8889)
- [ ] Wire ShipStack Express → Quinn bridge for all LLM/search
- [ ] Test end-to-end: Vercel → Quinn bridge → local Ollama
- [ ] Deploy local tests of Pinterest/TikTok auto-posters
- [ ] Implement Quinn-to-Vercel tunnel (Cloudflare Tunnel or Tailscale Funnel — TBD)

---

## End-of-Session Ritual (every session)

1. Update this CLAUDE.md with any architectural changes
2. Write/append `dropship-os/HANDOFF_TO_QUINN.md` with what was built/changed
3. Call `quinn_add_context(project='ship_stack_ai', section='session_summary', content='...')`
4. Commit to `dropship-os/` git repo

---

## Quick Reference

```
HOME:               C:\Users\integ\Documents\Claude\Projects\Drop shipping\dropship-os\
LOGS:               dropship-os\logs\                 (NOT quinn-proxy\logs)
QUINN:              http://127.0.0.1:8765
QDRANT:             http://127.0.0.1:6333
OLLAMA:             http://127.0.0.1:11434
VERCEL:             https://dropship-os-gamma.vercel.app

PROJECT BUCKET:     project_ship_stack_ai
MASTER BUCKET:      general_knowledge
GIT REPO:           github.com/Integritylanddevelopment/dropship-os

BADGE TOKEN:        Fresh one per Quinn tool call (directive #4)
LOCAL LLM:          llama3.2:3b (~6 sec on CPU, 0.5 sec on GPU when RTX 3060 arrives)

TODAY'S DATE:       2026-06-03
DIRECTIVES:         17 (cached from Quinn)
```

---

**Status:** READY TO BUILD  
**Cleanup:** COMPLETE  
**Lanes:** RESTORED
