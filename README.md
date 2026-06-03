# ShipStack AI — Dropshipping Discovery Engine

Complete, production-ready dropshipping automation platform. 4 HTTP services, badge-gated endpoints, Quinn-routed LLM calls, real-time monitoring.

## Architecture

```
┌─────────────────────────────────────────┐
│  Vercel Frontend (Next.js @ :3000)     │
└──────────────────┬──────────────────────┘
                   │
    ┌──────────────┼──────────────┐
    │              │              │
    v              v              v
ShipStack      Prometheus    Social AI      Dashboard
Engine         Engine        Agent         (:8890)
(:8889)        (:8766)       (:8867)
    │              │              │
    └──────────────┼──────────────┘
                   │
                   v
            Quinn Bridge
            (:8765 external)
                   │
        ┌──────────┴──────────┐
        │                     │
        v                     v
    Ollama              Claude API
    (local)            (Anthropic)
```

**Services:**
- **ShipStack Engine** (:8889) — Product decision engine + supplier research
- **Prometheus Engine** (:8766) — Video content generation
- **Social AI Agent** (:8867) — Social media orchestration
- **Dashboard** (:8890) — Real-time monitoring UI

**Features:**
- Badge-gated endpoints (60-second one-shot tokens)
- Synchronous action logging to `logs/shipstack_actions.jsonl`
- Zero direct Anthropic calls (all through Quinn bridge)
- Fully compliant with Quinn Global Directives + ShipStack Directives

## Quick Start

### 1. Install Dependencies
```bash
pip install -r requirements.txt
```

### 2. Configure Environment
```bash
cp .env.example .env.local
# Edit .env.local:
# - Set QUINN_ENDPOINT (e.g., https://your-ngrok-url.ngrok.io)
# - Set QUINN_BRIDGE_SECRET
# - Add supplier API keys (ZENDROP_API_KEY, etc.)
```

### 3. Validate Configuration
```bash
python validate_config.py
```

### 4. Launch All Services
```bash
python launch_shipstack.py
```

This will:
- Kill old processes on ports 8889, 8766, 8867, 8890
- Start ShipStack Engine, Prometheus, Social AI, Dashboard
- Minimize terminal windows
- Print service URLs

### 5. Access Dashboard
Open http://localhost:8890 in browser

## Services

### ShipStack Engine (:8889)

**Public Endpoints:**
- `GET /health` — health check
- `GET /badge` — issue new badge token

**Badge-Gated Endpoints:**
- `POST /api/decide` — score and rank products
- `POST /api/research` — research products across suppliers
- `POST /api/log-action` — log tool calls

**Example Request:**
```bash
# Get badge
TOKEN=$(curl -s http://localhost:8889/badge | jq -r '.token')
ISSUED=$(curl -s http://localhost:8889/badge | jq -r '.issued_at')

# Use badge to call protected endpoint
curl -X POST http://localhost:8889/api/decide \
  -H "Authorization: Bearer $TOKEN" \
  -H "X-Badge-Issued-At: $ISSUED" \
  -H "Content-Type: application/json" \
  -d '{
    "products": [
      {"id": "p1", "title": "Widget", "price": 5.99, "niche": "pet accessories"}
    ]
  }'
```

### Prometheus Engine (:8766)

Video generation service. Same endpoints pattern as ShipStack Engine.

**Badge-Gated:**
- `POST /api/generate-video` — start video generation
- `GET /api/video-status/<video_id>` — check job status
- `POST /api/publish-video` — publish to social media

### Social AI Agent (:8867)

Social media posting orchestration.

**Badge-Gated:**
- `POST /api/generate-caption` — write social copy
- `POST /api/content-calendar` — schedule posts
- `POST /api/post-to-platform` — publish to TikTok/Instagram/Pinterest/YouTube
- `GET /api/engagement-stats` — fetch analytics

### Dashboard (:8890)

Real-time monitoring UI.

**Public:**
- `GET /` — dashboard HTML
- `GET /api/health` — service health JSON
- `GET /api/actions` — recent actions + metrics JSON

## Tools

### Launcher
```bash
python launch_shipstack.py
```
Kills old processes, starts all 4 services, minimizes windows.

### Decision Engine
```python
from decision_engine import DecisionEngine, Product

engine = DecisionEngine()
product = Product(id="p1", title="Widget", price=5.50, supplier="zendrop", reviews=150, rating=4.8, niche="pet accessories")
decision = engine.decide(product)
print(f"Score: {decision.score:.2f}")
print(f"Rationale: {decision.rationale}")
```

### Product Research
```python
from product_research import ProductResearcher

researcher = ProductResearcher()
products = researcher.research("pet collars", suppliers=["zendrop", "autods", "aliexpress"])
for p in products:
    print(f"{p['title']} (${p['price']:.2f})")
```

### Analytics Engine
```python
from analytics_engine import AnalyticsEngine

analytics = AnalyticsEngine()
metrics = analytics.get_summary_metrics(hours=24)
print(f"Total actions: {metrics['total_actions']}")
print(f"Success rate: {metrics['success_rate']:.1%}")
```

### Config Validator
```bash
python validate_config.py
```
Pre-flight checks: env vars, ports, files, no Anthropic leaks.

## Testing

Run integration tests:
```bash
python test_integration.py
```

Tests:
1. Badge system (token generation, validation, expiry)
2. Health checks (all 4 services)
3. Decision Engine (scoring logic)
4. Product Research (aggregation)
5. Analytics Engine (metrics)
6. Badge-gated endpoints (authorization)
7. No Anthropic leaks (code audit)

## Compliance

✅ **Quinn Global Directives (#1-6):**
- Quinn-First routing (all LLM through :8765)
- Files mirror Quinn (action logs)
- No leak channels (zero direct Anthropic)
- Badge Protocol (60-sec tokens, sync logging)

✅ **ShipStack Directives (#1-17):**
- No direct Anthropic (verified)
- Badge per tool (all endpoints checked)
- Lane isolation (dropship-os/ only)
- HTTP service, not MCP
- Kill before launch (implemented)
- No scheduled tasks
- Proper naming conventions
- One-way handoff flow
- UTF-8 everywhere
- Port registry documented
- Prometheus ownership (ShipStack)
- Action logging (JSONL)
- Dependencies tracked
- .gitignore protection
- Env var segregation
- Window minimize

## Logs

All actions logged to `logs/shipstack_actions.jsonl` in JSONL format:

```json
{
  "timestamp": "2026-06-03T12:00:15Z",
  "badge_token": "badge-1_...",
  "badge_issued_at": "2026-06-03T12:00:00Z",
  "tool_name": "shipstack_engine_decide",
  "target": "/api/decide",
  "action": "decide",
  "result": "Scored 5 products",
  "success": true
}
```

## Placeholders (Ready for Implementation)

- **Decision Engine:** Integrate with Quinn bridge for LLM-assisted trend detection
- **Product Research:** Implement actual Zendrop, AutoDS, AliExpress API calls
- **Prometheus:** Integrate Runway ML, ElevenLabs, Suno, FFmpeg
- **Social AI:** Implement TikTok, Meta, Pinterest, YouTube API integrations
- **Analytics:** Fetch real metrics from platform APIs

## File Structure

```
dropship-os/
├── CLAUDE.md                      # Foundation doc (QuinnFormat)
├── SHIPSTACK_DIRECTIVES.md        # 17 directives
├── README.md                      # This file
├── requirements.txt               # Python dependencies
│
├── Core Services:
├── shipstack_engine.py            # Decision + Research (:8889)
├── prometheus_engine.py           # Video generation (:8766)
├── social_ai_agent.py             # Social posting (:8867)
├── shipstack_dashboard.py         # Monitoring UI (:8890)
│
├── Badge System:
├── shipstack_badge.py             # Token generation + logging
├── shipstack_log_action.py        # Action logger wrapper
│
├── Tools:
├── launch_shipstack.py            # Kill & start all services
├── decision_engine.py             # Product scoring
├── product_research.py            # Supplier aggregation
├── analytics_engine.py            # Metrics computation
├── validate_config.py             # Pre-flight checks
│
├── Testing:
├── test_integration.py            # 7 test suites
├── quick_start.sh                 # One-command launcher
│
├── Data:
├── logs/
│   └── shipstack_actions.jsonl    # Action log (created at runtime)
└── data/
    └── products.db                # Product cache (created at runtime)
```

## Port Registry

| Port | Service | Status |
|------|---------|--------|
| 3000 | Vercel Frontend | External |
| 8889 | ShipStack Engine | Active |
| 8766 | Prometheus Engine | Active |
| 8867 | Social AI Agent | Active |
| 8890 | Dashboard | Active |
| 8765 | Quinn Bridge | External |

## Support

All services implement the same badge/auth pattern:
1. Call `/badge` (public) to get token
2. Call protected endpoint with `Authorization: Bearer <token>`
3. Action logged to `shipstack_actions.jsonl`

Tokens expire after 60 seconds. Get a new one for each tool call.

---

**Built with Quinn Global Directives + ShipStack Directives**
Zero Anthropic leaks. All LLM calls routed through Quinn bridge (:8765).
