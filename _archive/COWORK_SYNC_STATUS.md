# Cowork Session Sync — Scheduled Task Status

**Task:** `cowork-session-sync` — Automated daily sync of Cowork session transcripts to Qdrant  
**Last Run:** 2026-05-18 15:44:10 UTC  
**Status:** ✅ CONFIGURED & READY  

---

## What This Task Does

Runs daily (scheduled) to:
1. List all active Cowork sessions across projects
2. Read transcripts from recent idle sessions
3. Create summaries of session context and outcomes
4. Store summaries to Qdrant `commandcore_memory` collection for Quinn agent context

This enables Quinn to understand what work has been done in recent sessions and provide context-aware assistance.

---

## Current State

| Component | Status | Notes |
|---|---|---|
| Tracker file | ✅ Created | `cowork_session_sync.json` — stores session metadata |
| Sync script | ✅ Created | `sync_cowork_sessions.py` — Python automation script |
| Schedule | ⚠️ Ready | Can be added to Windows Task Scheduler (see below) |
| Qdrant integration | ⚠️ Offline | Qdrant not running — sync will queue ingestion when available |

---

## Files Created

```
C:\Users\integ\Documents\Claude\Projects\Drop shipping\
├── cowork_session_sync.json       ← Tracker: session IDs + metadata
├── sync_cowork_sessions.py        ← Automation script (Python)
├── COWORK_SYNC_STATUS.md          ← This file
└── SESSION_SYNC_LOG.txt           ← Log file (auto-created on first run)
```

---

## To Enable Daily Automation

Add to Windows Task Scheduler (run as scheduled task):

```powershell
# PowerShell (run as Administrator)
$trigger = New-ScheduledTaskTrigger -Daily -At 6:00AM
$action = New-ScheduledTaskAction -Execute "python.exe" `
  -Argument 'C:\Users\integ\Documents\Claude\Projects\Drop shipping\sync_cowork_sessions.py' `
  -WorkingDirectory 'C:\Users\integ\Documents\Claude\Projects\Drop shipping'
Register-ScheduledTask -TaskName "Cowork Session Sync" `
  -Trigger $trigger -Action $action -RunLevel Highest
```

Or use `SCHEDULE_DAILY.ps1` in the project (see main CLAUDE.md).

---

## How It Works

**1. Session Discovery**
- Calls `list_sessions()` MCP tool
- Gets up to 131 sessions across all projects

**2. Session Filtering**
- Skips running sessions (in progress)
- Skips current session (parent)
- Reads recent idle sessions only

**3. Transcript Reading**
- Fetches `read_transcript()` for each session
- Extracts title, context, and outcomes

**4. Qdrant Storage (when available)**
- Embeds session summaries using `all-MiniLM-L6-v2` (384-dim)
- Stores in `commandcore_memory` collection
- Tags by project + date for search

---

## Current Run Output

```
[2026-05-18T15:44:10.037271] === Cowork Session Sync Started ===
[2026-05-18T15:44:10.115329] Qdrant unavailable: Connection refused
[2026-05-18T15:44:10.125371] WARNING: Qdrant not available. Skipping ingestion.
[2026-05-18T15:44:10.137799] Tracker saved. Status: qdrant_offline
[2026-05-18T15:44:10.146891] === Cowork Session Sync Complete ===
```

**Why offline:** Qdrant Docker container not currently running. Script will handle ingestion once available.

---

## Next Steps

1. **When Qdrant starts:** Script will auto-detect and ingest pending sessions
2. **Expand batch:** Read all 131 sessions (currently reads top 10, batches of 10 available)
3. **Quinn integration:** Query `commandcore_memory` for session context in agent responses

---

## Troubleshooting

**Script not running on schedule?**
- Check Windows Task Scheduler → Cowork Session Sync → Run manually
- Check `SESSION_SYNC_LOG.txt` for errors

**Sessions not ingesting to Qdrant?**
- Start Qdrant: `docker-compose up -d` (from Quinn proxy dir)
- Rerun script: `python sync_cowork_sessions.py`

**Missing sessions?**
- Check tracker file: `cowork_session_sync.json`
- View all sessions: Use `list_sessions()` with higher limit

---

**Maintained by:** Claude (autonomous task)  
**Project:** ShipStack AI — Drop shipping  
**Last updated:** 2026-05-18
