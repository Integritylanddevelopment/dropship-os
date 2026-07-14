# SHIPSTACK DIRECTIVES

**Owner:** ShipStack agent
**Last updated:** 2026-06-03
**Document version:** 1.0

---

# CRITICAL PREAMBLE

**The 17 Quinn Global Directives apply VERBATIM to ShipStack and CANNOT be overridden by anything in this file.** Call `quinn_badge()` to read them in full. The rules below are ShipStack-specific additions that layer on top of, and narrow, the globals.

---

# SHIPSTACK DIRECTIVE 1: Quinn-First, No Direct Anthropic

All ShipStack AI requests route through Quinn HTTP bridge at `http://127.0.0.1:8765`. Never import `anthropic`, never call `api.anthropic.com` directly, never set `ANTHROPIC_API_KEY` in ShipStack code or env files. Quinn handles all LLM routing.

---

# SHIPSTACK DIRECTIVE 2: Badge Per Tool

Before every tool call (reading files, writing files, running commands, calling external APIs):
1. Call `shipstack_badge()` to get a fresh one-shot token
2. Execute the tool with the token in the header or body
3. Call `shipstack_log_action()` to log the result

The badge is single-use. Expired or consumed tokens refuse with 403. This enforces that ShipStack agents stay aware of current rules (Global Directive #4).

---

# SHIPSTACK DIRECTIVE 3: Lane = dropship-os/ Only

All ShipStack files live in `C:\Users\integ\Documents\Claude\Projects\Drop shipping\dropship-os\` and nowhere else. Files written outside this path refuse with a path validation error. If you need to ask Quinn for something, write `HANDOFF_TO_QUINN_<DATE>_<TOPIC>.md` inside dropship-os/ and Quinn reads it next session.

---

# SHIPSTACK DIRECTIVE 4: HTTP Service, Not MCP

ShipStack runs as an HTTP service on :8889 (or another claimed port). It is NOT an MCP server. Quinn is the MCP server; ShipStack exposes HTTP routes. Quinn calls ShipStack's routes. Architectural boundary: MCP = Quinn only, HTTP = ShipStack's interface.

---

# SHIPSTACK DIRECTIVE 5: Kill Before Launch

On startup, before binding to any port, kill anything stale already listening on that port. Example:
```powershell
netstat -ano | find ":8889" | ForEach-Object { taskkill /PID (($ -split '\s+')[-1]) /F }
```
Then bind fresh. This prevents "address already in use" errors and ensures no ghost processes from prior crashes (Global Directive #5).

---

# SHIPSTACK DIRECTIVE 6: No Scheduled Tasks

NEVER use `Register-ScheduledTask`, `schtasks.exe /create`, or any Windows Task Scheduler. Scheduled tasks cause respawn chaos when services die unexpectedly. If a service needs automatic startup, add it to `LAUNCH_SHIPSTACK.ps1` or a similar one-click launcher (Global Directive #6).

---

# SHIPSTACK DIRECTIVE 7: Naming Conventions

Follow Quinn's standard exactly:
- Top-level docs: `UPPER_SNAKE_CASE.md` (CLAUDE.md, BUILD_PLAN.md, SHIPSTACK_DIRECTIVES.md)
- Handoffs: `HANDOFF_<DIRECTION>_<YYYY-MM-DD>[_<TOPIC>].md` (direction = FROM_QUINN or TO_QUINN)
- Instructions: `INSTRUCTIONS_<DIRECTION>_<YYYY-MM-DD>_<TOPIC>.md`
- Session summaries: `SESSION_SUMMARY_<YYYY-MM-DD>.md`
- Python modules: `lower_snake_case.py`
- PowerShell scripts: `UPPER_SNAKE_CASE.ps1` (verb-first: LAUNCH_SHIPSTACK.ps1, DEPLOY_GARYVEE_DASHBOARD.ps1)
- Dates: ALWAYS ISO-8601 (`2026-06-03`). Never `JUNE_03`. Never `06-03`.

---

# SHIPSTACK DIRECTIVE 8: Handoff Direction is ONE-WAY

Quinn writes `HANDOFF_FROM_QUINN_<DATE>.md` to dropship-os/. You read it. You reply with `HANDOFF_TO_QUINN_<DATE>.md` in the same folder. ShipStack NEVER originates `HANDOFF_FROM_SHIPSTACK_*` documents. The flow is: Quinn → (writes handoff) → ShipStack → (reads, replies) → Quinn.

---

# SHIPSTACK DIRECTIVE 9: UTF-8 Everywhere

First line of every Python script:
```python
import sys
sys.stdout.reconfigure(encoding='utf-8', errors='replace')
```
This prevents Windows console encoding errors that break logging and output (Global Directive #17).

---

# SHIPSTACK DIRECTIVE 10: Port Registry

Claim your ports and document them in CLAUDE.md Blueprint:
- **8889** — ShipStack engine (HTTP service)
- **8766** — Prometheus video generation
- **3000** — Vercel frontend (already claimed)
- **8765** — Quinn HTTP bridge (do not bind to this; you call it)

Two services cannot share a port. Add Blueprint rows for every service you run.

---

# SHIPSTACK DIRECTIVE 11: Prometheus Ownership

Prometheus (video generation engine) is ShipStack's as of 2026-06-03. You own:
- Files: prometheus_engine.py, prometheus_monitor.py, prometheus.py
- Port: 8766 (claimed)
- Dependencies: Quinn HTTP bridge for LLM calls
- Update CLAUDE.md Blueprint whenever Prometheus changes

---

# SHIPSTACK DIRECTIVE 12: No Leak Channels

No ANTHROPIC_API_KEY in ShipStack code, .env files, or config. All LLM inference goes through Quinn bridge. This is auditable:
```powershell
Get-ChildItem 'dropship-os' -Recurse -File | Select-String 'ANTHROPIC_API_KEY|sk-ant-|api.anthropic.com' -List
```
Zero results = compliant.

---

# SHIPSTACK DIRECTIVE 13: Action Logging

Every tool call logs synchronously to `dropship-os/logs/shipstack_actions.jsonl` (JSONL format). Log entry:
```json
{"timestamp": "2026-06-03T12:34:56Z", "tool_name": "read_file", "action": "read", "target": "/path", "result": "success", "summary": "...", "badge_token": "badge-xxx..."}
```
Append-only, never edit existing entries.

---

# SHIPSTACK DIRECTIVE 14: Prometheus & Social AI Depend on ShipStack Engine

Prometheus and Social AI agents call ShipStack engine routes (via HTTP on :8889). ShipStack engine calls Quinn bridge for LLM inference. The dependency chain is: Prometheus → ShipStack engine → Quinn bridge. No cross-calling between Prometheus and Social AI. All AI requests flow through ShipStack engine.

---

# SHIPSTACK DIRECTIVE 15: .gitignore Must Protect Secrets

ShipStack's `.gitignore` must include:
```
.env
.env.local
.env.production
.env.*.local
logs/
__pycache__/
*.pyc
.vercel/
node_modules/
```
No `.env*` files committed. Secrets stay in .env.local only (git-ignored).

---

# SHIPSTACK DIRECTIVE 16: Vercel Env Vars ≠ Local .env

Vercel environment variables (STRIPE_SECRET_KEY, ANTHROPIC_API_KEY in Vercel deployments) are managed separately from local .env. Local ShipStack never has ANTHROPIC_API_KEY. Vercel frontend gets it via Vercel secrets, routed through Quinn bridge in Vercel functions if needed.

---

# SHIPSTACK DIRECTIVE 17: Terminal Windows Must Minimize

Any PowerShell script that spawns a window must minimize it on launch (Global Directive #13):
```powershell
$ErrorActionPreference = 'SilentlyContinue'
try {
  Add-Type -Name W -Namespace P -MemberDefinition '[DllImport("user32.dll")] public static extern bool ShowWindow(int h, int s);' -ErrorAction SilentlyContinue
  $h = (Get-Process -Id $PID).MainWindowHandle
  if ($h -ne 0) { [P.W]::ShowWindow($h, 6) | Out-Null }
} catch {}
```
Or use `-WindowStyle Hidden` for `Start-Process` calls. No stray PowerShell windows piling up on the desktop.

---

# CHANGELOG

| Date | Change |
|------|--------|
| 2026-06-03 | v1.0 — initial SHIPSTACK_DIRECTIVES.md. 17 directives codifying Quinn Global Directives + ShipStack-specific rules. |

---

**Read the Quinn Global Directives via `quinn_badge()` for the complete foundation.** These directives layer on top and do not replace them.
