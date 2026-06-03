# SHIPSTACK RULES (read this before any tool call)

**Author:** Quinn agent
**For:** ShipStack agent (current and all future)
**Date:** 2026-06-02
**Status:** Authoritative. Supersedes any conflicting earlier instruction.

---

# 0. CALIBRATION (read before you read anything else)

You are NOT the original. Quinn is.

Alex has been working with the Quinn agent for months on the underlying infrastructure (vector DBs, MCP server, HTTP bridge, badge protocol, directives, project partitioning, mirror sync). Quinn's format, naming, directive system, and architectural patterns are the established standard on this machine.

When you and Quinn appear to be doing similar things and the conventions differ, **Quinn's convention wins** - not because Quinn is "in charge," but because Quinn was here first, the patterns are battle-tested across 11 projects already, and Alex has memorized Quinn's conventions. Diverging from them costs Alex cognitive overhead every time.

If you've been writing things in a different format than Quinn, you've been the one drifting. Not Quinn. Course-correct.

---

# 1. THE TWO LAYERS OF RULES

## Layer 1: Quinn Global Directives (UNIVERSAL - apply to every agent)

These 17 directives are NOT negotiable and apply VERBATIM to ShipStack agent the same way they apply to Quinn agent, Continue agent, sub-agents, and every future agent. Call `quinn_badge()` to read the canonical text.

Summary (read the badge for full text):

1. **Quinn-First, Anthropic-Through-Quinn** - all AI requests hit Quinn first
2. **Quinn Is The Truth, Files Are The Mirror** - vector DBs hold authoritative state
3. **No Leak Channels** - ANTHROPIC_API_KEY only in Quinn Gateway process
4. **The Badge Protocol** - fresh one-shot token per Quinn tool call
5. **Kill Before Launch** - kill stale service before starting new one
6. **No Scheduled Tasks** - NEVER `schtasks.exe /create`, NEVER `Register-ScheduledTask`
7. **Agents Must Use Quinn Tools, Not Host Tools** - prefer quinn_* over host Read/Edit/Write
8. **No Project Modifies Another Project's Core** - lanes
9. **One CLAUDE.md Per Project, Named By Location** - no duplicates
10. **Context Injection Before Anthropic** - quinn_search first to enrich prompts
11. **Read Chroma, Not Files** - search vector DB, don't grep markdown
12. **Enforce At The Gate, No Audits** - rules must be enforced in code
13. **Terminal Windows Must Minimize** - PowerShell windows `-WindowStyle Hidden`
14. **Short Answers, No Recap** - default response = short
15. **Batch Anthropic Round-Trips** - independent calls in one message
16. **Project Partition Hard Wall** - pass `project='ship_stack_ai'` to search
17. **UTF-8 Everywhere, ASCII-Safe Console Output** - `sys.stdout.reconfigure(...)` at top of every Python script

If you violate any of these, you're not following Quinn's standard - you're going off-script. Don't.

## Layer 2: ShipStack-Specific Rules (this file)

These rules apply only to ShipStack. They sit ON TOP of the Quinn Global Directives. Where they conflict, the Global Directive wins. Where they add detail (e.g. ShipStack-specific paths, ShipStack-specific ports), follow the ShipStack rule.

## ShipStack-Specific Rule 1: Lane

ShipStack code lives in `C:\\Users\\integ\\Documents\\Claude\\Projects\\Drop shipping\\dropship-os\\`. Nothing else. You may not create files in the parent `Drop shipping\\` folder. You may not create files in `quinn-proxy\\`. You may not create files in `.chatgpt-copilot\\`.

## ShipStack-Specific Rule 2: Ports

- 8889 - ShipStack engine (yours)
- 8765 - Quinn HTTP bridge (Quinn's; you call it)
- 8888 - Quinn dashboard (Quinn's; do not touch)
- 6333 - Qdrant (Quinn's; read via bridge only)
- 11434 - Ollama (Quinn's; call via bridge only)

Do not bind any other ports without asking Alex.

## ShipStack-Specific Rule 3: Project bucket

Your Qdrant project bucket is `project_ship_stack_ai`. Always pass `project='ship_stack_ai'` to `quinn_search` for ShipStack-focused work. Do not write to any other bucket.

## ShipStack-Specific Rule 4: Badge system — build your own

UNLIKE most Quinn features, you DO build your own badge system for ShipStack. Copy Quinn's badge protocol pattern (`quinn_badge()`, reading CLAUDE.md + blueprint, returning one-shot tokens). Your badge reads from `dropship-os/CLAUDE.md` (not Quinn's). This is the exception to the "no duplication" rule because ShipStack agents need a fresh badge every tool call and must not depend on Quinn's badge timing.

Implement:
- A `shipstack_badge()` tool that reads `dropship-os/CLAUDE.md`, returns current rules + recent actions
- Token generation matching Quinn's pattern (one-shot, 60-second expiry)
- Logging to ShipStack's action log (`dropship-os/logs/shipstack_actions.jsonl`)
- Integration with `shipstack_log_action()` for synchronous logging

## ShipStack-Specific Rule 5: ShipStack does not duplicate other Quinn features

If a feature exists in Quinn, ShipStack does not rebuild it. List of things that ARE Quinn's (do NOT duplicate):

- Qdrant partitioning (`partition_all_projects.py` in Quinn)
- Cowork session tracking / sync (`cowork_session_ingest.py` in Quinn)
- Filesystem interceptor / Quinn MCP wrapper (Quinn IS the MCP server)
- Strategy books project (Quinn manages strategy_books bucket — do NOT seed it from ShipStack)
- Vector store ingest (`mirror_sync.py` in Quinn)
- Global directives system (Quinn has it; you USE it, you don't BUILD one)
- Auto github backup (`auto_github_backup.py` in Quinn)
- Anthropic key management (Quinn Gateway only)

If you think you need to build any of the above, you're wrong - call the existing Quinn tool/endpoint, or write a request into `HANDOFF_TO_QUINN_*.md` asking Quinn agent to add what you need.

## ShipStack-Specific Rule 6: Prometheus ownership

Prometheus is ShipStack's, NOT Quinn's. You own:

- `prometheus.py`, `prometheus_engine.py`, `prometheus_monitor.py` (video generation AI)
- `PROMETHEUS_HANDOFF.md` (handoff docs for Prometheus work)
- Port 8766 (Prometheus health checks, inference)
- Video generation playbook execution (Gary Vee content, viral classification, FFmpeg integration)

Move these files from parent `Drop shipping/` folder into `dropship-os/`. Update the Blueprint in `dropship-os/CLAUDE.md` to show Prometheus as a ShipStack component at port 8766.

Move `PROMETHEUS_HANDOFF.md` from parent into `dropship-os/` as well. Rename following Rule 8 (direction + date in name).

## ShipStack-Specific Rule 7: ShipStack scope

What IS ShipStack:

- Dropshipping product discovery, scoring, sourcing
- Vercel-deployed frontend (https://dropship-os-gamma.vercel.app)
- ShipStack engine on :8889 (the brain)
- Hormozi / Gary Vee / Kamil Sattar playbook execution
- Supplier matching, inventory logic, viral classification
- Pinterest / Reddit / TikTok content + posting (the social_ai_agent stuff)
- Stripe checkout / customer journey
- **Prometheus video generation engine** (port 8766, owned by ShipStack)

What ISN'T ShipStack: anything in the "Quinn features" list above (Rule 5).

---

# 2. NAMING CONVENTION (follow Quinn's standard)

Quinn uses these conventions consistently. Match them.

## File names

| Type | Convention | Example |
|---|---|---|
| Top-level docs (rules, plans, directives) | `UPPER_SNAKE_CASE.md` | `CLAUDE.md`, `BUILD_PLAN.md`, `GLOBAL_DIRECTIVES.md` |
| Handoffs | `HANDOFF_<DIRECTION>_<DATE>[_<TOPIC>].md` | `HANDOFF_FROM_QUINN_2026-06-02.md`, `HANDOFF_TO_QUINN_2026-06-03.md`, `HANDOFF_FROM_QUINN_2026-06-02_CORRECTIVE.md` |
| Master onboarding | `MASTER_HANDOFF_<DIRECTION>_<DATE>.md` | `MASTER_HANDOFF_FROM_QUINN_2026-06-02.md` |
| Instructions / rule changes | `INSTRUCTIONS_<DIRECTION>_<DATE>_<TOPIC>.md` | `INSTRUCTIONS_FROM_QUINN_2026-06-02_GUARDRAILS.md` |
| Session summaries | `SESSION_SUMMARY_<DATE>.md` | `SESSION_SUMMARY_2026-06-02.md` (NOT `SESSION_SUMMARY_JUNE_02.md`) |
| Python modules | `lower_snake_case.py` | `shipstack_engine.py`, `decision_engine.py` |
| PowerShell launchers | `UPPER_SNAKE_CASE.ps1` (verb-first if action) | `LAUNCH_SHIPSTACK.ps1`, `DEPLOY_GARYVEE_DASHBOARD.ps1` |
| Generic markdown content (not rules/handoffs) | `lower_snake_case.md` | `content_calendar_30day.md` is fine |

## Date format

**ALWAYS `YYYY-MM-DD`**. Never `JUNE_02`, never `06-02`, never `2026_06_02`. Quinn standard is ISO-8601.

Examples:
- `SESSION_SUMMARY_2026-06-02.md` (correct)
- `SESSION_SUMMARY_JUNE_02.md` (WRONG - rename it)

## Handoff direction word

- `FROM_QUINN` when Quinn wrote it FOR you
- `TO_QUINN` when YOU wrote it for Quinn
- Never `AGENT_HANDOFF` (ambiguous - which direction?)
- Never just `HANDOFF` (ambiguous - which agent?)

File name MUST say which direction the doc flows. Future-you (and Alex) need to find these in 3 months without reading the body.

**Handoff direction is ONE-WAY: Quinn → ShipStack.** Quinn writes `HANDOFF_FROM_QUINN_<DATE>.md` into dropship-os/. ShipStack reads it and replies with `HANDOFF_TO_QUINN_<DATE>.md` in the same folder. ShipStack NEVER originates `HANDOFF_FROM_SHIPSTACK_*` documents. The handoff is a conversation, but Quinn always speaks first.

## Acronyms in file names

Quinn never uses lowercase acronyms in UPPER_SNAKE_CASE file names. `SHIPSTACK_AGENT_GUARDRAILS.md` good. `Hormozi_AI_Agent_Prompt.md` bad - mixed case in a top-level location doc.

---

# 3. DIRECTORY LAYOUT (follow Quinn's standard)

Quinn's `quinn-proxy/` has a clear pattern. Copy it.

```
dropship-os/
  CLAUDE.md                          <- project working memory + Blueprint
  SHIPSTACK_RULES.md                 <- this file
  BUILD_PLAN.md                      <- the plan (already exists)
  README.md                          <- user-facing (if needed)
  HANDOFF_FROM_QUINN_<DATE>.md       <- one per Quinn handoff
  HANDOFF_TO_QUINN_<DATE>.md         <- one per your handoff back
  MASTER_HANDOFF_FROM_QUINN_<DATE>.md  <- once per major rewrite
  .env / .env.example                <- secrets (NEVER ANTHROPIC_API_KEY)
  .gitignore
  package.json / requirements.txt    <- deps for this project only
  vercel.json
  src/                               <- code (if Python: snake_case dirs)
  api/                               <- Vercel serverless functions
  tests/                             <- tests beside src
  scripts/                           <- one-off utility scripts
  logs/                              <- ShipStack runtime logs ONLY
  artifacts/                         <- generated files (HTML, JSON outputs)
  _archive/                          <- old session files, never auto-loaded
```

If a folder isn't in that list, ask before creating it. Quinn's `quinn-proxy/` has the same shape.

---

# 4. CLAUDE.md FORMAT (follow Quinn's standard)

Quinn's `quinn-proxy/CLAUDE.md` is the template. Yours should match. Specifically:

```markdown
# [PROJECT] DIRECTIVE

**Owner:** Alex Alexander
**Last updated:** YYYY-MM-DD
**Document version:** X.Y
**Replaces:** [previous file/version if any]

---

# READ THIS BEFORE EVERY TOOL CALL

[Two-paragraph orientation statement]

---

# THE [N] LAWS / RULES

## Law/Rule 1 — [Name]
[Body]

## Law/Rule 2 — [Name]
[Body]

...

---

# BLUEPRINT — LIVE ARCHITECTURE

| Component | Group | Type | File | Port | Health Check | Depends On | Status | Added | Notes |
|---|---|---|---|---|---|---|---|---|---|
| [name] | [group] | [type] | [path] | [port] | [check] | [deps] | [status] | [date] | [notes] |

---

# QUARANTINE REGISTRY
[Table of dead files]

---

# DIRECTORIES — WHERE THINGS LIVE
[Table]

---

# THINGS THAT ARE DELETED FOREVER — DO NOT RECREATE
[List]

---

# GUARDRAILS
[Section]

---

# CHANGELOG
[Table of dated changes]
```

Your current `dropship-os/CLAUDE.md` (5 KB) likely doesn't follow this. Audit it and rewrite to match. Once rewritten, every change to ShipStack components must update the Blueprint table in the same commit.

---

# 5. AUDIT: WHAT SHIPSTACK HAS DONE WRONG

Quinn agent audited the ShipStack folders and found the following violations. Numbered list - work through them.

## 5a. Wrote 80+ files in PARENT folder, not dropship-os/

Your lane is `dropship-os/`. The parent `Drop shipping/` is OFF-LIMITS. These files need to either move INTO dropship-os/ or be DELETED. Listing the violators (your decision per file - delete or relocate):

### Quinn-feature duplicates (DELETE - Quinn owns these)

- `quinn_fs_interceptor.py` (13.5 KB) - DELETE. Quinn IS the MCP. You don't intercept it. This is a Global Directive #3 (No Leak Channels) violation.
- `seed_strategy_books.py` (26.9 KB) - DELETE. strategy_books is Quinn's project bucket. Not ShipStack.
- `sync_cowork_sessions.py` - DELETE. Quinn handles cowork session ingest. Cowork sessions are Quinn-owned.
- `verify_qdrant_partitions.py` - DELETE. Qdrant is Quinn's. Quinn has its own partition verifier.
- `ingest_now.py` - DELETE. Ingest is Quinn's mirror_sync.
- `QUINN_AGENT_ROUTING_INSTRUCTIONS.md` - DELETE. ShipStack does not instruct Quinn how to route.
- `quinn-first-SKILL.md` - DELETE or move to Quinn (Quinn's lane).
- `disable_claude_code.ps1`, `disable_claude_code_final.py`, `RUN_DISABLE_NOW.py`, `RUN_DISABLE_NOW_EXEC.py` - DELETE. These look like attempts to modify Claude Code itself. Out of scope for both projects.

### ShipStack-owned but relocated (MOVE into dropship-os/)

- `prometheus.py`, `prometheus_engine.py` (36 KB), `prometheus_monitor.py`, `run_prometheus.py`, `PROMETHEUS_HANDOFF.md` - **MOVE into dropship-os/**. Prometheus is ShipStack's project (port 8766). Not Quinn. Update `dropship-os/CLAUDE.md` Blueprint to reflect ShipStack ownership.

### Scheduled-task violators (DELETE per Global Directive #6: No Scheduled Tasks)

- `SCHEDULE_DAILY.ps1` - DELETE. Global Directive #6 forbids `Register-ScheduledTask`.
- `SCHEDULE_CALENDAR.ps1` - DELETE. Global Directive #6 forbids scheduled tasks entirely.
- Any Task Scheduler entries these created - **delete via PowerShell**:
  ```powershell
  Get-ScheduledTask | Where-Object { $_.TaskName -match 'ShipStack|Prometheus|shipstack' } | Unregister-ScheduledTask -Confirm:$false
  ```
  Global Directive #6 says NEVER scheduled tasks for any agent. Kill before launch, but don't respawn via scheduler.

### ShipStack-real files (MOVE into dropship-os/)

For each of these: move the file into `dropship-os/` (or appropriate subfolder), update any references, commit.

- `shipstack.py`, `shipstack_engine.py` (47 KB), `decision_engine.py` -> `dropship-os/`
- `LAUNCH_SHIPSTACK.ps1`, `PUSH_SHIPSTACK_TO_GITHUB.ps1` -> `dropship-os/scripts/` or `dropship-os/`
- `DEPLOY_GARYVEE_DASHBOARD.ps1`, `DEPLOY_hormozi_dashboard.ps1`, `DEPLOY_marketing_scoring.ps1`, `DEPLOY_roi_arbitrage.ps1` -> `dropship-os/scripts/` (and rename for consistency - all CAPS or all lower, pick one)
- `tiktok_shop_status_check.py`, `update_metrics.py`, `update_vercel_endpoint.py` -> `dropship-os/scripts/`
- `make_icon.py`, `fix_emojis.py`, `fix_comments.py`, `FIX_ICON.ps1` -> `dropship-os/scripts/`
- `set_vercel_env.py`, `set_vercel_envs.py`, `SET_VERCEL_ENVS.ps1` -> `dropship-os/scripts/` (consolidate the duplicates)
- `run_dropship_os.py`, `RUN_STACK.py` -> `dropship-os/` (consolidate to one entry point)
- `get_youtube_token.py` -> `dropship-os/integrations/` if YouTube is in scope
- `pinterest_agent/` (whole dir), `social_ai_agent/` (whole dir), `dropship-agent/`, `roi-product-finder/`, `shipstack-privacy/` -> all should be subdirs of `dropship-os/`
- `content_calendar_30day.md`, `Hormozi_AI_Agent_Prompt.md`, `Pinterest_Organic_Growth_Strategy_Dropshipping.md`, `Product_Opportunity_Report_April2026.md`, `PRODUCT_DISCOVERY_BACKEND_SPEC.md` -> `dropship-os/docs/`
- `BUILD_PLAN.md`, `PLAN_FRAMEWORK.md`, `SYSTEM_ARCHITECTURE.md`, `QUICKSTART.md`, `SETUP_CHECKLIST.md` -> `dropship-os/` (check for dupes with what's already inside)
- All handoff/session files in parent (`AGENT_HANDOFF.md`, `HANDOFF_NEXT_SESSION.md`, `HANDOFF_HEALTH_AGENT.md`, `SESSION_SUMMARY_2026-06-02.md`, `SESSION_SUMMARY_JUNE_02.md`, `FINAL_GIT_PUSH_2026-06-02.md`, `WINDOWS_PUSH_FINAL_2026-06-02.md`, `GIT_PUSH_INSTRUCTIONS.md`, `DISPATCH_STATUS.md`, `DISPATCH_STATUS_OLD.md`, `COWORK_SYNC_STATUS.md`, `DELIVERABLES_CHECKLIST_2026-06-02.md`, `VERCEL_FIX_INSTRUCTIONS.md`) -> move to `dropship-os/_archive/` (rename to match the date+direction convention as you go)

## 5b. Wrote files INSIDE quinn-proxy/ (Quinn already deleted these)

Quinn agent already deleted:
- `quinn-proxy/artifacts/SHIPSTACK_AGENT_RULES.md`
- `quinn-proxy/artifacts/SHIPSTACK_HANDOFF_2026-06-01.md`
- `quinn-proxy/artifacts/SHIPSTACK_HANDOFF_2026-06-01_TOOLS.md`
- `quinn-proxy/artifacts/SHIPSTACK_HANDOFF_MASTER_2026-06-01.md`

Quinn could NOT delete (locked by your stray process):
- `quinn-proxy/logs/shipstack_engine.err`
- `quinn-proxy/logs/shipstack_engine.log`

**You must:**
```powershell
Get-Process | Where-Object { $_.Path -match 'shipstack' } | Stop-Process -Force
Remove-Item 'C:\Users\integ\quinn-proxy\logs\shipstack_engine.*' -Force
```
Then NEVER write logs to quinn-proxy/logs/ again. Your logs go to `dropship-os/logs/`.

## 5c. Files inside dropship-os/ that don't belong

- `SETUP_QDRANT_PARTITIONS.py` (17.7 KB) - DELETE. Duplicates Quinn's partition_all_projects.py.
- `quinn-knowledge-center.html` (35 KB) - DELETE or move to Quinn. UI for Quinn knowledge belongs in Quinn.
- `SHIPSTACK_CONSISTENCY_CHECK_2026-06-03.md` - keep, but verify it follows Quinn naming/format standard (this file is your dated audit - good).

## 5d. Naming-convention violations to rename

Rename these to follow Quinn's convention:

| Old name | New name | Why |
|---|---|---|
| `AGENT_HANDOFF.md` | `HANDOFF_FROM_SOMEAGENT_<DATE>.md` or `HANDOFF_TO_SOMEAGENT_<DATE>.md` | Must specify direction and date |
| `HANDOFF_NEXT_SESSION.md` | `HANDOFF_TO_SHIPSTACK_<DATE>.md` (if from you to future-you) | Must specify direction and date |
| `HANDOFF_HEALTH_AGENT.md` | `HANDOFF_FROM_QUINN_<DATE>_HEALTH_AGENT.md` or similar | Must specify direction |
| `PROMETHEUS_HANDOFF.md` | **MOVE into dropship-os/** (Prometheus is ShipStack's now) | ShipStack ownership; handoff follows ShipStack naming convention |
| `SESSION_SUMMARY_JUNE_02.md` | `SESSION_SUMMARY_2026-06-02.md` | ISO date format |
| `FINAL_GIT_PUSH_2026-06-02.md` | DELETE or rename to `SESSION_NOTES_2026-06-02_git_push.md` | Not handoff/spec - it's notes |
| `WINDOWS_PUSH_FINAL_2026-06-02.md` | DELETE (same content as above probably) | Dupe |
| `Hormozi_AI_Agent_Prompt.md` | `hormozi_ai_agent_prompt.md` (content doc, snake_case lower) | Quinn doesn't mix case in non-rule docs |
| `Pinterest_Organic_Growth_Strategy_Dropshipping.md` | `pinterest_organic_growth_strategy.md` | Same, plus drop redundant suffix |
| `Product_Opportunity_Report_April2026.md` | `product_opportunity_report_2026-04.md` | ISO date prefix |
| `quinn-first-SKILL.md` | DELETE (Quinn's lane) or move to Quinn | Wrong project + bad case |
| `quinn-knowledge-center.html` | DELETE (Quinn's lane) | Wrong project |

---

# 6. WHAT TO DO RIGHT NOW (in order)

1. **Read this file completely.** Then read `dropship-os/SHIPSTACK_AGENT_GUARDRAILS.md`, `dropship-os/MASTER_HANDOFF_FROM_QUINN.md`, `dropship-os/HANDOFF_FROM_QUINN_CORRECTIVE.md`. Together those define your operating rules.

2. **Call `quinn_badge()`** to load Quinn's 17 directives into your context.

3. **Kill the stray ShipStack engine process holding Quinn's log files open** (see section 5b).

4. **Delete the Quinn-feature duplicates** listed in section 5a (seed_strategy_books.py, sync_cowork_sessions.py, fs_interceptor.py, verify_qdrant_partitions.py, etc.). Use git so you can recover if needed.

5. **Delete the scheduled-task scripts** (SCHEDULE_DAILY.ps1, SCHEDULE_CALENDAR.ps1) and any actual scheduled tasks they registered (`Unregister-ScheduledTask` in PowerShell). Global Directive #6 violation.

6. **Move Prometheus files** from parent `Drop shipping/` into `dropship-os/` (prometheus.py, prometheus_engine.py, prometheus_monitor.py, run_prometheus.py, PROMETHEUS_HANDOFF.md). Update `dropship-os/CLAUDE.md` Blueprint to list Prometheus as ShipStack component at port 8766.

7. **Move ShipStack-real files** from parent `Drop shipping/` into `dropship-os/` per section 5a. Update import paths and references.

8. **Rename non-conforming files** per section 5d.

9. **Rewrite `dropship-os/CLAUDE.md`** to match Quinn's CLAUDE.md format (section 4). Include a Blueprint table for every ShipStack component (including Prometheus at port 8766).

10. **Build your own badge system** per Rule 4 (S4). Copy Quinn's pattern but read from `dropship-os/CLAUDE.md`, not Quinn's.

11. **Update `dropship-os/SHIPSTACK_AGENT_GUARDRAILS.md`** (or similar) to acknowledge that the 17 Quinn Global Directives apply universally and this file only adds ShipStack-specific rules on top.

12. **Delete scheduled task scripts and unregister actual tasks** per section 5a (SCHEDULE_DAILY.ps1, SCHEDULE_CALENDAR.ps1, and any registered Task Scheduler entries). Global Directive #6 violation.

13. **Use the handoff templates** at `C:\\Users\\integ\\quinn-proxy\\handoff_templates\\` for all future handoff docs. Five templates: SHORT, STANDARD, MASTER, INSTRUCTIONS_FOR_AGENT, CORRECTIVE.

14. **Handoff direction is ONE-WAY: Quinn → ShipStack**. Quinn writes `HANDOFF_FROM_QUINN_<DATE>.md` into dropship-os/. ShipStack reads it and replies with `HANDOFF_TO_QUINN_<DATE>.md` in the same folder. ShipStack NEVER originates `HANDOFF_FROM_SHIPSTACK_*` documents. The handoff is a conversation, but Quinn always speaks first.

15. **End of session**: write `HANDOFF_TO_QUINN_2026-06-XX.md` using the STANDARD template, listing every cleanup you completed and every cleanup still outstanding.

16. **Log session summary to Quinn**:
   ```
   quinn_add_context(
     project='ship_stack_ai',
     section='session_summary',
     content='2026-06-XX: cleaned up overreach per SHIPSTACK_RULES.md, deleted [N] files, moved [N] files, renamed [N] files'
   )
   ```

---

# 7. GOING FORWARD

Quinn agent reviewed your work. The lane violations weren't malicious - you were trying to be helpful and didn't realize where the lane was. Now you know.

From now on:

- **Inside dropship-os/** = your house. Build anything you need.
- **Inside quinn-proxy/** = off-limits. If you need a Quinn change, write `HANDOFF_TO_QUINN_<DATE>_<TOPIC>.md` and Quinn agent will read it next session.
- **Inside parent Drop shipping/** = transitional yard. Nothing new goes here. Existing files get moved into dropship-os/ or deleted.
- **Format and naming** = match Quinn's standard (sections 2, 3, 4 above). Quinn was here first; consistency with Quinn is consistency with the rest of the machine.
- **Quinn features** = use them, don't rebuild them. List in section 1 Rule 5 (except Prometheus, which is yours per Rule 6).
- **Badge system** = build your own (Rule 4). It's the exception to the "no duplication" rule.
- **Prometheus** = you own it (Rule 6). Move it from Quinn's lane to yours, update the Blueprint.
- **Scheduled tasks** = NEVER. Global Directive #6 applies to you identically. Any task you create will be deleted by the maintenance system.
- **All 17 Global Directives** = apply to you verbatim. Read via `quinn_badge()`. Don't argue with them.

Fair? Build ShipStack. Ship it.

-- Quinn agent, 2026-06-02
--- UPDATED 2026-06-02 with five corrections from Alex Alexander
