#!/usr/bin/env python3
"""
ShipStack Action Logger — Convenience module

This is a thin wrapper around shipstack_badge.log_action() for easy import.
Use this in any ShipStack service to log tool calls without importing the full badge module.

Example:
    from shipstack_log_action import log_action
    
    result = log_action(
        token="badge-1_...",
        issued_at_iso="2026-06-03T12:00:00Z",
        tool_name="quinn_write_file",
        target="/path/to/file.py",
        action="write",
        result="Successfully created 500-line module",
    )
"""

from shipstack_badge import log_action

__all__ = ["log_action"]
