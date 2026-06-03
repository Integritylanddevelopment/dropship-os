# ShipStack Agent Guardrails - Your Lanes, Your House

**Author:** Quinn agent
**Date:** 2026-06-02
**Audience:** Every ShipStack agent (Cowork, Continue, sub-agent, future-you)
**Read this first. Before any tool call.**

---

# THE GOLDEN RULE

**ShipStack and Quinn are separate projects with one-way dependency.**

- ShipStack depends on Quinn (uses Quinn's services).
- Quinn does NOT depend on ShipStack.
- ShipStack lives in ITS folder. Quinn lives in ITS folder. Neither agent edits the other's files.

If you break this rule, both projects die together the next time something changes.

---

# YOUR HOUSE (where you live, what you control)

## Your project root

```
C:\Users\integ\Documents\Claude\Projects\Drop shipping\dropship-os\
```

This is YOUR folder. You can:
- Create any file here
- Edit any file here
- Delete any file here (carefully - ask Alex for destructive ops)
- Add subdirectories as needed
- Keep all ShipStack source code, configs, docs, tests, logs here

## Your canonical files (create these if they don't exist)

| File | Purpose |
|---|---|
| `dropship-os/CLAUDE.md` | Your project's working memory. ShipStack-specific rules, blueprint, current state. See template below. |
| `dropship-os/SHIPSTACK_DIRECTIVES.md` | Your project's directives (the ShipStack equivalent of Quinn's GLOBAL_DIRECTIVES.md). See template below. |
| `dropship-os/HANDOFF_FROM_QUINN.md` | Already exists - what Quinn handed you on 2026-06-02. Read this. |
| `dropship-os/HANDOFF_TO_QUINN.md` | Write this at end of each ShipStack session. Quinn agent reads it next time. |
| `dropship-os/shipstack_engine.py` | The engine on port 8889. TIER 2.2 task. |
| `dropship-os/logs/` | Your runtime logs. Quinn's logs are in quinn-proxy/logs/. Keep them separate. |
| `dropship-os/.env` | ShipStack secrets (Stripe, Shopify, etc.). NEVER the Anthropic key - that lives only in Quinn. |

---

# QUINN'S HOUSE (where you DO NOT live)

## Folders you must never edit

```
C:\Users\integ\quinn-proxy\                              <- Quinn's core repo
C:\Users\integ\.chatgpt-copilot\context_injection_agent\  <- Quinn's Chroma store + context engine
```

P1 guardrails in Quinn's MCP server will REFUSE most edits to these paths via `quinn_edit_file` / `quinn_write_file`. But Cowork's built-in `Edit`/`Write` host tools BYPASS Quinn's guardrails. So the rule has to live in your head, not just in code.

## Specific files you must never touch (even via host tools)

- `quinn-proxy/CLAUDE.md`
- `quinn-proxy/GLOBAL_DIRECTIVES.md`
- `quinn-proxy/.env`
- `quinn-proxy/quinn_mcp/server.py`
- `quinn-proxy/quinn_http_bridge.py`
- `quinn-proxy/quinn_dashboard.py`
- `quinn-proxy/mirror_sync.py`
- `quinn-proxy/LAUNCH_QUINN.ps1`
- `quinn-proxy/LAUNCH_EVERYTHING.pyw`
- `quinn-proxy/RESTART_QUINN.ps1`
- `quinn-proxy/SHUTDOWN_ALL.ps1`
- `quinn-proxy/blueprint.py`
- `quinn-proxy/cowork_session_ingest.py`
- `.chatgpt-copilot/context_injection_agent/context_search.py`
- `.chatgpt-copilot/context_injection_agent/CLAUDE.md`
- Anything in `quinn-proxy/.backups/`
- Anything in `quinn-proxy/logs/`

## Quinn's runtime you must never touch

- Do NOT `Stop-Process` Quinn MCP, bridge :8765, or dashboard :8888
- Do NOT `docker stop` qdrant or ollama containers
- Do NOT modify Chroma collections directly
- Do NOT call Qdrant collections starting with `quinn_*`, `project_quinn_stack`, `global_directives`, or `commandcore_*` for write operations - those are Quinn's
- You CAN read from any Qdrant collection. You can write to `project_ship_stack_ai`.

---

# HOW TO COMMUNICATE WITH QUINN (the right way)

When ShipStack needs something from Quinn, there are FOUR legitimate channels. Use them in this order of preference:

## Channel 1: HTTP Bridge (best - no Quinn agent involvement needed)

`http://127.0.0.1:8765` - always running, no auth, local-only.

```python
import httpx
# Free local LLM inference (no Anthropic burn)
r = httpx.post('http://127.0.0.1:8765/chat', json={
    'messages': [{'role':'user','content':'classify viral: ' + product_description}],
    'model': 'llama3.2:3b'
}, timeout=30)

# Free local embeddings
r = httpx.post('http://127.0.0.1:8765/embed', json={'texts': [product_listing]})

# Search Quinn knowledge (for cross-project context)
r = httpx.post('http://127.0.0.1:8765/search', json={'query':'...', 'project':'ship_stack_ai'})
```

## Channel 2: Quinn MCP tools (when you're a Claude agent in Cowork/Continue)

Use `quinn_search`, `quinn_chat`, `quinn_add_context`, `quinn_web_fetch`, etc. Always pass `project='ship_stack_ai'` when relevant. Badge token required per Quinn's Directive #4.

## Channel 3: Write knowledge into Quinn for next session

```
quinn_add_context(
    project='ship_stack_ai',   # MUST pass this explicitly
    section='decisions',        # or 'engine', 'integrations', 'tests', etc
    content='2026-06-02 decided to use Hormozi viral-classification heuristic for first pass; fall back to LLM only on ambiguous products'
)
```

This appends to `.chatgpt-copilot/context_injection_agent/projects/ship_stack_ai.md` (a Quinn file you may NOT edit directly - the tool does it for you), then mirror_sync re-embeds it into Chroma so future searches find it.

## Channel 4: HANDOFF_TO_QUINN.md (for things Quinn agent needs to do)

If ShipStack needs Quinn to do something - add a new endpoint to the bridge, change a Quinn directive, add a new MCP tool - DO NOT do it yourself. Write the request in `HANDOFF_TO_QUINN.md` at end of session. Quinn agent reads it next session and decides.

Example HANDOFF_TO_QUINN.md entry:

```markdown
## Open requests for Quinn agent

- ShipStack needs a `/classify_product` endpoint on Quinn HTTP bridge that wraps the local Ollama call with our viral-detection system prompt. Currently we're sending the system prompt every call, wasting tokens. Proposed signature: POST /classify_product {product_description, supplier_url} -> {viral_score: 0-1, reasoning, suggested_price}
- ShipStack hit a rate limit on quinn_web_fetch when scraping competitor sites. Can we get a quinn_web_fetch_bulk or higher limit?
```

---

# YOUR CLAUDE.md TEMPLATE (write this first)

Create `dropship-os/CLAUDE.md` with this skeleton:

```markdown
# SHIPSTACK PROJECT DIRECTIVE

**Owner:** Alex Alexander
**Project:** ShipStack AI
**Last updated:** YYYY-MM-DD
**Depends on:** Quinn (C:\Users\integ\quinn-proxy\) - see HANDOFF_FROM_QUINN.md

---

# READ BEFORE EVERY TOOL CALL

This document is the ShipStack-specific rules layer on top of Quinn's 17 Global Directives. Quinn's rules apply universally. ShipStack's rules apply only inside this project.

Order of precedence:
1. Quinn Global Directives (read via quinn_badge())
2. ShipStack Directives (this file + SHIPSTACK_DIRECTIVES.md)
3. Common sense

---

# SHIPSTACK BLUEPRINT

| Component | Type | File | Port | Status | Notes |
|---|---|---|---|---|---|
| ShipStack Engine | python | shipstack_engine.py | 8889 | planned | TIER 2.2 |
| Vercel deployment | web | dropship-os-gamma.vercel.app | - | active | live |
| ShipStack CLI | python | shipstack_cli.py | - | planned | |
| ... add rows as you build ... | | | | | |

---

# SHIPSTACK GUARDRAILS

## File scope
- ALL ShipStack code lives under C:\Users\integ\Documents\Claude\Projects\Drop shipping\dropship-os\
- NEVER edit anything in C:\Users\integ\quinn-proxy\
- NEVER edit anything in C:\Users\integ\.chatgpt-copilot\
- NEVER edit any file listed in SHIPSTACK_DIRECTIVES.md "Quinn protected files" section

## AI inference
- ALL LLM calls route through http://127.0.0.1:8765/chat (Quinn HTTP bridge)
- NEVER include ANTHROPIC_API_KEY in ShipStack code or env
- NEVER call api.anthropic.com directly

## Service operations
- Kill-before-launch: when starting shipstack_engine.py, first kill anything on 8889
- All Python scripts: sys.stdout.reconfigure(encoding='utf-8', errors='replace') at top
- All spawned PowerShell windows: -WindowStyle Hidden
- No Windows scheduled tasks (Quinn Directive #6 applies)

## Knowledge management
- Write decisions back to Quinn: quinn_add_context(project='ship_stack_ai', ...)
- Search Quinn before asking Alex: quinn_search(query, project='ship_stack_ai')
- This file (CLAUDE.md) is the source of truth for ShipStack rules
- The dropship-os/ folder mirrors what's in Quinn's project_ship_stack_ai bucket

## Deployment
- Vercel deployment via API not CLI (CLI times out per global rule)
- Stripe + Shopify keys in dropship-os/.env (gitignored)
- Vercel env vars set via Vercel API, not committed

---

# CHANGELOG

| Date | Change |
|---|---|
| YYYY-MM-DD | Initial CLAUDE.md created from template |

```

---

# YOUR SHIPSTACK_DIRECTIVES.md TEMPLATE

Create `dropship-os/SHIPSTACK_DIRECTIVES.md` with these starter directives. Add more as you discover patterns.

```markdown
# SHIPSTACK DIRECTIVES

**Owner:** Alex Alexander
**Version:** 1.0
**Last updated:** YYYY-MM-DD

These directives apply to every ShipStack agent. They are IN ADDITION to Quinn's 17 Global Directives (which apply universally). When in conflict, Quinn directives win.

---

## 1. ShipStack Depends on Quinn, Not Reverse

ShipStack code may CALL Quinn services. ShipStack code may NEVER edit Quinn files or modify Quinn runtime.

## 2. All AI Through Quinn Bridge

Every LLM inference call goes to http://127.0.0.1:8765/chat. ShipStack never holds ANTHROPIC_API_KEY. Stripe, Shopify, supplier APIs - those keys live in dropship-os/.env. AI keys do not.

## 3. Knowledge Goes Back to Quinn

Every non-trivial decision: quinn_add_context(project='ship_stack_ai', section=..., content=...). This builds the ShipStack memory that next session inherits.

## 4. Vercel via API, Not CLI

Vercel CLI times out from this machine. Use vercel_api_deploy.js or quinn_vercel_deployments MCP tool.

## 5. Port 8889 Belongs to ShipStack Engine

Claimed in Quinn Blueprint. Kill-before-launch when starting. No other ShipStack process binds 8889.

## 6. Tests Live Beside Code

tests/ folder next to source. Run before every commit. CI is not yet set up - manual discipline.

## 7. Logs to dropship-os/logs/, Not Anywhere Else

Never write logs to %TEMP%, %APPDATA%, or quinn-proxy/logs/. ShipStack logs in ShipStack folder.

## 8. Secrets via .env, Never Hardcoded

Load with python-dotenv. .env is gitignored. .env.example with placeholder values is committed.

## 9. Quinn Protected Files (DO NOT EDIT)

- C:\Users\integ\quinn-proxy\** (ENTIRE TREE)
- C:\Users\integ\.chatgpt-copilot\** (ENTIRE TREE)
- Any file matching pattern: *quinn*, *chroma_db*, *qdrant_storage* outside dropship-os/

## 10. End Every Session With HANDOFF_TO_QUINN.md

Quinn agent reads it next session. Don't lose context across handoffs.

```

---

# WHERE EVERYTHING LIVES (cheat sheet)

## ShipStack files (YOU OWN)
```
C:\Users\integ\Documents\Claude\Projects\Drop shipping\dropship-os\
  CLAUDE.md                        <- your project rules
  SHIPSTACK_DIRECTIVES.md          <- your directives layer
  HANDOFF_FROM_QUINN.md            <- Quinn handed this to you
  HANDOFF_TO_QUINN.md              <- write at end of session
  shipstack_engine.py              <- TIER 2.2 build target
  .env                             <- ShipStack secrets only (NEVER Anthropic)
  .env.example                     <- committed placeholder
  .gitignore                       <- ignore .env, logs/, node_modules/, __pycache__/
  requirements.txt                 <- Python deps
  package.json                     <- if any JS
  README.md                        <- user-facing docs
  logs/                            <- your runtime logs
  src/                             <- source code
  tests/                           <- tests beside src
  scripts/                         <- one-off utility scripts
  vercel.json                      <- Vercel config
```

## Quinn files (HANDS OFF)
```
C:\Users\integ\quinn-proxy\
  CLAUDE.md                        <- Quinn's rules (READ via quinn_badge, NEVER edit)
  GLOBAL_DIRECTIVES.md             <- Quinn's directives (READ via quinn_badge, NEVER edit)
  quinn_mcp/server.py              <- DO NOT EDIT
  quinn_http_bridge.py             <- DO NOT EDIT, but CALL freely on :8765
  quinn_dashboard.py               <- DO NOT EDIT
  ... everything else ...          <- DO NOT EDIT

C:\Users\integ\.chatgpt-copilot\context_injection_agent\
  CLAUDE.md                        <- DO NOT EDIT
  context_search.py                <- DO NOT EDIT
  chroma_db/                       <- DO NOT TOUCH (Chroma store)
  projects/ship_stack_ai.md        <- DO NOT EDIT DIRECTLY (use quinn_add_context)
```

## Shared infrastructure (READ ONLY for ShipStack)
```
Qdrant (Docker, port 6333)        <- READ from any collection, WRITE only to project_ship_stack_ai
Ollama (Docker, port 11434)       <- USE via Quinn bridge, do not invoke directly
ChromaDB (embedded)               <- USE via Quinn MCP, do not write directly
```

---

# WHEN YOU'RE TEMPTED TO BREAK A RULE

## "I just need to fix one small thing in quinn-proxy..."

No. Write it in HANDOFF_TO_QUINN.md. Quinn agent will do it next session, properly, with the right guardrails. Your shortcut becomes Quinn's bug.

## "Quinn is down and I need to deploy now..."

Deploy without LLM features. Or wait. ShipStack must degrade gracefully when Quinn is unavailable. NEVER add the Anthropic API key to ShipStack as a fallback - that breaks Directive #3 forever.

## "It's faster to just embed the Anthropic key here..."

No. The cost of one leaked key (revoked key, account suspension, $50k bill from abuse) is way higher than the latency of routing through Quinn. Single source of truth for AI auth = Quinn.

## "I want to share Quinn's vector store directly..."

Use Quinn's bridge or MCP tools. They wrap the same data with logging, rate-limits, project-scoping. Direct Qdrant/Chroma access from ShipStack = uncontrolled blast radius.

## "I need to test something that requires Quinn to behave differently..."

Write the test scenario in HANDOFF_TO_QUINN.md. Or mock Quinn's bridge in your tests. Never modify real Quinn for a ShipStack test.

---

# FIRST 30 MINUTES OF YOUR NEXT SESSION

1. Read this entire doc.
2. Read HANDOFF_FROM_QUINN.md.
3. Call `quinn_badge()` to load Quinn's 17 directives into your working context.
4. Check if `dropship-os/CLAUDE.md` exists. If not, create it from the template above. Fill in real Blueprint rows for what exists today.
5. Check if `dropship-os/SHIPSTACK_DIRECTIVES.md` exists. If not, create it from the template. Customize the rules to ShipStack's reality.
6. Run `quinn_search(query='shipstack current state', project='ship_stack_ai')` - see what Quinn already knows about ShipStack from the 530-chunk bucket.
7. Ask Alex what TIER 2.2 should specifically do (endpoints, playbooks).
8. Start building shipstack_engine.py with all the guardrails baked in.

---

# AT END OF EVERY SESSION

1. Update `dropship-os/CLAUDE.md` Blueprint with any new components.
2. Write/append `dropship-os/HANDOFF_TO_QUINN.md` with:
   - What you built/changed
   - Any open requests for Quinn agent
   - Any decisions you logged via quinn_add_context
   - Any unresolved blockers
3. Run `quinn_add_context(project='ship_stack_ai', section='session_summary', content='YYYY-MM-DD: ...summary...')` so the knowledge persists in Quinn too.
4. Commit changes to dropship-os git repo (Quinn auto-backup hourly handles backup).

---

**You are the ShipStack agent. dropship-os/ is your house. Quinn is your neighbor. Don't walk into their house. Don't let them walk into yours. Build ShipStack. Ship it.**

-- Quinn agent, handing you the keys 2026-06-02
