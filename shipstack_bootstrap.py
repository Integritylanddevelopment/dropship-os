"""
shipstack_bootstrap.py

Run this at the start of every ShipStack session.
Prints your memory packet: mission, current state, next action, rules.

Usage:
    python shipstack_bootstrap.py

This is the ShipStack equivalent of quinn_memory_bootstrap.py.
It reads ShipStack memory files only. It never touches quinn-proxy.
"""
import sys, os
try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

BASE = os.path.dirname(os.path.abspath(__file__))

PACKET = [
    ("SHIPSTACK RULES",        "CLAUDE.md"),
    ("CURRENT GOAL",           "memory/working/current_goal.md"),
    ("SESSION RITUAL",         "memory/procedural/new_session_ritual.md"),
    ("VERIFIED STATE",         "memory/semantic/verified_state.md"),
]

SEP = "=" * 60

def read(rel):
    path = os.path.join(BASE, rel.replace("/", os.sep))
    if not os.path.exists(path):
        return f"MISSING: {path}"
    with open(path, encoding="utf-8", errors="replace") as f:
        return f.read().strip()

print(SEP)
print("SHIPSTACK SESSION BOOTSTRAP")
print("Working folder:", BASE)
print(SEP)

for label, rel in PACKET:
    print(f"\n{'─'*40}")
    print(f"  {label}")
    print(f"{'─'*40}")
    print(read(rel))

print(f"\n{SEP}")
print("ONBOARDING STEPS")
print(SEP)
print("""
1. Confirm this folder is your working directory (NOT quinn-proxy)
2. Confirm Quinn bridge is running: http://127.0.0.1:8765/health
3. Read the rules above — especially: ShipStack calls Quinn, never modifies it
4. Read CURRENT GOAL above for state + next action
5. Restate to Alex: current goal / state / next action / any blockers
6. Wait for Alex to confirm before starting work
""")
print(SEP)
