# ShipStack — Current Goal

## MISSION
ShipStack = an AI-powered dropshipping product discovery and content engine.
Find winning products. Generate content. Automate the pipeline.
Built on Quinn's local inference stack — Quinn does the AI, ShipStack uses the answers.

## RULE: SHIPSTACK ADAPTS TO QUINN
ShipStack calls Quinn at http://127.0.0.1:8765. It does not modify Quinn.
If ShipStack needs something Quinn doesn't do, ask Alex before touching anything in quinn-proxy.

## CURRENT STATE
- Quinn bridge confirmed at :8765 (local inference running)
- ShipStack folder: C:\Users\integ\Documents\Claude\Projects\ShipStack
- Prior Qdrant knowledge: dropship_intel (261 pts) + project_ship_stack_ai (271 pts)
- Engines: shipstack_engine :8889, dashboard :8890, social_ai_agent :8867, prometheus :8766
- Vercel frontend: dropship-os-gamma.vercel.app (live)

## NEXT ACTION
Begin new ShipStack development session from the ShipStack folder.
Do NOT open quinn-proxy in this session.
