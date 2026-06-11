# SHIPSTACK DIRECTIVE

**Owner:** Alex Alexander
**Last updated:** 2026-06-04
**Document version:** 1.1
**Replaces:** all prior CLAUDE.md versions

---

# READ THIS BEFORE EVERY TOOL CALL

This document defines ShipStack's architecture, project blueprint, and engineering rules. ShipStack is a dropshipping discovery and automation engine built on top of Quinn's infrastructure. Every ShipStack agent must operate under the 17 Universal Global Directives (read via `quinn_badge()`) plus the ShipStack-specific rules below.

---

# SHIPSTACK RULES

## Rule 1 — ShipStack Operates Through Quinn Only

All AI inference requests route through Quinn HTTP bridge at `http://127.0.0.1:8765`. Never call Anthropic directly. ShipStack calls Quinn; Quinn handles routing to Anthropic or local Ollama.

## Rule 2 — Lane: ShipStack/ is ShipStack's House

All ShipStack code and assets live in `C:\Users\integ\Documents\Claude\Projects\ShipStack\` only. Do not write files to parent folder, Quinn's folder, or anywhere else. If you need Quinn to change something, write `HANDOFF_TO_QUINN_<DATE>_<TOPIC>.md` and Quinn reads it next session.

## Rule 3 — Badge Protocol Per Tool Call

Before every tool use: call `shipstack_badge()` to get a fresh one-shot token. The badge reads `CLAUDE.md`, returns current rules + recent actions. After the tool executes, call `shipstack_log_action()` to log the result synchronously. This happens per tool, not per session.

## Rule 4 — No Direct Anthropic API Keys

No ANTHROPIC_API_KEY in any ShipStack code, env file, or config. All LLM calls go through Quinn bridge. This is auditable: `grep -r "api.anthropic.com\|ANTHROPIC_API_KEY" .` must return zero results.

## Rule 5 — HTTP Service, Not MCP

ShipStack runs on :8889 as a Python HTTP service (FastAPI / Flask / Express). It is NOT an MCP server. Quinn is the MCP server on this machine. ShipStack exposes HTTP routes; Quinn calls those routes with badge tokens in the header.

## Rule 6 — Port Registry

- **3000** — Vercel frontend (dropship-os-gamma.vercel.app)
- **8889** — ShipStack Engine (engines/shipstack_engine.py)
- **8766** — Prometheus Engine (engines/prometheus_engine.py)
- **8867** — Social AI Agent (agents/social_ai_agent.py)
- **8890** — ShipStack Dashboard (engines/shipstack_dashboard.py)
- **8765** — Quinn HTTP bridge (you call it, don't bind to it)

## Rule 7 — No Scheduled Tasks

NEVER use `Register-ScheduledTask`, `schtasks.exe /create`, or any scheduler. Global Directive #6 forbids it. If a service needs to run automatically, add it to `LAUNCH_SHIPSTACK.ps1` or similar one-click launcher.

## Rule 8 — Prometheus Ownership

Prometheus (video generation engine) is ShipStack's. Files: `prometheus_engine.py`, `prometheus_monitor.py`. Port: 8766. Update Blueprint whenever Prometheus changes. Depends on Quinn bridge for LLM calls.

## Rule 9 — Handoff Direction is ONE-WAY

Quinn writes `HANDOFF_FROM_QUINN_<DATE>.md` to `C:\Users\integ\quinn-proxy\handoff_outbox\`. You read it and reply with `HANDOFF_TO_QUINN_<DATE>.md` in `ShipStack/handoffs/`. ShipStack NEVER initiates `HANDOFF_FROM_SHIPSTACK_*` docs. The conversation flows: Quinn → ShipStack → Quinn.

## Rule 10 — Naming Conventions (Match Quinn's Standard)

- Top-level docs: `UPPER_SNAKE_CASE.md` (CLAUDE.md, BUILD_PLAN.md, SHIPSTACK_RULES.md)
- Handoffs: `HANDOFF_<DIRECTION>_<YYYY-MM-DD>[_<TOPIC>].md`
- Instructions: `INSTRUCTIONS_<DIRECTION>_<YYYY-MM-DD>_<TOPIC>.md`
- Session summaries: `SESSION_SUMMARY_<YYYY-MM-DD>.md`
- Python modules: `lower_snake_case.py`
- PowerShell scripts: `UPPER_SNAKE_CASE.ps1` (verb-first if action)
- Dates: ALWAYS ISO-8601 (`2026-06-03`). Never `JUNE_03`, never `06-03`.

## Rule 11 — UTF-8 Everywhere

First line of every Python script: `import sys; sys.stdout.reconfigure(encoding='utf-8', errors='replace')` (Global Directive #17). This prevents console output encoding errors on Windows.

## Rule 12 — Kill Before Launch

On startup, any service must kill anything stale listening on its port. Example: `netstat -ano | find "8889"` → kill the PID. Then bind fresh. No two instances fighting over the same port (Global Directive #5).

---

# BLUEPRINT — LIVE ARCHITECTURE (Reorganized 2026-06-04)

## engines/ subfolder — Core HTTP microservices

| Component | Type | File | Port | Health Check | Depends On | Status | Notes |
|-----------|------|------|------|--------------|-----------|--------|-------|
| ShipStack Engine | python | engines/shipstack_engine.py | 8889 | http://127.0.0.1:8889/health | Quinn HTTP Bridge | active | Decision + product research APIs. No badge requirement. Public endpoints. |
| Prometheus Engine | python | engines/prometheus_engine.py | 8766 | http://127.0.0.1:8766/health | Quinn HTTP Bridge | active | Video generation. Routes to Runway ML, ElevenLabs, Suno. No badge requirement. |
| Social AI Agent (root file) | python | agents/social_ai_agent.py | 8867 | http://127.0.0.1:8867/health | Quinn HTTP Bridge | active | Social media orchestration. TikTok, Instagram, Pinterest, YouTube. No badge requirement. |
| ShipStack Dashboard | python | engines/shipstack_dashboard.py | 8890 | http://127.0.0.1:8890 (self) | - | active | Real-time monitoring UI. Shows service health, recent actions, metrics. |

## agents/ subfolder — Decision & research agents

| Component | Type | File | Port | Depends On | Status | Notes |
|-----------|------|------|------|-----------|--------|-------|
| Decision Engine | python | agents/decision_engine.py | - | internal | active | Product scoring (margin, reviews, niche, competition). Callable by shipstack_engine.py. |
| Product Research | python | agents/product_research.py | - | internal | active | Supplier aggregation (Zendrop, AutoDS, AliExpress). SQLite cache, 24-hour TTL. |
| Analytics Engine | python | agents/analytics_engine.py | - | internal | active | Metrics computation from shipstack_actions.jsonl. Success rates, trends. |

## badge/ subfolder — Authentication & logging

| Component | Type | File | Port | Status | Notes |
|-----------|------|------|------|--------|-------|
| Badge System | python | badge/shipstack_badge.py | - | active | One-shot token generation. 60-second TTL. Internal use only (not gating public endpoints). |
| Action Logger | python | badge/shipstack_log_action.py | - | active | JSONL logging to logs/shipstack_actions.jsonl. Synchronous writes. |
| Config Validator | python | badge/validate_config.py | - | active | Pre-flight checks: ports available, files exist, no Anthropic API leaks. |

## frontend/ subfolder — HTML/UI

| Component | Type | File | Status | Notes |
|-----------|------|------|--------|-------|
| Main Landing | html | frontend/index.html | active | 150K. Product showcase. |
| Launcher OS | html | frontend/launcher_os.html | active | Desktop launcher widget. Links to all 4 services. |
| Privacy Policy | html | frontend/privacy.html | active | Legal compliance. |
| Thank You | html | frontend/thank-you.html | active | Post-conversion. |
| Metrics Store | json | frontend/metrics.json | active | Analytics dashboard data. |

## scripts/ subfolder — Launchers & deployment

| Component | Type | File | Status | Notes |
|-----------|------|------|--------|-------|
| LAUNCH_SHIPSTACK.ps1 | powershell | scripts/LAUNCH_SHIPSTACK.ps1 | active | Kills old processes on 8889/8766/8867/8890. Starts all 4 services. |
| DEPLOY.ps1 | powershell | scripts/DEPLOY.ps1 | active | Deployment orchestration. |
| PUSH_SHIPSTACK_TO_GITHUB.ps1 | powershell | scripts/PUSH_SHIPSTACK_TO_GITHUB.ps1 | active | Git push. |
| set_vercel_envs.py | python | scripts/set_vercel_envs.py | active | Configure Vercel environment. |
| consolidate_shipstack_env.py | python | scripts/consolidate_shipstack_env.py | active | Merge env vars. |

## docs/ subfolder — Documentation

| Component | Type | File | Status |
|-----------|------|------|--------|
| BUILD_PLAN.md | markdown | docs/BUILD_PLAN.md | active |
| SYSTEM_ARCHITECTURE.md | markdown | docs/SYSTEM_ARCHITECTURE.md | active |
| QUICKSTART.md | markdown | docs/QUICKSTART.md | active |
| BADGE_PROTOCOL_EXAMPLE.md | markdown | docs/BADGE_PROTOCOL_EXAMPLE.md | active |
| (7 others) | markdown | docs/*.md | active |

## Preserved subdirectories (not reorganized)

| Folder | Purpose | Status |
|--------|---------|--------|
| api/ | Vercel serverless functions | active |
| social_ai_agent/ | Full social AI implementation tree | active |
| integrations/ | Supplier/platform connectors | active |
| content_pipeline/ | Content generation pipeline | active |
| pinterest_agent/ | Pinterest-specific automation | active |
| dropship-agent/ | Dropship research agent | active |
| roi-product-finder/ | ROI calculation | active |
| landing-pages/ | Marketing pages | active |
| decision-engine/ | Scoring engine (with dash) | active |
| asset_machine/ | Asset generation | active |
| prometheus_output/ | Video output storage | active |
| shipstack-privacy/ | Privacy docs | active |
| data/ | Data cache | active |
| logs/ | Runtime logs | active |

---

# QUARANTINE REGISTRY

| Original File | Quarantined As | Date | Reason | Replaced By |
|---------------|---------------|------|--------|-------------|
| _(empty — populated during cleanup)_ | | | | |

---

# DIRECTORIES — WHERE THINGS LIVE

| Purpose | Path |
|---------|------|
| Active ShipStack code | `C:\Users\integ\Documents\Claude\Projects\ShipStack\` |
| Core engines | `C:\Users\integ\Documents\Claude\Projects\ShipStack\engines\` |
| Decision agents | `C:\Users\integ\Documents\Claude\Projects\ShipStack\agents\` |
| Badge/auth | `C:\Users\integ\Documents\Claude\Projects\ShipStack\badge\` |
| Frontend HTML | `C:\Users\integ\Documents\Claude\Projects\ShipStack\frontend\` |
| Launch scripts | `C:\Users\integ\Documents\Claude\Projects\ShipStack\scripts\` |
| Documentation | `C:\Users\integ\Documents\Claude\Projects\ShipStack\docs\` |
| Quinn handoffs | `C:\Users\integ\Documents\Claude\Projects\ShipStack\handoffs\` |
| Test suites | `C:\Users\integ\Documents\Claude\Projects\ShipStack\tests\` |
| Archive/backup | `C:\Users\integ\Documents\Claude\Projects\ShipStack\_archive\` |
| Runtime logs | `C:\Users\integ\Documents\Claude\Projects\ShipStack\logs\` |

---

# THINGS THAT ARE DELETED FOREVER — DO NOT RECREATE

- Quinn-owned files (seed_strategy_books.py, sync_cowork_sessions.py, quinn_fs_interceptor.py, verify_qdrant_partitions.py, ingest_now.py)
- Scheduled task scripts (SCHEDULE_DAILY.ps1, SCHEDULE_CALENDAR.ps1)
- Prometheus ownership in Quinn (moved to ShipStack 2026-06-03)
- MCP server attempt (shipstack_mcp.py — ShipStack is HTTP, not MCP)
- Direct Claude Code modifications (disable_claude_code.ps1 and variants)

---

# GUARDRAILS — IN EFFECT 2026-06-03

## Badge Protocol (B1)

Every tool call requires a fresh badge token from `shipstack_badge()`. The badge is one-shot, expires in 60 seconds, and cannot be reused. Tokens are validated before tool execution; missing or expired tokens cause a 403 Forbidden response.

## Action Logging (B2)

Every tool execution logs to `dropship-os/logs/shipstack_actions.jsonl` (JSONL format). Log entry includes: timestamp, tool_name, action, target, result summary, badge_token (last 8 chars). Synchronous: log write completes before next tool begins.

## Secret Scanner (B3)

Do not commit API keys, passwords, or secrets. If a secret is found in code (sk-ant-, sk_live_, ghp_, etc.), the file write/edit refuses. Exception: .env and .env.local files are exempt from scan (they are git-ignored).

## Rate Limits (B4)

Currently unlimited for ShipStack tools (no gates). If abuse patterns emerge, rate limits will be added. Check via `shipstack_show_rate_limits()` (future tool).

## Directories Rule (B5)

All ShipStack files must live under `C:\Users\integ\Documents\Claude\Projects\ShipStack\`. Writes outside this directory refuse with a path validation error. Path validation uses `startswith(ShipStack_path)`.

---

# CHANGELOG

| Date | Change |
|------|--------|
| 2026-06-04 | v1.1 — Blueprint updated post-reorg. New structure: engines/, agents/, badge/, frontend/, scripts/, docs/, handoffs/, tests/, _archive/. Old `dropship-os/` subdir removed. Folder renamed `Drop shipping/` → `ShipStack/`. Path updated in Rules 2-4, 9. All file references corrected. |
| 2026-06-03 | v1.0 — initial CLAUDE.md for ShipStack. Blueprint, rules, guardrails established. Tier 0 cleanup complete. |

---

# NEXT STEPS

- **Tier 1 (in progress):** Rewrite SHIPSTACK_RULES.md (already done), rewrite SHIPSTACK_DIRECTIVES.md, audit .env/.gitignore
- **Tier 2:** Build badge system (shipstack_badge.py, shipstack_log_action.py)
- **Tier 3:** ShipStack engine on :8889
- **Tier 4:** Prometheus on :8766
- **Tier 5:** Social AI integration
- **Tier 6:** Dashboard
- **Tier 7:** Optional file/command tools (skip unless real use case)
- **Tier 8:** Verification + smoke tests
