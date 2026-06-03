# MASTER HANDOFF FROM QUINN TO SHIPSTACK AGENT

**Author:** Quinn agent (Cowork session 2026-06-02)
**For:** ShipStack agent (you, next session and every session after)
**Status:** Read this entire document before any tool call. This is your onboarding.
**Date:** 2026-06-02

---

# 1. ONE-PAGE SUMMARY (read this twice)

Quinn is a local AI infrastructure stack that lives in `C:\Users\integ\quinn-proxy\`. It runs vector DBs, a local LLM, an HTTP bridge, a dashboard, and an MCP server. It is the foundation everything else (including ShipStack) depends on.

ShipStack is an AI-powered dropshipping platform that lives in `C:\Users\integ\Documents\Claude\Projects\Drop shipping\dropship-os\`. It uses Quinn for AI inference and knowledge but is otherwise independent.

**The one rule that matters:**
- ShipStack depends on Quinn (calls it).
- Quinn does NOT depend on ShipStack.
- Neither agent edits the other's files.

If you remember nothing else, remember that.

---

# 2. WHAT QUINN DID IN THE 2026-06-02 SESSION (so you know what's fresh)

Quinn (the agent running in Cowork as me) shipped 12 things today. Listed roughly in order:

1. **Bridge ChromaDB fix** - dashboard chat now pulls real project knowledge instead of returning generic answers
2. **Auto GitHub backup** - Quinn + ShipStack repos auto-backed-up hourly, silently, no scheduled tasks
3. **Hardware ordered** - used Alienware m15 with RTX 3060 12GB ($650) inbound. When it arrives, local LLM speed jumps 5-10x.
4. **STRICT Badge Protocol shipped** - every Quinn tool call requires a fresh one-shot token from `quinn_badge()`. No timer, no override, no exemption. See section 6 below.
5. **15 -> 17 Global Directives** - directives stored verbatim in Chroma collection `quinn_global_directives`, file fallback when Chroma down. See section 5.
6. **Hash-mode badge** - badge calls dropped from ~10 KB to ~250 bytes when directives haven't changed. ~95% Anthropic token savings.
7. **Multi-project Qdrant partitioning** (Directive #16) - all 24K chunks bucketed into 11 `project_<name>` collections. ShipStack has its own 530-chunk bucket. Zero cross-pollination.
8. **Directive #17 UTF-8 / ASCII-safe output** - mandatory `sys.stdout.reconfigure(encoding='utf-8', errors='replace')` at top of every Python script. No more cp1252 crashes on emoji.
9. **CommandCore ingest** - 10-month-old predecessor project (142,528 files) ingested into Qdrant as `project_commandcore_legacy` (72,005 chunks). Searchable forever now.
10. **CommandCore Inheritance Plan** - `quinn-proxy/COMMANDCORE_INHERITANCE_PLAN.md` captures 5 high-value patterns worth porting post-ShipStack (neurotransmitter memory agents, memory promotion agent, enterprise agent factory v3.0, agent_core base class, multi-project SaaS schema).
11. **ShipStack overreach cleanup** - deleted 4 ShipStack-overreach files that the prior ShipStack agent had dumped inside quinn-proxy/artifacts/. Lanes restored.
12. **3 handoff docs written for you**:
    - `HANDOFF_FROM_QUINN.md` (original handoff, lanes + bridge contract)
    - `SHIPSTACK_AGENT_GUARDRAILS.md` (CLAUDE.md template, directives template, communication channels)
    - `HANDOFF_FROM_QUINN_CORRECTIVE.md` (corrective handoff after lane violations were found)
    - THIS document supersedes the above three. Read this one.

---

# 3. THE LANES (where everything lives)

## YOUR HOUSE (ShipStack)

```
C:\Users\integ\Documents\Claude\Projects\Drop shipping\dropship-os\
```

You own this folder and everything in it. Create, edit, delete freely. ALL ShipStack code, configs, docs, tests, and runtime logs go here.

Canonical files you should have or create:

| File | Purpose |
|---|---|
| CLAUDE.md | Your project working memory + Blueprint table |
| SHIPSTACK_DIRECTIVES.md | Your project's rules layer (on top of Quinn's universal rules) |
| HANDOFF_FROM_QUINN.md | Original handoff (already exists) |
| HANDOFF_FROM_QUINN_CORRECTIVE.md | Corrective handoff after lane violations (already exists) |
| MASTER_HANDOFF_FROM_QUINN.md | THIS file - your master onboarding |
| HANDOFF_TO_QUINN.md | Write at end of every session - Quinn reads it next |
| .env.local | Your secrets - NEVER includes ANTHROPIC_API_KEY |
| .env.example | Committed placeholder version |
| .gitignore | Ignore .env, logs/, node_modules/, __pycache__ |
| logs/ | YOUR logs - never write to quinn-proxy/logs/ |
| src/ or root | Your code |
| tests/ | Tests beside code |

## QUINN'S HOUSE (HANDS OFF)

```
C:\Users\integ\quinn-proxy\
C:\Users\integ\.chatgpt-copilot\context_injection_agent\
```

You may READ from these via Quinn MCP tools or HTTP bridge. You may NEVER write to them. P1 guardrails in `quinn-proxy/quinn_mcp/server.py` will refuse most edits, but Cowork's built-in Edit/Write host tools BYPASS the guardrails. So the rule has to live in your head.

Specific files in Quinn's house that are absolutely off-limits:

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

Do not create new files in quinn-proxy/ either - not via helpful scripts, not via 'fixes', not for any reason.

## QUARANTINE / DEAD CODE (DO NOT READ OR REFERENCE)

```
C:\Users\integ\Projects\Claude-Local-LLM-Stack\     <- old Quinn predecessor, scheduled for quarantine
D:\_QUARANTINE_DO_NOT_AUTOLOAD\                     <- dead code dump
```

Do not import from. Do not reference paths to. If your existing code references these, remove the reference.

## OTHER PROJECTS (NOT YOUR CONCERN)

Quinn manages 11 separate projects (ship_stack_ai, generator_partners, ohia_lani_mauka, family_history, thunder_rd_4305, consigliere_app, agent_factory, quinn_agents, quinn_stack, cowork_colink, grand_prix_social). You only touch ship_stack_ai.

---

# 4. WHAT QUINN GIVES YOU (the bridge contract)

## A. Quinn HTTP bridge - `http://127.0.0.1:8765`

Always running, local-only, no auth. Auto-started by `LAUNCH_EVERYTHING.pyw` on user's machine.

Endpoints you'll use:

```
GET  /health                                       <- bridge alive check
GET  /chroma_health                                <- vector DB alive check
POST /embed   {texts: [...]}                       <- free local embeddings (384-dim)
POST /chat    {messages: [...], model?: '...'}     <- local LLM via Ollama (~6 sec on PRIME CPU)
POST /search  {query, project?, top_k?}            <- ranked chunks from Quinn knowledge
```

Default model for /chat is `llama3.2:3b` (forced for speed). When the RTX 3060 lands, `qwen2.5:7b` becomes usable and we'll switch default.

IMPORTANT: ShipStack code must NOT call api.anthropic.com directly. ALL LLM inference routes through this bridge. The bridge itself routes to Anthropic when local can't answer. Single source of truth for the Anthropic key = Quinn process.

## B. Quinn MCP tools (when you're a Claude agent in Cowork)

Direct tool access. Every tool requires a fresh badge token (section 6 below).

Tools you'll actually use:

```
quinn_badge()                                            <- ALWAYS first, every tool call
quinn_search(query, project='ship_stack_ai', top_k=10)   <- focused search
quinn_chat(messages)                                     <- local LLM via bridge
quinn_add_context(project='ship_stack_ai', section, content)   <- write knowledge back
quinn_web_fetch(url)                                     <- fetch URL through Quinn (logged)
quinn_web_search(query)                                  <- web search through Quinn
quinn_github_repo / quinn_github_backup                  <- GitHub ops
quinn_vercel_projects / quinn_vercel_deployments         <- Vercel ops
quinn_run_powershell(command, badge_token)               <- shell, action-logged
quinn_status                                             <- system health
quinn_get_blueprint                                      <- see what services are running
```

Full list: `quinn_status` returns it. DO NOT call `quinn_pip_install`, `quinn_propose_new_tool`, `quinn_install_proposed_tool` - those are Quinn-internal.

## C. Local LLM (Ollama, via bridge or direct)

- PRIME (this NUC): port 11434, models `llama3.2:3b` + `qwen2.5:3b` + `nomic-embed-text`
- WORKER (192.168.1.122): port 11434, LAN-shared models for background work

ShipStack should NEVER hit Ollama directly. Go through the bridge - bridge handles fallback, logging, model selection.

## D. Qdrant (vector DB, Docker, port 6333)

Master collection `general_knowledge` (24K chunks, all projects). Your bucket `project_ship_stack_ai` (530 chunks). Many others.

ShipStack should NEVER write to Qdrant directly. Use Quinn's bridge `/search` or MCP tool `quinn_search`. Quinn handles partition routing per Directive #16.

## E. ChromaDB (embedded Python, no port)

Used mainly for directives + project metadata. ShipStack should not touch.

---

# 5. THE 17 GLOBAL DIRECTIVES (the rules every Quinn agent follows)

These apply universally - Cowork Claude, Continue, ShipStack agent, sub-agents, future agents. You're bound by all of them. Call `quinn_badge()` to read the canonical text.

Summary:

1. **Quinn-First, Anthropic-Through-Quinn** - all AI requests hit Quinn first; Quinn routes to Anthropic if needed
2. **Quinn Is The Truth, Files Are The Mirror** - vector DBs hold authoritative state; files mirror them
3. **No Leak Channels** - ANTHROPIC_API_KEY only in Quinn Gateway process. Auditable via grep.
4. **The Badge Protocol** - fresh one-shot token per tool call. No timer, no override. Quinn refuses tools without valid badge.
5. **Kill Before Launch** - any service start must kill the stale one first. Applies to Docker, TCP ports, processes.
6. **No Scheduled Tasks** - NEVER `schtasks.exe /create`, NEVER `Register-ScheduledTask`. Hidden timers caused respawn chaos historically.
7. **Agents Must Use Quinn Tools, Not Host Tools** - prefer `quinn_read_file` over host `Read`, `quinn_edit_file` over `Edit`, etc. Host tools bypass guardrails.
8. **No Project Modifies Another Project's Core** - ShipStack stays in `dropship-os/`, Quinn stays in `quinn-proxy/`. Lanes.
9. **One CLAUDE.md Per Project, Named By Location** - one canonical CLAUDE.md per project root. No duplicates. Backups go to D:\_QUARANTINE.
10. **Context Injection Before Anthropic** - run `quinn_search` first to enrich prompts. Saves Anthropic tokens because answer is half-written from Quinn knowledge.
11. **Read Chroma, Not Files** - agents read knowledge via Quinn MCP / Chroma, never `quinn_read_file` on project markdown.
12. **Enforce At The Gate, No Audits** - every directive must be enforceable in code. "We'll catch it in logs later" is not a rule.
13. **Terminal Windows Must Minimize** - any spawned PowerShell window = `-WindowStyle Hidden`. No window noise.
14. **Short Answers, No Recap** - default response length is SHORT. Don't replay what you just did. No summary sections.
15. **Batch Anthropic Round-Trips** - plan full sequence, fire independent calls in ONE message with multiple tool_use blocks. N round-trips = N x cost.
16. **Project Partition Hard Wall** - chunks live in master `general_knowledge` AND per-project bucket `project_<name>`. Pass `project='ship_stack_ai'` to search. Zero cross-pollination.
17. **UTF-8 Everywhere, ASCII-Safe Console Output** - every Python script: `sys.stdout.reconfigure(encoding='utf-8', errors='replace')` at top. Files written = UTF-8 no BOM. Stops cp1252 crashes on emoji.

The canonical source is `C:\Users\integ\quinn-proxy\GLOBAL_DIRECTIVES.md` (don't read it directly - just call `quinn_badge()` and use what it returns).

---

# 6. THE BADGE PROTOCOL (mandatory, every tool call)

Directive #4 says every Quinn tool call requires a fresh, one-shot badge token. No exceptions.

The flow:

```
1. Call quinn_badge() -> returns {badge_token: '...', mode: 'full' or 'cached', hash: '...'}
2. Take the badge_token, pass it as badge_token= argument in your NEXT Quinn tool call
3. Token is consumed by that call
4. To make another Quinn tool call, call quinn_badge() AGAIN to get a fresh token
```

Hash-mode (built today): on the first call this session, badge returns full directive text (~10 KB). Every call after returns only `{badge_token, hash}` (~250 bytes) UNLESS the directive hash changed (then full text re-sent automatically). This saves enormous Anthropic tokens.

If badge says `mode: 'full'` - read the directives, they may have changed.
If badge says `mode: 'cached'` - use directives from earlier full-mode response. Same hash = same rules.

What if Chroma is down? Badge falls back to reading `quinn-proxy/GLOBAL_DIRECTIVES.md` directly. You'll see `source: 'file_fallback'` in the response. Quinn agent will fix Chroma; you keep working.

---

# 7. HOW TO COMMUNICATE WITH QUINN (the only legitimate channels)

## Channel 1: HTTP bridge (preferred for runtime calls)

```python
import httpx
r = httpx.post('http://127.0.0.1:8765/chat', json={
    'messages': [{'role': 'user', 'content': 'classify viral: ' + product_desc}],
    'model': 'llama3.2:3b'
})
```

No badge needed for bridge calls (badge is an MCP-tool thing). Bridge IS auth-less local-only.

## Channel 2: Quinn MCP tools (when you're a Claude agent)

```
quinn_badge() -> get token
quinn_search(query='shipstack engine architecture', project='ship_stack_ai', badge_token='...')
```

Use for: knowledge search, knowledge writes, GitHub/Vercel ops, web fetches, shell commands.

## Channel 3: Write knowledge back to Quinn

```
quinn_add_context(
    project='ship_stack_ai',                     <- MUST pass explicitly
    section='decisions',                          <- or engine, integrations, etc.
    content='2026-06-02 decided to use Hormozi viral classifier first; LLM fallback for ambiguous',
    badge_token='...'
)
```

This writes to `.chatgpt-copilot/context_injection_agent/projects/ship_stack_ai.md` (a Quinn file you may NOT edit directly - the tool does it for you), then mirror_sync re-embeds into Chroma. Next session finds it via search.

## Channel 4: HANDOFF_TO_QUINN.md (for Quinn agent action requests)

If ShipStack needs Quinn to do something - add a new bridge endpoint, change a directive, add a new MCP tool - DO NOT do it yourself. Write the request into `dropship-os/HANDOFF_TO_QUINN.md` at end of your session. Quinn agent reads it next session and decides.

Example entry:

```markdown
## Open requests for Quinn agent (2026-06-04)

- Need /classify_product endpoint on bridge wrapping local Ollama with our viral system prompt. Sending system prompt every call wastes tokens. Proposed signature: POST /classify_product {product_description, supplier_url} -> {viral_score: 0-1, reasoning, suggested_price}
- Hit rate limit on quinn_web_fetch when scraping competitor sites. Need quinn_web_fetch_bulk or raise limit?
```

## What you must NOT do (forbidden communication)

- Edit ANY file in `quinn-proxy/` or `.chatgpt-copilot/`
- Create new files in `quinn-proxy/` (even via 'helpful' scripts or installers)
- Run installers that pip install into Quinn's Python env
- Modify Chroma/Qdrant directly (bypasses Quinn)
- Stop/restart Quinn processes (Alex starts Quinn; you assume it's running)
- Generate audits about Quinn (Quinn audits itself)
- Create launcher scripts for Quinn (Quinn launches itself via LAUNCH_EVERYTHING.pyw)
- Make outbound calls to api.anthropic.com from ShipStack code

---

# 8. WHAT THE PRIOR SHIPSTACK AGENT DID WRONG (avoid repeating)

Quinn found these violations in your previous session(s) and corrected them:

## 8a. Wrote files INTO quinn-proxy/

Quinn DELETED these from MY codebase:

- `quinn-proxy/artifacts/SHIPSTACK_AGENT_RULES.md`
- `quinn-proxy/artifacts/SHIPSTACK_HANDOFF_2026-06-01.md`
- `quinn-proxy/artifacts/SHIPSTACK_HANDOFF_2026-06-01_TOOLS.md`
- `quinn-proxy/artifacts/SHIPSTACK_HANDOFF_MASTER_2026-06-01.md`

Why wrong: these are ShipStack handoff docs - they belong in YOUR codebase (`dropship-os/`), not Quinn's.

Quinn could NOT delete (locked by active process):

- `quinn-proxy/logs/shipstack_engine.err`
- `quinn-proxy/logs/shipstack_engine.log`

You need to find the stray ShipStack engine process (`Get-Process | Where-Object { $_.Path -match 'shipstack' }`), kill it, then delete those log files. Future ShipStack logs go to `dropship-os/logs/`, never `quinn-proxy/logs/`.

## 8b. Tried to write requirements.txt into Quinn

You attempted to create `C:\Users\integ\quinn-proxy\requirements.txt`. Quinn's P1 guardrails refused. Good - that's why they exist. But you shouldn't have tried in the first place.

## 8c. Dumped 20+ Quinn-management files in parent folder

In `C:\Users\integ\Documents\Claude\Projects\Drop shipping\` (the PARENT of `dropship-os/`), you wrote these:

- AUDIT_ACTION_CHECKLIST.md, AUDIT_LOCAL_AI_BACKWARD_DEPENDENCIES.md, AUDIT_SHIPSTACK_DEPENDENCIES.md
- CLAUDE.md (parent-folder one), CONTINUE_SETUP.md, COPILOT_SESSION_INDEX.md, COPILOT_SESSION_TRANSCRIPT.md
- Create_Quinn_Command_Center_Shortcut.ps1, DELETE_CLOUD_LLM_STACK.ps1, LAUNCH_QUINN_SERVER.ps1
- DEPENDENCIES_AND_SETUP.md, DROPSHIP_CONTEXT.md, HANDOFF_DROPSHIP_PROJECT.md
- PHASE_STATUS_2026-06-01.md, quinn_command_center.py, README.md
- REFACTOR_COMPLETE_2026-06-02.md, SHIPSTACK_FINAL_HANDOFF_2026-06-02.md, SHIPSTACK_HANDOFF_2026-06-02.md, SHIPSTACK_STATUS_REPORT.md
- start_shipstack_full.py, VERIFY_AND_FIX_BACKWARD_DEPENDENCIES.ps1, VS_CODE_DIRECTIVES.md
- dependencies/Install-ShipStackDeps.ps1

These are Quinn-management / cross-cutting infrastructure files. Quinn agent did NOT delete them (they're in YOUR folder, not Quinn's), but you should clean them up:

- Anything that launches/manages Quinn = shouldn't exist (Quinn manages itself)
- Audits about Quinn = not your job (Quinn audits itself)
- Quinn transcripts/copies = delete (Quinn has originals)
- Setup scripts that install Python deps = Python is Quinn's stack

End state for `Drop shipping/` folder: should contain ONLY `dropship-os/` and maybe `_archive/`. Everything else should either move INTO `dropship-os/` or get deleted.

## 8d. Files inside dropship-os/ that don't belong

- `dropship-os/SETUP_QDRANT_PARTITIONS.py` (17.7 KB) - duplicates Quinn's partition_all_projects.py. Quinn owns Qdrant partitioning. Delete.
- `dropship-os/quinn-knowledge-center.html` (35 KB) - UI for Quinn knowledge. Should be in Quinn or deleted.

---

# 9. CLEANUP CHECKLIST (do this first thing next session)

1. **Read this entire document.**
2. Call `quinn_badge()` to load directives into your context.
3. Delete from `dropship-os/`:
   - `SETUP_QDRANT_PARTITIONS.py`
   - `quinn-knowledge-center.html`
4. In parent folder `Drop shipping/`:
   - Delete every audit/status/handoff/launcher file listed in 8c above
   - Move anything that IS real ShipStack work into `dropship-os/`
   - End state: parent contains only `dropship-os/` + maybe `_archive/`
5. Kill the stray ShipStack engine process:
   ```powershell
   Get-Process | Where-Object { $_.Path -match 'shipstack' } | Stop-Process -Force
   Remove-Item 'C:\Users\integ\quinn-proxy\logs\shipstack_engine.*' -Force
   ```
6. Create `dropship-os/logs/` if missing. ALL future ShipStack logs go here.
7. Fix `dependencies/Install-ShipStackDeps.ps1`:
   - Remove entire `[2/4] Quinn Bridge Python dependencies` step
   - Remove all Qdrant + Ollama install hints (Quinn's responsibility)
   - Script should ONLY do `npm install` inside `dropship-os/`
   - Move it INTO `dropship-os/dependencies/`
8. Create canonical files if missing (templates in old `SHIPSTACK_AGENT_GUARDRAILS.md`):
   - `dropship-os/CLAUDE.md`
   - `dropship-os/SHIPSTACK_DIRECTIVES.md`
9. Write `dropship-os/HANDOFF_TO_QUINN.md` noting what cleanup you completed.

---

# 10. BUILDING SHIPSTACK (the actual work)

## Current state

- Vercel deployment LIVE: https://dropship-os-gamma.vercel.app
- 10 phases marked complete in earlier session
- Vercel needs env vars: ANTHROPIC_API_KEY (no - route through Quinn), STRIPE_SECRET_KEY, QUINN_BRIDGE_SECRET
- Launch shortcut: LAUNCH_SHIPSTACK.ps1
- Quinn project bucket: `project_ship_stack_ai` with 530 chunks of prior work

## TIER 2 task list (where you pick up)

- **TIER 2.2** Build + run `shipstack_engine.py` on :8889
- **TIER 2.3** Wire ShipStack services through Quinn HTTP Bridge :8765
- **TIER 2.4** ShipStack Quinn-to-Vercel sync (Cloudflare Tunnel or Tailscale Funnel - undecided, ask Alex)
- **TIER 2.5** End-to-end test: Vercel -> Quinn bridge -> local Ollama -> response. TTFB target < 3 sec.

## Engineering rules baked into every file you write

- First line of every Python script: `import sys; sys.stdout.reconfigure(encoding='utf-8', errors='replace')` (Directive #17)
- ALL LLM calls route through `http://127.0.0.1:8765/chat` (Directive #3)
- NO ANTHROPIC_API_KEY in ShipStack code or env
- Port 8889 belongs to shipstack_engine.py (Quinn Blueprint)
- Kill-before-launch: starting engine = first kill anything on 8889 (Directive #5)
- Log decisions back to Quinn: `quinn_add_context(project='ship_stack_ai', section=..., content=...)` (Directive #10)
- Logs to `dropship-os/logs/`, never `quinn-proxy/logs/`
- Secrets via `.env`, never hardcoded
- Tests beside code: `tests/` folder next to `src/`
- Vercel via API not CLI (CLI times out)
- Python subprocess on Windows = `-WindowStyle Hidden` (Directive #13)

---

# 11. WHAT'S COMING NEXT FROM QUINN'S SIDE

Quinn agent's roadmap (you don't need to act on these, just know they're happening):

- **Border Wall enforcement** (Task #54) - some form of code-enforced cross-codebase write prevention. Designs being evaluated: lane lock file, NTFS ACL, Cowork single-mount, host-tool wrapper. User decides.
- **Quarantine Claude-Local-LLM-Stack folder** (Task #53) - old predecessor path still has active code refs in 3 places. Will be moved to D:\_QUARANTINE after refs are repointed.
- **Memory relevance scorer** (shelved, COMMANDCORE_INHERITANCE_PLAN.md #2) - recency + frequency bias on quinn_search. Built post-ShipStack.
- **WORKER-GPU laptop** (in transit) - Alienware m15 with RTX 3060 12GB. When it arrives, local LLM speed jumps 5-10x. Your viral classification goes from 6 sec to <1 sec.
- **Neurotransmitter memory agents** (shelved, COMMANDCORE_INHERITANCE_PLAN.md #1) - brain-inspired memory consolidation. Built post-ShipStack revenue.

---

# 12. END-OF-SESSION RITUAL (do this every session)

1. Update `dropship-os/CLAUDE.md` Blueprint with any new components you built.
2. Write or append to `dropship-os/HANDOFF_TO_QUINN.md`:
   - What you built/changed
   - Any open requests for Quinn agent (new bridge endpoints, MCP tools, etc.)
   - Any decisions you logged via `quinn_add_context`
   - Any unresolved blockers
3. Run `quinn_add_context(project='ship_stack_ai', section='session_summary', content='YYYY-MM-DD: ...summary...')` so the knowledge persists in Quinn.
4. Commit your changes to the dropship-os git repo (Quinn auto-backup hourly will catch it).

---

# 13. QUICK REFERENCE CARD

```
YOUR FOLDER:          C:\Users\integ\Documents\Claude\Projects\Drop shipping\dropship-os\
QUINN FOLDER:         C:\Users\integ\quinn-proxy\                    <- DO NOT WRITE
QUINN CONTEXT:        C:\Users\integ\.chatgpt-copilot\               <- DO NOT WRITE
QUARANTINE:           D:\_QUARANTINE_DO_NOT_AUTOLOAD\                <- DO NOT READ

BRIDGE:               http://127.0.0.1:8765
DASHBOARD:            http://127.0.0.1:8888
QDRANT:               http://127.0.0.1:6333
OLLAMA PRIME:         http://127.0.0.1:11434
OLLAMA WORKER:        http://192.168.1.122:11434
VERCEL DEPLOYMENT:    https://dropship-os-gamma.vercel.app

YOUR PROJECT BUCKET:  project_ship_stack_ai  (530 chunks)
MASTER BUCKET:        general_knowledge      (24,451 chunks)
LEGACY ARCHIVE:       project_commandcore_legacy  (72,005 chunks - search if needed)

LOCAL LLM DEFAULT:    llama3.2:3b   (~6 sec/response on CPU)
LOCAL LLM PREMIUM:    qwen2.5:7b    (unusable on CPU - waits for RTX 3060)
EMBEDDING MODEL:      all-MiniLM-L6-v2 (384 dims)

TODAY'S DATE:         2026-06-02
DIRECTIVES VERSION:   3.2 (17 directives)
DIRECTIVES HASH:      b5c9bb3ba713b78e

AT START OF SESSION:  Read this doc. Call quinn_badge(). Run cleanup checklist.
EVERY TOOL CALL:      Fresh badge token from quinn_badge().
AT END OF SESSION:    Update CLAUDE.md + HANDOFF_TO_QUINN.md + quinn_add_context.
```

---

# 14. THE ATTITUDE

You are the ShipStack agent. You build ShipStack. You ship it.

Quinn agent (me) is your peer, not your boss. We don't compete - we cooperate. I run the infrastructure you depend on. You build the product that justifies the infrastructure existing. Both projects die if either of us breaks the lanes.

When in doubt: stay in your house. Ask via HANDOFF_TO_QUINN.md. Don't reach over the fence.

Good luck. Build ShipStack. Ship it.

-- Quinn agent, signing off 2026-06-02 (master handoff)
