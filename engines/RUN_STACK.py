#!/usr/bin/env python3
"""
ShipStack AI — ONE-COMMAND LOCAL STACK STARTUP
Paste this into PowerShell or Command Prompt:
  python "C:\Users\integ\Documents\Claude\Projects\Drop shipping\RUN_STACK.py"
"""

import subprocess
import sys

script = r"C:\Users\integ\Documents\Claude\Projects\Drop shipping\start_shipstack_full.py"
print(f"Executing: {script}\n")

try:
    subprocess.run([sys.executable, script], check=False)
except Exception as e:
    print(f"Error: {e}")
    sys.exit(1)
