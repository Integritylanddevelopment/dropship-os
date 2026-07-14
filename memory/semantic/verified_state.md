# ShipStack Verified State

## Infrastructure
- Quinn bridge: http://127.0.0.1:8765 (confirmed running as of 2026-06-15)
- ShipStack folder: C:\Users\integ\Documents\Claude\Projects\ShipStack
- ShipStack logs: C:\Users\integ\Documents\Claude\Projects\ShipStack\logs\
- LAUNCH_SHIPSTACK.pyw: fixed 2026-06-15 to use ShipStack .env + ShipStack logs

## Prior Data in Qdrant (shared, do not delete)
- dropship_intel: 261 points — product research
- project_ship_stack_ai: 271 points — ShipStack decisions and context

## Services
- :8889 ShipStack Engine
- :8890 ShipStack Dashboard
- :8891 Pipeline Dashboard
- :8867 Social AI Agent
- :8766 Prometheus Engine
- Vercel: dropship-os-gamma.vercel.app

## Separation from Quinn (confirmed 2026-06-15)
- LAUNCH_SHIPSTACK no longer loads quinn-proxy/.env
- LAUNCH_SHIPSTACK writes logs to ShipStack/logs/ not Quinn/logs/
- ShipStack CLAUDE.md has session folder rule at top
- 12 stale ShipStack log files removed from Quinn/logs/
