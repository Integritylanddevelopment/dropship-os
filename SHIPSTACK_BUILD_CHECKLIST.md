# ShipStack Build Checklist

**Owner:** ShipStack agent
**Date:** 2026-06-03
**Status:** Pending (prioritized list)

---

## TIER 1: Badge System (Foundation — required before ANY other work)

These must be built first. All other tools depend on the badge protocol.

### S1.1: shipstack_badge.py
- **Location:** `dropship-os/shipstack_badge.py`
- **Purpose:** Issue one-shot badge tokens (matching Quinn's pattern)
- **Implementation:**
  - Read from `dropship-os/CLAUDE.md` (not Quinn's)
  - Return current SHIPSTACK_RULES.md + recent actions + hash
  - Mint fresh token with `secrets.token_urlsafe(24)` (60-second GC age)
  - Track active tokens in memory dict: `{token_string: issued_at_epoch}`
  - Two fallback sources: Qdrant collection `shipstack_global_directives` (primary), file fallback
- **Output schema:**
  ```json
  {
    "mode": "full|cached",
    "rules": "[full SHIPSTACK_RULES.md text]",
    "blueprint": "[table from CLAUDE.md]",
    "badge_token": "badge-xxx...",
    "hash": "sha256-xxx...",
    "source": "qdrant|file",
    "fetched_at": "2026-06-03T12:34:56Z",
    "recent_actions": [last 10 from shipstack_actions.jsonl]
  }
  ```

### S1.2: shipstack_log_action.py
- **Location:** `dropship-os/shipstack_log_action.py`
- **Purpose:** Synchronous action logging (one-shot, before next action begins)
- **Implementation:**
  - Append to `dropship-os/logs/shipstack_actions.jsonl` (JSONL format)
  - Log entry structure:
    ```json
    {
      "timestamp": "2026-06-03T12:34:56Z",
      "tool_name": "quinn_read_file",
      "target": "C:\\path\\to\\file.md",
      "action": "read",
      "result": "success|error",
      "summary": "Read 2048 bytes",
      "badge_token_used": "badge-xxx..."
    }
    ```
  - Create `logs/` directory if missing
  - Return confirmation: `{"ok": True, "logged_at": timestamp}`

### S1.3: shipstack_mcp.py (MCP Server)
- **Location:** `dropship-os/shipstack_mcp.py`
- **Purpose:** MCP server exposing ShipStack tools (stdout transport, like Quinn)
- **Implementation:**
  - FastMCP server (from mcp package)
  - Load badge protocol from Quinn's pattern (_gated_mcp_tool decorator)
  - Register tools: shipstack_badge, shipstack_log_action, + others below
  - Monkey-patch @mcp.tool to auto-gate with badge (same as Quinn does)
  - Logging to stderr (stdout is transport)
- **Tools to register:** (see TIER 2, 3, 4 below)

### S1.4: .env (ShipStack configuration)
- **Location:** `dropship-os/.env`
- **Contents:**
  ```
  SHIPSTACK_DIR=C:\Users\integ\Documents\Claude\Projects\Drop shipping\dropship-os
  SHIPSTACK_LOGS_DIR=C:\Users\integ\Documents\Claude\Projects\Drop shipping\dropship-os\logs
  SHIPSTACK_PROJECTS_DIR=C:\Users\integ\Documents\Claude\Projects\Drop shipping\dropship-os\projects
  QUINN_BRIDGE_URL=http://127.0.0.1:8765
  SHIPSTACK_PORT=3000
  SHIPSTACK_ENGINE_PORT=8889
  PROMETHEUS_PORT=8766
  ```
  - NO ANTHROPIC_API_KEY (routes through Quinn only)
  - NO STRIPE_SECRET_KEY (only in Vercel env vars)

---

## TIER 2: File Tools (Reading/Writing/Editing — required for all downstream work)

### S2.1: shipstack_read_file.py
- **Location:** `dropship-os/shipstack_read_file.py`
- **Purpose:** Safe file reading (logs action, returns content)
- **Input:** file_path, offset (optional), limit (optional)
- **Output:** content (cat -n format with line numbers) + read status
- **Protected files:** Same as Quinn (P1 list in SHIPSTACK_RULES.md S1.4)

### S2.2: shipstack_write_file.py
- **Location:** `dropship-os/shipstack_write_file.py`
- **Purpose:** Safe file writing (logs action, creates backups)
- **Input:** file_path, content
- **Output:** write confirmation + backup info
- **Protected files:** Refuse edit without `user_authorized=True`
- **Secret scanner:** Scan for known key prefixes (sk-ant-, ghp_, etc.) — refuse unless `user_authorized=True`

### S2.3: shipstack_edit_file.py
- **Location:** `dropship-os/shipstack_edit_file.py`
- **Purpose:** Safe in-place editing (find/replace)
- **Input:** file_path, old_string, new_string
- **Output:** edit confirmation + line count changed
- **Protected files:** Refuse edit without `user_authorized=True`
- **Secret scanner:** Scan for known key prefixes — refuse unless `user_authorized=True`

### S2.4: shipstack_list_dir.py
- **Location:** `dropship-os/shipstack_list_dir.py`
- **Purpose:** Directory listing + tree traversal
- **Input:** path, recursive (optional), pattern (optional)
- **Output:** sorted file list (by modification time) + directory structure
- **Restricted:** Cannot list parent folders above dropship-os/

---

## TIER 3: Command Execution (PowerShell & Python — required for automation)

### S3.1: shipstack_run_powershell.py
- **Location:** `dropship-os/shipstack_run_powershell.py`
- **Purpose:** Run PowerShell commands (gated)
- **Input:** command (string), cwd (optional), timeout (max 600s)
- **Output:** stdout, stderr, exit code + execution log
- **Guardrails:**
  - Dangerous command blocklist (Remove-Item -Recurse, rm -rf, format c:, etc.)
  - Window minimize enforcement (per Global Directive #13)
  - Rate limit: 20 per hour (gated via badge)

### S3.2: shipstack_run_python.py
- **Location:** `dropship-os/shipstack_run_python.py`
- **Purpose:** Run Python scripts (gated)
- **Input:** command (string), cwd (optional), timeout (max 600s)
- **Output:** stdout, stderr, exit code + execution log
- **Guardrails:**
  - Dangerous command blocklist (same as PowerShell)
  - Rate limit: 20 per hour (gated via badge)

---

## TIER 4: Prometheus Integration (Video Generation Engine)

### S4.1: prometheus_engine.py (moved from parent folder)
- **Location:** `dropship-os/prometheus_engine.py`
- **Purpose:** Video generation AI (Gary Vee playbook execution)
- **Ports:** 8766 (health check)
- **Dependencies:** FFmpeg, OpenAI/Anthropic LLM (via Quinn bridge), music/voice APIs (Suno, ElevenLabs)
- **Integration:** Call Quinn's LLM via port 8765, not direct Anthropic

### S4.2: prometheus_monitor.py (moved from parent folder)
- **Location:** `dropship-os/prometheus_monitor.py`
- **Purpose:** Health checks, queue management, retry logic
- **Features:**
  - Monitor port 8766 (health endpoint)
  - Track video generation queue
  - Retry failed renders

### S4.3: PROMETHEUS_HANDOFF.md (moved from parent folder)
- **Location:** `dropship-os/PROMETHEUS_HANDOFF.md`
- **Purpose:** Handoff document for Prometheus work (renamed per Rule 8: direction + date)
- **Rename:** `PROMETHEUS_HANDOFF_2026-06-03.md` (add date when moved)

---

## TIER 5: ShipStack Engine (Core Business Logic)

### S5.1: shipstack_engine.py (refactored from parent folder)
- **Location:** `dropship-os/shipstack_engine.py`
- **Purpose:** ShipStack brain (product scoring, supplier matching, viral classification)
- **Input:** product data, competitor analysis, trend signals
- **Output:** ranked opportunity scores + sourcing recommendations
- **Ports:** 8889 (health check)
- **Dependencies:** Decision engine, Prometheus for content generation

### S5.2: decision_engine.py (refactored from parent folder)
- **Location:** `dropship-os/decision_engine.py`
- **Purpose:** Hormozi/Gary Vee playbook scoring (margin, volume, saturation, viral potential)
- **Integration:** Called by shipstack_engine.py

---

## TIER 6: Social AI Integration (Content + Posting)

### S6.1: social_ai_agent/ (moved from parent folder)
- **Location:** `dropship-os/social_ai_agent/`
- **Purpose:** Pinterest/Reddit/TikTok content generation + auto-posting
- **Features:**
  - Content calendar generation
  - Organic growth strategy (Hormozi playbook)
  - Caption generation (Gary Vee style)
  - Posting automation (with rate limiting)

### S6.2: pinterest_agent/ (moved from parent folder)
- **Location:** `dropship-os/pinterest_agent/`
- **Purpose:** Pinterest-specific organic growth
- **Features:**
  - Board creation + Pin scheduling
  - Rich pins with product links
  - Viral classification feedback loop

---

## TIER 7: Dashboard & Launcher

### S7.1: launcher_os.html (already built)
- **Location:** `dropship-os/launcher_os.html` OR desktop shortcut
- **Status:** ✅ Already created
- **Features:** Desktop launcher for ShipStack services (Quinn, Prometheus, ShipStack engine, Vercel deployment)

### S7.2: shipstack_dashboard.html (to be built)
- **Location:** `dropship-os/artifacts/shipstack_dashboard.html`
- **Purpose:** Real-time metrics dashboard (product discovery, viral scores, revenue)
- **Metrics:**
  - Products discovered (24h, 7d, 30d)
  - Top opportunities by margin/volume
  - Prometheus video queue status
  - Pinterest/TikTok posting performance
  - Revenue by channel

---

## TIER 8: Cleanup & Housekeeping

### S8.1: Delete Quinn duplicates (from parent folder)
- `quinn_fs_interceptor.py` ✓
- `seed_strategy_books.py` ✓
- `sync_cowork_sessions.py` ✓
- `verify_qdrant_partitions.py` ✓
- `ingest_now.py` ✓
- `QUINN_AGENT_ROUTING_INSTRUCTIONS.md` ✓
- `quinn-first-SKILL.md` ✓
- Disable Claude Code scripts ✓

### S8.2: Delete scheduled task scripts (from parent folder)
- `SCHEDULE_DAILY.ps1` ✓
- `SCHEDULE_CALENDAR.ps1` ✓
- Unregister Task Scheduler entries ✓ (Global Directive #6)

### S8.3: Move Prometheus files (from parent folder → dropship-os/)
- `prometheus.py` ✓
- `prometheus_engine.py` ✓
- `prometheus_monitor.py` ✓
- `run_prometheus.py` ✓
- `PROMETHEUS_HANDOFF.md` ✓

### S8.4: Organize ShipStack code (from parent folder → dropship-os/)
- Move all real ShipStack files per section 5a of SHIPSTACK_RULES.md ✓

---

## TIMELINE & PRIORITY

| Tier | Name | Est. Time | Blocker | Status |
|---|---|---|---|---|
| 1 | Badge System | 2h | nothing | PENDING |
| 2 | File Tools | 1.5h | Tier 1 | PENDING |
| 3 | Command Execution | 1h | Tier 1 | PENDING |
| 4 | Prometheus Integration | 3h | Tier 1, 2, 3 | PENDING |
| 5 | ShipStack Engine | 2h | Tier 1, 2, 3 | PENDING |
| 6 | Social AI | 2h | Tier 5 | PENDING |
| 7 | Dashboard | 1.5h | Tier 5 | PARTIALLY DONE (launcher exists) |
| 8 | Cleanup | 1h | Tier 1, 2, 3 | PENDING |

**Total estimated time:** ~14.5 hours

**Critical path:** Tier 1 → 2 → 3 → (4, 5, 6 in parallel) → 7 → 8

---

## VERIFICATION CHECKLIST (before marking complete)

- [ ] All Tier 1 tools pass `quinn_badge()` → return valid token
- [ ] All tools in Tiers 2-3 log actions to `shipstack_actions.jsonl`
- [ ] No tool imports or calls Anthropic API directly (all via Quinn bridge :8765)
- [ ] `dropship-os/CLAUDE.md` Blueprint table lists all built components
- [ ] No files remain in parent `Drop shipping/` folder (all moved or deleted)
- [ ] No scheduled tasks registered (Global Directive #6)
- [ ] SHIPSTACK_RULES.md S1.4 "ShipStack-specific rules" match actual implementation
- [ ] Desktop launcher `launcher_os.html` appears on desktop
- [ ] Handoff doc written: `HANDOFF_TO_QUINN_2026-06-03.md`

---

## NOTES

- Quinn's badge is in `quinn_mcp/server.py` lines 125-331 (reference implementation)
- ShipStack badge follows same pattern but reads `dropship-os/CLAUDE.md` (not Quinn's)
- All tools gate behind badge except `shipstack_badge()` itself
- No agent-to-agent tool calls (ShipStack ← Quinn only, one-way data flow)
- Prometheus move is ownership transfer, not duplication (remove from Quinn's Blueprint)
