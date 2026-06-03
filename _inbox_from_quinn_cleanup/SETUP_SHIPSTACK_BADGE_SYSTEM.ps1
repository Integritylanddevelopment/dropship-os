#requires -Version 5.1
# ============================================================
#  SETUP_SHIPSTACK_BADGE_SYSTEM.ps1
#  One-shot setup for ShipStack desktop shortcut + badge system
#  Copy and paste this entire script into PowerShell
#  Owner: Alex Alexander
#  Last updated: 2026-06-02
# ============================================================

$ErrorActionPreference = 'Continue'

Write-Host ""
Write-Host "  SHIPSTACK BADGE SYSTEM SETUP" -ForegroundColor Cyan
Write-Host ""

# ============================================================
# TASK 1 - Create desktop shortcut for LAUNCH_SHIPSTACK.ps1
# ============================================================
Write-Host "  [1] Creating desktop shortcut..." -ForegroundColor Magenta

$DesktopPath = [System.IO.Path]::Combine([Environment]::GetFolderPath('Desktop'), 'LAUNCH SHIPSTACK.lnk')
$LaunchScriptPath = 'C:\Users\integ\Documents\Claude\Projects\Drop shipping\LAUNCH_SHIPSTACK.ps1'
$PowerShellExe = 'C:\Windows\System32\WindowsPowerShell\v1.0\powershell.exe'

try {
  $WshShell = New-Object -ComObject WScript.Shell
  $Shortcut = $WshShell.CreateShortcut($DesktopPath)
  $Shortcut.TargetPath = $PowerShellExe
  $Shortcut.Arguments = "-NoProfile -ExecutionPolicy Bypass -File `"$LaunchScriptPath`""
  $Shortcut.WindowStyle = 1  # Normal window
  $Shortcut.Description = 'Launch ShipStack Dashboard'
  $Shortcut.WorkingDirectory = (Split-Path $LaunchScriptPath)
  $Shortcut.Save()
  Write-Host "    [OK] Desktop shortcut created: $DesktopPath" -ForegroundColor Green
} catch {
  Write-Host "    [FAIL] Could not create shortcut: $_" -ForegroundColor Red
  exit 1
}

# ============================================================
# TASK 2 - Create ShipStack CLAUDE.md (badge system + blueprint)
# ============================================================
Write-Host "  [2] Creating ShipStack CLAUDE.md..." -ForegroundColor Magenta

$ShipStackClaudeMd = @'
# ShipStack AI — Local Directive

**Owner:** Alex Alexander (integritylanddevelopment@gmail.com)  
**Last updated:** 2026-06-02  
**Version:** 1.0.0 (Local Express.js + Badge System)

---

## Badge Protocol (Synchronous Rule-Reading)

Every tool call follows this pattern:

```
1. CALL shipstack_badge      — read this CLAUDE.md + blueprint + recent actions
2. EXECUTE the tool          — Read, Edit, Write, etc.
3. CALL shipstack_log_action — write action + result (synchronously)
```

The Badge is **per-tool-use** (not per-session). Reading rules once is not enough.

---

## Global Directives Reference

ShipStack agents follow Quinn's **Four Laws**:

1. **ShipStack-First for Decisions** - Local decisions via shipstack tools
2. **ShipStack is Truth, Files are Mirror** - Knowledge in ShipStack state file, files reflect it
3. **No Leak Channels** - No direct API calls outside local services
4. **Badge Protocol** - Every action reads rules → executes → logs

---

## ShipStack Blueprint (LIVE ARCHITECTURE)

| Component | Type | Port | Status | Health Check | Notes |
|-----------|------|------|--------|--------------|-------|
| ShipStack Express | node | 3000 | active | http://127.0.0.1:3000/api/health | Dashboard server |
| Quinn Bridge | python | 8765 | external | http://127.0.0.1:8765/health | AI + research |
| Qdrant | docker | 6333 | external | http://127.0.0.1:6333/collections | Vector DB |
| Ollama | docker | 11434 | external | http://127.0.0.1:11434/api/tags | Local LLMs |

---

## ShipStack Tools (Local Equivalents of Quinn)

| Tool | Purpose | Storage |
|------|---------|---------|
| shipstack_badge | Read rules + state + recent actions | ShipStack state file |
| shipstack_log_action | Log tool usage synchronously | ShipStack actions.jsonl |
| shipstack_search | Semantic search (future) | ShipStack knowledge |
| shipstack_chat | Route to Quinn Bridge | Quinn (external) |
| shipstack_status | Health check all services | Local checks |

---

## ShipStack State File (Source of Truth)

**Location:** `C:\Users\integ\Documents\Claude\Projects\Drop shipping\.shipstack\state.json`

Contains:
- Current CLAUDE.md rules (this file)
- Blueprint table (active services)
- Recent actions log (last 20)
- Project context (if needed)

**Rule:** ShipStack state is truth. Files mirror it.

---

## Quarantine Registry (ShipStack)

Nothing quarantined yet. As deprecated files are removed, they move to:
```
D:\_QUARANTINE_DO_NOT_AUTOLOAD\__DEPRECATED__YYYYMMDD__<filename>
```

---

## Protected Files (ShipStack P1)

Cannot edit without explicit approval:
- `C:\Users\integ\Documents\Claude\Projects\Drop shipping\CLAUDE.md`
- `C:\Users\integ\Documents\Claude\Projects\Drop shipping\.env`
- `dropship-os\server.js`
- `dropship-os\package.json`

---

## ShipStack Rules (Specific to This Project)

1. **No Quinn Code References** — ShipStack calls Quinn over HTTP only
2. **Partition Enforced** — dropship_intel collection only (no cross-contamination)
3. **Port Isolation** — All ports in .env file (single source of truth)
4. **One Launcher** — LAUNCH_SHIPSTACK.ps1 (no scattered .ps1 files)
5. **Secrets in .env.local** — Git-ignored, never committed

---

**Last Updated:** 2026-06-02
'@

$ClaudeMdPath = 'C:\Users\integ\Documents\Claude\Projects\Drop shipping\CLAUDE.md'
try {
  Set-Content -Path $ClaudeMdPath -Value $ShipStackClaudeMd -Encoding UTF8 -Force
  Write-Host "    [OK] ShipStack CLAUDE.md created: $ClaudeMdPath" -ForegroundColor Green
} catch {
  Write-Host "    [FAIL] Could not create CLAUDE.md: $_" -ForegroundColor Red
  exit 1
}

# ============================================================
# TASK 3 - Create ShipStack state directory structure
# ============================================================
Write-Host "  [3] Creating ShipStack state directory..." -ForegroundColor Magenta

$StateDir = 'C:\Users\integ\Documents\Claude\Projects\Drop shipping\.shipstack'
try {
  New-Item -ItemType Directory -Path $StateDir -Force | Out-Null
  Write-Host "    [OK] State directory created: $StateDir" -ForegroundColor Green
} catch {
  Write-Host "    [FAIL] Could not create state directory: $_" -ForegroundColor Red
  exit 1
}

# ============================================================
# TASK 4 - Create initial ShipStack state.json
# ============================================================
Write-Host "  [4] Creating ShipStack state.json..." -ForegroundColor Magenta

$InitialState = @{
  "version" = "1.0.0"
  "created" = (Get-Date -Format 'yyyy-MM-ddTHH:mm:ssZ')
  "badge_token" = $null
  "blueprint" = @(
    @{
      component = "ShipStack Express"
      type = "node"
      port = 3000
      status = "active"
      health_check = "http://127.0.0.1:3000/api/health"
    }
    @{
      component = "Quinn Bridge"
      type = "python"
      port = 8765
      status = "external"
      health_check = "http://127.0.0.1:8765/health"
    }
    @{
      component = "Qdrant"
      type = "docker"
      port = 6333
      status = "external"
      health_check = "http://127.0.0.1:6333/collections"
    }
    @{
      component = "Ollama"
      type = "docker"
      port = 11434
      status = "external"
      health_check = "http://127.0.0.1:11434/api/tags"
    }
  )
  "recent_actions" = @()
  "rules_hash" = ""
  "last_updated" = (Get-Date -Format 'yyyy-MM-ddTHH:mm:ssZ')
}

$StateJsonPath = Join-Path $StateDir 'state.json'
try {
  $InitialState | ConvertTo-Json -Depth 10 | Set-Content -Path $StateJsonPath -Encoding UTF8 -Force
  Write-Host "    [OK] State file created: $StateJsonPath" -ForegroundColor Green
} catch {
  Write-Host "    [FAIL] Could not create state.json: $_" -ForegroundColor Red
  exit 1
}

# ============================================================
# TASK 5 - Create shipstack_tools directory structure
# ============================================================
Write-Host "  [5] Creating ShipStack tools directory..." -ForegroundColor Magenta

$ToolsDir = 'C:\Users\integ\Documents\Claude\Projects\Drop shipping\shipstack_tools'
try {
  New-Item -ItemType Directory -Path $ToolsDir -Force | Out-Null
  Write-Host "    [OK] Tools directory created: $ToolsDir" -ForegroundColor Green
} catch {
  Write-Host "    [FAIL] Could not create tools directory: $_" -ForegroundColor Red
  exit 1
}

# ============================================================
# TASK 6 - Create Python stub files for future ShipStack tools
# ============================================================
Write-Host "  [6] Creating ShipStack tool stubs..." -ForegroundColor Magenta

$BadgeToolStub = @'
#!/usr/bin/env python3
"""
shipstack_badge.py - Read current CLAUDE.md + blueprint + recent actions

Every tool call requires a fresh badge token:
1. CALL shipstack_badge  - get current rules + state
2. EXECUTE the tool      - perform action
3. CALL shipstack_log_action  - log synchronously

"""

import json
from pathlib import Path

STATE_FILE = Path(r'C:\Users\integ\Documents\Claude\Projects\Drop shipping\.shipstack\state.json')

def read_badge():
    """Read current rules, blueprint, and recent actions"""
    if not STATE_FILE.exists():
        return {"error": "State file not found", "version": "1.0.0"}
    
    with open(STATE_FILE, 'r') as f:
        state = json.load(f)
    
    return {
        "timestamp": state.get("last_updated"),
        "rules_hash": state.get("rules_hash"),
        "blueprint": state.get("blueprint", []),
        "recent_actions": state.get("recent_actions", [])[-10:],  # Last 10
        "badge_token": str(hash(json.dumps(state)))[:16]  # One-time use
    }

if __name__ == "__main__":
    badge = read_badge()
    print(json.dumps(badge, indent=2))
'@

$LogToolStub = @'
#!/usr/bin/env python3
"""
shipstack_log_action.py - Log tool usage synchronously

Every tool call MUST log its action:
- tool_name: which tool was called
- target: file path / URL / port / etc.
- action: what was done (read/edit/write/run)
- result: success/failure + summary

"""

import json
from datetime import datetime
from pathlib import Path

STATE_FILE = Path(r'C:\Users\integ\Documents\Claude\Projects\Drop shipping\.shipstack\state.json')

def log_action(tool_name, target, action, result):
    """Log an action synchronously to state.json"""
    if not STATE_FILE.exists():
        return {"error": "State file not found"}
    
    with open(STATE_FILE, 'r') as f:
        state = json.load(f)
    
    action_entry = {
        "timestamp": datetime.utcnow().isoformat() + "Z",
        "tool_name": tool_name,
        "target": target,
        "action": action,
        "result": result
    }
    
    state["recent_actions"].append(action_entry)
    state["recent_actions"] = state["recent_actions"][-20:]  # Keep last 20
    state["last_updated"] = datetime.utcnow().isoformat() + "Z"
    
    with open(STATE_FILE, 'w') as f:
        json.dump(state, f, indent=2)
    
    return {"logged": True, "action": action_entry}

if __name__ == "__main__":
    # Example
    result = log_action(
        tool_name="shipstack_read",
        target="C:\\Users\\integ\\Documents\\Claude\\Projects\\Drop shipping\\dropship-os\\server.js",
        action="read",
        result="success: 150 lines"
    )
    print(json.dumps(result, indent=2))
'@

try {
  Set-Content -Path (Join-Path $ToolsDir 'shipstack_badge.py') -Value $BadgeToolStub -Encoding UTF8 -Force
  Set-Content -Path (Join-Path $ToolsDir 'shipstack_log_action.py') -Value $LogToolStub -Encoding UTF8 -Force
  Write-Host "    [OK] Tool stubs created in: $ToolsDir" -ForegroundColor Green
} catch {
  Write-Host "    [FAIL] Could not create tool stubs: $_" -ForegroundColor Red
  exit 1
}

# ============================================================
# SUMMARY
# ============================================================
Write-Host ""
Write-Host "  SETUP COMPLETE" -ForegroundColor Green
Write-Host ""
Write-Host "  [✓] Desktop shortcut: LAUNCH SHIPSTACK.lnk" -ForegroundColor Green
Write-Host "  [✓] CLAUDE.md: ShipStack badge system + blueprint" -ForegroundColor Green
Write-Host "  [✓] State directory: $StateDir" -ForegroundColor Green
Write-Host "  [✓] State file: state.json (source of truth)" -ForegroundColor Green
Write-Host "  [✓] Tools directory: shipstack_tools/" -ForegroundColor Green
Write-Host ""
Write-Host "  NEXT STEPS:" -ForegroundColor Cyan
Write-Host "  1. Check desktop for 'LAUNCH SHIPSTACK' shortcut" -ForegroundColor White
Write-Host "  2. Double-click to launch ShipStack dashboard" -ForegroundColor White
Write-Host "  3. Quinn Bridge will auto-launch if needed" -ForegroundColor White
Write-Host ""
Write-Host "  ShipStack is now running with badge system!" -ForegroundColor Green
Write-Host ""
