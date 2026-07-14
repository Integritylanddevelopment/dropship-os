#!/usr/bin/env python3
"""
ShipStack Badge Protocol — One-Shot Token Generator
====================================================

Implements Directive #2: Badge Per Tool

Every tool call by every agent must:
1. Call get_badge() — read current rules, get one-shot token
2. Execute the tool
3. Call log_action() — write result into shipstack_actions.jsonl

Badges are per-tool-use, not per-session. Tokens expire in 60 seconds.
"""

import os
import json
import time
import hashlib
from pathlib import Path
from datetime import datetime, timedelta
from typing import Optional, Dict, Any

# Paths
SHIPSTACK_ROOT = Path(__file__).parent.parent  # badge/ -> ShipStack root
CLAUDE_MD = SHIPSTACK_ROOT / "CLAUDE.md"
SHIPSTACK_DIRECTIVES = SHIPSTACK_ROOT / "docs" / "SHIPSTACK_DIRECTIVES.md"
ACTIONS_LOG = SHIPSTACK_ROOT / "logs" / "shipstack_actions.jsonl"

# Ensure logs directory exists
ACTIONS_LOG.parent.mkdir(parents=True, exist_ok=True)


def get_badge() -> Dict[str, Any]:
    """
    Read current directives and return a one-shot badge token.
    
    Returns:
    {
        "token": "badge-1_...",  # one-shot, expires 60 seconds from now
        "claude_md_hash": "sha256...",  # current rules fingerprint
        "directives_hash": "sha256...",
        "issued_at": "2026-06-03T12:00:00Z",
        "expires_at": "2026-06-03T12:01:00Z",
        "rules_summary": {
            "lane": "dropship-os/ only",
            "quinn_bridge": "http://localhost:8765",
            "ports": {"engine": 8889, "prometheus": 8766, "vercel": 3000},
            "no_anthropic_keys": True,
            "action_logging": True,
        }
    }
    """
    now = datetime.utcnow()
    expires = now + timedelta(seconds=60)
    
    # Read current directives
    claude_md_text = CLAUDE_MD.read_text() if CLAUDE_MD.exists() else ""
    directives_text = SHIPSTACK_DIRECTIVES.read_text() if SHIPSTACK_DIRECTIVES.exists() else ""
    
    # Hash them for drift detection
    claude_md_hash = hashlib.sha256(claude_md_text.encode()).hexdigest()[:16]
    directives_hash = hashlib.sha256(directives_text.encode()).hexdigest()[:16]
    
    # Generate one-shot token
    token_seed = f"{now.isoformat()}-{os.urandom(16).hex()}"
    token = f"badge-1_{hashlib.sha256(token_seed.encode()).hexdigest()[:20]}"
    
    return {
        "token": token,
        "issued_at": now.isoformat() + "Z",
        "expires_at": expires.isoformat() + "Z",
        "claude_md_hash": claude_md_hash,
        "directives_hash": directives_hash,
        "rules_summary": {
            "lane": "dropship-os/ only — no writes outside this folder",
            "quinn_bridge": "http://localhost:8765 (or ngrok tunnel)",
            "ports": {
                "shipstack_engine": 8889,
                "prometheus_engine": 8766,
                "vercel_frontend": 3000,
                "quinn_bridge": 8765,
            },
            "no_anthropic_keys": "ANTHROPIC_API_KEY must NOT appear in .env.local or code",
            "no_direct_anthropic": "All LLM calls route through Quinn bridge, never direct to api.anthropic.com",
            "action_logging": "Every tool call logged to shipstack_actions.jsonl",
            "kill_before_launch": "Always kill old process before starting new service on same port",
            "no_scheduled_tasks": "No Windows scheduled tasks allowed",
        }
    }


def validate_token(token: str, issued_at_iso: str) -> bool:
    """
    Check if a badge token is still valid (not expired).
    
    Token format: "badge-1_<20-char-hex>"
    Validity: 60 seconds from issued_at
    """
    if not token.startswith("badge-1_"):
        return False
    
    try:
        issued = datetime.fromisoformat(issued_at_iso.replace("Z", "+00:00"))
        now = datetime.utcnow()
        return (now - issued).total_seconds() < 60
    except:
        return False


def log_action(
    token: str,
    issued_at_iso: str,
    tool_name: str,
    target: str,
    action: str,
    result: str,
    success: bool = True,
) -> Dict[str, Any]:
    """
    Log a tool call to shipstack_actions.jsonl.
    
    Args:
        token: badge token from get_badge()
        issued_at_iso: issued_at from get_badge()
        tool_name: e.g., "quinn_read_file", "quinn_write_file", "quinn_run_powershell"
        target: file path, URL, port, or process name
        action: "read", "write", "edit", "run", "execute", etc.
        result: summary of outcome (success or error message)
        success: True if action succeeded
    
    Returns:
        {
            "logged": True,
            "line_number": 12345,
            "timestamp": "2026-06-03T12:00:15Z"
        }
    """
    # Validate token first
    if not validate_token(token, issued_at_iso):
        return {
            "logged": False,
            "error": "Badge token expired or invalid",
            "token": token,
        }
    
    # Build log entry
    now = datetime.utcnow()
    entry = {
        "timestamp": now.isoformat() + "Z",
        "badge_token": token,
        "badge_issued_at": issued_at_iso,
        "tool_name": tool_name,
        "target": target,
        "action": action,
        "result": result,
        "success": success,
    }
    
    # Append to JSONL
    try:
        with open(ACTIONS_LOG, "a") as f:
            f.write(json.dumps(entry) + "\n")
        
        # Count lines for response
        line_count = sum(1 for _ in open(ACTIONS_LOG))
        
        return {
            "logged": True,
            "line_number": line_count,
            "timestamp": entry["timestamp"],
        }
    except Exception as e:
        return {
            "logged": False,
            "error": f"Failed to write log: {str(e)}",
        }


def get_recent_actions(limit: int = 10) -> list:
    """
    Return the last N lines from shipstack_actions.jsonl.
    """
    if not ACTIONS_LOG.exists():
        return []
    
    lines = []
    try:
        with open(ACTIONS_LOG, "r") as f:
            for line in f:
                if line.strip():
                    lines.append(json.loads(line))
        return lines[-limit:]
    except:
        return []


if __name__ == "__main__":
    # Test the badge system
    print("=== ShipStack Badge Protocol ===\n")
    
    # 1. Get a badge
    badge = get_badge()
    print(f"Badge token: {badge['token']}")
    print(f"Valid for 60 seconds (expires at {badge['expires_at']})")
    print(f"\nRules digest:")
    for key, val in badge["rules_summary"].items():
        print(f"  {key}: {val}")
    
    # 2. Simulate a tool call with logging
    print("\n--- Simulating tool call ---")
    log_result = log_action(
        token=badge["token"],
        issued_at_iso=badge["issued_at"],
        tool_name="quinn_read_file",
        target="C:\\Users\\integ\\Documents\\Claude\\Projects\\Drop shipping\\dropship-os\\CLAUDE.md",
        action="read",
        result="Successfully read foundation doc (9.2 KB)",
        success=True,
    )
    print(f"Logged: {log_result['logged']}")
    print(f"Line: {log_result.get('line_number', 'N/A')}")
    
    # 3. Show recent actions
    print("\n--- Recent actions (last 5) ---")
    recent = get_recent_actions(5)
    for action in recent:
        print(f"  {action['timestamp']} | {action['tool_name']} | {action['action']} | {action['result'][:40]}")
