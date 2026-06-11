#!/usr/bin/env python3
"""
ShipStack Handoff Writer - Enforces redaction on all handoff writes.

ONLY way to write a handoff. Forces redact + leak-check + UTF-8.
Raises if any unscrubbed pattern slipped through.

Usage:
    from badge.handoff_writer import write_handoff
    write_handoff("HANDOFF_TO_QUINN_2026-06-04_EXAMPLE.md", content)
"""

import sys
from pathlib import Path
from datetime import datetime

# Add Quinn to path
_QUINN_PATH = Path(r'C:\Users\integ\quinn-proxy')
if str(_QUINN_PATH) not in sys.path:
    sys.path.insert(0, str(_QUINN_PATH))

from secret_redactor import redact, scan_for_leaks

HANDOFF_DIR = Path(__file__).parent.parent / "handoffs"


def write_handoff(filename: str, content: str) -> Path:
    """
    ONLY way to write a handoff. Forces redact + leak-check + UTF-8.

    Raises RuntimeError if any unscrubbed patterns survive redaction.

    Args:
        filename: Name of handoff file (e.g., 'HANDOFF_TO_QUINN_2026-06-04_EXAMPLE.md')
        content: Handoff content (will be redacted before writing)

    Returns:
        Path to written file

    Raises:
        RuntimeError: If secrets survive the redaction pass
    """
    # Redact all patterns
    safe = redact(content)

    # Paranoid: scan AFTER redaction to catch any survivors
    leaks = scan_for_leaks(safe)
    if leaks:
        raise RuntimeError(f"Handoff writer refused: secrets survived redaction: {leaks}")

    # Write to handoffs/ directory
    path = HANDOFF_DIR / filename
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(safe, encoding="utf-8", newline="\n")

    return path


if __name__ == "__main__":
    # Test: write a dummy handoff
    # Test strings are split so the scanner doesn't fire on this source file itself.
    # The write_handoff function will redact them on the way through.
    test_content = """# Test Handoff

This is a test.

Remote: https://user:""" + "ghp_" + """1234567890abcdefghij@github.com/user/repo.git
Stripe: """ + "sk_live_" + """abcd1234efgh5678ijkl9012mnopqrst

Should be redacted.
"""

    try:
        result = write_handoff("TEST_HANDOFF.md", test_content)
        print(f"✓ Test handoff written to {result}")
        print(f"✓ Content:")
        print(result.read_text())
    except RuntimeError as e:
        print(f"✗ Test failed: {e}")
