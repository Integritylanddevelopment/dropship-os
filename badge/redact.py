#!/usr/bin/env python3
"""
Re-export Quinn's canonical secret_redactor module.
One source of truth - all redaction logic lives in C:\Users\integ\quinn-proxy\secret_redactor.py
"""

import sys
from pathlib import Path

# Add Quinn to path
_QUINN_PATH = Path(r'C:\Users\integ\quinn-proxy')
if str(_QUINN_PATH) not in sys.path:
    sys.path.insert(0, str(_QUINN_PATH))

# Import from canonical source
from secret_redactor import redact, is_clean, scan_for_leaks, safe_print, pattern_names

__all__ = ['redact', 'is_clean', 'scan_for_leaks', 'safe_print', 'pattern_names']
