# ShipStack AI — Health Agent Handoff
**For:** AI agent tasked with building/fixing the ShipStack Health Monitor
**From:** ShipStack AI audit session, 2026-05-05
**Owner:** Alex Alexander (integritylanddevelopment@gmail.com)
**Project folder:** `C:\Users\integ\Documents\Claude\Projects\Drop shipping\`
**Live site:** https://dropship-os-hazel.vercel.app

---

## The Core Problem You Are Solving

The ShipStack AI Command Center has a status dashboard that shows green/red dots for:
- Quinn Bridge (port 8765)
- Ollama (port 11434)
- Qdrant (port 6333)
- Stripe
- Pinterest
- Prometheus

**These dots are LYING.** They show green based on shallow checks that do not verify actual functionality. Example from today's audit:

- Quinn Bridge showed GREEN — process was running on port 8765, responding to HTTP
- But: the localtunnel/ngrok URL in Vercel (`QUINN_ENDPOINT`) was a dead stale URL
- Result: the live site chat was silently falling back to direct Anthropic, completely bypassing Quinn, Qdrant memory search, and 2,811 vectors of stored intelligence
- Alex had no idea. Everything looked green.

This is the problem. The health agent must do DEEP checks, not process checks. And when it finds a problem, it must FIX it — not just alert.

---

## What a Real Health Check Looks Like for Each Service

### Quinn Bridge
**Shallow (current — wrong):** `curl http://127.0.0.1:8765` returns 200
**Deep (required):**
1. `GET http://127.0.0.1:8765/stats` — verify `general_knowledge` vector count > 0
2. `POST http://127.0.0.1:8765/chat` with `{"messages":[{"role":"user","content":"test"}]}` — verify response has `content` field and `source` is not `error`
3. Check Vercel `QUINN_ENDPOINT` env var — fetch that URL's `/stats` from the public internet — verify it matches local Quinn (proves tunnel is alive)
4. If tunnel is dead: trigger tunnel restart or alert with specific fix instructions

### Ollama
**Shallow (wrong):** port 11434 responds
**Deep (required):**
1. `GET http://127.0.0.1:11434/api/tags` — verify `qwen2.5:7b` and `qwen2.5:3b` are in the model list
2. `POST http://127.0.0.1:11434/api/generate` with model `qwen2.5:3b`, prompt `"ping"` — verify response comes back in under 10 seconds
3. If model missing: surface exact `ollama pull qwen2.5:7b` command

### Qdrant
**Shallow (wrong):** port 6333 responds
**Deep (required):**
1. `GET http://127.0.0.1:6333/collections/general_knowledge` — verify `points_count > 0`
2. `GET http://127.0.0.1:6333/collections/dropship_intel` — verify `points_count > 0` (if 0, partitioning script has not been run)
3. `GET http://127.0.0.1:6333/collections/strategy_books` — verify `points_count > 0`
4. If `dropship_intel` or `strategy_books` have 0 points: the fix is to run `SETUP_QDRANT_PARTITIONS.py`

### Stripe
**Shallow (wrong):** env var `STRIPE_SECRET_KEY` is set
**Deep (required):**
1. `GET https://api.stripe.com/v1/balance` with Bearer auth — verify 200 response (proves key is valid and live)
2. If 401: key is wrong or revoked

### QUINN_ENDPOINT (Vercel tunnel)
This is the most critical and most broken check. Two things must BOTH be true:
1. `QUINN_ENDPOINT` is set in Vercel
2. That URL is actually reachable and returns valid Quinn `/stats` data from the public internet

Current code only checks #1. It never checks #2. This is why it showed green while being dead.

---

## Current Status (as of 2026-05-05 audit)

| Service | Process | Deep Check | Notes |
|---|---|---|---|
| Quinn Bridge | Running (port 8765) | Partially working | `/stats` responds but shows 0 vectors for dropship_intel/strategy_books |
| Qdrant | Running (port 6333) | Working | `general_knowledge` has 2,811 points. `dropship_intel` and `strategy_books` have 0 points — partitioning not run |
| Ollama | Unknown | Not checked | Assumed running, not verified |
| QUINN_ENDPOINT tunnel | Dead | Broken | Vercel has stale localtunnel URL `cute-wings-pump.loca.lt` — not reachable |
| Stripe | Connected | Working | Returns $0.00 revenue (correct, no sales yet) |
| Pinterest | Token in .env | Not deep-checked | `PINTEREST_ACCESS_TOKEN` exists, never verified against API |

---

## The Fix Architecture the Health Agent Needs

The health agent is NOT just a monitor. It needs to be an autonomous fixer. Here is the decision tree:

```
Health Agent runs every 5 minutes
    |
    FOR EACH service:
        Run deep check
        |
        PASS -> show green, log OK
        |
        FAIL -> classify failure type:
            |
            FIXABLE AUTOMATICALLY:
                - Qdrant 0 vectors -> run SETUP_QDRANT_PARTITIONS.py
                - Dead tunnel -> restart localtunnel/ngrok, update Vercel QUINN_ENDPOINT
                - Missing metrics.json -> run decision_engine.py
            |
            NEEDS HUMAN + CAN GUIDE:
                - Ollama model missing -> show exact pull command
                - Stripe key invalid -> link to Stripe dashboard
                - Pinterest token expired -> link to Pinterest dev console
            |
            LOG + ALERT:
                - Write failure to health_log.json with timestamp + failure type + fix attempted
```

---

## What Tools the Health Agent Needs to Fix Problems

### To fix the tunnel (highest priority):
The agent needs to be able to restart the ngrok/localtunnel AND update the Vercel env var automatically.

**Option A — Vercel API (recommended):**
```
PATCH https://api.vercel.com/v10/projects/{projectId}/env/{envId}
Authorization: Bearer {VERCEL_TOKEN}
Body: {"value": "https://new-ngrok-url.ngrok.io"}
```
Vercel project ID: `prj_uFSUtfgA5yC8puLDMzAZig8Ik30a`
Vercel team ID: `team_qd9zTuDQ41euDNXJwHVVPocq`
Env var IDs: get these by calling `GET /v10/projects/{projectId}/env`
After updating env var, trigger redeploy: `POST /v13/deployments` (or just use the existing deploy hook)

The agent needs a `VERCEL_TOKEN` added to `.env` for this to work.

**Option B — Subprocess restart:**
The agent can call `subprocess.Popen` to restart `START_QUINN_BRIDGE.bat` and then use pyngrok or subprocess to start a new ngrok tunnel, capture the URL, and call the Vercel API to update it.

### To fix Qdrant partitions:
```python
subprocess.run([sys.executable, 'SETUP_QDRANT_PARTITIONS.py'], cwd=PROJECT_DIR)
```

### To fix missing metrics.json:
```python
subprocess.run([sys.executable, 'decision_engine.py'], cwd=PROJECT_DIR)
```

### To escalate to Claude/Anthropic API:
When the health agent encounters a problem it cannot classify or fix automatically, it should:
1. Capture the full error context (service name, error message, last known good state)
2. POST to Anthropic API with the system prompt: "You are ShipStack AI's diagnostic agent. Given this error, provide the exact fix as a shell command or API call."
3. If the returned fix is a shell command: execute it (with a safety allowlist of permitted commands)
4. If it requires human action: write to `health_alerts.json` and surface in the dashboard

**Anthropic API key:** Already in `.env` as `ANTHROPIC_API_KEY`. Use `claude-haiku-4-5-20251001` for speed/cost on health checks. Escalate to `claude-sonnet-4-6` only for complex diagnosis.

---

## Where the Health Agent Should Live

**File:** `C:\Users\integ\Documents\Claude\Projects\Drop shipping\health_agent.py`

**Run mode:** Windows Task Scheduler, every 5 minutes
```
Action: python health_agent.py --check-all
```

**Output files:**
- `health_status.json` — current state of all services (read by dashboard)
- `health_log.json` — append-only log of all checks + fixes
- `health_alerts.json` — unresolved issues requiring human action

**Dashboard integration:** `index.html` already has status dots. The health agent should write `health_status.json` to the `dropship-os/` folder so the metrics API or a new `/api/health` endpoint can serve it. The dots should read from this file instead of doing their own shallow checks.

---

## The False Green Problem — Specific Code to Fix in index.html

The current status dots in the dashboard are set by `setApiDot()` in `populateRevenue()`. They check:
- Stripe: `src2.stripe === 'live'` — OK, this is a real check
- Pinterest: `!!m.pinterest_connected` — field doesn't exist in API response, always false
- TikTok: `!!m.tiktok_connected` — same, always false
- Zendrop: `!!m.zendrop_connected` — same, always false
- Prometheus: polls `/api/prometheus?action=status` — OK

The Quinn/Ollama/Qdrant dots are set elsewhere in the dashboard by JavaScript that checks if ports respond. None of them verify actual functionality.

**The fix:** Add a `/api/health` Vercel edge function that reads `health_status.json` (written by the local health agent, committed to the repo or fetched via Quinn bridge `/health` endpoint). The dashboard dots read from this instead of doing their own checks.

---

## Key Files to Read Before Starting

```
C:\Users\integ\Documents\Claude\Projects\Drop shipping\
├── CLAUDE.md                          <- project rules, port registry, all env vars
├── .env                               <- all API keys
├── dropship-os\
│   ├── quinn_web_bridge.py            <- Quinn bridge source — understand /chat, /stats endpoints
│   ├── START_QUINN_BRIDGE.bat         <- how Quinn starts
│   ├── api\metrics.js                 <- where Stripe/Qdrant checks currently live
│   └── index.html                     <- where status dots are rendered (setApiDot function)
└── SETUP_QDRANT_PARTITIONS.py         <- the script to run when dropship_intel has 0 vectors
```

---

## Priority Order for the Health Agent Build

1. Write `health_agent.py` with deep checks for Quinn, Ollama, Qdrant, Stripe, tunnel
2. Add auto-fix: Qdrant partitions (run script), metrics.json (run decision_engine.py)
3. Add Vercel API integration to auto-update `QUINN_ENDPOINT` when tunnel changes
4. Write `/api/health` Vercel edge function that exposes `health_status.json`
5. Update `index.html` status dots to read from `/api/health` instead of shallow port checks
6. Add Windows Task Scheduler entry for 5-minute health cycle

Do NOT show green unless the deep check passes. A service that is "running" but not actually serving its function is red.
